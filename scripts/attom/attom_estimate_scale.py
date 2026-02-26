#!/usr/bin/env python3
"""
Estimate total properties across multiple ZIP codes to understand scraping scale.
"""
import os
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ATTOM_API_KEY")
BASE_URL = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"

HEADERS = {
    "Accept": "application/json",
    "APIKey": API_KEY
}

ZIP_CODES = [
    92037, 92014, 92075, 92024, 92007, 92118, 92106, 92107, 92109, 92011,
    92008, 92130, 92127, 92029, 92651, 92629, 92624, 92672, 92657, 92625,
    92663, 92661, 92662, 92648, 92649, 90274, 90275, 90277, 90278, 90254,
    90266, 90292, 90732, 90731
]

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def get_property_count(postal_code):
    """Get total property count for a ZIP code."""
    url = f"{BASE_URL}/property/address"
    params = {
        "postalCode": postal_code,
        "page": 1,
        "pageSize": 1  # Just need count, not data
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            total = data.get("status", {}).get("total", 0)
            return total
        else:
            return f"Error: {response.status_code}"
    except Exception as e:
        return f"Error: {e}"

def main():
    log("=" * 70)
    log("ATTOM SCALE ESTIMATION")
    log("=" * 70)
    log(f"Estimating property counts for {len(ZIP_CODES)} ZIP codes...")
    log("")
    
    results = []
    total_properties = 0
    
    for i, zip_code in enumerate(ZIP_CODES, 1):
        count = get_property_count(zip_code)
        
        if isinstance(count, int):
            total_properties += count
            status = f"{count:,} properties"
            results.append((zip_code, count))
        else:
            status = count
            results.append((zip_code, 0))
        
        log(f"[{i:2}/{len(ZIP_CODES)}] ZIP {zip_code}: {status}")
        time.sleep(0.3)  # Rate limiting
    
    log("")
    log("=" * 70)
    log("SUMMARY")
    log("=" * 70)
    
    # Sort by count descending
    results.sort(key=lambda x: x[1], reverse=True)
    
    log("")
    log("Top 10 ZIP codes by property count:")
    for zip_code, count in results[:10]:
        log(f"  {zip_code}: {count:,}")
    
    log("")
    log(f"TOTAL PROPERTIES: {total_properties:,}")
    log("")
    
    # Estimate API calls and time
    # For full details: 7 endpoints per property
    endpoints_per_property = 7
    total_api_calls = total_properties * endpoints_per_property
    
    # Estimate time (assuming ~0.5 seconds per API call with rate limiting)
    seconds_per_call = 0.5
    total_seconds = total_api_calls * seconds_per_call
    total_hours = total_seconds / 3600
    
    # Plus pagination calls to get all property IDs first
    pagination_calls = total_properties / 100  # 100 per page
    
    log("ESTIMATED EFFORT:")
    log(f"  Properties to fetch:     {total_properties:,}")
    log(f"  Pagination API calls:    {int(pagination_calls):,}")
    log(f"  Detail API calls:        {total_api_calls:,} (7 endpoints x {total_properties:,})")
    log(f"  Total API calls:         {int(pagination_calls + total_api_calls):,}")
    log(f"  Estimated time:          {total_hours:.1f} hours ({total_hours/24:.1f} days)")
    log("")
    log("NOTE: ATTOM API may have rate limits or quotas that affect this estimate.")
    log("=" * 70)

if __name__ == "__main__":
    main()
