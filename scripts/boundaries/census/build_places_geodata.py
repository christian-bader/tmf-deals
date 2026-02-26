#!/usr/bin/env python3
"""
Export state-level municipal/place boundaries as Foundry-ready GeoJSON and CSV.

Source:
  - TIGER/Line 2024 place shapefiles (per-state)
  - Download: https://www2.census.gov/geo/tiger/TIGER2024/PLACE/tl_2024_{STATEFP}_place.zip

Places include incorporated cities, towns, CDPs (Census Designated Places),
and other recognized communities. Filter on CLASSFP to get only incorporated
places (C1, C2, C5) vs CDPs (U1, U2).

Outputs (per state):
  - data/boundaries/census/{state_abbrev}_places.geojson
  - data/boundaries/census/{state_abbrev}_places.csv

GeoJSON is in WGS 84 (EPSG:4326).

GEOID structure: STATEFP (2 digits) + PLACEFP (5 digits)
  e.g. 0644000 = state 06 (California) + place 44000 (Los Angeles)
"""

import csv
import json
import os
import sys

import geopandas as gpd
from shapely.validation import make_valid

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
CENSUS_DIR = os.path.join(PROJECT_ROOT, "data", "boundaries", "census")
SOURCE_DIR = os.path.join(CENSUS_DIR, "source")

TARGET_CRS = "EPSG:4326"

STATES = {
    "06": "ca",
    "13": "ga",
}

GEOJSON_COLUMNS = [
    "STATEFP", "PLACEFP", "GEOID", "NAME", "NAMELSAD", "LSAD",
    "CLASSFP", "FUNCSTAT", "ALAND", "AWATER", "INTPTLAT", "INTPTLON",
    "geometry",
]

CSV_COLUMNS = [
    "state_fips", "place_fips", "geoid", "name", "namelsad", "lsad",
    "classfp", "funcstat", "aland", "awater", "intptlat", "intptlon",
    "geometry_wkt",
]


def geometry_to_wkt(geometry):
    if not geometry:
        return None
    geom_type = geometry.get("type", "")
    coordinates = geometry.get("coordinates", [])
    if geom_type == "Polygon":
        rings = []
        for ring in coordinates:
            points = ", ".join(f"{c[0]} {c[1]}" for c in ring)
            rings.append(f"({points})")
        return f"POLYGON ({', '.join(rings)})"
    elif geom_type == "MultiPolygon":
        polygons = []
        for polygon in coordinates:
            rings = []
            for ring in polygon:
                points = ", ".join(f"{c[0]} {c[1]}" for c in ring)
                rings.append(f"({points})")
            polygons.append(f"({', '.join(rings)})")
        return f"MULTIPOLYGON ({', '.join(polygons)})"
    return str(geometry)


def fix_geometries(gdf):
    invalid_mask = ~gdf.geometry.is_valid
    if invalid_mask.any():
        print(f"  Fixing {invalid_mask.sum()} invalid geometries...")
        gdf.loc[invalid_mask, "geometry"] = gdf.loc[invalid_mask, "geometry"].apply(make_valid)
    return gdf


def build_state(state_fips, state_abbrev):
    shp_dir = os.path.join(SOURCE_DIR, f"tl_2024_{state_fips}_place")
    shp_path = os.path.join(shp_dir, f"tl_2024_{state_fips}_place.shp")

    if not os.path.exists(shp_path):
        print(f"Error: {shp_path} not found")
        print(f"Download: https://www2.census.gov/geo/tiger/TIGER2024/PLACE/tl_2024_{state_fips}_place.zip")
        return

    print(f"Processing places for {state_abbrev.upper()} (FIPS {state_fips})...")
    gdf = gpd.read_file(shp_path)
    gdf = gdf.to_crs(TARGET_CRS)
    gdf = fix_geometries(gdf)

    available_cols = [c for c in GEOJSON_COLUMNS if c in gdf.columns]
    gdf = gdf[available_cols].copy()
    gdf = gdf.sort_values("GEOID").reset_index(drop=True)

    out_geojson = os.path.join(CENSUS_DIR, f"{state_abbrev}_places.geojson")
    out_csv = os.path.join(CENSUS_DIR, f"{state_abbrev}_places.csv")

    gdf.to_file(out_geojson, driver="GeoJSON")
    print(f"  {len(gdf)} places -> {out_geojson}")

    with open(out_geojson, "r") as f:
        data = json.load(f)

    prop_keys = [c for c in GEOJSON_COLUMNS if c != "geometry"]
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for feature in data["features"]:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            writer.writerow([props.get(k, "") for k in prop_keys] + [geometry_to_wkt(geom)])

    print(f"  {len(data['features'])} rows -> {out_csv}")

    incorporated = gdf[gdf["CLASSFP"].isin(["C1", "C2", "C5"])] if "CLASSFP" in gdf.columns else gdf
    print(f"  Incorporated places: {len(incorporated)}, CDPs: {len(gdf) - len(incorporated)}")


def main():
    os.makedirs(CENSUS_DIR, exist_ok=True)

    for state_fips, state_abbrev in STATES.items():
        build_state(state_fips, state_abbrev)

    print("\nDone!")


if __name__ == "__main__":
    main()
