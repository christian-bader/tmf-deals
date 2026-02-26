import csv
import urllib.request
import urllib.parse
import json
import time
import sys

FILE = "data/tmf/deals_rows.csv"

GEOCODE_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"


def reverse_geocode(lat, lon):
    params = urllib.parse.urlencode({
        "x": lon,
        "y": lat,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    })
    url = f"{GEOCODE_URL}?{params}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        geos = data.get("result", {}).get("geographies", {})

        county_info = (geos.get("Counties") or [{}])[0]
        state_info = (geos.get("States") or [{}])[0]
        cousub_info = (geos.get("County Subdivisions") or [{}])[0]
        tract_info = (geos.get("Census Tracts") or [{}])[0]

        return {
            "state_fips": state_info.get("STATE", ""),
            "county_fips": county_info.get("COUNTY", ""),
            "county_geoid": county_info.get("GEOID", ""),
            "county_name": county_info.get("BASENAME", ""),
            "cousub_geoid": cousub_info.get("GEOID", ""),
            "cousub_name": cousub_info.get("BASENAME", ""),
            "tract_geoid": tract_info.get("GEOID", ""),
        }
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return {}


with open(FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    old_fields = reader.fieldnames
    rows = list(reader)

GEO_FIELDS = [
    "state_fips", "county_fips", "county_geoid",
    "county_name", "cousub_geoid", "cousub_name", "tract_geoid",
]

new_fields = old_fields + [f for f in GEO_FIELDS if f not in old_fields]

total = len(rows)
matched = 0

for i, row in enumerate(rows):
    lat = row.get("latitude", "").strip()
    lon = row.get("longitude", "").strip()

    if not lat or not lon:
        print(f"[{row['id']}] No coordinates, skipping")
        for f in GEO_FIELDS:
            row[f] = ""
        continue

    print(f"[{i+1}/{total}] {row['display_name']}")
    geo = reverse_geocode(lat, lon)
    time.sleep(0.3)

    if geo.get("county_geoid"):
        matched += 1
        print(f"  -> {geo['county_name']} County ({geo['county_geoid']}), tract {geo['tract_geoid']}")
    else:
        print(f"  -> NO GEO MATCH")

    for f in GEO_FIELDS:
        row[f] = geo.get(f, "")

print(f"\nDone: {matched}/{total} matched")

with open(FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=new_fields)
    writer.writeheader()
    writer.writerows(rows)

print(f"Updated {FILE} with {len(GEO_FIELDS)} new columns")
