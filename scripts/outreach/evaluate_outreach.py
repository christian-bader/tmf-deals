#!/usr/bin/env python3
"""
Evaluate whether to send outreach to a broker, using LLM with full context.

The LLM decides:
1. Should we email this broker?
2. If yes, what should we say?
3. If no, why not?

Usage:
    python evaluate_outreach.py                    # Evaluate all eligible brokers
    python evaluate_outreach.py --broker-id UUID   # Evaluate specific broker
    python evaluate_outreach.py --dry-run          # Preview without saving
    python evaluate_outreach.py --limit 5          # Limit number evaluated
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv
from supabase import create_client, Client

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

# Load templates as examples for the LLM
TEMPLATES_DIR = PROJECT_ROOT / 'templates'

# Rate limiting
API_DELAY_SECONDS = 1.0


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_anthropic_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError("Missing ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def load_template_examples() -> str:
    """Load all email templates as examples for the LLM."""
    examples = []
    
    templates = [
        ('Cold outreach - Active listing (seller agent)', 'sale-listing-seller-agent.md'),
        ('Cold outreach - Pending sale (seller agent)', 'sale-under-contract-seller-agent.md'),
        ('Cold outreach - Sold (buyer agent)', 'sale-sold-buyer-agent.md'),
        ('Follow-up (no response to initial outreach)', 'follow-up.md'),
    ]
    
    for description, filename in templates:
        path = TEMPLATES_DIR / filename
        if path.exists():
            content = path.read_text().strip()
            examples.append(f"### {description}\n```\n{content}\n```")
    
    return "\n\n".join(examples)


def get_used_listing_ids(supabase: Client) -> set:
    """Get all listing IDs that have already been used in suggested emails."""
    result = supabase.table('suggested_emails') \
        .select('new_listing_ids') \
        .execute()
    
    used_ids = set()
    for row in (result.data or []):
        ids = row.get('new_listing_ids') or []
        used_ids.update(ids)
    
    return used_ids


def get_broker_context(supabase: Client, broker_id: str, used_listing_ids: set = None) -> dict:
    """Gather all context about a broker for the LLM."""
    
    if used_listing_ids is None:
        used_listing_ids = set()
    
    # Broker info
    broker = supabase.table('brokers').select('*').eq('id', broker_id).single().execute()
    broker_data = broker.data
    
    # Their listings (with used/new flag)
    listings_result = supabase.table('broker_listings') \
        .select('role, listing_id, listings(*)') \
        .eq('broker_id', broker_id) \
        .execute()
    
    all_listings = listings_result.data or []
    
    # Separate into new (never emailed about) and already-used
    new_listings = []
    used_listings = []
    for item in all_listings:
        listing_id = item.get('listing_id')
        if listing_id in used_listing_ids:
            used_listings.append(item)
        else:
            new_listings.append(item)
    
    # Conversation history
    messages_result = supabase.table('email_messages') \
        .select('direction, subject, body_text, sent_at, gmail_thread_id') \
        .eq('broker_id', broker_id) \
        .order('sent_at', desc=True) \
        .limit(10) \
        .execute()
    messages = messages_result.data or []
    
    # Get most recent thread ID for reply continuity
    most_recent_thread_id = messages[0].get('gmail_thread_id') if messages else None
    
    # Conversation summary
    convo_result = supabase.table('broker_conversations') \
        .select('*') \
        .eq('broker_id', broker_id) \
        .execute()
    convo = convo_result.data[0] if convo_result.data else None
    
    return {
        'broker': broker_data,
        'new_listings': new_listings,
        'used_listings': used_listings,
        'all_listings': all_listings,
        'messages': messages,
        'conversation_summary': convo,
        'most_recent_thread_id': most_recent_thread_id,
    }


def format_listing_line(item: dict) -> str:
    """Format a single listing for the prompt."""
    role = item.get('role', 'unknown')
    listing = item.get('listings', {})
    if not listing:
        return None
    
    address = listing.get('address', 'Unknown address')
    price = listing.get('price')
    status = listing.get('status', 'unknown')
    sale_date = listing.get('sale_date')
    listing_date = listing.get('listing_date')
    
    price_str = f"${price:,.0f}" if price else "Price unknown"
    date_str = sale_date or listing_date or ""
    
    return f"- {address} | {price_str} | {status} | {role} agent | {date_str}"


def format_listings_for_prompt(new_listings: list, used_listings: list) -> str:
    """Format broker's listings for the prompt, distinguishing new from already-emailed."""
    sections = []
    
    # New listings (not yet emailed about)
    if new_listings:
        lines = ["**NEW LISTINGS (not yet emailed about):**"]
        for item in new_listings:
            line = format_listing_line(item)
            if line:
                lines.append(line)
        if len(lines) > 1:
            sections.append("\n".join(lines))
    
    # Already-emailed listings (for context only)
    if used_listings:
        lines = ["**PREVIOUS LISTINGS (already emailed about - for context only):**"]
        for item in used_listings:
            line = format_listing_line(item)
            if line:
                lines.append(line)
        if len(lines) > 1:
            sections.append("\n".join(lines))
    
    if not sections:
        return "No listings found for this broker."
    
    return "\n\n".join(sections)


