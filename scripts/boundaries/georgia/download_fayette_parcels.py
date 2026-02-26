#!/usr/bin/env python3
"""
Download Fayette County parcel data from the public ArcGIS FeatureServer.

Source:
  https://services.arcgis.com/j3zNT485kmwrBtMJ/arcgis/rest/services/Fay_Parcels/FeatureServer/0

Output:
  data/boundaries/fayette_parcels.geojson
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "boundaries", "fayette_parcels.geojson")

BASE_URL = "https://services.arcgis.com/j3zNT485kmwrBtMJ/arcgis/rest/services/Fay_Parcels/FeatureServer/0/query"
PAGE_SIZE = 1000


def query(params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"{BASE_URL}?{qs}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def get_count() -> int:
    result = query({"where": "1=1", "returnCountOnly": "true", "f": "json"})
    return result["count"]


def download_all():
    total = get_count()
    print(f"Total parcels: {total}")
    print(f"Page size: {PAGE_SIZE}, estimated pages: {(total // PAGE_SIZE) + 1}")

    all_features = []
    offset = 0
    page = 0

    while True:
        page += 1
        params = {
            "where": "1=1",
            "outFields": "*",
            "outSR": "4326",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
        }

        try:
            data = query(params)
        except Exception as e:
            print(f"  Error on page {page} (offset {offset}): {e}")
            print("  Retrying in 5s...")
            time.sleep(5)
            try:
                data = query(params)
            except Exception as e2:
                print(f"  Retry failed: {e2}. Stopping.")
                break

        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)
        offset += len(features)
        print(f"  Page {page}: {len(features)} features (total so far: {len(all_features)}/{total})")

        if len(features) < PAGE_SIZE:
            break

        time.sleep(0.2)

    print(f"\nDownloaded {len(all_features)} features")

    geojson = {
        "type": "FeatureCollection",
        "features": all_features,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(geojson, f)

    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"Wrote {OUTPUT_PATH} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    download_all()
