#!/usr/bin/env python3
"""
Import clean demo data into Supabase.

Clears existing data and imports only the verified demo dataset.

Usage:
    python import_demo.py
    python import_demo.py --dry-run
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
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
env_path = PROJECT_ROOT / '.env'
load_dotenv(env_path)

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

DEMO_DIR = PROJECT_ROOT / 'data' / 'listings' / 'demo'


def get_supabase_client() -> Client:
    """Create Supabase client from environment variables."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def clear_all_data(supabase: Client):
    """Clear all existing data from tables (in correct order for FK constraints)."""
    print("Clearing existing data...")
    
    # Delete in order respecting foreign keys
    tables_to_clear = [
        'broker_listings',
        'sent_email_logs',
        'suggested_emails',
        'outreach_suppression_logs',
        'brokers',
        'listings',
    ]
    
    for table in tables_to_clear:
        try:
            # Delete all rows - use a filter that matches everything
            result = supabase.table(table).delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
            count = len(result.data) if result.data else 0
            print(f"  Cleared {table}: {count} rows")
        except Exception as e:
            # Table might not exist yet
            if 'does not exist' in str(e).lower() or 'relation' in str(e).lower():
                print(f"  Skipped {table}: table doesn't exist yet")
            else:
                print(f"  Warning clearing {table}: {e}")


def parse_price(price_str: str) -> Optional[float]:
    if not price_str:
        return None
    cleaned = re.sub(r'[^\d.]', '', price_str)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def parse_int(val: str) -> Optional[int]:
    if not val:
        return None
    try:
        return int(float(val))
    except ValueError:
        return None


def parse_float(val: str) -> Optional[float]:
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def parse_date(date_str: str) -> Optional[str]:
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, '%b %d, %Y')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        return None


