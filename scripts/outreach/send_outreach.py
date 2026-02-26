"""
Send outreach emails to listing agents from recently sold properties.

Usage:
    # Dry run (default) - shows what would be sent
    python send_outreach.py
    
    # Actually send emails
    python send_outreach.py --send
    
    # Limit number of emails
    python send_outreach.py --send --limit 5
"""

import argparse
import csv
import time
from pathlib import Path
from datetime import datetime

from gmail_auth import send_email, get_profile

DATA_DIR = Path(__file__).parent.parent.parent / 'data' / 'listings' / 'daily'
RECENTLY_SOLD_FILE = DATA_DIR / 'recently_sold.csv'
SENT_LOG_FILE = Path(__file__).parent / 'sent_emails.csv'

EMAIL_TEMPLATE = """Hi {agent_first_name},

I came across the property at {address} that recently sold for ${price:,.0f} and saw you represented the seller.

I'm an investor focused on San Diego residential properties and I'm actively looking to acquire more homes in the area. I specialize in quick, cash purchases with flexible terms.

If you have any clients with properties they're looking to sell - whether on or off market - I'd love to connect. I can typically close in 2-3 weeks and am happy to work around your clients' timelines.

Would you have a few minutes to chat this week?

Best,
Christian

---
Christian Bader
IDI Investments
"""


def load_recently_sold() -> list[dict]:
    """Load recently sold listings."""
    if not RECENTLY_SOLD_FILE.exists():
        raise FileNotFoundError(f"Recently sold file not found: {RECENTLY_SOLD_FILE}")
    
    with open(RECENTLY_SOLD_FILE) as f:
        return list(csv.DictReader(f))


def load_sent_emails() -> set[str]:
    """Load set of already-contacted agent emails."""
    if not SENT_LOG_FILE.exists():
        return set()
    
    with open(SENT_LOG_FILE) as f:
        reader = csv.DictReader(f)
        return {row['agent_email'] for row in reader}


def log_sent_email(listing: dict, agent_email: str):
    """Log a sent email to the tracking file."""
    file_exists = SENT_LOG_FILE.exists()
    
    with open(SENT_LOG_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'sent_at', 'agent_email', 'agent_name', 'address', 'price', 'listing_id'
        ])
        if not file_exists:
            writer.writeheader()
        
        writer.writerow({
            'sent_at': datetime.now().isoformat(),
            'agent_email': agent_email,
            'agent_name': listing.get('agent_name', ''),
            'address': listing.get('address', ''),
            'price': listing.get('price', ''),
            'listing_id': listing.get('listing_id', listing.get('mls_number', '')),
        })


def get_agent_first_name(full_name: str) -> str:
    """Extract first name from full agent name."""
    if not full_name:
        return "there"
    return full_name.split()[0]


def format_email(listing: dict) -> tuple[str, str]:
    """Generate subject and body for a listing."""
    address = listing.get('address', listing.get('street_address', 'your recent listing'))
    price = float(listing.get('price', listing.get('sold_price', '0')).replace(',', '').replace('$', '') or 0)
    agent_name = listing.get('agent_name', listing.get('listing_agent', ''))
    
    subject = f"Re: {address}"
    
    body = EMAIL_TEMPLATE.format(
        agent_first_name=get_agent_first_name(agent_name),
        address=address,
        price=price,
    )
    
    return subject, body


def find_agent_email(listing: dict) -> str | None:
    """Extract agent email from listing."""
    for key in ['agent_email', 'listing_agent_email', 'email']:
        email = listing.get(key, '')
        if email and '@' in email:
            return email
    return None


def main():
    parser = argparse.ArgumentParser(description='Send outreach emails to listing agents')
    parser.add_argument('--send', action='store_true', help='Actually send emails (default is dry run)')
    parser.add_argument('--limit', type=int, default=10, help='Max emails to send (default: 10)')
    parser.add_argument('--delay', type=float, default=5.0, help='Seconds between emails (default: 5)')
    args = parser.parse_args()
    
    if args.send:
        profile = get_profile()
        print(f"Sending from: {profile['emailAddress']}")
    else:
        print("=== DRY RUN MODE (use --send to actually send) ===\n")
    
    listings = load_recently_sold()
    sent_emails = load_sent_emails()
    
    print(f"Found {len(listings)} recently sold listings")
    print(f"Already contacted {len(sent_emails)} agents\n")
    
    sent_count = 0
    skipped_no_email = 0
    skipped_already_sent = 0
    
    for listing in listings:
        if sent_count >= args.limit:
            print(f"\nReached limit of {args.limit} emails")
            break
        
        agent_email = find_agent_email(listing)
        
        if not agent_email:
            skipped_no_email += 1
            continue
        
        if agent_email in sent_emails:
            skipped_already_sent += 1
            continue
        
        subject, body = format_email(listing)
        address = listing.get('address', listing.get('street_address', 'Unknown'))
        
        print(f"{'Sending' if args.send else 'Would send'} to: {agent_email}")
        print(f"  Property: {address}")
        print(f"  Subject: {subject}")
        
        if args.send:
            try:
                send_email(
                    to=agent_email,
                    subject=subject,
                    body=body,
                    dry_run=False
                )
                log_sent_email(listing, agent_email)
                sent_emails.add(agent_email)
                sent_count += 1
                
                if sent_count < args.limit:
                    print(f"  Waiting {args.delay}s before next email...")
                    time.sleep(args.delay)
                    
            except Exception as e:
                print(f"  ERROR: {e}")
        else:
            sent_count += 1
        
        print()
    
    print(f"\n{'Sent' if args.send else 'Would send'}: {sent_count} emails")
    print(f"Skipped (no email): {skipped_no_email}")
    print(f"Skipped (already contacted): {skipped_already_sent}")


if __name__ == '__main__':
    main()
