#!/usr/bin/env python3
"""
Generate Redfin saved search URLs for target zip codes.

Usage:
    python generate_redfin_urls.py

This outputs URLs you can open in your browser to create saved searches.
Set each one to "Daily" email alerts.
"""

TARGET_ZIPS = {
    "San Diego Coastal/North": [
        92037,  # La Jolla
        92014,  # Del Mar
        92075,  # Solana Beach
        92024,  # Encinitas
        92007,  # Cardiff
        92118,  # Coronado
        92106,  # Point Loma
        92107,  # Ocean Beach
        92109,  # Pacific Beach / Mission Beach
        92011,  # Carlsbad (west)
        92008,  # Carlsbad
        92130,  # Carmel Valley
        92127,  # Rancho Bernardo (east)
        92029,  # Escondido (south)
    ],
    "Orange County Coastal": [
        92651,  # Laguna Beach
        92629,  # Dana Point
        92624,  # Capistrano Beach
        92672,  # San Clemente
        92657,  # Newport Coast
        92625,  # Corona del Mar
        92663,  # Newport Beach
        92661,  # Balboa Island
        92662,  # Balboa Peninsula
        92648,  # Huntington Beach
        92649,  # Huntington Beach (west)
    ],
}


def generate_redfin_url(zipcode: int, min_price: int = 1_500_000, max_price: int = 20_000_000) -> str:
    """Generate a Redfin search URL for a single zip code (active for-sale only, with price range)."""
    # Redfin URL format: min-price=X,max-price=Y (no 'include=sold' means active only)
    return f"https://www.redfin.com/zipcode/{zipcode}/filter/property-type=house+condo+townhouse,min-price={min_price},max-price={max_price}"


def generate_zillow_url(zipcode: int) -> str:
    """Generate a Zillow search URL for a single zip code."""
    return f"https://www.zillow.com/homes/{zipcode}_rb/"


def main():
    print("=" * 70)
    print("REDFIN SAVED SEARCH URLS")
    print("=" * 70)
    print("\nOpen each URL, then click 'Save Search' and set to 'Daily' alerts.\n")
    
    all_zips = []
    
    for region, zips in TARGET_ZIPS.items():
        print(f"\n### {region} ({len(zips)} zips)")
        print("-" * 50)
        for z in zips:
            url = generate_redfin_url(z)
            print(f"  {z}: {url}")
            all_zips.append(z)
    
    print("\n" + "=" * 70)
    print(f"TOTAL: {len(all_zips)} zip codes to monitor")
    print("=" * 70)
    
    # Also output as a simple list for bulk opening
    print("\n\n### BULK OPEN (copy/paste into terminal):")
    print("# macOS:")
    urls = [generate_redfin_url(z) for z in all_zips]
    # Print in batches of 5 to avoid overwhelming the browser
    for i in range(0, len(urls), 5):
        batch = urls[i:i+5]
        print(f"open {' '.join(batch)}")
    
    print("\n\n### ALTERNATIVE: Zillow URLs")
    print("-" * 50)
    for z in all_zips[:5]:
        print(f"  {z}: {generate_zillow_url(z)}")
    print(f"  ... and {len(all_zips) - 5} more")


if __name__ == "__main__":
    main()
