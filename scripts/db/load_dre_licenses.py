#!/usr/bin/env python3
"""
Load CA DRE license database into Supabase.

Usage:
    python load_dre_licenses.py [--file PATH]

Default file: data/ca-dre/CurrList.csv
"""

import argparse
import csv
import os
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

DEFAULT_DRE_FILE = Path(__file__).parent.parent.parent / 'data' / 'ca-dre' / 'CurrList.csv'

# Batch size for inserts
BATCH_SIZE = 500


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def parse_date(date_str: str) -> Optional[str]:
    """Parse date like '20250522' to '2025-05-22'."""
    if not date_str or len(date_str) != 8:
        return None
    try:
        dt = datetime.strptime(date_str, '%Y%m%d')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        return None


def transform_row(row: dict) -> dict:
    """Transform CSV row to database record."""
    return {
        'license_number': row.get('lic_number', '').strip(),
        'last_name': row.get('lastname_primary', '').strip() or None,
        'first_name': row.get('firstname_secondary', '').strip() or None,
        'name_suffix': row.get('name_suffix', '').strip() or None,
        'license_type': row.get('lic_type', '').strip() or None,
        'license_status': row.get('lic_status', '').strip() or None,
        'license_effective_date': parse_date(row.get('lic_effective_date', '')),
        'license_expiration_date': parse_date(row.get('lic_expiration_date', '')),
        'original_license_date': parse_date(row.get('original_date_of_license', '')),
        'related_license_number': row.get('related_lic_number', '').strip() or None,
        'related_name': ' '.join(filter(None, [
            row.get('related_firstname_secondary', '').strip(),
            row.get('related_lastname_primary', '').strip(),
            row.get('related_name_suffix', '').strip()
        ])) or None,
        'related_license_type': row.get('related_lic_type', '').strip() or None,
        'address_1': row.get('address_1', '').strip() or None,
        'address_2': row.get('address_2', '').strip() or None,
        'city': row.get('city', '').strip() or None,
        'state': row.get('state', '').strip() or None,
        'zip_code': row.get('zip_code', '').strip() or None,
        'county_name': row.get('county_name', '').strip() or None,
    }


def load_dre_licenses(supabase: Client, csv_path: str) -> dict:
    """Load DRE licenses from CSV into Supabase.
    
    IMPORTANT: One license number can have multiple rows (e.g., Broker + Officer).
    We prefer Broker/Salesperson over Officer/Corporation to ensure we get the
    individual agent's record, not their corporate officer designation.
    """
    stats = {'inserted': 0, 'skipped': 0, 'duplicates': 0, 'errors': 0}
    
    # Priority: lower is better (prefer individual over corporate)
    TYPE_PRIORITY = {
        'Broker': 1,
        'Salesperson': 2,
        'Officer': 3,
        'Corporation': 4,
    }
    
    # First pass: collect best record for each license
    print(f"Reading DRE licenses from {csv_path}...")
    best_records = {}  # license_number -> (priority, record)
    
    with open(csv_path, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            lic_num = row.get('lic_number', '').strip()
            if not lic_num:
                stats['skipped'] += 1
                continue
            
            lic_type = row.get('lic_type', '').strip()
            priority = TYPE_PRIORITY.get(lic_type, 99)
            
            existing = best_records.get(lic_num)
            if not existing or priority < existing[0]:
                best_records[lic_num] = (priority, row)
            else:
                stats['duplicates'] += 1
    
    total_unique = len(best_records)
    print(f"  Found {total_unique:,} unique licenses ({stats['duplicates']:,} duplicate rows skipped)")
    
    # Second pass: insert best records
    print(f"Inserting into Supabase...")
    batch = []
    
    for i, (lic_num, (_, row)) in enumerate(best_records.items(), 1):
        if i % 10000 == 0 or i == 1:
            print(f"  [{i:,}/{total_unique:,}] Processing...")
        
        record = transform_row(row)
        batch.append(record)
        
        if len(batch) >= BATCH_SIZE:
            try:
                supabase.table('dre_licenses').upsert(
                    batch,
                    on_conflict='license_number'
                ).execute()
                stats['inserted'] += len(batch)
            except Exception as e:
                print(f"  Error inserting batch: {e}")
                stats['errors'] += len(batch)
            batch = []
    
    # Insert remaining
    if batch:
        try:
            supabase.table('dre_licenses').upsert(
                batch,
                on_conflict='license_number'
            ).execute()
            stats['inserted'] += len(batch)
        except Exception as e:
            print(f"  Error inserting final batch: {e}")
            stats['errors'] += len(batch)
    
    print(f"  [{total_unique:,}/{total_unique:,}] Done!")
    return stats


def main():
    parser = argparse.ArgumentParser(description='Load CA DRE licenses into Supabase')
    parser.add_argument('--file', type=str, default=str(DEFAULT_DRE_FILE),
                        help=f'DRE CSV file (default: {DEFAULT_DRE_FILE})')
    args = parser.parse_args()
    
    if not Path(args.file).exists():
        print(f"Error: File not found: {args.file}")
        return
    
    supabase = get_supabase_client()
    print(f"Connected to Supabase: {SUPABASE_URL}")
    
    stats = load_dre_licenses(supabase, args.file)
    
    print(f"\n=== SUMMARY ===")
    print(f"Inserted/Updated: {stats['inserted']:,}")
    print(f"Skipped: {stats['skipped']:,}")
    print(f"Errors: {stats['errors']:,}")


if __name__ == '__main__':
    main()