def format_conversation_for_prompt(messages: list) -> str:
    """Format conversation history for the prompt."""
    if not messages:
        return "No prior email conversation with this broker."
    
    lines = ["Conversation history (most recent first):\n"]
    for msg in messages:
        direction = msg.get('direction', 'unknown')
        who = "DAN SENT" if direction == 'outbound' else "BROKER REPLIED"
        subject = msg.get('subject', '(no subject)')
        sent_at = msg.get('sent_at', '')[:10]
        body = msg.get('body_text', '')
        
        # Truncate body for context
        body_preview = body[:500] + "..." if body and len(body) > 500 else body
        
        lines.append(f"[{sent_at}] {who}")
        lines.append(f"Subject: {subject}")
        lines.append(f"{body_preview}\n")
    
    return "\n".join(lines)


def format_conversation_summary(convo: dict) -> str:
    """Format conversation summary stats."""
    if not convo:
        return "No prior contact."
    
    thread_count = convo.get('thread_count', 0)
    sent = convo.get('sent_count', 0)
    received = convo.get('received_count', 0)
    last_interaction = convo.get('last_interaction', '')
    has_replied = convo.get('has_replied', False)
    
    if thread_count == 0:
        return "No prior contact."
    
    reply_status = "They have replied to us." if has_replied else "They have NOT replied to any of our emails."
    
    return f"""Prior contact summary:
- {thread_count} email thread(s)
- {sent} emails sent by Dan
- {received} emails received from broker
- Last interaction: {last_interaction[:10] if last_interaction else 'unknown'}
- {reply_status}"""


