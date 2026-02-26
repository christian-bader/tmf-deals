"""
Enrich listings with San Diego County parcel data.

Takes listings CSV with addresses, geocodes them, finds matching parcels,
and outputs enriched CSV with APN (linking key to shapes) and parcel details.

Usage:
    # Single address lookup
    python scripts/geopoints/enrich_listings_with_parcels.py --address "1547 Caminito Solidago, La Jolla, CA 92037"

    # Enrich listings file
    python scripts/geopoints/enrich_listings_with_parcels.py --input data/listings/daily/all_listings_2026-02-25.csv

    # Dry run (show what would be processed)
    python scripts/geopoints/enrich_listings_with_parcels.py --input data/listings/daily/all_listings_2026-02-25.csv --dry-run
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ENV_FILE = ".env"

SD_PARCELS_URL = (
    "https://gis-public.sandiegocounty.gov/arcgis/rest/services/"
    "sdep_warehouse/PARCELS_ALL/FeatureServer/0/query"
)

GOOGLE_GEO_URL = "https://maps.googleapis.com/maps/api/geocode/json"

SD_ZIPS = {
    "92037", "92014", "92075", "92024", "92007",
    "92118", "92106", "92107", "92109",
    "92011", "92008", "92130", "92127", "92029",
}


def load_api_key():
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                if line.startswith("GOOGLE_GEOCODING_API_KEY="):
                    return line.strip().split("=", 1)[1]
    key = os.environ.get("GOOGLE_GEOCODING_API_KEY")
    if key:
        return key
    raise RuntimeError("GOOGLE_GEOCODING_API_KEY not found in .env or environment")


def fetch_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "ListingEnricher/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def geocode_address(address, api_key):
    params = urllib.parse.urlencode({"address": address, "key": api_key})
    data = fetch_json(f"{GOOGLE_GEO_URL}?{params}")
    if data.get("status") != "OK" or not data.get("results"):
        return None, None
    loc = data["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def score_address_match(parcel_attrs, input_address):
    input_upper = input_address.upper()
    input_parts = set(input_upper.replace(",", " ").split())

    situs_num = str(parcel_attrs.get("SITUS_ADDRESS", "")).strip()
    situs_street = (parcel_attrs.get("SITUS_STREET") or "").strip().upper()
    situs_suffix = (parcel_attrs.get("SITUS_SUFFIX") or "").strip().upper()

    score = 0
    if situs_num and situs_num in input_parts:
        score += 10
    for word in situs_street.split():
        if word in input_parts:
            score += 5
    if situs_suffix and situs_suffix in input_parts:
        score += 2
    return score


def find_parcel(lat, lon, input_address=""):
    buf = 0.0003
    envelope = f"{lon - buf},{lat - buf},{lon + buf},{lat + buf}"
    params = urllib.parse.urlencode({
        "geometry": envelope,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    })
    url = f"{SD_PARCELS_URL}?{params}"

    try:
        data = fetch_json(url)
    except Exception as e:
        print(f"  Parcel query error: {e}", file=sys.stderr)
        return None

    features = data.get("features", [])
    if not features:
        return None

    if len(features) == 1 or not input_address:
        return {k: v for k, v in features[0]["attributes"].items() if v is not None}

    scored = []
    for feat in features:
        attrs = feat["attributes"]
        s = score_address_match(attrs, input_address)
        scored.append((s, attrs))

    scored.sort(key=lambda x: x[0], reverse=True)
    return {k: v for k, v in scored[0][1].items() if v is not None}


def lookup_single(address, api_key, verbose=True):
    if verbose:
        print(f"Address: {address}")
    
    lat, lon = geocode_address(address, api_key)
    if not lat:
        if verbose:
            print("  Failed to geocode")
        return None

    if verbose:
        print(f"  Coords: {lat}, {lon}")

    parcel = find_parcel(lat, lon, input_address=address)
    if not parcel:
        if verbose:
            print("  No parcel found")
        return None

    if verbose:
        situs = " ".join(filter(None, [
            str(parcel.get("SITUS_ADDRESS", "")),
            parcel.get("SITUS_PRE_DIR", ""),
            parcel.get("SITUS_STREET", ""),
            parcel.get("SITUS_SUFFIX", ""),
        ])).strip()
        print(f"  Parcel APN: {parcel.get('APN')}")
        print(f"  Situs: {situs}, {parcel.get('SITUS_COMMUNITY', '')} {parcel.get('SITUS_ZIP', '').strip()[:5]}")
        print(f"  Owner: {parcel.get('OWN_NAME1')}")
        print(f"  Assessed: ${parcel.get('ASR_TOTAL', 0):,}")

    return {
        "latitude": lat,
        "longitude": lon,
        "parcel_apn": parcel.get("APN"),
        "parcel_apn_8": parcel.get("APN_8"),
        "parcel_owner": parcel.get("OWN_NAME1"),
        "parcel_assessed_total": parcel.get("ASR_TOTAL"),
        "parcel_assessed_land": parcel.get("ASR_LAND"),
        "parcel_assessed_impr": parcel.get("ASR_IMPR"),
        "parcel_sqft_living": parcel.get("TOTAL_LVG_AREA"),
        "parcel_acreage": parcel.get("ACREAGE"),
        "parcel_beds": parcel.get("BEDROOMS"),
        "parcel_baths": parcel.get("BATHS"),
        "parcel_community": parcel.get("SITUS_COMMUNITY"),
        "parcel_zip": (parcel.get("SITUS_ZIP") or "").strip()[:5],
    }


PARCEL_COLS = [
    "latitude", "longitude",
    "parcel_apn", "parcel_apn_8", "parcel_owner",
    "parcel_assessed_total", "parcel_assessed_land", "parcel_assessed_impr",
    "parcel_sqft_living", "parcel_acreage", "parcel_beds", "parcel_baths",
    "parcel_community", "parcel_zip",
]


def enrich_listings(input_path, output_path=None, dry_run=False, limit=None):
    api_key = load_api_key()

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        old_fields = list(reader.fieldnames)
        rows = list(reader)

    new_fields = old_fields + [c for c in PARCEL_COLS if c not in old_fields]

    sd_rows = [r for r in rows if r.get("zipcode", "").strip()[:5] in SD_ZIPS]
    non_sd_rows = [r for r in rows if r.get("zipcode", "").strip()[:5] not in SD_ZIPS]

    print(f"Total listings: {len(rows)}")
    print(f"San Diego zips: {len(sd_rows)}")
    print(f"Non-SD zips (skipped): {len(non_sd_rows)}")

    if dry_run:
        print("\n[DRY RUN] Would process:")
        for r in sd_rows[:10]:
            print(f"  {r.get('address', '?')}")
        if len(sd_rows) > 10:
            print(f"  ... and {len(sd_rows) - 10} more")
        return

    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_with_parcels{ext}"

    matched = 0
    failed = 0
    process_rows = sd_rows[:limit] if limit else sd_rows

    print(f"\nProcessing {len(process_rows)} San Diego listings...")

    for i, row in enumerate(process_rows):
        address = row.get("address", "")
        if not address:
            for c in PARCEL_COLS:
                row[c] = ""
            failed += 1
            continue

        print(f"[{i+1}/{len(process_rows)}] {address[:60]}...")

        result = lookup_single(address, api_key, verbose=False)

        if result and result.get("parcel_apn"):
            for k, v in result.items():
                row[k] = v if v is not None else ""
            matched += 1
            print(f"  -> APN: {result['parcel_apn']}")
        else:
            for c in PARCEL_COLS:
                row[c] = ""
            failed += 1
            print(f"  -> no match")

        time.sleep(0.1)

    for row in non_sd_rows:
        for c in PARCEL_COLS:
            row[c] = ""

    all_rows = process_rows + (sd_rows[limit:] if limit else []) + non_sd_rows

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=new_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDone: {matched} matched, {failed} failed")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich listings with SD parcel data")
    parser.add_argument("--address", type=str, help="Single address lookup")
    parser.add_argument("--input", "-i", type=str, help="Input listings CSV")
    parser.add_argument("--output", "-o", type=str, help="Output CSV (default: input_with_parcels.csv)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--limit", type=int, help="Limit number of rows to process")
    args = parser.parse_args()

    if args.address:
        api_key = load_api_key()
        lookup_single(args.address, api_key)
    elif args.input:
        enrich_listings(args.input, args.output, args.dry_run, args.limit)
    else:
        parser.print_help()
