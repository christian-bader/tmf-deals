#!/usr/bin/env python3
"""
Import listing CSVs into Supabase.

Usage:
    # Import active listings
    python import_to_supabase.py --active data/listings/daily/all_listings_2026-02-25_enriched.csv
    
    # Import sold listings
    python import_to_supabase.py --sold data/listings/daily/recently_sold.csv
    
    # Import both
    python import_to_supabase.py --active data/listings/daily/all_listings_*.csv --sold data/listings/daily/recently_sold.csv

Environment variables:
    SUPABASE_URL - Your Supabase project URL
    SUPABASE_KEY - Your Supabase anon/service key
"""

import argparse
import csv
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

# Load .env from repo root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')


def get_supabase_client() -> Client:
    """Create Supabase client from environment variables."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError(
            "Missing SUPABASE_URL or SUPABASE_KEY environment variables.\n"
            "Set them with:\n"
            "  export SUPABASE_URL=https://xxx.supabase.co\n"
            "  export SUPABASE_KEY=your-anon-key"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def parse_price(price_str: str) -> Optional[float]:
    """Parse price string like '$1,900,000' to float."""
    if not price_str:
        return None
    cleaned = re.sub(r'[^\d.]', '', price_str)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def parse_int(val: str) -> Optional[int]:
    """Parse integer, handling empty strings."""
    if not val:
        return None
    try:
        return int(float(val))
    except ValueError:
        return None


def parse_float(val: str) -> Optional[float]:
    """Parse float, handling empty strings."""
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def parse_date(date_str: str) -> Optional[str]:
    """Parse date string like 'Feb 25, 2026' to ISO format."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, '%b %d, %Y')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        return None


def normalize_status(status: str) -> str:
    """Normalize listing status to our enum values."""
    status_lower = (status or '').lower().strip()
    if status_lower in ['sold', 'closed']:
        return 'sold'
    elif status_lower in ['pending', 'contingent', 'under contract']:
        return 'pending'
    else:
        return 'active'


def upsert_listing(supabase: Client, row: dict, is_sold: bool = False) -> Optional[str]:
    """Upsert a listing and return its ID."""
    source_url = row.get('redfin_url', '').strip()
    if not source_url:
        return None
    
    status = 'sold' if is_sold else normalize_status(row.get('listing_status', 'active'))
    
    listing_data = {
        'source_url': source_url,
        'address': row.get('address', '').strip(),
        'city': row.get('city', '').strip(),
        'state': row.get('state', 'CA').strip(),
        'zip': row.get('zipcode', row.get('zip', '')).strip(),
        'price': parse_price(row.get('price', '')),
        'beds': parse_int(row.get('beds', '')),
        'baths': parse_float(row.get('baths', '')),
        'sqft': parse_int(row.get('sqft', '')),
        'lot_size': row.get('lot_size', '').strip() or None,
        'year_built': parse_int(row.get('year_built', '')),
        'property_type': row.get('property_type', '').strip() or None,
        'stories': parse_int(row.get('stories', '')),
        'garage_spaces': parse_int(row.get('garage_spaces', '')),
        'price_per_sqft': parse_float(row.get('price_per_sqft', '')),
        'hoa_dues': parse_float(row.get('hoa_dues', '')),
        'status': status,
        'listing_date': parse_date(row.get('listing_date', '')),
        'mls_number': row.get('mls_number', '').strip() or None,
        'days_on_market': parse_int(row.get('days_on_market', '')),
        'description': (row.get('description', '') or '')[:500],
        'source_platform': 'redfin',
        'scraped_at': row.get('scraped_at', '').strip() or None,
    }
    scrape_instance_id = (row.get('scrape_instance_id') or '').strip()
    if scrape_instance_id:
        listing_data['scrape_instance_id'] = scrape_instance_id
    
    listing_data = {k: v for k, v in listing_data.items() if v is not None}
    
    result = supabase.table('listings').upsert(
        listing_data,
        on_conflict='source_url'
    ).execute()
    
    if result.data:
        return result.data[0]['id']
    return None


# Cache for DRE lookups to avoid repeated queries
DRE_CACHE = {}


def lookup_dre_license(supabase: Client, license_number: str) -> Optional[dict]:
    """Look up a license in the DRE database. Returns canonical info."""
    if not license_number:
        return None
    
    license_number = license_number.strip()
    
    if license_number in DRE_CACHE:
        return DRE_CACHE[license_number]
    
    result = supabase.table('dre_licenses').select(
        'id, license_number, first_name, last_name, name_suffix, full_name, license_type, license_status'
    ).eq('license_number', license_number).execute()
    
    if result.data:
        DRE_CACHE[license_number] = result.data[0]
        return result.data[0]
    
    DRE_CACHE[license_number] = None
    return None


