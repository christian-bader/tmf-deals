#!/usr/bin/env python3
"""
Daily Listing Pipeline

Scrapes all target zip codes, identifies NEW listings since yesterday,
enriches with DRE data, and outputs a ready-for-outreach CSV.

Usage:
    python daily_pipeline.py                    # Run full pipeline
    python daily_pipeline.py --dry-run          # Show what would be scraped without scraping
    python daily_pipeline.py --skip-scrape      # Just diff/enrich existing data

Schedule with cron (e.g., every day at 7am):
    0 7 * * * cd /path/to/repo && python scripts/listings/daily_pipeline.py >> logs/pipeline.log 2>&1

Output:
    data/listings/daily/new_listings_YYYY-MM-DD.csv  - New listings for outreach
    data/listings/daily/all_listings_YYYY-MM-DD.csv  - Full snapshot for diffing
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from scrape_current_listings import fetch_redfin_search, fetch_listing_details, ListingRecord, TARGET_ZIPS

import time
from dataclasses import asdict

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "listings" / "daily"
DRE_FILE = PROJECT_ROOT / "data" / "ca-dre" / "CurrList.csv"


def load_dre_database() -> dict:
    """Load the CA DRE licensee database for enrichment."""
    print("Loading DRE database...", file=sys.stderr)
    dre_lookup = {}
    
    if not DRE_FILE.exists():
        print(f"  Warning: DRE file not found at {DRE_FILE}", file=sys.stderr)
        return dre_lookup
    
    with open(DRE_FILE, encoding="latin-1") as f:
        for row in csv.DictReader(f):
            lic_num = row.get("lic_number", "").lstrip("0")
            dre_lookup[lic_num] = row
    
    print(f"  Loaded {len(dre_lookup):,} licensees", file=sys.stderr)
    return dre_lookup


def load_previous_listings(date: datetime) -> set:
    """Load identifiers from previous day's snapshot to identify new listings.
    
    Uses MLS number as primary key, falls back to Redfin URL for listings without MLS.
    """
    prev_date = date - timedelta(days=1)
    prev_file = DATA_DIR / f"all_listings_{prev_date.strftime('%Y-%m-%d')}.csv"
    
    if not prev_file.exists():
        print(f"  No previous file found ({prev_file.name}), all listings will be 'new'", file=sys.stderr)
        return set()
    
    print(f"  Loading previous listings from {prev_file.name}...", file=sys.stderr)
    identifiers = set()
    
    with open(prev_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Use MLS number if available, otherwise use Redfin URL
            mls = row.get("mls_number", "").strip()
            url = row.get("redfin_url", "").strip()
            
            if mls:
                identifiers.add(f"mls:{mls}")
            if url:
                identifiers.add(f"url:{url}")
    
    print(f"  Found {len(identifiers):,} previous listing identifiers", file=sys.stderr)
    return identifiers


def enrich_with_dre(listing: dict, dre_lookup: dict) -> dict:
    """Add full DRE info to a listing record."""
    dre_num = listing.get("agent_dre", "").lstrip("0")
    dre_info = dre_lookup.get(dre_num, {})
    
    # Add enriched fields
    listing["agent_full_name"] = f"{dre_info.get('firstname_secondary', '')} {dre_info.get('lastname_primary', '')}".strip()
    listing["agent_license_type"] = dre_info.get("lic_type", "")
    listing["agent_license_status"] = dre_info.get("lic_status", "")
    listing["agent_license_expires"] = dre_info.get("lic_expiration_date", "")
    listing["agent_business_address"] = dre_info.get("address_1", "")
    listing["agent_business_city"] = dre_info.get("city", "")
    listing["agent_business_zip"] = dre_info.get("zip_code", "")
    
    # If salesperson, get broker info
    if dre_info.get("lic_type") == "Salesperson":
        listing["supervising_broker_name"] = f"{dre_info.get('related_firstname_secondary', '')} {dre_info.get('related_lastname_primary', '')}".strip()
        listing["supervising_broker_dre"] = dre_info.get("related_lic_number", "")
    else:
        listing["supervising_broker_name"] = ""
        listing["supervising_broker_dre"] = ""
    
    return listing


def scrape_all_zips(delay: float = 2.0) -> list[dict]:
    """Scrape all target zip codes and return listing records."""
    all_listings = []
    
    print(f"\nScraping {len(TARGET_ZIPS)} zip codes...", file=sys.stderr)
    
    for zip_idx, zipcode in enumerate(TARGET_ZIPS, 1):
        print(f"\n[{zip_idx}/{len(TARGET_ZIPS)}] Zip code {zipcode}", file=sys.stderr)
        
        listing_urls = fetch_redfin_search(zipcode)
        
        for i, url in enumerate(listing_urls, 1):
            print(f"    [{i}/{len(listing_urls)}] Fetching...", file=sys.stderr, end="\r")
            record = fetch_listing_details(url)
            if record:
                all_listings.append(asdict(record))
            time.sleep(delay)
        
        print(f"    Scraped {len(listing_urls)} listings from {zipcode}", file=sys.stderr)
        
        # Longer delay between zip codes
        if zip_idx < len(TARGET_ZIPS):
            time.sleep(3)
    
    return all_listings


def run_pipeline(dry_run: bool = False, skip_scrape: bool = False, delay: float = 2.0):
    """Run the full daily pipeline."""
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"DAILY LISTING PIPELINE - {date_str}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    
    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load DRE database
    dre_lookup = load_dre_database()
    
    # Load previous day's listings for diffing
    previous_mls = load_previous_listings(today)
    
    if dry_run:
        print(f"\n[DRY RUN] Would scrape {len(TARGET_ZIPS)} zip codes:", file=sys.stderr)
        for z in TARGET_ZIPS:
            print(f"  - {z}", file=sys.stderr)
        return
    
    # Scrape or load existing
    all_file = DATA_DIR / f"all_listings_{date_str}.csv"
    
    if skip_scrape and all_file.exists():
        print(f"\nSkipping scrape, loading existing {all_file.name}...", file=sys.stderr)
        with open(all_file, encoding="utf-8") as f:
            all_listings = list(csv.DictReader(f))
    else:
        all_listings = scrape_all_zips(delay=delay)
    
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"PROCESSING {len(all_listings)} LISTINGS", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    
    # Identify new listings (check both MLS number and URL)
    new_listings = []
    for listing in all_listings:
        mls = listing.get("mls_number", "").strip()
        url = listing.get("redfin_url", "").strip()
        
        is_new = True
        if mls and f"mls:{mls}" in previous_mls:
            is_new = False
        if url and f"url:{url}" in previous_mls:
            is_new = False
        
        if is_new:
            new_listings.append(listing)
    
    print(f"  New listings (not in yesterday's data): {len(new_listings)}", file=sys.stderr)
    
    # Enrich all listings with DRE data
    print(f"  Enriching with DRE data...", file=sys.stderr)
    enriched_all = [enrich_with_dre(l, dre_lookup) for l in all_listings]
    enriched_new = [enrich_with_dre(l, dre_lookup) for l in new_listings]
    
    # Write full snapshot (for tomorrow's diff)
    print(f"\nWriting {len(enriched_all)} listings to {all_file.name}...", file=sys.stderr)
    if enriched_all:
        with open(all_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=enriched_all[0].keys())
            writer.writeheader()
            writer.writerows(enriched_all)
    
    # Write new listings (for outreach)
    new_file = DATA_DIR / f"new_listings_{date_str}.csv"
    print(f"Writing {len(enriched_new)} NEW listings to {new_file.name}...", file=sys.stderr)
    if enriched_new:
        # Reorder columns for outreach-friendly format
        outreach_columns = [
            "address", "city", "zipcode", "price", "listing_date",
            "beds", "baths", "sqft", "property_type", "year_built",
            "agent_full_name", "agent_dre", "agent_phone", "agent_license_type",
            "brokerage", "supervising_broker_name", "supervising_broker_dre",
            "agent_business_address", "agent_business_city", "agent_business_zip",
            "mls_number", "days_on_market", "redfin_url",
        ]
        
        with open(new_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=outreach_columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(enriched_new)
    else:
        # Write empty file with headers
        with open(new_file, "w", newline="", encoding="utf-8") as f:
            f.write("address,city,zipcode,price,listing_date,beds,baths,sqft,property_type,year_built,"
                   "agent_full_name,agent_dre,agent_phone,agent_license_type,brokerage,"
                   "supervising_broker_name,supervising_broker_dre,"
                   "agent_business_address,agent_business_city,agent_business_zip,"
                   "mls_number,days_on_market,redfin_url\n")
    
    # Print summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"SUMMARY", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"  Total listings scraped: {len(all_listings)}", file=sys.stderr)
    print(f"  New listings today:     {len(new_listings)}", file=sys.stderr)
    print(f"  With DRE match:         {sum(1 for l in enriched_new if l.get('agent_full_name'))}", file=sys.stderr)
    print(f"\n  Output files:", file=sys.stderr)
    print(f"    {all_file}", file=sys.stderr)
    print(f"    {new_file}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
    
    return enriched_new


def main():
    parser = argparse.ArgumentParser(
        description="Daily listing pipeline - scrape, diff, enrich, output"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually scraping"
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip scraping, just process existing today's file"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between requests in seconds (default: 2.0)"
    )
    
    args = parser.parse_args()
    
    new_listings = run_pipeline(
        dry_run=args.dry_run,
        skip_scrape=args.skip_scrape,
        delay=args.delay
    )
    
    # Print new listings to stdout for piping
    if new_listings and not args.dry_run:
        print("\n=== NEW LISTINGS FOR OUTREACH ===\n")
        for l in new_listings[:10]:
            print(f"{l.get('address', 'N/A')}")
            print(f"  Price: {l.get('price', 'N/A')} | Listed: {l.get('listing_date', 'N/A')}")
            print(f"  Agent: {l.get('agent_full_name', 'N/A')} ({l.get('agent_license_type', '')})")
            print(f"  Phone: {l.get('agent_phone', 'N/A')}")
            print(f"  DRE #: {l.get('agent_dre', 'N/A')}")
            print()
        
        if len(new_listings) > 10:
            print(f"... and {len(new_listings) - 10} more (see CSV file)")


if __name__ == "__main__":
    main()
