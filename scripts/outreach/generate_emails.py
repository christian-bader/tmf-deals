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
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
TEMPLATES_DIR = PROJECT_ROOT / 'templates'

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


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


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


def generate_intro_single(first_name: str, address: str, category: tuple) -> str:
    """Generate intro for a single property - no LLM needed, just template."""
    status, role = category
    
    if status == 'sold' and role == 'buyer':
        return f"Hi {first_name},\n\nCongrats on closing {address}."
    elif status == 'pending':
        return f"Hi {first_name},\n\nCongrats on {address} going pending."
    else:  # active
        return f"Hi {first_name},\n\nSaw your listing at {address} — beautiful spot."


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


def get_template_body(template_name: str) -> str:
    """Load template and extract boilerplate (skip greeting + personalized first paragraph)."""
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
    
    return '\n'.join(lines[start_idx:]).strip()


def build_full_email(intro: str, template_name: str) -> str:
    """Combine personalized intro with template boilerplate (starting at 'I'm with Trinity...')."""
    boilerplate = get_template_body(template_name)
    # Intro already includes "Hi X," and first paragraph
    # Boilerplate starts with "I'm with Trinity..."
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
    
    print(f"Fetching eligible brokers...")
    
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
            
            # Generate intro - simple template for single, LLM for multiple
            try:
                # Always pick one property (first/best match) - simpler and more natural
                address = get_short_address(relevant[0].get('address', ''))
                intro = generate_intro_single(first_name, address, category)
                print(f"    Property: {address} ({len(relevant)} total)")
            except Exception as e:
                print(f"    Error generating intro: {e}")
                continue
            
            # Build full email
            full_body = build_full_email(intro, template_name)
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