def upsert_broker(supabase: Client, name: str, phone: str, 
                  license_number: str, brokerage: str) -> Optional[str]:
    """
    Upsert a broker by DRE license and return their ID.
    
    One broker per DRE license. Uses DRE database for canonical name.
    Emails are stored separately in broker_emails table.
    """
    license_number = (license_number or '').strip()
    scraped_name = (name or '').strip()
    
    if not license_number:
        return None
    
    # Look up canonical info from DRE database
    dre_info = lookup_dre_license(supabase, license_number)
    
    # Determine canonical name: prefer DRE, fall back to scraped
    if dre_info and dre_info.get('full_name'):
        canonical_name = dre_info['full_name']
        name_from_dre = True
    else:
        canonical_name = scraped_name or None
        name_from_dre = False
    
    # Check if broker exists
    result = supabase.table('brokers').select('id').eq('license_number', license_number).execute()
    
    if result.data:
        broker_id = result.data[0]['id']
        
        # Update with any new info
        update_data = {}
        if name_from_dre and canonical_name:
            update_data['name'] = canonical_name
            update_data['name_from_dre'] = True
        if dre_info:
            update_data['dre_license_id'] = dre_info['id']
            update_data['dre_verified'] = True
        if phone:
            update_data['phone'] = phone.strip()
        if brokerage:
            update_data['brokerage_name'] = brokerage.strip()
        
        if update_data:
            supabase.table('brokers').update(update_data).eq('id', broker_id).execute()
        
        return broker_id
    else:
        # Insert new broker
        broker_data = {
            'license_number': license_number,
            'name': canonical_name,
            'phone': (phone or '').strip() or None,
            'brokerage_name': (brokerage or '').strip() or None,
            'state_licensed': 'CA',
            'dre_verified': dre_info is not None,
            'name_from_dre': name_from_dre,
        }
        
        if dre_info:
            broker_data['dre_license_id'] = dre_info['id']
        
        broker_data = {k: v for k, v in broker_data.items() if v is not None}
        
        result = supabase.table('brokers').insert(broker_data).execute()
        if result.data:
            return result.data[0]['id']
    
    return None


def add_broker_email(supabase: Client, broker_id: str, email: str, 
                     listing_id: Optional[str] = None) -> bool:
    """
    Add an email for a broker in the broker_emails junction table.
    
    Returns True if email was added/updated, False if skipped.
    """
    if not broker_id or not email:
        return False
    
    email = email.strip().lower()
    if not email:
        return False
    
    try:
        # Upsert: create new or update last_seen_at if exists
        supabase.table('broker_emails').upsert({
            'broker_id': broker_id,
            'email': email,
            'source_listing_id': listing_id,
            'last_seen_at': datetime.utcnow().isoformat(),
        }, on_conflict='broker_id,email').execute()
        return True
    except Exception as e:
        if 'duplicate' not in str(e).lower():
            print(f"  Warning: Could not add broker email: {e}")
        return False


def link_broker_listing(supabase: Client, broker_id: str, listing_id: str, role: str):
    """Create broker-listing relationship."""
    if not broker_id or not listing_id:
        return
    
    try:
        supabase.table('broker_listings').upsert({
            'broker_id': broker_id,
            'listing_id': listing_id,
            'role': role,
        }, on_conflict='broker_id,listing_id,role').execute()
    except Exception as e:
        if 'duplicate' not in str(e).lower():
            print(f"  Warning: Could not link broker to listing: {e}")


def import_active_listings(supabase: Client, csv_path: str) -> dict:
    """Import active/pending listings CSV."""
    stats = {'listings': 0, 'brokers': 0, 'emails': 0, 'links': 0, 'skipped': 0}
    
    with open(csv_path) as f:
        total_rows = sum(1 for _ in f) - 1
    
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            address = row.get('address', 'unknown')
            
            if i % 50 == 0 or i == 1:
                print(f"  [{i}/{total_rows}] Processing: {address[:50]}...")
            
            listing_id = upsert_listing(supabase, row, is_sold=False)
            if not listing_id:
                stats['skipped'] += 1
                continue
            stats['listings'] += 1
            
            # Get agent info
            license_number = row.get('agent_dre', '').strip()
            agent_email = row.get('agent_email', '') or row.get('inferred_email', '')
            
            if license_number:
                broker_id = upsert_broker(
                    supabase,
                    name=row.get('listing_agent', ''),
                    phone=row.get('agent_phone', ''),
                    license_number=license_number,
                    brokerage=row.get('brokerage', ''),
                )
                
                if broker_id:
                    stats['brokers'] += 1
                    
                    # Add email if present
                    if agent_email and add_broker_email(supabase, broker_id, agent_email, listing_id):
                        stats['emails'] += 1
                    
                    link_broker_listing(supabase, broker_id, listing_id, 'seller')
                    stats['links'] += 1
    
    print(f"  [{total_rows}/{total_rows}] Done!")
    return stats


