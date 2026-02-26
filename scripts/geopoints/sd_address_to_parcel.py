"""
SD County Address/Coordinates-to-Parcel Pipeline

Primary mode: coordinates → parcel + census hierarchy
Fallback mode: address string → Google geocode → coordinates → parcel + census

Usage:
    # From coordinates (preferred — no ambiguity)
    python scripts/geopoints/sd_address_to_parcel.py --lat 32.857467 --lon -117.254313

    # From address (convenience — uses Google geocoding)
    python scripts/geopoints/sd_address_to_parcel.py --address "2260 Calle Frescota La Jolla"

    # Batch: enrich deals_rows.csv with parcel data
    python scripts/geopoints/sd_address_to_parcel.py --batch
"""

import csv
import json
import os
import sys
import time
import urllib.request
import urllib.parse

# --- Config ---

ENV_FILE = ".env"
DEALS_FILE = "data/tmf/deals_rows.csv"

SD_PARCELS_URL = (
    "https://gis-public.sandiegocounty.gov/arcgis/rest/services/"
    "sdep_warehouse/PARCELS_ALL/FeatureServer/0/query"
)

CENSUS_GEO_URL = (
    "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
)

GOOGLE_GEO_URL = "https://maps.googleapis.com/maps/api/geocode/json"

SD_COUNTY_FIPS = "06073"


