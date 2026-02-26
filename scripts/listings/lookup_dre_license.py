#!/usr/bin/env python3
"""
Look up California DRE (Department of Real Estate) license information.

Uses the California Department of Consumer Affairs (DCA) public API.
API Docs: https://iservices.dca.ca.gov/docs/search

Usage:
    python lookup_dre_license.py --license 01487611
    python lookup_dre_license.py --name "Shahbazi, Ghazal"
    python lookup_dre_license.py --name "Smith" --limit 10

Note: DRE license numbers are typically 8 digits, sometimes shown with leading zeros.
"""

import argparse
import json
import requests
from typing import Optional


DCA_API_BASE = "https://iservices.dca.ca.gov/api/search/v1"

# DRE board codes in the DCA system
DRE_BOARD_CODES = ["RE"]  # Real Estate


def search_by_license(license_number: str) -> dict:
    """Look up a specific DRE license number."""
    # Normalize license number (remove leading zeros, then pad to 8 digits)
    clean_num = license_number.lstrip("0")
    padded_num = clean_num.zfill(8)
    
    params = {
        "licenseNumber": padded_num,
        "boardCode": "RE",
    }
    
    response = requests.get(DCA_API_BASE, params=params)
    response.raise_for_status()
    return response.json()


def search_by_name(name: str, limit: int = 25) -> dict:
    """Search for DRE licensees by name."""
    params = {
        "name": name,
        "boardCode": "RE",
        "top": limit,
    }
    
    response = requests.get(DCA_API_BASE, params=params)
    response.raise_for_status()
    return response.json()


def format_license_info(record: dict) -> str:
    """Format a single license record for display."""
    lines = []
    
    name = record.get("name", "Unknown")
    lic_num = record.get("licenseNumber", "")
    lic_type = record.get("licenseType", "")
    status = record.get("licenseStatus", "")
    issue_date = record.get("issueDate", "")
    exp_date = record.get("expirationDate", "")
    address = record.get("address", {})
    
    lines.append(f"Name: {name}")
    lines.append(f"DRE #: {lic_num}")
    lines.append(f"Type: {lic_type}")
    lines.append(f"Status: {status}")
    lines.append(f"Issued: {issue_date}")
    lines.append(f"Expires: {exp_date}")
    
    if address:
        city = address.get("city", "")
        state = address.get("state", "")
        zip_code = address.get("zip", "")
        if city or state:
            lines.append(f"Location: {city}, {state} {zip_code}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Look up California DRE license information"
    )
    parser.add_argument(
        "--license", "-l",
        help="DRE license number to look up (e.g., 01487611)"
    )
    parser.add_argument(
        "--name", "-n",
        help="Name to search for (e.g., 'Smith, John' or just 'Smith')"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Max results for name search (default: 25)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON"
    )
    
    args = parser.parse_args()
    
    if not args.license and not args.name:
        parser.error("Must specify either --license or --name")
    
    try:
        if args.license:
            print(f"Looking up DRE #{args.license}...")
            result = search_by_license(args.license)
        else:
            print(f"Searching for '{args.name}'...")
            result = search_by_name(args.name, args.limit)
        
        if args.json:
            print(json.dumps(result, indent=2))
            return
        
        records = result.get("results", [])
        
        if not records:
            print("No records found.")
            return
        
        print(f"\nFound {len(records)} record(s):\n")
        print("=" * 50)
        
        for i, record in enumerate(records, 1):
            if i > 1:
                print("-" * 50)
            print(format_license_info(record))
        
        print("=" * 50)
        
    except requests.RequestException as e:
        print(f"API Error: {e}")
        raise


if __name__ == "__main__":
    main()
