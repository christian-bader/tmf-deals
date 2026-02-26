#!/usr/bin/env python3
"""
Fetch all properties from ATTOM API for a given zip code using pagination.
"""
import os
import sys
import requests
import json
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

def log(msg):
    """Print timestamped log message and flush immediately."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def fetch_properties_by_zip(postal_code: str, page_size: int = 100):
    """Fetch all properties in a zip code using pagination."""
    all_properties = []
    page = 1
    total_fetched = 0
    start_time = time.time()
    
    log(f"Starting property fetch for ZIP: {postal_code}")
    log(f"API Base URL: {BASE_URL}")
    log(f"Page size: {page_size}")
    log("-" * 60)
    
    while True:
        url = f"{BASE_URL}/property/address"
        params = {
            "postalCode": postal_code,
            "page": page,
            "pageSize": page_size
        }
        
        log(f"PAGE {page}: Requesting {url}?postalCode={postal_code}&page={page}&pageSize={page_size}")
        
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            log(f"ERROR: Request failed - {e}")
            break
        
        log(f"PAGE {page}: Response status: {response.status_code}")
        
        if response.status_code != 200:
            log(f"ERROR: API returned {response.status_code}")
            log(f"Response: {response.text[:500]}")
            break
        
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            log(f"ERROR: Failed to parse JSON - {e}")
            break
        
        # Check if we have properties
        if "property" not in data:
            log("INFO: No 'property' key in response - end of data")
            if "status" in data:
                log(f"Status: {data['status']}")
            break
            
        properties = data.get("property", [])
        if not properties:
            log("INFO: Empty property list - end of data")
            break
        
        all_properties.extend(properties)
        total_fetched += len(properties)
        
        # Get pagination info from status
        status = data.get("status", {})
        total = status.get("total", 0)
        
        elapsed = time.time() - start_time
        rate = total_fetched / elapsed if elapsed > 0 else 0
        
        log(f"PAGE {page}: Retrieved {len(properties)} properties")
        log(f"         Progress: {total_fetched}/{total} ({100*total_fetched/total:.1f}%)")
        log(f"         Rate: {rate:.1f} properties/sec | Elapsed: {elapsed:.1f}s")
        
        # Check if we've fetched all
        if total_fetched >= total or len(properties) < page_size:
            log("-" * 60)
            log(f"COMPLETE: Fetched all {total_fetched} properties in {elapsed:.1f} seconds")
            break
        
        page += 1
        log(f"         Sleeping 0.5s before next request...")
        time.sleep(0.5)  # Rate limiting
    
    return all_properties

def find_property_by_address(properties: list, street_search: str):
    """Search for a property by partial street address."""
    matches = []
    search_lower = street_search.lower()
    
    for prop in properties:
        address = prop.get("address", {})
        line1 = address.get("line1", "").lower()
        oneline = address.get("oneLine", "").lower()
        
        if search_lower in line1 or search_lower in oneline:
            matches.append(prop)
    
    return matches

def main():
    postal_code = "92037"
    
    log("=" * 60)
    log("ATTOM PROPERTY FETCHER")
    log("=" * 60)
    log(f"Target ZIP code: {postal_code}")
    log(f"API Key: {API_KEY[:8]}...{API_KEY[-4:] if API_KEY else 'NOT SET'}")
    log("")
    
    if not API_KEY:
        log("ERROR: ATTOM_API_KEY not found in environment!")
        sys.exit(1)
    
    properties = fetch_properties_by_zip(postal_code)
    
    log("")
    log("=" * 60)
    log(f"RESULTS: Total properties retrieved: {len(properties)}")
    log("=" * 60)
    
    # Save all properties to JSON for reference
    output_file = f"attom_properties_{postal_code}.json"
    log(f"Saving all properties to {output_file}...")
    with open(output_file, "w") as f:
        json.dump(properties, f, indent=2)
    log(f"SAVED: {output_file}")
    
    # Search for specific address
    search_address = "2260 calle frescota"
    log("")
    log("=" * 60)
    log(f"SEARCHING FOR: {search_address}")
    log("=" * 60)
    
    matches = find_property_by_address(properties, search_address)
    
    if matches:
        for match in matches:
            address = match.get("address", {})
            identifier = match.get("identifier", {})
            attom_id = identifier.get("attomId") or identifier.get("Id")
            
            log("")
            log("*** MATCH FOUND ***")
            log(f"  Address:  {address.get('oneLine', 'N/A')}")
            log(f"  ATTOM ID: {attom_id}")
            log(f"  FIPS:     {identifier.get('fips', 'N/A')}")
            log(f"  APN:      {identifier.get('apn', 'N/A')}")
    else:
        log("No exact match found. Trying broader search for 'frescota'...")
        matches = find_property_by_address(properties, "frescota")
        if matches:
            log(f"Found {len(matches)} properties matching 'frescota':")
            for match in matches:
                address = match.get("address", {})
                identifier = match.get("identifier", {})
                attom_id = identifier.get("attomId") or identifier.get("Id")
                log(f"  - {address.get('oneLine', 'N/A')} | ATTOM ID: {attom_id}")
        else:
            log("No properties found matching 'frescota'.")
            log("Listing first 10 properties as sample:")
            for i, prop in enumerate(properties[:10]):
                addr = prop.get("address", {}).get("oneLine", "N/A")
                log(f"  {i+1}. {addr}")

if __name__ == "__main__":
    main()
