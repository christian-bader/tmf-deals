#!/usr/bin/env python3
"""
Extract a clean demo dataset from scraped listings.

Filters to only include listings with:
- Valid agent name (not empty, not Redfin corporate)
- Valid DRE number (not 01521930 which is Redfin Corp)
- Valid email address
- Matching DRE-to-name (agent name appears in email or vice versa for confidence)

Usage:
    python extract_clean_demo.py --limit 100
    python extract_clean_demo.py --limit 100 --status active
"""

import argparse
import csv
import re
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "listings" / "daily"
OUTPUT_DIR = PROJECT_ROOT / "data" / "listings" / "demo"

# Redfin corporate DRE - skip these
REDFIN_CORPORATE_DRE = "01521930"


def is_clean_listing(row: dict) -> tuple[bool, str]:
    """
    Check if a listing has clean, trustworthy agent data.
    Returns (is_clean, reason_if_not_clean).
    """
    agent = row.get("listing_agent", "").strip()
    dre = row.get("agent_dre", "").strip()
    email = row.get("agent_email", "").strip()
    
    # Must have agent name
    if not agent:
        return False, "no_agent_name"
    
    # Must have DRE
    if not dre:
        return False, "no_dre"
    
    # Skip Redfin corporate listings
    if dre == REDFIN_CORPORATE_DRE:
        return False, "redfin_corporate"
    
    # Must have email
    if not email:
        return False, "no_email"
    
    # Confidence check: agent name should relate to email
    # Extract name parts for matching
    agent_parts = agent.lower().replace("'", "").replace("-", "").split()
    email_prefix = email.split("@")[0].lower()
    
    # Check if any part of agent name appears in email
    name_in_email = any(part in email_prefix for part in agent_parts if len(part) > 2)
    
    # Also check reverse - common email patterns
    # e.g., "jsmith" for "John Smith", "john.smith", etc.
    first_initial = agent_parts[0][0] if agent_parts else ""
    last_name = agent_parts[-1] if len(agent_parts) > 1 else ""
    
    email_matches_pattern = (
        name_in_email or
        f"{first_initial}{last_name}" in email_prefix or
        email_prefix.startswith(agent_parts[0][:3]) if agent_parts else False
    )
    
    if not email_matches_pattern:
        # Still allow if email looks professional (has @ known brokerage)
        known_brokerages = ["compass", "remax", "coldwellbanker", "kw", "century21", 
                           "sothebys", "berkshire", "elliman", "exp", "realty"]
        domain = email.split("@")[1].lower() if "@" in email else ""
        is_professional = any(b in domain for b in known_brokerages)
        
        if not is_professional:
            return False, "email_name_mismatch"
    
    return True, "clean"


def extract_clean_demo(
    limit_per_status: int = 100,
    status_filter: str = None
) -> dict:
    """
    Extract clean demo listings from all CSV files.
    Returns stats about the extraction.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    stats = {
        "total_processed": 0,
        "clean_found": 0,
        "by_status": defaultdict(int),
        "rejection_reasons": defaultdict(int),
    }
    
    # Find all listing CSVs (not enriched versions)
    csv_files = list(DATA_DIR.glob("*.csv"))
    csv_files = [f for f in csv_files if "_enriched" not in f.name]
    
    if not csv_files:
        print(f"No CSV files found in {DATA_DIR}")
        return stats
    
    # Collect all listings
    all_listings = []
    for csv_file in csv_files:
        print(f"Reading {csv_file.name}...")
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["_source_file"] = csv_file.name
                all_listings.append(row)
    
    print(f"Total listings loaded: {len(all_listings)}")
    
    # Group by status
    by_status = defaultdict(list)
    for row in all_listings:
        status = row.get("listing_status", "").lower()
        source_file = row.get("_source_file", "")
        
        # Normalize status
        # If from recently_sold.csv, it's a sold listing
        if "sold" in source_file.lower():
            status = "sold"
        elif "sold" in status or "closed" in status:
            status = "sold"
        elif "pending" in status or "under contract" in status:
            status = "pending"
        elif "active" in status or "for sale" in status:
            status = "active"
        elif not status:
            status = "unknown"
        else:
            status = "other"
        by_status[status].append(row)
    
    print(f"By status: {dict((k, len(v)) for k, v in by_status.items())}")
    
    # Filter and extract clean listings
    clean_listings = defaultdict(list)
    
    for status, listings in by_status.items():
        if status_filter and status != status_filter:
            continue
        
        for row in listings:
            stats["total_processed"] += 1
            
            is_clean, reason = is_clean_listing(row)
            
            if is_clean:
                if len(clean_listings[status]) < limit_per_status:
                    clean_listings[status].append(row)
                    stats["clean_found"] += 1
                    stats["by_status"][status] += 1
            else:
                stats["rejection_reasons"][reason] += 1
    
    # Write clean listings to output files
    for status, listings in clean_listings.items():
        if not listings:
            continue
        
        output_file = OUTPUT_DIR / f"demo_{status}.csv"
        
        # Get fieldnames from first row, excluding internal fields
        fieldnames = [k for k in listings[0].keys() if not k.startswith("_")]
        
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in listings:
                # Remove internal fields
                clean_row = {k: v for k, v in row.items() if not k.startswith("_")}
                writer.writerow(clean_row)
        
        print(f"Wrote {len(listings)} {status} listings to {output_file.name}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Extract clean demo listings")
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max listings per status category (default: 100)"
    )
    parser.add_argument(
        "--status", type=str, default=None,
        choices=["active", "pending", "sold", "other", "unknown"],
        help="Only extract listings with this status"
    )
    args = parser.parse_args()
    
    print(f"Extracting clean demo dataset (limit={args.limit} per status)...")
    print()
    
    stats = extract_clean_demo(
        limit_per_status=args.limit,
        status_filter=args.status
    )
    
    print()
    print("=== Extraction Summary ===")
    print(f"Total processed: {stats['total_processed']}")
    print(f"Clean listings found: {stats['clean_found']}")
    print(f"By status: {dict(stats['by_status'])}")
    print()
    print("Rejection reasons:")
    for reason, count in sorted(stats["rejection_reasons"].items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")
    print()
    print(f"Clean demo files written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