def build_prompt(context: dict, template_examples: str) -> str:
    """Build the full prompt for the LLM."""
    
    broker = context['broker']
    
    prompt = f"""You are Dan's outreach assistant at Trinity Mortgage Fund.

## YOUR NORTH STAR GOAL
Close hard money loan deals. Brokers are the gatekeepers — they have investor clients who need fast financing for flips, bridge loans, new construction, etc. Your job is to build relationships with brokers so they think of Trinity when their clients need capital.

## ABOUT TRINITY MORTGAGE FUND
- Private lending fund based in Del Mar, CA
- Business-purpose loans for real estate investors (NOT owner-occupied)
- Loan types: bridge loans, fix & flip, new construction, cash-out refi
- Typical loan range: $500K - $5M+
- Key differentiator: Can close in under 10 days
- Dan's phone: (858) 775-0962

## DAN'S VOICE & STYLE
Dan's emails are:
- Short and casual (never salesy or corporate)
- Direct but friendly
- No pressure ("No need to respond — just wanted to introduce myself")
- Reference specific properties to show he's paying attention
- Sign off: "Dan" followed by "Trinity Mortgage Fund" and phone number

## EXAMPLE EMAILS (USE THESE AS STYLE GUIDES)

{template_examples}

---

## BROKER TO EVALUATE

**Name:** {broker.get('name', 'Unknown')}
**Email:** {broker.get('email', 'Unknown')}
**Brokerage:** {broker.get('brokerage_name', 'Unknown')}
**DRE License:** {broker.get('license_number', 'Unknown')}

## THEIR LISTING ACTIVITY

{format_listings_for_prompt(context['new_listings'], context['used_listings'])}

Note: Only reference NEW listings (ones we haven't emailed about yet). If there are no new listings, there may not be a reason to reach out.

## EMAIL HISTORY WITH THIS BROKER

{format_conversation_summary(context['conversation_summary'])}

{format_conversation_for_prompt(context['messages'])}

---

## YOUR TASK

You ARE Dan. Think like him. Dan wants to:
- Stay top of mind with every broker who might send deals
- Congratulate people on wins (closings, new listings)
- Keep relationships warm with casual touchpoints
- Never be salesy or pushy — just be a helpful presence

Put yourself in Dan's shoes and decide: **Would Dan want to reach out right now?**

Consider:
1. Is there something worth mentioning (new listing, recent sale, congrats-worthy event)?
2. If we've emailed recently with no reply, would another email feel spammy? (Generally wait 2-4 weeks)
3. If there's an active deal/conversation in progress, would this interrupt it awkwardly?

**Calibrate tone to the relationship:**
- **Cold contact:** Introduce yourself and Trinity, mention the listing
- **Previous outreach, no reply:** Don't re-introduce. Reference the new activity as a reason to reconnect
- **Engaged (they've replied before):** Casual and warm, reference your history
- **Active client (heavy back-and-forth):** Super minimal — just a quick "saw this, nice" kind of note. 1-2 sentences max. They know who you are.

**Respond with valid JSON only:**

```json
{{
  "decision": "send" or "skip",
  "reason": "One sentence explaining your reasoning",
  "email": {{
    "subject": "Short subject line",
    "body": "Full email body with signature"
  }}
}}
```

If decision is "skip", set email to null. Only skip if there's truly no reason to reach out (no new activity) or if you'd be interrupting an active conversation about something specific.

IMPORTANT: 
- Write emails in Dan's voice (see examples above)
- Keep emails SHORT — under 100 words for cold, even shorter for warm relationships
- Always include the signature block: Dan\\nTrinity Mortgage Fund\\n(858) 775-0962
- Reference specific properties when relevant
- Don't re-introduce Trinity if we've already emailed this person
- For active clients, think "quick text to a friend" energy — 1-2 sentences is fine
"""
    
    return prompt


def has_pending_draft(supabase: Client, broker_id: str) -> bool:
    """Check if broker already has a pending draft email."""
    result = supabase.table('suggested_emails') \
        .select('id') \
        .eq('broker_id', broker_id) \
        .eq('status', 'draft') \
        .limit(1) \
        .execute()
    return len(result.data or []) > 0


def evaluate_broker(
    supabase: Client, 
    anthropic_client: anthropic.Anthropic,
    broker_id: str,
    broker_name: str,
    template_examples: str,
    used_listing_ids: set,
    dry_run: bool = False
) -> dict:
    """Evaluate a single broker and return the decision."""
    
    # Check for existing draft (duplicate protection)
    if not dry_run and has_pending_draft(supabase, broker_id):
        return {
            'broker_id': broker_id,
            'broker_name': broker_name,
            'decision': 'skip',
            'reason': 'Already has a pending draft email',
            'email': None
        }
    
    # Gather context
    context = get_broker_context(supabase, broker_id, used_listing_ids)
    
    # Use name from context if not provided
    if broker_name == 'Unknown' or not broker_name:
        broker_name = context['broker'].get('name', 'Unknown')
    
    broker_email = context['broker'].get('email', '')
    
    if not broker_email:
        return {
            'broker_id': broker_id,
            'broker_name': broker_name,
            'decision': 'skip',
            'reason': 'No email address on file',
            'email': None
        }
    
    # Check if there are new listings to trigger outreach
    if not context['new_listings']:
        return {
            'broker_id': broker_id,
            'broker_name': broker_name,
            'decision': 'skip',
            'reason': 'No new listings to trigger outreach',
            'email': None
        }
    
    # Build prompt
    prompt = build_prompt(context, template_examples)
    
    # Call LLM
    message = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    # Parse response
    response_text = message.content[0].text
    
    # Extract JSON from response (handle markdown code blocks)
    if "```json" in response_text:
        json_str = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        json_str = response_text.split("```")[1].split("```")[0].strip()
    else:
        json_str = response_text.strip()
    
    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"  Failed to parse LLM response: {e}")
        print(f"  Raw response: {response_text[:500]}")
        return {
            'broker_id': broker_id,
            'broker_name': broker_name,
            'decision': 'error',
            'reason': f'Failed to parse LLM response: {e}',
            'email': None
        }
    
    result['broker_id'] = broker_id
    result['broker_name'] = broker_name
    
    # Track which listing IDs would be used (for in-memory dedup within a run)
    new_listing_ids = [item.get('listing_id') for item in context['new_listings'] if item.get('listing_id')]
    result['new_listing_ids'] = new_listing_ids
    
    # Save to database
    if not dry_run:
        if result['decision'] == 'send' and result.get('email'):
            supabase.table('suggested_emails').insert({
                'broker_id': broker_id,
                'new_listing_ids': new_listing_ids[:5],  # Limit to 5
                'subject': result['email'].get('subject', ''),
                'body_content': result['email'].get('body', ''),
                'is_first_contact': context['conversation_summary'] is None or context['conversation_summary'].get('thread_count', 0) == 0,
                'status': 'draft',
                'reply_to_thread_id': context.get('most_recent_thread_id'),
            }).execute()
        
        elif result['decision'] == 'skip':
            supabase.table('outreach_suppression_logs').insert({
                'broker_id': broker_id,
                'reason': result.get('reason', 'LLM decided to skip'),
            }).execute()
    
    return result


