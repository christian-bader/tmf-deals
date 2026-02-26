#!/usr/bin/env python3
"""
Export all US county boundaries as Foundry-ready GeoJSON and CSV.

Source:
  - TIGER/Line 2024 county shapefile (national)

Outputs:
  - data/boundaries/census/us_counties.geojson
  - data/boundaries/census/us_counties.csv

GeoJSON is in WGS 84 (EPSG:4326), ready for Palantir Foundry import
via Pipeline Builder's parseGeoJsonV1 transform.

GEOID structure: STATEFP (2 digits) + COUNTYFP (3 digits)
  e.g. 13189 = state 13 (Georgia) + county 189 (McDuffie)
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
BOUNDARY_DIR = CENSUS_DIR

COUNTY_SHP = os.path.join(SOURCE_DIR, "tl_2024_us_county", "tl_2024_us_county.shp")

OUT_GEOJSON = os.path.join(BOUNDARY_DIR, "us_counties.geojson")
OUT_CSV = os.path.join(BOUNDARY_DIR, "us_counties.csv")

TARGET_CRS = "EPSG:4326"

GEOJSON_COLUMNS = [
    "STATEFP", "COUNTYFP", "GEOID", "NAME", "NAMELSAD", "LSAD", "CLASSFP",
    "ALAND", "AWATER", "INTPTLAT", "INTPTLON", "geometry",
]

CSV_COLUMNS = [
    "state_fips", "county_fips", "geoid", "name", "namelsad", "lsad", "classfp",
    "aland", "awater", "intptlat", "intptlon", "geometry_wkt",
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


def build_geojson():
    print("Processing counties (national)...")
    gdf = gpd.read_file(COUNTY_SHP)
    gdf = gdf.to_crs(TARGET_CRS)
    gdf = fix_geometries(gdf)
    gdf = gdf[GEOJSON_COLUMNS].copy()
    gdf = gdf.sort_values(["STATEFP", "COUNTYFP"]).reset_index(drop=True)

    os.makedirs(BOUNDARY_DIR, exist_ok=True)
    gdf.to_file(OUT_GEOJSON, driver="GeoJSON")
    print(f"  {len(gdf)} counties -> {OUT_GEOJSON}")
    return gdf


def build_csv():
    print("Converting to CSV...")
    with open(OUT_GEOJSON, "r") as f:
        data = json.load(f)

    prop_keys = ["STATEFP", "COUNTYFP", "GEOID", "NAME", "NAMELSAD", "LSAD", "CLASSFP",
                 "ALAND", "AWATER", "INTPTLAT", "INTPTLON"]

    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for feature in data["features"]:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            writer.writerow(
                [props.get(k, "") for k in prop_keys] + [geometry_to_wkt(geom)]
            )

    print(f"  {len(data['features'])} rows -> {OUT_CSV}")


def validate():
    print("\nValidation:")
    gdf = gpd.read_file(OUT_GEOJSON)
    print(f"  Features: {len(gdf)}, CRS: {gdf.crs}")
    print(f"  Geometries valid: {gdf.geometry.is_valid.all()}")
    print(f"  Null geometries: {gdf.geometry.isna().sum()}")
    print(f"  Unique states: {gdf['STATEFP'].nunique()}")
    print(f"  GEOID = STATEFP + COUNTYFP: {(gdf['GEOID'] == gdf['STATEFP'] + gdf['COUNTYFP']).all()}")
    for path in [OUT_GEOJSON, OUT_CSV]:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  {os.path.basename(path)}: {size_mb:.1f} MB")


def main():
    if not os.path.exists(COUNTY_SHP):
        print(f"Error: {COUNTY_SHP} not found", file=sys.stderr)
        print("Download from: https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip", file=sys.stderr)
        sys.exit(1)

    build_geojson()
    build_csv()
    validate()
    print("\nDone!")


if __name__ == "__main__":
    main()