def import_sold_listings(supabase: Client, csv_path: str) -> dict:
    """Import recently sold listings CSV (has both listing + buyer agents)."""
    stats = {'listings': 0, 'brokers': 0, 'emails': 0, 'links': 0, 'skipped': 0}
    
    with open(csv_path) as f:
        total_rows = sum(1 for _ in f) - 1
    
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            address = row.get('address', 'unknown')
            
            if i % 25 == 0 or i == 1:
                print(f"  [{i}/{total_rows}] Processing: {address[:50]}...")
            
            listing_id = upsert_listing(supabase, row, is_sold=True)
            if not listing_id:
                stats['skipped'] += 1
                continue
            stats['listings'] += 1
            
            # Listing agent (seller's rep)
            seller_license = row.get('agent_dre', '').strip()
            if seller_license:
                broker_id = upsert_broker(
                    supabase,
                    name=row.get('listing_agent', ''),
                    phone=row.get('agent_phone', ''),
                    license_number=seller_license,
                    brokerage=row.get('brokerage', ''),
                )
                if broker_id:
                    stats['brokers'] += 1
                    
                    seller_email = row.get('agent_email', '').strip()
                    if seller_email and add_broker_email(supabase, broker_id, seller_email, listing_id):
                        stats['emails'] += 1
                    
                    link_broker_listing(supabase, broker_id, listing_id, 'seller')
                    stats['links'] += 1
            
            # Buyer's agent
            buyer_license = row.get('buyer_agent_dre', '').strip()
            if buyer_license:
                buyer_broker_id = upsert_broker(
                    supabase,
                    name=row.get('buyer_agent', ''),
                    phone=row.get('buyer_agent_phone', ''),
                    license_number=buyer_license,
                    brokerage=row.get('buyer_brokerage', ''),
                )
                if buyer_broker_id:
                    stats['brokers'] += 1
                    
                    buyer_email = row.get('buyer_agent_email', '').strip()
                    if buyer_email and add_broker_email(supabase, buyer_broker_id, buyer_email, listing_id):
                        stats['emails'] += 1
                    
                    link_broker_listing(supabase, buyer_broker_id, listing_id, 'buyer')
                    stats['links'] += 1
    
    print(f"  [{total_rows}/{total_rows}] Done!")
    return stats


def main():
    parser = argparse.ArgumentParser(description='Import listing CSVs into Supabase')
    parser.add_argument('--active', nargs='*', help='Active listings CSV file(s)')
    parser.add_argument('--sold', nargs='*', help='Sold listings CSV file(s)')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be imported')
    args = parser.parse_args()
    
    if not args.active and not args.sold:
        parser.print_help()
        print("\nError: Provide at least one CSV with --active or --sold")
        return
    
    if args.dry_run:
        print("DRY RUN - Would import:")
        if args.active:
            for f in args.active:
                print(f"  Active: {f}")
        if args.sold:
            for f in args.sold:
                print(f"  Sold: {f}")
        return
    
    supabase = get_supabase_client()
    print(f"Connected to Supabase: {SUPABASE_URL}")
    
    total_stats = {'listings': 0, 'brokers': 0, 'emails': 0, 'links': 0, 'skipped': 0}
    
    if args.active:
        for csv_path in args.active:
            print(f"\nImporting active listings from: {csv_path}")
            stats = import_active_listings(supabase, csv_path)
            print(f"  Listings: {stats['listings']}, Brokers: {stats['brokers']}, Emails: {stats['emails']}, Links: {stats['links']}")
            for k in total_stats:
                total_stats[k] += stats[k]
    
    if args.sold:
        for csv_path in args.sold:
            print(f"\nImporting sold listings from: {csv_path}")
            stats = import_sold_listings(supabase, csv_path)
            print(f"  Listings: {stats['listings']}, Brokers: {stats['brokers']}, Emails: {stats['emails']}, Links: {stats['links']}")
            for k in total_stats:
                total_stats[k] += stats[k]
    
    print(f"\n=== TOTAL ===")
    print(f"Listings: {total_stats['listings']}")
    print(f"Brokers: {total_stats['brokers']}")
    print(f"Emails: {total_stats['emails']}")
    print(f"Links: {total_stats['links']}")
    print(f"Skipped: {total_stats['skipped']}")


if __name__ == '__main__':
    main()
