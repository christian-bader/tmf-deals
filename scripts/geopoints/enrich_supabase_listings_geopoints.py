"""
Pull listings from Supabase and enrich them with latitude/longitude via Google Geocoding.

Fetches rows from the `listings` table (optionally only those missing coords),
builds full address from address, city, state, zip, geocodes, and updates each row.

Requires .env (repo root or scripts/ or scripts/geopoints/) with:
  SUPABASE_URL=...  (or VITE_SUPABASE_URL, same as frontend)
  SUPABASE_ANON_KEY=...  (or VITE_SUPABASE_ANON_KEY)
  GOOGLE_GEOCODING_API_KEY=...

Usage:
  # Geocode only listings missing latitude/longitude (default)
  python scripts/geopoints/enrich_supabase_listings_geopoints.py

  # Process all listings (re-geocode existing coords)
  python scripts/geopoints/enrich_supabase_listings_geopoints.py --all

  # Limit how many to process (e.g. for testing)
  python scripts/geopoints/enrich_supabase_listings_geopoints.py --limit 10

  # Dry run: show what would be processed, no writes
  python scripts/geopoints/enrich_supabase_listings_geopoints.py --dry-run

  # Show current listings with geopoints only (no geocoding; tests Supabase pull)
  python scripts/geopoints/enrich_supabase_listings_geopoints.py --show-only
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

# Repo root = parent of scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
# Check repo root and scripts/ so scripts/.env.local works
ENV_LOCATIONS = [
    REPO_ROOT / ".env",
    REPO_ROOT / "scripts" / ".env.local",
    REPO_ROOT / "scripts" / ".env",
    SCRIPT_DIR / ".env.local",
    SCRIPT_DIR / ".env",
]
GOOGLE_GEO_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def load_env():
    """Load .env into os.environ from first existing file."""
    for path in ENV_LOCATIONS:
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")
            return


def get_supabase_config():
    url = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("VITE_SUPABASE_ANON_KEY")
    )
    if not url or not key:
        raise RuntimeError(
            "Need SUPABASE_URL (or VITE_SUPABASE_URL) and SUPABASE_ANON_KEY (or VITE_SUPABASE_ANON_KEY) in .env"
        )
    return url, key


def get_required_env(*keys):
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing in .env or environment: {', '.join(missing)}")
    return [os.environ[k] for k in keys]


def geocode_address(address: str, api_key: str):
    params = urllib.parse.urlencode({"address": address, "key": api_key})
    url = f"{GOOGLE_GEO_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "SupabaseListingsGeopoints/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"  Geocode request error: {e}", file=sys.stderr)
        return None, None
    if data.get("status") != "OK" or not data.get("results"):
        return None, None
    loc = data["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def build_full_address(row: dict) -> str:
    parts = [
        row.get("address"),
        row.get("city"),
        row.get("state"),
        row.get("zip"),
    ]
    return ", ".join(p for p in parts if p and str(p).strip()).strip()


def _print_results_table(client, build_full_address):
    """Fetch listings with coords and print as table."""
    try:
        show_response = (
            client.table("listings")
            .select("id,address,city,state,zip,latitude,longitude")
            .not_.is_("latitude", "null")
            .order("sale_date", desc=True)
            .limit(20)
            .execute()
        )
    except Exception:
        show_response = (
            client.table("listings")
            .select("id,address,city,state,zip,latitude,longitude")
            .order("sale_date", desc=True)
            .limit(50)
            .execute()
        )
    rows = [r for r in (show_response.data or []) if r.get("latitude") is not None and r.get("longitude") is not None]
    if not rows:
        print("No listings with geopoints yet.")
        return
    col_w = 44
    print(f"\n{'Address':<{col_w}} {'Latitude':>10} {'Longitude':>11}")
    print("-" * (col_w + 10 + 11 + 2))
    for r in rows:
        addr = (build_full_address(r) or r.get("address") or "")[: col_w - 1]
        lat, lon = r.get("latitude"), r.get("longitude")
        lat_s = f"{lat:.5f}" if lat is not None else ""
        lon_s = f"{lon:.5f}" if lon is not None else ""
        print(f"{addr:<{col_w}} {lat_s:>10} {lon_s:>11}")
    print(f"\n(Showing {len(rows)} rows)")


def run(supabase_url: str, supabase_key: str, api_key: str, all_listings: bool, limit: Optional[int], dry_run: bool, show_only: bool):
    try:
        from supabase import create_client
    except ImportError:
        print("Install the Supabase client: pip install supabase", file=sys.stderr)
        sys.exit(1)

    client = create_client(supabase_url, supabase_key)

    if show_only:
        # Only fetch and display current state (no Google key needed)
        print("Fetching listings with geopoints from Supabase...")
        _print_results_table(client, build_full_address)
        # Also show count missing coords
        missing = client.table("listings").select("id").is_("latitude", "null").execute()
        total_missing = len(missing.data or [])
        print(f"\nListings still missing coords: {total_missing}")
        return

    if all_listings:
        response = client.table("listings").select("id,address,city,state,zip,latitude,longitude").order("sale_date", desc=True).execute()
    else:
        response = (
            client.table("listings")
            .select("id,address,city,state,zip,latitude,longitude")
            .is_("latitude", "null")
            .order("sale_date", desc=True)
            .execute()
        )

    rows = response.data or []
    if limit is not None:
        rows = rows[:limit]

    total = len(rows)
    if total == 0:
        print("No listings to process.")
        return

    print(f"Processing {total} listing(s). Dry run: {dry_run}")
    if dry_run:
        for i, r in enumerate(rows[:15]):
            addr = build_full_address(r) or "(no address)"
            print(f"  [{i+1}] {addr}")
        if total > 15:
            print(f"  ... and {total - 15} more")
        return

    updated = 0
    failed = 0
    for i, row in enumerate(rows):
        listing_id = row.get("id")
        full_address = build_full_address(row)
        if not full_address:
            print(f"[{i+1}/{total}] id={listing_id} — no address, skip")
            failed += 1
            continue

        print(f"[{i+1}/{total}] {full_address[:60]}{'...' if len(full_address) > 60 else ''}")
        lat, lon = geocode_address(full_address, api_key)
        if lat is None:
            print("  -> no result")
            failed += 1
        else:
            resp = client.table("listings").update({"latitude": lat, "longitude": lon}).eq("id", listing_id).execute()
            if getattr(resp, "error", None) is None:
                print(f"  -> {lat}, {lon}")
                updated += 1
            else:
                print(f"  -> update failed: {resp.error}")
                failed += 1

        time.sleep(0.15)

    print(f"\nDone: {updated} updated, {failed} failed.")
    print("\n--- Listings with geopoints (sample) ---")
    _print_results_table(client, build_full_address)


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Enrich Supabase listings with geopoints via Google Geocoding")
    parser.add_argument("--all", action="store_true", help="Process all listings (default: only missing coords)")
    parser.add_argument("--limit", type=int, help="Max number of listings to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed, no updates")
    parser.add_argument("--show-only", action="store_true", help="Only fetch and show listings with geopoints (no geocoding)")
    args = parser.parse_args()

    supabase_url, supabase_key = get_supabase_config()
    api_key = "" if args.show_only else get_required_env("GOOGLE_GEOCODING_API_KEY")[0]

    run(
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        api_key=api_key,
        all_listings=args.all,
        limit=args.limit,
        dry_run=args.dry_run,
        show_only=args.show_only,
    )


if __name__ == "__main__":
    main()
