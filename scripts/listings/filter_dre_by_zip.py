#!/usr/bin/env python3
"""
Filter California DRE licensee database to target zip codes.

This script takes the full DRE CurrList.csv (437K+ licensees) and filters
to only those with business addresses in your target zip codes.

Usage:
    python filter_dre_by_zip.py

Output:
    data/ca-dre/target_licensees.csv - Filtered licensee list
    data/ca-dre/brokers_by_zip.csv - Just brokers, grouped by zip

Data source:
    https://www.dre.ca.gov/Licensees/ExamineeLicenseeListDataFiles.html
    Updated daily by CA DRE
"""

import csv
from collections import defaultdict
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DRE_DATA = PROJECT_ROOT / "data" / "ca-dre"
INPUT_FILE = DRE_DATA / "CurrList.csv"
OUTPUT_ALL = DRE_DATA / "target_licensees.csv"
OUTPUT_BROKERS = DRE_DATA / "brokers_by_zip.csv"

# Target zip codes (San Diego + Orange County only)
TARGET_ZIPS = {
    # San Diego Coastal/North
    "92037",  # La Jolla
    "92014",  # Del Mar
    "92075",  # Solana Beach
    "92024",  # Encinitas
    "92007",  # Cardiff
    "92118",  # Coronado
    "92106",  # Point Loma
    "92107",  # Ocean Beach
    "92109",  # Pacific Beach / Mission Beach
    "92011",  # Carlsbad (west)
    "92008",  # Carlsbad
    "92130",  # Carmel Valley
    "92127",  # Rancho Bernardo (east)
    "92029",  # Escondido (south)
    # Orange County Coastal
    "92651",  # Laguna Beach
    "92629",  # Dana Point
    "92624",  # Capistrano Beach
    "92672",  # San Clemente
    "92657",  # Newport Coast
    "92625",  # Corona del Mar
    "92663",  # Newport Beach
    "92661",  # Balboa Island
    "92662",  # Balboa Peninsula
    "92648",  # Huntington Beach
    "92649",  # Huntington Beach (west)
}


def normalize_zip(zip_code: str) -> str:
    """Normalize zip code to 5 digits."""
    if not zip_code:
        return ""
    # Handle ZIP+4 format (93420-1234)
    return zip_code.strip()[:5]


def main():
    print(f"Reading {INPUT_FILE}...")
    
    all_licensees = []
    brokers_by_zip = defaultdict(list)
    stats = defaultdict(int)
    
    with open(INPUT_FILE, newline="", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            zip_code = normalize_zip(row.get("zip_code", ""))
            
            if zip_code not in TARGET_ZIPS:
                continue
            
            lic_type = row.get("lic_type", "")
            stats[lic_type] += 1
            stats["total"] += 1
            stats[f"zip_{zip_code}"] += 1
            
            all_licensees.append(row)
            
            # Track brokers separately (they're the decision makers)
            if lic_type == "Broker":
                brokers_by_zip[zip_code].append({
                    "name": f"{row.get('firstname_secondary', '')} {row.get('lastname_primary', '')}".strip(),
                    "dre_number": row.get("lic_number", ""),
                    "address": row.get("address_1", ""),
                    "city": row.get("city", ""),
                    "zip": zip_code,
                    "county": row.get("county_name", ""),
                    "status": row.get("lic_status", ""),
                    "expires": row.get("lic_expiration_date", ""),
                })
    
    # Write all filtered licensees
    print(f"\nWriting {len(all_licensees)} licensees to {OUTPUT_ALL}...")
    with open(OUTPUT_ALL, "w", newline="", encoding="utf-8") as f:
        if all_licensees:
            writer = csv.DictWriter(f, fieldnames=all_licensees[0].keys())
            writer.writeheader()
            writer.writerows(all_licensees)
    
    # Write brokers summary
    broker_rows = []
    for zip_code in sorted(brokers_by_zip.keys()):
        broker_rows.extend(brokers_by_zip[zip_code])
    
    print(f"Writing {len(broker_rows)} brokers to {OUTPUT_BROKERS}...")
    with open(OUTPUT_BROKERS, "w", newline="", encoding="utf-8") as f:
        if broker_rows:
            writer = csv.DictWriter(f, fieldnames=broker_rows[0].keys())
            writer.writeheader()
            writer.writerows(broker_rows)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total licensees in target zips: {stats['total']:,}")
    print(f"  - Brokers: {stats.get('Broker', 0):,}")
    print(f"  - Salespersons: {stats.get('Salesperson', 0):,}")
    print(f"  - Corporations: {stats.get('Corporation', 0):,}")
    
    print("\nBy zip code:")
    for zip_code in sorted(TARGET_ZIPS):
        count = stats.get(f"zip_{zip_code}", 0)
        if count > 0:
            print(f"  {zip_code}: {count:,} licensees")
    
    print("\n" + "=" * 60)
    print(f"Output files:")
    print(f"  {OUTPUT_ALL}")
    print(f"  {OUTPUT_BROKERS}")


if __name__ == "__main__":
    main()
