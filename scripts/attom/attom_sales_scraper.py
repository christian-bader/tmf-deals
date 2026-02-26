"""
ATTOM API Sales Data Scraper

Pulls all property sale transactions from ATTOM's /sale/detail endpoint
for specified counties, date ranges, and price filters. Paginates through
results in quarterly batches and writes incrementally to CSV.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ATTOM_API_KEY")
BASE_URL = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"
HEADERS = {"Accept": "application/json", "apikey": API_KEY}
PAGE_SIZE = 100
RATE_LIMIT_PAUSE = 1.0  # seconds between requests

COUNTIES = {
    "san_diego": "CO06073",
    "solano": "CO06095",
}

CSV_COLUMNS = [
    "attom_id", "fips", "apn",
    "address_one_line", "address_line1", "address_line2",
    "city", "state", "zip",
    "latitude", "longitude",
    "county", "muni_name",
    "property_type", "property_indicator", "property_class", "property_subtype",
    "year_built", "universal_size_sqft", "lot_size_acres", "lot_size_sqft",
    "beds", "baths_total", "units_count",
    "sale_amt", "sale_date", "sale_record_date", "sale_trans_type",
    "sale_disclosure_type", "sale_doc_num",
    "price_per_bed", "price_per_sqft",
    "cash_or_mortgage", "resale_or_new",
]


def generate_quarterly_windows(start_date: str, end_date: str):
    """Yield (start, end) date strings in ~quarterly chunks."""
    start = datetime.strptime(start_date, "%Y/%m/%d")
    end = datetime.strptime(end_date, "%Y/%m/%d")
    current = start
    while current < end:
        window_end = min(current + timedelta(days=90), end)
        yield current.strftime("%Y/%m/%d"), window_end.strftime("%Y/%m/%d")
        current = window_end + timedelta(days=1)


def extract_record(prop: dict) -> dict:
    """Flatten a single ATTOM property record into a CSV row dict."""
    ident = prop.get("identifier", {})
    addr = prop.get("address", {})
    loc = prop.get("location", {})
    area = prop.get("area", {})
    summary = prop.get("summary", {})
    bldg = prop.get("building", {})
    sale = prop.get("sale", {})
    amount = sale.get("amount", {})
    calc = sale.get("calculation", {})
    size = bldg.get("size", {})
    rooms = bldg.get("rooms", {})
    bldg_summary = bldg.get("summary", {})

    return {
        "attom_id": ident.get("attomId"),
        "fips": ident.get("fips"),
        "apn": ident.get("apn"),
        "address_one_line": addr.get("oneLine"),
        "address_line1": addr.get("line1"),
        "address_line2": addr.get("line2"),
        "city": addr.get("locality"),
        "state": addr.get("countrySubd"),
        "zip": addr.get("postal1"),
        "latitude": loc.get("latitude"),
        "longitude": loc.get("longitude"),
        "county": area.get("countrysecsubd"),
        "muni_name": area.get("munname"),
        "property_type": summary.get("propertyType"),
        "property_indicator": summary.get("propIndicator"),
        "property_class": summary.get("propclass"),
        "property_subtype": summary.get("propsubtype"),
        "year_built": summary.get("yearbuilt"),
        "universal_size_sqft": size.get("universalsize"),
        "lot_size_acres": prop.get("lot", {}).get("lotsize1"),
        "lot_size_sqft": prop.get("lot", {}).get("lotsize2"),
        "beds": rooms.get("beds"),
        "baths_total": rooms.get("bathstotal"),
        "units_count": bldg_summary.get("unitsCount"),
        "sale_amt": amount.get("saleamt"),
        "sale_date": sale.get("saleTransDate"),
        "sale_record_date": amount.get("salerecdate"),
        "sale_trans_type": amount.get("saletranstype"),
        "sale_disclosure_type": amount.get("saledisclosuretype"),
        "sale_doc_num": amount.get("saledocnum"),
        "price_per_bed": calc.get("priceperbed"),
        "price_per_sqft": calc.get("pricepersizeunit"),
        "cash_or_mortgage": sale.get("cashormortgagepurchase"),
        "resale_or_new": sale.get("resaleornewconstruction"),
    }


def fetch_sales(county_geo_id: str, start_date: str, end_date: str,
                min_sale: int = None, max_sale: int = None):
    """Generator that yields all sale records for a county + date window, handling pagination."""
    page = 1
    total_fetched = 0

    while True:
        params = {
            "geoID": county_geo_id,
            "startSaleSearchDate": start_date,
            "endSaleSearchDate": end_date,
            "pageSize": PAGE_SIZE,
            "page": page,
            "orderBy": "SaleSearchDate asc",
        }
        if min_sale is not None:
            params["minSaleAmt"] = min_sale
        if max_sale is not None:
            params["maxSaleAmt"] = max_sale

        resp = requests.get(f"{BASE_URL}/sale/detail", headers=HEADERS, params=params)

        if resp.status_code == 401:
            print("ERROR: Unauthorized. Check your API key.")
            sys.exit(1)

        if resp.status_code == 429:
            print("  Rate limited, waiting 30s...")
            time.sleep(30)
            continue

        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code} on page {page}, skipping")
            break

        data = resp.json()
        status = data.get("status", {})

        if status.get("code") == 400:
            break

        total = status.get("total", 0)
        properties = data.get("property", [])

        if not properties:
            break

        for prop in properties:
            yield extract_record(prop)

        total_fetched += len(properties)
        print(f"    Page {page}: got {len(properties)} records ({total_fetched}/{total} total)")

        if total_fetched >= total:
            break

        page += 1
        time.sleep(RATE_LIMIT_PAUSE)


def scrape_county(county_name: str, county_geo_id: str, start_date: str,
                  end_date: str, output_dir: str, min_sale: int = None,
                  max_sale: int = None):
    """Scrape all sales for a county across quarterly windows, write to CSV."""
    output_path = Path(output_dir) / f"sales_{county_name}.csv"
    total_records = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        windows = list(generate_quarterly_windows(start_date, end_date))
        for i, (win_start, win_end) in enumerate(windows, 1):
            print(f"\n[{county_name}] Window {i}/{len(windows)}: {win_start} → {win_end}")
            window_count = 0

            for record in fetch_sales(county_geo_id, win_start, win_end, min_sale, max_sale):
                writer.writerow(record)
                window_count += 1

            total_records += window_count
            print(f"  Window total: {window_count} | Running total: {total_records}")

    print(f"\n{'='*60}")
    print(f"[{county_name}] DONE — {total_records} records saved to {output_path}")
    return total_records


def main():
    start_date = "2021/02/24"
    end_date = "2026/02/24"
    min_sale = 1_000_000
    max_sale = 10_000_000
    output_dir = Path(__file__).resolve().parent.parent / "data"
    output_dir.mkdir(exist_ok=True)

    print(f"ATTOM Sales Scraper")
    print(f"Date range: {start_date} — {end_date}")
    print(f"Sale amount: ${min_sale:,} — ${max_sale:,}")
    print(f"Output dir: {output_dir}")

    for county_name, geo_id in COUNTIES.items():
        print(f"\n{'='*60}")
        print(f"Starting: {county_name} ({geo_id})")
        print(f"{'='*60}")
        scrape_county(county_name, geo_id, start_date, end_date,
                      str(output_dir), min_sale, max_sale)


if __name__ == "__main__":
    main()
