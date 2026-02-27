#!/usr/bin/env python3
"""
Export Southern California ZCTAs as GeoJSON for the frontend map.

Reads TIGER/Line ZCTA shapefile with a bounding box so only SoCal is loaded.
Outputs a simplified GeoJSON to frontend/public/socal_zctas.geojson for the
Search Configuration map (polygons instead of points).

Southern California bbox (lon_min, lat_min, lon_max, lat_max) in NAD83:
  approx. -121, 32, -114, 34.5  (San Diego, Orange, LA, Riverside, San Bernardino, Imperial, Ventura)

Requires:
  - TIGER/Line 2024 ZCTA shapefile (same as build_zcta_geodata.py)
  - Download: https://www2.census.gov/geo/tiger/TIGER2024/ZCTA520/tl_2024_us_zcta520.zip
  - Extract to: data/boundaries/census/source/tl_2024_us_zcta520/

Usage:
  python scripts/boundaries/census/build_socal_zctas.py
"""

import os
import sys

import geopandas as gpd
from shapely.validation import make_valid

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
CENSUS_DIR = os.path.join(PROJECT_ROOT, "data", "boundaries", "census")
SOURCE_DIR = os.path.join(CENSUS_DIR, "source")
ZCTA_SHP = os.path.join(SOURCE_DIR, "tl_2024_us_zcta520", "tl_2024_us_zcta520.shp")

# Southern California bbox (west, south, east, north) in NAD83 / WGS84-like lon,lat
SOCAL_BBOX = (-121.0, 32.0, -114.0, 34.6)

OUT_GEOJSON = os.path.join(PROJECT_ROOT, "frontend", "public", "socal_zctas.geojson")
TARGET_CRS = "EPSG:4326"
SIMPLIFY_TOLERANCE = 0.0005  # degrees (~50m); increase to shrink file


def fix_geometries(gdf):
    invalid_mask = ~gdf.geometry.is_valid
    if invalid_mask.any():
        n = invalid_mask.sum()
        gdf.loc[invalid_mask, "geometry"] = gdf.loc[invalid_mask, "geometry"].apply(make_valid)
        print(f"  Fixed {n} invalid geometries")
    return gdf


def main():
    if not os.path.exists(ZCTA_SHP):
        print(f"Error: {ZCTA_SHP} not found", file=sys.stderr)
        print("Download: https://www2.census.gov/geo/tiger/TIGER2024/ZCTA520/tl_2024_us_zcta520.zip", file=sys.stderr)
        print(f"Extract to: {os.path.dirname(ZCTA_SHP)}/", file=sys.stderr)
        sys.exit(1)

    print("Loading SoCal ZCTAs (bbox filter)...")
    # bbox in same CRS as shapefile (NAD83)
    gdf = gpd.read_file(ZCTA_SHP, bbox=SOCAL_BBOX)
    print(f"  Loaded {len(gdf)} ZCTAs")

    gdf = gdf.to_crs(TARGET_CRS)
    gdf = fix_geometries(gdf)

    # Keep only zip code and geometry for frontend (use 'zip' for consistent props)
    gdf = gdf[["ZCTA5CE20", "geometry"]].copy()
    gdf["zip"] = gdf["ZCTA5CE20"].astype(str)
    gdf = gdf[["zip", "geometry"]]

    print("Simplifying geometries...")
    gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)

    os.makedirs(os.path.dirname(OUT_GEOJSON), exist_ok=True)
    gdf.to_file(OUT_GEOJSON, driver="GeoJSON")
    size_kb = os.path.getsize(OUT_GEOJSON) / 1024
    print(f"  Wrote {len(gdf)} ZCTAs -> {OUT_GEOJSON} ({size_kb:.0f} KB)")
    print("Done. Restart or refresh the frontend to load the map.")


if __name__ == "__main__":
    main()