def load_api_key():
    with open(ENV_FILE) as f:
        for line in f:
            if line.startswith("GOOGLE_GEOCODING_API_KEY="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("GOOGLE_GEOCODING_API_KEY not found in .env")


def fetch_json(url, timeout=15):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# --- Geocode (fallback for address-only input) ---

def geocode_address(address, api_key):
    params = urllib.parse.urlencode({"address": address, "key": api_key})
    data = fetch_json(f"{GOOGLE_GEO_URL}?{params}")
    if data.get("status") != "OK" or not data.get("results"):
        return None, None
    loc = data["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


# --- Parcel lookup (spatial query with buffer + address ranking) ---

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
    url = (
        f"{SD_PARCELS_URL}"
        f"?geometry={envelope}"
        f"&geometryType=esriGeometryEnvelope"
        f"&inSR=4326"
        f"&spatialRel=esriSpatialRelIntersects"
        f"&outFields=*"
        f"&returnGeometry=false"
        f"&f=json"
    )
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


# --- Census hierarchy ---

def get_census_hierarchy(lat, lon):
    params = urllib.parse.urlencode({
        "x": lon, "y": lat,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    })
    try:
        data = fetch_json(f"{CENSUS_GEO_URL}?{params}")
    except Exception as e:
        print(f"  Census query error: {e}", file=sys.stderr)
        return {}

    geos = data.get("result", {}).get("geographies", {})
    state = (geos.get("States") or [{}])[0]
    county = (geos.get("Counties") or [{}])[0]
    place = (geos.get("Incorporated Places") or geos.get("Census Designated Places") or [{}])[0]
    tract = (geos.get("Census Tracts") or [{}])[0]

    return {
        "census_state_fips": state.get("STATE", ""),
        "census_state_name": state.get("NAME", ""),
        "census_county_fips": county.get("COUNTY", ""),
        "census_county_geoid": county.get("GEOID", ""),
        "census_county_name": county.get("NAME", ""),
        "census_place_geoid": place.get("GEOID", ""),
        "census_place_name": place.get("NAME", ""),
        "census_place_classfp": place.get("CLASSFP", ""),
        "census_tract_geoid": tract.get("GEOID", ""),
    }


# --- Single address/coordinate lookup ---

def resolve(lat, lon, address="", verbose=True):
    parcel = find_parcel(lat, lon, input_address=address)
    if verbose and parcel:
        situs = " ".join(filter(None, [
            str(parcel.get("SITUS_ADDRESS", "")),
            parcel.get("SITUS_PRE_DIR", ""),
            parcel.get("SITUS_STREET", ""),
            parcel.get("SITUS_SUFFIX", ""),
        ])).strip()
        print(f"  Parcel:  APN={parcel.get('APN')}  Owner={parcel.get('OWN_NAME1')}")
        print(f"  Situs:   {situs}, {parcel.get('SITUS_COMMUNITY', '')} {parcel.get('SITUS_ZIP', '')}")
        print(f"  Value:   ${parcel.get('ASR_TOTAL', 0):,}")
    elif verbose:
        print("  No parcel found")

    hierarchy = get_census_hierarchy(lat, lon)
    if verbose and hierarchy:
        print(f"  Census:  {hierarchy.get('census_place_name', '?')} / {hierarchy.get('census_county_name', '?')} / {hierarchy.get('census_state_name', '?')}")
        print(f"  Tract:   {hierarchy.get('census_tract_geoid', '?')}")

    return {**(parcel or {}), **hierarchy}


# --- Batch: enrich deals_rows.csv ---

PARCEL_OUTPUT_COLS = [
    "parcel_apn", "parcel_owner", "parcel_assessed_total",
    "parcel_assessed_land", "parcel_assessed_impr",
    "parcel_sqft_living", "parcel_sqft_lot", "parcel_beds", "parcel_baths",
    "parcel_community", "parcel_zip",
]


def batch_enrich():
    with open(DEALS_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        old_fields = reader.fieldnames
        deals = list(reader)

    new_fields = old_fields + [c for c in PARCEL_OUTPUT_COLS if c not in old_fields]

    total = len(deals)
    matched = 0
    skipped = 0

    for i, deal in enumerate(deals):
        lat = deal.get("latitude", "").strip()
        lon = deal.get("longitude", "").strip()
        county = deal.get("county_geoid", "").strip()

        if not lat or not lon:
            skipped += 1
            for c in PARCEL_OUTPUT_COLS:
                deal[c] = ""
            continue

        if county and county != SD_COUNTY_FIPS:
            skipped += 1
            for c in PARCEL_OUTPUT_COLS:
                deal[c] = ""
            continue

        print(f"[{i+1}/{total}] {deal.get('display_name', deal.get('address', '?'))}")
        result = resolve(float(lat), float(lon), address=deal.get("address", ""), verbose=False)

        if result.get("APN"):
            deal["parcel_apn"] = result.get("APN", "")
            deal["parcel_owner"] = result.get("OWN_NAME1", "")
            deal["parcel_assessed_total"] = result.get("ASR_TOTAL", "")
            deal["parcel_assessed_land"] = result.get("ASR_LAND", "")
            deal["parcel_assessed_impr"] = result.get("ASR_IMPR", "")
            deal["parcel_sqft_living"] = result.get("TOTAL_LVG_AREA", "")
            deal["parcel_sqft_lot"] = result.get("USABLE_SQ_FEET", "")
            deal["parcel_beds"] = result.get("BEDROOMS", "")
            deal["parcel_baths"] = result.get("BATHS", "")
            deal["parcel_community"] = result.get("SITUS_COMMUNITY", "")
            deal["parcel_zip"] = (result.get("SITUS_ZIP") or "").strip()[:5]
            matched += 1
            print(f"  -> APN {deal['parcel_apn']}  Owner: {deal['parcel_owner']}")
        else:
            for c in PARCEL_OUTPUT_COLS:
                deal[c] = ""
            print(f"  -> no parcel")

        time.sleep(0.3)

    output_path = DEALS_FILE.replace(".csv", "_with_parcels.csv")
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=new_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(deals)

    print(f"\nDone: {matched} parcel matches, {skipped} skipped (non-SD or no coords)")
    print(f"Output: {output_path}")


# --- CLI ---

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SD County address/coords to parcel + census")
    parser.add_argument("--lat", type=float, help="Latitude")
    parser.add_argument("--lon", type=float, help="Longitude")
    parser.add_argument("--address", type=str, help="Address string (uses Google geocoding)")
    parser.add_argument("--batch", action="store_true", help="Enrich deals_rows.csv with parcel data")
    args = parser.parse_args()

    if args.batch:
        batch_enrich()
    elif args.lat and args.lon:
        print(f"Coordinates: {args.lat}, {args.lon}")
        result = resolve(args.lat, args.lon, address=args.address or "")
    elif args.address:
        api_key = load_api_key()
        print(f"Geocoding: {args.address}")
        lat, lon = geocode_address(args.address, api_key)
        if lat:
            print(f"Coords: {lat}, {lon}")
            result = resolve(lat, lon, address=args.address)
        else:
            print("Failed to geocode")
    else:
        parser.print_help()