def main():
    parser = argparse.ArgumentParser(description='Evaluate outreach opportunities using LLM')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving to DB')
    parser.add_argument('--broker-id', type=str, help='Evaluate specific broker by ID')
    parser.add_argument('--limit', type=int, default=10, help='Max brokers to evaluate')
    args = parser.parse_args()
    
    print("Outreach Evaluation")
    print("=" * 50)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()
    
    supabase = get_supabase_client()
    anthropic_client = get_anthropic_client()
    template_examples = load_template_examples()
    
    # Pre-fetch all listing IDs that have been used in suggested emails
    print("Loading used listing IDs...")
    used_listing_ids = get_used_listing_ids(supabase)
    print(f"Found {len(used_listing_ids)} listings already used in outreach")
    print()
    
    # Get brokers to evaluate
    if args.broker_id:
        # Get broker name for single broker
        broker_result = supabase.table('brokers').select('id, name').eq('id', args.broker_id).single().execute()
        brokers = [{'broker_id': args.broker_id, 'name': broker_result.data.get('name', 'Unknown')}]
    else:
        # Use outreach_opportunities view (brokers not contacted in 30 days)
        result = supabase.table('outreach_opportunities') \
            .select('broker_id, name, email') \
            .limit(args.limit) \
            .execute()
        brokers = result.data or []
    
    print(f"Evaluating {len(brokers)} broker(s)")
    print()
    
    stats = {'send': 0, 'skip': 0, 'error': 0}
    
    for i, broker in enumerate(brokers):
        broker_id = broker.get('broker_id')
        broker_name = broker.get('name', 'Unknown')
        
        print(f"Evaluating: {broker_name}")
        
        try:
            result = evaluate_broker(
                supabase, 
                anthropic_client, 
                broker_id,
                broker_name,
                template_examples,
                used_listing_ids,
                args.dry_run
            )
            
            decision = result.get('decision', 'error')
            reason = result.get('reason', '')
            stats[decision] = stats.get(decision, 0) + 1
            
            print(f"  Decision: {decision.upper()}")
            print(f"  Reason: {reason}")
            
            if decision == 'send' and result.get('email'):
                print(f"  Subject: {result['email'].get('subject', '')}")
                if args.dry_run:
                    print(f"  Body preview: {result['email'].get('body', '')[:200]}...")
                
                # Add new listing IDs to used set (for this run)
                used_listing_ids.update(result.get('new_listing_ids', []))
            
            print()
            
            # Rate limiting between API calls
            if i < len(brokers) - 1 and decision not in ('skip',):
                time.sleep(API_DELAY_SECONDS)
            
        except Exception as e:
            print(f"  Error: {e}")
            stats['error'] += 1
            print()
    
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Send: {stats.get('send', 0)}")
    print(f"Skip: {stats.get('skip', 0)}")
    print(f"Error: {stats.get('error', 0)}")


if __name__ == '__main__':
    main()
