import csv
import urllib.request
import urllib.parse
import json
import time
import os
import sys

FILE = "data/tmf/deals_rows.csv"
ENV_FILE = ".env"

def load_env(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

load_env(ENV_FILE)
API_KEY = os.environ["GOOGLE_GEOCODING_API_KEY"]

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

def geocode(full_address):
    params = urllib.parse.urlencode({
        "address": full_address,
        "key": API_KEY,
    })
    url = f"{GEOCODE_URL}?{params}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if data.get("status") == "OK" and data.get("results"):
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
        else:
            print(f"  status: {data.get('status')} | {data.get('error_message', '')}", file=sys.stderr)
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
    return None, None

with open(FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

total = len(rows)
matched_before = sum(1 for r in rows if r.get("latitude"))
print(f"Starting: {matched_before}/{total} already have coords\n")

newly_matched = 0
total_geocoded = 0

for row in rows:
    fa = row["full_address"]

    if row.get("latitude"):
        total_geocoded += 1
        continue

    print(f"[{row['id']}] {fa}")
    lat, lon = geocode(fa)
    time.sleep(0.05)

    if lat:
        row["latitude"] = lat
        row["longitude"] = lon
        newly_matched += 1
        total_geocoded += 1
        print(f"  -> {lat}, {lon}")
    else:
        print(f"  -> NO MATCH")

print(f"\nGoogle pass: {newly_matched} new matches")
print(f"Total with coords: {total_geocoded}/{total}")

with open(FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Updated {FILE}")
