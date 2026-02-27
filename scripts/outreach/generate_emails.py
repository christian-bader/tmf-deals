#!/usr/bin/env python3
"""
Generate suggested emails for broker outreach.

Uses Claude to write personalized intro paragraphs, then combines with
template boilerplate.

Usage:
    python generate_emails.py --limit 5
    python generate_emails.py --limit 5 --dry-run
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
TEMPLATES_DIR = PROJECT_ROOT / 'templates'

# Trinity HQ city for special messaging
HQ_CITY = "Del Mar"

# Template mapping by listing status + role
TEMPLATES = {
    ('active', 'seller'): 'sale-listing-seller-agent.md',
    ('pending', 'seller'): 'sale-under-contract-seller-agent.md',
    ('sold', 'buyer'): 'sale-sold-buyer-agent.md',
}

# Emails to exclude from outreach
EXCLUDED_EMAILS = {
    'rande@randeturner.com',
    'melissa@randeturner.com', 
    'craig@clgproperties.com',
}

# Cache for TMF deals (loaded once at startup)
TMF_DEALS_CACHE = None


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_anthropic_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError("Missing ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def fetch_tmf_deals(supabase: Client) -> list:
    """Fetch all TMF deals from Supabase (cached)."""
    global TMF_DEALS_CACHE
    if TMF_DEALS_CACHE is not None:
        return TMF_DEALS_CACHE
    
    result = supabase.table('deals').select('*').execute()
    TMF_DEALS_CACHE = result.data or []
    return TMF_DEALS_CACHE


def extract_city(city_state: str) -> str:
    """Extract city from 'City, ST' format."""
    if not city_state:
        return ""
    return city_state.split(',')[0].strip()


def months_since(date_str: str) -> int:
    """Calculate months since a date string (YYYY-MM-DD)."""
    if not date_str:
        return 999
    try:
        deal_date = datetime.strptime(date_str[:10], '%Y-%m-%d')
        now = datetime.now()
        return (now.year - deal_date.year) * 12 + (now.month - deal_date.month)
    except:
        return 999


def find_relevant_deals(listing_city: str, deals: list) -> dict:
    """
    Find TMF deals relevant to a listing's location.
    
    Returns context dict for LLM with:
    - listing_city: the city of the listing
    - is_hq_city: True if Del Mar
    - recent_deals: list of deals in same city (within 12 months)
    - older_deals: list of deals in same city (older than 12 months)
    - total_deals_in_city: count
    """
    listing_city_lower = (listing_city or "").lower().strip()
    if not listing_city_lower:
        return None
    
    is_hq_city = listing_city_lower == HQ_CITY.lower()
    
    city_deals = []
    for deal in deals:
        deal_city = extract_city(deal.get('location', '')).lower()
        if deal_city == listing_city_lower:
            months = months_since(deal.get('date'))
            city_deals.append({
                'street': deal.get('display_address', ''),
                'city': extract_city(deal.get('location', '')),
                'months_ago': months,
                'date': deal.get('date'),
            })
    
    if not city_deals:
        return None
    
    # Sort by recency
    city_deals.sort(key=lambda x: x['months_ago'])
    
    recent = [d for d in city_deals if d['months_ago'] <= 12]
    older = [d for d in city_deals if d['months_ago'] > 12]
    
    return {
        'listing_city': listing_city,
        'is_hq_city': is_hq_city,
        'recent_deals': recent[:3],  # Limit to top 3 most recent
        'older_deals': older[:2],
        'total_deals_in_city': len(city_deals),
    }


def generate_local_deal_line(context: dict, client: anthropic.Anthropic) -> tuple[str, bool]:
    """
    Use Claude to generate a natural sentence about local TMF deals.
    
    Returns (sentence, is_hq_format) tuple.
    - is_hq_format is True if the sentence includes "I run a private lending fund" (for HQ city)
    """
    if not context:
        return "", False
    
    is_hq = context.get('is_hq_city', False)
    
    if is_hq:
        system_prompt = """You write a single sentence for a cold email from a private lender (Trinity Mortgage Fund) to a real estate agent.

The agent's listing is in Del Mar, where Trinity is headquartered. Write ONE sentence that combines introducing the fund with mentioning a local deal.

IMPORTANT: Start with exactly "I run a private lending fund headquartered in Del Mar" then add the deal reference.

Example: "I run a private lending fund headquartered in Del Mar and we just closed a deal over on Balboa Ave a few months ago."

Rules:
- Keep it casual and under 25 words
- Don't mention loan amounts or borrower details
- Use a specific street name from the deals provided
- Use natural time references ("a few months ago", "last month", "recently")
- Return ONLY the sentence, no quotes or explanation"""
    else:
        system_prompt = """You write a single sentence for a cold email from a private lender (Trinity Mortgage Fund) to a real estate agent.

Given facts about TMF's deal history near the agent's listing, write ONE natural sentence establishing local credibility.