def import_demo_file(supabase: Client, csv_path: Path, status: str) -> dict:
    """Import a single demo CSV file."""
    stats = {'listings': 0, 'brokers': 0, 'emails': 0, 'links': 0}
    
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"  Importing {len(rows)} {status} listings...")
    
    for i, row in enumerate(rows, 1):
        # Insert listing
        listing_data = {
            'source_url': row.get('redfin_url', '').strip(),
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
            'description': (row.get('description', '') or '')[:500] or None,
            'source_platform': 'redfin',
        }
        
        listing_data = {k: v for k, v in listing_data.items() if v is not None}
        
        # Upsert to handle duplicates (same property in active + pending)
        result = supabase.table('listings').upsert(
            listing_data, on_conflict='source_url'
        ).execute()
        if not result.data:
            continue
        
        listing_id = result.data[0]['id']
        stats['listings'] += 1
        
        # Insert broker
        license_number = row.get('agent_dre', '').strip()
        agent_email = row.get('agent_email', '').strip()
        
        if license_number:
            # Check if broker exists
            existing = supabase.table('brokers').select('id').eq('license_number', license_number).execute()
            
            if existing.data:
                broker_id = existing.data[0]['id']
                # Update with new info if we have it
                update_data = {}
                if agent_email:
                    update_data['email'] = agent_email.lower()
                if row.get('listing_agent', '').strip():
                    update_data['name'] = row.get('listing_agent', '').strip()
                if row.get('agent_phone', '').strip():
                    update_data['phone'] = row.get('agent_phone', '').strip()
                if row.get('brokerage', '').strip():
                    update_data['brokerage_name'] = row.get('brokerage', '').strip()
                if update_data:
                    supabase.table('brokers').update(update_data).eq('id', broker_id).execute()
            else:
                # Insert new broker
                broker_data = {
                    'license_number': license_number,
                    'name': row.get('listing_agent', '').strip() or None,
                    'email': agent_email.lower() if agent_email else None,
                    'phone': row.get('agent_phone', '').strip() or None,
                    'brokerage_name': row.get('brokerage', '').strip() or None,
                    'state_licensed': 'CA',
                }
                broker_data = {k: v for k, v in broker_data.items() if v is not None}
                
                result = supabase.table('brokers').insert(broker_data).execute()
                if result.data:
                    broker_id = result.data[0]['id']
                    stats['brokers'] += 1
                    if agent_email:
                        stats['emails'] += 1
                else:
                    broker_id = None
                
            if broker_id:
                # Link broker to listing (listing agent is always seller role)
                existing_link = supabase.table('broker_listings').select('id').eq(
                    'broker_id', broker_id
                ).eq('listing_id', listing_id).eq('role', 'seller').execute()
                
                if not existing_link.data:
                    supabase.table('broker_listings').insert({
                        'broker_id': broker_id,
                        'listing_id': listing_id,
                        'role': 'seller',
                    }).execute()
                    stats['links'] += 1
        
        # Handle buyer agent for sold listings
        if status == 'sold':
            buyer_license = row.get('buyer_agent_dre', '').strip()
            buyer_email = row.get('buyer_agent_email', '').strip()
            
            if buyer_license:
                # Check if buyer broker exists
                existing = supabase.table('brokers').select('id').eq('license_number', buyer_license).execute()
                
                if existing.data:
                    buyer_broker_id = existing.data[0]['id']
                    # Update with new info
                    update_data = {}
                    if buyer_email:
                        update_data['email'] = buyer_email.lower()
                    if row.get('buyer_agent', '').strip():
                        update_data['name'] = row.get('buyer_agent', '').strip()
                    if update_data:
                        supabase.table('brokers').update(update_data).eq('id', buyer_broker_id).execute()
                else:
                    # Insert new buyer broker
                    buyer_data = {
                        'license_number': buyer_license,
                        'name': row.get('buyer_agent', '').strip() or None,
                        'email': buyer_email.lower() if buyer_email else None,
                        'phone': row.get('buyer_agent_phone', '').strip() or None,
                        'brokerage_name': row.get('buyer_brokerage', '').strip() or None,
                        'state_licensed': 'CA',
                    }
                    buyer_data = {k: v for k, v in buyer_data.items() if v is not None}
                    
                    result = supabase.table('brokers').insert(buyer_data).execute()
                    if result.data:
                        buyer_broker_id = result.data[0]['id']
                        stats['brokers'] += 1
                        if buyer_email:
                            stats['emails'] += 1
                    else:
                        buyer_broker_id = None
                
                if buyer_broker_id:
                    # Check if link exists
                    existing_link = supabase.table('broker_listings').select('id').eq(
                        'broker_id', buyer_broker_id
                    ).eq('listing_id', listing_id).eq('role', 'buyer').execute()
                    
                    if not existing_link.data:
                        supabase.table('broker_listings').insert({
                            'broker_id': buyer_broker_id,
                            'listing_id': listing_id,
                            'role': 'buyer',
                        }).execute()
                        stats['links'] += 1
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Import clean demo data into Supabase')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be imported')
    parser.add_argument('--no-clear', action='store_true', help='Skip clearing existing data')
    args = parser.parse_args()
    
    # Check demo files exist
    demo_files = {
        'active': DEMO_DIR / 'demo_active.csv',
        'pending': DEMO_DIR / 'demo_pending.csv',
        'sold': DEMO_DIR / 'demo_sold.csv',
    }
    
    existing_files = {k: v for k, v in demo_files.items() if v.exists()}
    
    if not existing_files:
        print(f"No demo files found in {DEMO_DIR}")
        print("Run extract_clean_demo.py first to create demo data.")
        return
    
    print("Demo files to import:")
    for status, path in existing_files.items():
        with open(path) as f:
            count = sum(1 for _ in f) - 1
        print(f"  {status}: {path.name} ({count} rows)")
    
    if args.dry_run:
        print("\nDry run - no changes made.")
        return
    
    supabase = get_supabase_client()
    print(f"\nConnected to Supabase: {SUPABASE_URL}")
    
    # Clear existing data
    if not args.no_clear:
        clear_all_data(supabase)
    
    # Import demo files
    print("\nImporting demo data...")
    total_stats = {'listings': 0, 'brokers': 0, 'emails': 0, 'links': 0}
    
    for status, path in existing_files.items():
        stats = import_demo_file(supabase, path, status)
        print(f"    {status}: {stats['listings']} listings, {stats['brokers']} brokers, {stats['emails']} emails")
        for k in total_stats:
            total_stats[k] += stats[k]
    
    print(f"\n=== IMPORT COMPLETE ===")
    print(f"Total listings: {total_stats['listings']}")
    print(f"Total brokers: {total_stats['brokers']}")
    print(f"Total emails: {total_stats['emails']}")
    print(f"Total links: {total_stats['links']}")


if __name__ == '__main__':
    main()
