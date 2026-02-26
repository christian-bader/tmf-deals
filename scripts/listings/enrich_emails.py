#!/usr/bin/env python3
"""
Enrich missing agent emails using brokerage email patterns.

For agents at known brokerages without emails, infers email using common patterns:
- firstname.lastname@brokerage.com
- firstname@brokerage.com
- firstnamelastname@brokerage.com

Usage:
    python enrich_emails.py data/listings/daily/all_listings_2026-02-25.csv
"""

import argparse
import csv
import re
from pathlib import Path


# Known brokerage domains and their email patterns
# Pattern tokens: {first}, {last}, {firstlast}, {first.last}, {flast}
BROKERAGE_PATTERNS = {
    # Major brokerages
    "compass": ("compass.com", "{first.last}"),
    "berkshire hathaway": ("bhhscal.com", "{first.last}"),
    "coldwell banker": ("cbcal.com", "{first.last}"),
    "keller williams": ("kw.com", "{first.last}"),
    "sotheby": ("sothebysrealty.com", "{first.last}"),
    "pacific sotheby": ("pacificsir.com", "{first.last}"),
    "willis allen": ("willisallen.com", "{first.last}"),
    "douglas elliman": ("elliman.com", "{first.last}"),
    "exp realty": ("exprealty.com", "{first.last}"),
    "re/max": ("remax.net", "{first.last}"),
    "century 21": ("century21.com", "{first.last}"),
    "real broker": ("realbroker.com", "{first.last}"),
    "barry estates": ("barryestates.com", "{first}"),
    
    # Regional/boutique
    "windermere": ("windermere.com", "{first.last}"),
    "first team": ("firstteam.com", "{first.last}"),
    "seven gables": ("sevengables.com", "{first.last}"),
}


def normalize_brokerage(brokerage: str) -> str:
    """Normalize brokerage name for matching."""
    if not brokerage:
        return ""
    return re.sub(r'[^a-z0-9\s]', '', brokerage.lower()).strip()


def extract_name_parts(full_name: str) -> tuple[str, str]:
    """Extract first and last name from full name."""
    if not full_name:
        return "", ""
    parts = full_name.strip().split()
    if len(parts) >= 2:
        first = parts[0].lower()
        last = parts[-1].lower()
        # Remove common suffixes
        if last in ("jr", "sr", "ii", "iii", "iv"):
            last = parts[-2].lower() if len(parts) > 2 else ""
        return first, last
    elif len(parts) == 1:
        return parts[0].lower(), ""
    return "", ""


def generate_email(first: str, last: str, domain: str, pattern: str) -> str:
    """Generate email from name parts using pattern."""
    if not first or not domain:
        return ""
    
    # Clean name parts (remove non-alpha chars)
    first = re.sub(r'[^a-z]', '', first)
    last = re.sub(r'[^a-z]', '', last)
    
    if not first:
        return ""
    
    # Replace pattern tokens
    email_user = pattern
    email_user = email_user.replace("{first.last}", f"{first}.{last}" if last else first)
    email_user = email_user.replace("{first}", first)
    email_user = email_user.replace("{last}", last)
    email_user = email_user.replace("{firstlast}", f"{first}{last}")
    email_user = email_user.replace("{flast}", f"{first[0]}{last}" if last else first)
    
    return f"{email_user}@{domain}"


def find_brokerage_match(brokerage: str) -> tuple[str, str] | None:
    """Find matching brokerage pattern."""
    norm = normalize_brokerage(brokerage)
    for key, (domain, pattern) in BROKERAGE_PATTERNS.items():
        if key in norm:
            return domain, pattern
    return None


def enrich_emails(input_path: Path, output_path: Path = None) -> dict:
    """Enrich missing emails in CSV file."""
    if output_path is None:
        stem = input_path.stem
        output_path = input_path.parent / f"{stem}_enriched.csv"
    
    rows = []
    stats = {
        "total": 0,
        "had_email": 0,
        "enriched": 0,
        "no_match": 0,
        "no_name": 0,
    }
    
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        # Add inferred_email field if not present
        if "inferred_email" not in fieldnames:
            fieldnames = list(fieldnames) + ["inferred_email"]
        
        for row in reader:
            stats["total"] += 1
            
            # Already has email
            if row.get("agent_email"):
                stats["had_email"] += 1
                row["inferred_email"] = ""
                rows.append(row)
                continue
            
            # Try to infer email
            agent_name = row.get("listing_agent", "")
            brokerage = row.get("brokerage", "")
            
            if not agent_name:
                stats["no_name"] += 1
                row["inferred_email"] = ""
                rows.append(row)
                continue
            
            match = find_brokerage_match(brokerage)
            if not match:
                stats["no_match"] += 1
                row["inferred_email"] = ""
                rows.append(row)
                continue
            
            domain, pattern = match
            first, last = extract_name_parts(agent_name)
            
            if first:
                inferred = generate_email(first, last, domain, pattern)
                row["inferred_email"] = inferred
                stats["enriched"] += 1
            else:
                row["inferred_email"] = ""
                stats["no_name"] += 1
            
            rows.append(row)
    
    # Write output
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return stats, output_path


def main():
    parser = argparse.ArgumentParser(description="Enrich missing agent emails")
    parser.add_argument("input", help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output CSV file (default: input_enriched.csv)")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None
    
    print(f"Enriching emails in {input_path}...")
    stats, output_path = enrich_emails(input_path, output_path)
    
    print(f"\nResults:")
    print(f"  Total rows: {stats['total']}")
    print(f"  Already had email: {stats['had_email']}")
    print(f"  Enriched (inferred): {stats['enriched']}")
    print(f"  No brokerage match: {stats['no_match']}")
    print(f"  No agent name: {stats['no_name']}")
    print(f"\nWrote to: {output_path}")


if __name__ == "__main__":
    main()
