"""
Download San Diego County parcel boundary polygons as GeoJSON, filtered by ZIP.

Source: https://gis-public.sandiegocounty.gov/arcgis/rest/services/sdep_warehouse/PARCELS_ALL/FeatureServer/0

Outputs WGS84 (EPSG:4326) GeoJSON ready for web mapping.
"""

import json
import os
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = (
    "https://gis-public.sandiegocounty.gov/arcgis/rest/services/"
    "sdep_warehouse/PARCELS_ALL/FeatureServer/0/query"
)

TARGET_ZIPS = [
    "92037", "92014", "92075", "92024", "92007",
    "92118", "92106", "92107", "92109",
    "92011", "92008", "92130", "92127", "92029",
]

FIELDS = [
    "OBJECTID", "APN", "APN_8",
    "OWN_NAME1", "SITUS_ZIP", "SITUS_COMMUNITY",
    "ASR_TOTAL", "ASR_ZONE", "ACREAGE",
    "TOTAL_LVG_AREA", "BEDROOMS", "BATHS", "UNITQTY",
]

PAGE_SIZE = 1000
MAX_RETRIES = 3
OUTPUT_DIR = "data/boundaries/san-diego"


def query_features(where, offset=0):
    params = {
        "where": where,
        "outFields": ",".join(FIELDS),
        "returnGeometry": "true",
        "outSR": "4326",
        "geometryPrecision": 7,
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "orderByFields": "OBJECTID ASC",
        "f": "geojson",
    }
    url = f"{BASE_URL}?{urlencode(params)}"
    for attempt in range(MAX_RETRIES):
        try:
            req = Request(url, headers={"User-Agent": "ParcelDownloader/1.0"})
            with urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(f"API error: {data['error']}")
            return data
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = 5 * (attempt + 1)
                print(f"  Retry {attempt+1}: {e} (waiting {wait}s)")
                time.sleep(wait)
            else:
                raise


def get_count(where):
    params = {"where": where, "returnCountOnly": "true", "f": "json"}
    url = f"{BASE_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "ParcelDownloader/1.0"})
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8")).get("count", 0)


def download_zip(zip_code):
    where = f"SITUS_ZIP LIKE '{zip_code}%'"
    total = get_count(where)
    print(f"\n[{zip_code}] {total:,} parcels")

    if total == 0:
        return []

    all_features = []
    offset = 0
    while offset < total:
        data = query_features(where, offset)
        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)
        offset += len(features)
        pct = min(100, offset / total * 100)
        print(f"  {offset:,} / {total:,} ({pct:.1f}%)")
        time.sleep(0.3)

    return all_features


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_features = []

    for zip_code in TARGET_ZIPS:
        features = download_zip(zip_code)
        all_features.extend(features)

    geojson = {
        "type": "FeatureCollection",
        "features": all_features,
    }

    output_path = os.path.join(OUTPUT_DIR, "parcels_san_diego_shapes.geojson")
    with open(output_path, "w") as f:
        json.dump(geojson, f)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nDone. {len(all_features):,} parcels -> {output_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
