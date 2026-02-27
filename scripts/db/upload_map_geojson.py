#!/usr/bin/env python3
"""
Upload SoCal ZCTA GeoJSON to Supabase map_geojson table.

Reads frontend/public/socal_zctas.geojson (or the path you pass) and upserts
a row with name='socal_zctas' so the frontend can load the map from Supabase.

Requires:
  - Table map_geojson (run scripts/db/migrations/005_map_geojson.sql in Supabase first)
  - SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY for write if RLS restricts anon)

Usage:
  python scripts/db/upload_map_geojson.py
  python scripts/db/upload_map_geojson.py --file frontend/public/socal_zctas.geojson
"""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# Load .env from repo root, then scripts/.env.local (so scripts/.env.local wins)
repo_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(repo_root / ".env")
load_dotenv(repo_root / "scripts" / ".env.local")

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("VITE_SUPABASE_ANON_KEY")
)

LAYER_NAME = "socal_zctas"
DEFAULT_FILE = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "socal_zctas.geojson"


def main():
    parser = argparse.ArgumentParser(description="Upload SoCal ZCTA GeoJSON to Supabase map_geojson")
    parser.add_argument(
        "--file", "-f",
        type=Path,
        default=DEFAULT_FILE,
        help=f"Path to GeoJSON file (default: {DEFAULT_FILE})",
    )
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit(
            "Missing SUPABASE_URL or SUPABASE_KEY (or VITE_SUPABASE_*). Set in .env or environment."
        )
    if not args.file.exists():
        raise SystemExit(f"File not found: {args.file}. Run build_socal_zctas.py first.")

    with open(args.file, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    if "type" not in geojson or "features" not in geojson:
        raise SystemExit("GeoJSON must be a FeatureCollection with 'type' and 'features'.")

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    row = {"name": LAYER_NAME, "geojson": geojson}
    result = client.table("map_geojson").upsert(row, on_conflict="name").execute()

    print(f"Uploaded '{LAYER_NAME}' to map_geojson ({len(geojson.get('features', []))} features).")
    if result.data:
        print(f"  Row id: {result.data[0].get('id')}")


if __name__ == "__main__":
    main()
