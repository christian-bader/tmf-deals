"""
Enrich non-SD County deals with parcel data via ATTOM API.

Reads deals_rows_with_parcels.csv, finds rows with empty parcel_apn,
looks them up via ATTOM's property/detail endpoint using lat/lon,
and fills in parcel fields.

Usage:
    python scripts/geopoints/attom_enrich_non_sd.py
"""

import csv
import json
import os
import sys
import time
import urllib.request
import urllib.parse

ENV_FILE = ".env"
INPUT_FILE = "data/tmf/deals_rows_with_parcels.csv"
OUTPUT_FILE = "data/tmf/deals_rows_with_parcels.csv"

ATTOM_BASE = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"


def load_env():
    keys = {}
    with open(ENV_FILE) as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                keys[k] = v
    return keys


def attom_fetch(endpoint, params, api_key):
    qs = urllib.parse.urlencode(params)
    url = f"{ATTOM_BASE}/{endpoint}?{qs}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "APIKey": api_key,
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def lookup_by_address(address_line, city_state, api_key):
    """Look up property by address components."""
    parts = city_state.replace(",", " ").split()
    city = " ".join(parts[:-1]) if len(parts) > 1 else parts[0] if parts else ""
    state = parts[-1] if len(parts) > 1 else "CA"

    params = {
        "address1": address_line,
        "address2": f"{city}, {state}",
    }

    try:
        data = attom_fetch("property/detailmortgageowner", params, api_key)
        props = data.get("property", [])
        if not props:
            data = attom_fetch("property/detail", params, api_key)
            props = data.get("property", [])
        if props:
            return props[0]
    except Exception as e:
        print(f"  ATTOM error: {e}", file=sys.stderr)

    return None


def extract_parcel_fields(prop):
    """Extract parcel-equivalent fields from ATTOM property response."""
    ident = prop.get("identifier", {})
    addr = prop.get("address", {})
    assessment = prop.get("assessment", {})
    assessed = assessment.get("assessed", {})
    market = assessment.get("market", {})
    building = prop.get("building", {})
    size = building.get("size", {})
    rooms = building.get("rooms", {})
    summary = prop.get("summary", {})
    lot = prop.get("lot", {})

    assd_land = assessed.get("assdttlvalue", market.get("mktttlvalue", ""))
    assd_impr = assessed.get("assdimprvalue", "")
    assd_total = assessed.get("assdttlvalue", "")

    return {
        "parcel_apn": ident.get("apn", ""),
        "parcel_owner": "",
        "parcel_assessed_total": assd_total,
        "parcel_assessed_land": assessed.get("assdlandvalue", ""),
        "parcel_assessed_impr": assd_impr,
        "parcel_sqft_living": size.get("livingsize", size.get("universalsize", "")),
        "parcel_sqft_lot": lot.get("lotsize2", ""),
        "parcel_beds": rooms.get("beds", ""),
        "parcel_baths": rooms.get("bathstotal", ""),
        "parcel_community": addr.get("locality", ""),
        "parcel_zip": addr.get("postal1", ""),
    }


def try_owner_lookup(prop):
    """Try to extract owner from mortgage/owner endpoint."""
    owners = prop.get("owner", {})
    if owners:
        owner1 = owners.get("owner1", {})
        name = owner1.get("fullName", "")
        if not name:
            first = owner1.get("firstNameAndMi", "")
            last = owner1.get("lastName", "")
            name = f"{last} {first}".strip()
        return name
    return ""


def main():
    env = load_env()
    api_key = env.get("ATTOM_API_KEY")
    if not api_key:
        print("ATTOM_API_KEY not found in .env")
        sys.exit(1)

    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        deals = list(reader)

    missing = [(i, d) for i, d in enumerate(deals) if not d.get("parcel_apn")]
    print(f"Total deals: {len(deals)}, missing parcel: {len(missing)}")
    print()

    matched = 0
    for idx, deal in missing:
        addr = deal.get("address", "")
        cs = deal.get("city_state", "")

        # Parse street address from full address (strip city/state)
        addr_parts = addr.split(",")
        street = addr_parts[0].strip() if addr_parts else addr

        print(f"[{deal['id']}] {street} | {cs}")

        prop = lookup_by_address(street, cs, api_key)
        time.sleep(1.0)

        if prop:
            fields = extract_parcel_fields(prop)
            owner = try_owner_lookup(prop)
            if owner:
                fields["parcel_owner"] = owner

            for k, v in fields.items():
                deal[k] = v

            if fields.get("parcel_apn"):
                matched += 1
                print(f"  -> APN {fields['parcel_apn']}  Owner: {fields.get('parcel_owner', '?')}")
            else:
                print(f"  -> ATTOM hit but no APN")
        else:
            print(f"  -> no ATTOM match")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(deals)

    print(f"\nDone: {matched} new parcel matches from ATTOM")
    print(f"Updated: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