Rules:
- Keep it casual and brief (under 20 words ideal)
- Don't mention loan amounts or borrower details
- Prefer mentioning specific street names when available (e.g., "over on Neptune")
- Use natural time references ("last month", "a couple months ago", "recently")
- If multiple deals, you can say "We've done several deals in {city}"
- Return ONLY the sentence, no quotes or explanation
- If the data doesn't support a good sentence, return empty string"""

    user_prompt = f"""Listing city: {context['listing_city']}
Is TMF HQ city (Del Mar): {context['is_hq_city']}
Recent deals in this city (within 12 months): {json.dumps(context['recent_deals'])}
Older deals in this city: {json.dumps(context['older_deals'])}
Total deals in this city: {context['total_deals_in_city']}

Write one sentence about TMF's local presence/deals for the email intro."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            system=system_prompt,
        )
        result = response.content[0].text.strip()
        # Clean up any quotes the model might add
        result = result.strip('"\'')
        return result, is_hq
    except Exception as e:
        print(f"    Warning: Failed to generate local deal line: {e}")
        return "", False


def load_template(template_name: str) -> str:
    """Load a template file and return its content."""
    path = TEMPLATES_DIR / template_name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text()


def get_broker_first_name(name: str) -> str:
    """Extract first name from full name."""
    if not name:
        return "there"
    return name.split()[0]


def format_price(price: float) -> str:
    """Format price as $X.XM or $XXXk."""
    if not price:
        return ""
    if price >= 1_000_000:
        return f"${price/1_000_000:.1f}M".replace(".0M", "M")
    return f"${price/1_000:,.0f}k"


def get_short_address(address: str) -> str:
    """Get just the street address (no city/state/zip)."""
    if not address:
        return ""
    # "123 Main St, La Jolla, CA 92037" -> "123 Main St"
    return address.split(',')[0].strip()


def categorize_broker(broker: dict) -> Optional[tuple]:
    """
    Determine the best template category for a broker based on their listings.
    Returns (status, role) tuple or None if no match.
    """
    listings = broker.get('listings', [])
    if not listings or listings == []:
        return None
    
    # Parse listings JSON if it's a string
    if isinstance(listings, str):
        try:
            listings = json.loads(listings)
        except:
            return None
    
    if not listings:
        return None
    
    # Priority: sold+buyer > pending+seller > active+seller
    for listing in listings:
        if listing.get('status') == 'sold' and listing.get('role') == 'buyer':
            return ('sold', 'buyer')
    
    for listing in listings:
        if listing.get('status') == 'pending' and listing.get('role') == 'seller':
            return ('pending', 'seller')
    
    for listing in listings:
        if listing.get('status') == 'active' and listing.get('role') == 'seller':
            return ('active', 'seller')
    
    return None


def generate_intro_single(first_name: str, address: str, category: tuple, local_deal_line: str = "") -> str:
    """Generate intro for a single property, optionally with local deal reference."""
    status, role = category
    
    # Build the intro sentence based on category
    if status == 'sold' and role == 'buyer':
        intro = f"Hi {first_name},\n\nCongrats on closing {address}."
    elif status == 'pending':
        intro = f"Hi {first_name},\n\nCongrats on {address} going pending."
    else:  # active
        intro = f"Hi {first_name},\n\nSaw your listing at {address} — beautiful spot."
    
    # Append local deal line if we have one
    if local_deal_line:
        intro = f"{intro} {local_deal_line}"
    
    return intro


def generate_subject(broker: dict, category: tuple) -> str:
    """Generate email subject line."""
    listings = broker.get('listings', [])
    if isinstance(listings, str):
        listings = json.loads(listings)
    
    status, role = category
    relevant = [l for l in listings if l.get('status') == status and l.get('role') == role]
    
    if relevant:
        return get_short_address(relevant[0].get('address', ''))
    
    return "quick intro"


def get_template_body(template_name: str, skip_intro_line: bool = False) -> str:
    """
    Load template and extract boilerplate (skip greeting + personalized first paragraph).
    
    If skip_intro_line is True, also skip the "I run a private lending fund in Del Mar" line
    (used when the local deal line already includes this for HQ city cases).
    """
    content = load_template(template_name)
    lines = content.strip().split('\n')
    
    # Skip: line 0 (Hi X,), line 1 (blank), line 2 (personalized intro), line 3 (blank)
    # Keep everything from line 4 onwards (the "I'm reaching out..." or "I'm with Trinity..." paragraph)
    
    # Find the second blank line - everything after that is boilerplate
    blank_count = 0
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip() == '':
            blank_count += 1
        if blank_count >= 2:
            start_idx = i + 1
            break
    
    boilerplate = '\n'.join(lines[start_idx:]).strip()
    
    if skip_intro_line:
        # Remove the "I run a private lending fund in Del Mar." sentence
        # The boilerplate typically starts with this, followed by "We do business-purpose loans..."
        boilerplate = boilerplate.replace(
            "I run a private lending fund in Del Mar. ", ""
        )
    
    return boilerplate


def build_full_email(intro: str, template_name: str, skip_intro_line: bool = False) -> str:
    """Combine personalized intro with template boilerplate."""
    boilerplate = get_template_body(template_name, skip_intro_line=skip_intro_line)
    return f"{intro}\n\n{boilerplate}"


def get_listing_ids(broker: dict, category: tuple) -> list:
    """Get listing IDs for this email."""
    listings = broker.get('listings', [])
    if isinstance(listings, str):
        listings = json.loads(listings)
    
    status, role = category
    relevant = [l for l in listings if l.get('status') == status and l.get('role') == role]
    
    return [l.get('listing_id') for l in relevant if l.get('listing_id')]


def main():
    parser = argparse.ArgumentParser(description='Generate suggested emails')
    parser.add_argument('--limit', type=int, default=0, help='Max emails per category (0 = no limit)')
    parser.add_argument('--dry-run', action='store_true', help='Print but do not save')
    args = parser.parse_args()
    
    supabase = get_supabase_client()
    claude = get_anthropic_client()
    
    # Fetch TMF deal history for local personalization
    print("Fetching TMF deal history...")
    tmf_deals = fetch_tmf_deals(supabase)
    print(f"Loaded {len(tmf_deals)} TMF deals for local matching")
    
    print(f"\nFetching eligible brokers...")
    
    # Query outreach opportunities view
    result = supabase.table('outreach_opportunities').select('*').execute()
    brokers = result.data or []
    
    print(f"Found {len(brokers)} eligible brokers")
    
    # Categorize brokers
    categorized = {
        ('active', 'seller'): [],
        ('pending', 'seller'): [],
        ('sold', 'buyer'): [],
    }
    
    for broker in brokers:
        cat = categorize_broker(broker)
        if cat and cat in categorized:
            categorized[cat].append(broker)
    
    print(f"\nBy category:")
    for cat, brokers_list in categorized.items():
        print(f"  {cat[0]} ({cat[1]}): {len(brokers_list)} brokers")
    
    # Generate emails for each category
    total_generated = 0
    
    for category, brokers_list in categorized.items():
        template_name = TEMPLATES.get(category)
        if not template_name:
            continue
        
        print(f"\n=== Generating {category[0]} / {category[1]} emails ===")
        
        generated_this_category = 0
        for broker in brokers_list:
            if args.limit and generated_this_category >= args.limit:
                break
                
            broker_id = broker.get('broker_id')
            name = broker.get('name', 'Unknown')
            email = broker.get('email', '')
            
            # Skip excluded emails
            if email and email.lower() in EXCLUDED_EMAILS:
                continue
            
            first_name = get_broker_first_name(name)
            
            print(f"\n  {name} ({email})")
            
            # Get relevant listings for this category
            listings = broker.get('listings', [])
            if isinstance(listings, str):
                listings = json.loads(listings)
            
            status, role = category
            relevant = [l for l in listings if l.get('status') == status and l.get('role') == role]
            
            if not relevant:
                print(f"    Skipping - no {status}/{role} listings")
                continue
            
            # Generate intro with local deal personalization
            try:
                # Always pick one property (first/best match) - simpler and more natural
                listing = relevant[0]
                address = get_short_address(listing.get('address', ''))
                listing_city = listing.get('city', '')
                
                # Find relevant TMF deals near this listing
                deal_context = find_relevant_deals(listing_city, tmf_deals)
                local_deal_line = ""
                is_hq_format = False
                if deal_context:
                    local_deal_line, is_hq_format = generate_local_deal_line(deal_context, claude)
                    if local_deal_line:
                        print(f"    Local deal line: {local_deal_line}")
                
                intro = generate_intro_single(first_name, address, category, local_deal_line)
                print(f"    Property: {address}, {listing_city} ({len(relevant)} total)")
            except Exception as e:
                print(f"    Error generating intro: {e}")
                continue
            
            # Build full email (skip "I run a private lending fund" line if HQ format already includes it)
            full_body = build_full_email(intro, template_name, skip_intro_line=is_hq_format)
            subject = generate_subject(broker, category)
            listing_ids = get_listing_ids(broker, category)
            
            print(f"    Subject: {subject}")
            print(f"    Listings: {len(listing_ids)}")
            
            if args.dry_run:
                print(f"    [DRY RUN] Would save to suggested_emails")
                print(f"\n--- EMAIL PREVIEW ---\n{full_body[:500]}...\n---")
            else:
                # Insert into suggested_emails
                try:
                    supabase.table('suggested_emails').insert({
                        'broker_id': broker_id,
                        'new_listing_ids': listing_ids,
                        'subject': subject,
                        'body_content': full_body,
                        'is_first_contact': True,
                        'status': 'draft',
                    }).execute()
                    print(f"    Saved to suggested_emails")
                    total_generated += 1
                    generated_this_category += 1
                except Exception as e:
                    print(f"    Error saving: {e}")
    
    print(f"\n=== COMPLETE ===")
    print(f"Total emails generated: {total_generated}")


if __name__ == '__main__':
    main()
