"""
Bulk download San Diego County PARCELS_ALL data from the public ArcGIS FeatureServer.

Source: https://gis-public.sandiegocounty.gov/arcgis/rest/services/sdep_warehouse/PARCELS_ALL/FeatureServer/0

Contains 1M+ parcels with coordinates, assessed values, property details, and
last recorded document info. Does NOT contain actual sale prices — cross-reference
with the 408.1 property sales report from the Assessor's office for that.

Usage:
    python scripts/download_parcels.py [--output parcels.csv] [--land-use-filter residential]
"""

import argparse
import csv
import json
import os
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE_URL = (
    "https://gis-public.sandiegocounty.gov/arcgis/rest/services/"
    "sdep_warehouse/PARCELS_ALL/FeatureServer/0/query"
)

FIELDS = [
    "OBJECTID", "APN", "APN_8",
    "OWN_NAME1", "OWN_NAME2",
    "OWN_ADDR1", "OWN_ADDR2", "OWN_ZIP",
    "SITUS_ADDRESS", "SITUS_PRE_DIR", "SITUS_STREET", "SITUS_SUFFIX",
    "SITUS_POST_DIR", "SITUS_SUITE", "SITUS_ZIP", "SITUS_COMMUNITY",
    "ASR_LAND", "ASR_IMPR", "ASR_TOTAL",
    "DOCTYPE", "DOCNMBR", "DOCDATE",
    "ACREAGE", "TAXSTAT", "OWNEROCC",
    "ASR_ZONE", "ASR_LANDUSE", "NUCLEUS_ZONE_CD", "NUCLEUS_USE_CD",
    "TOTAL_LVG_AREA", "BEDROOMS", "BATHS",
    "UNITQTY", "POOL",
    "X_COORD", "Y_COORD",
]

PAGE_SIZE = 2000
MAX_RETRIES = 3
RETRY_DELAY = 5


def query_features(where="1=1", offset=0):
    params = {
        "where": where,
        "outFields": ",".join(FIELDS),
        "returnGeometry": "false",
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "orderByFields": "OBJECTID ASC",
        "f": "json",
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
        except (URLError, HTTPError, TimeoutError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (attempt + 1)
                print(f"  Retry {attempt+1}/{MAX_RETRIES} after error: {e} (waiting {wait}s)")
                time.sleep(wait)
            else:
                raise


def get_total_count(where="1=1"):
    params = {
        "where": where,
        "returnCountOnly": "true",
        "f": "json",
    }
    url = f"{BASE_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "ParcelDownloader/1.0"})
    with urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("count", 0)


def build_situs_address(attrs):
    """Reconstruct full street address from component fields."""
    parts = []
    if attrs.get("SITUS_ADDRESS"):
        parts.append(str(attrs["SITUS_ADDRESS"]))
    if attrs.get("SITUS_PRE_DIR"):
        parts.append(attrs["SITUS_PRE_DIR"].strip())
    if attrs.get("SITUS_STREET"):
        parts.append(attrs["SITUS_STREET"].strip())
    if attrs.get("SITUS_SUFFIX"):
        parts.append(attrs["SITUS_SUFFIX"].strip())
    if attrs.get("SITUS_POST_DIR"):
        parts.append(attrs["SITUS_POST_DIR"].strip())
    if attrs.get("SITUS_SUITE"):
        parts.append(f"#{attrs['SITUS_SUITE'].strip()}")
    return " ".join(parts)


def download_all(output_path, where="1=1"):
    total = get_total_count(where)
    print(f"Total parcels matching query: {total:,}")
    if total == 0:
        print("No records found.")
        return

    csv_fields = FIELDS + ["FULL_SITUS_ADDRESS"]
    written = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()

        offset = 0
        while offset < total:
            data = query_features(where=where, offset=offset)
            features = data.get("features", [])
            if not features:
                break

            for feat in features:
                attrs = feat["attributes"]
                attrs["FULL_SITUS_ADDRESS"] = build_situs_address(attrs)
                writer.writerow(attrs)
                written += 1

            offset += len(features)
            pct = min(100, offset / total * 100)
            print(f"  Downloaded {offset:,} / {total:,} ({pct:.1f}%)")

            time.sleep(0.25)

    print(f"\nDone. Wrote {written:,} rows to {output_path}")


RESIDENTIAL_USE_CODES = [
    "01", "02", "03", "04", "05", "06", "07", "08", "09",
    "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
]


def main():
    parser = argparse.ArgumentParser(description="Download San Diego County parcel data")
    parser.add_argument(
        "--output", "-o",
        default="parcels_san_diego.csv",
        help="Output CSV file path (default: parcels_san_diego.csv)",
    )
    parser.add_argument(
        "--land-use-filter",
        choices=["residential", "commercial", "all"],
        default="all",
        help="Filter by land use type (default: all)",
    )
    parser.add_argument(
        "--min-assessed-value",
        type=int,
        default=None,
        help="Minimum total assessed value filter",
    )
    parser.add_argument(
        "--max-assessed-value",
        type=int,
        default=None,
        help="Maximum total assessed value filter",
    )
    args = parser.parse_args()

    where_clauses = ["1=1"]

    if args.land_use_filter == "residential":
        codes = ",".join(f"'{c}'" for c in RESIDENTIAL_USE_CODES)
        where_clauses.append(f"NUCLEUS_USE_CD IN ({codes})")
    elif args.land_use_filter == "commercial":
        codes = ",".join(f"'{c}'" for c in RESIDENTIAL_USE_CODES)
        where_clauses.append(f"NUCLEUS_USE_CD NOT IN ({codes})")

    if args.min_assessed_value is not None:
        where_clauses.append(f"ASR_TOTAL >= {args.min_assessed_value}")
    if args.max_assessed_value is not None:
        where_clauses.append(f"ASR_TOTAL <= {args.max_assessed_value}")

    where = " AND ".join(where_clauses)
    print(f"Query filter: {where}")
    print(f"Output: {args.output}\n")

    download_all(args.output, where=where)


if __name__ == "__main__":
    main()
