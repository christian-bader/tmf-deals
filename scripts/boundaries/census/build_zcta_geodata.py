#!/usr/bin/env python3
"""
Export all US ZIP Code Tabulation Areas (ZCTAs) as Foundry-ready GeoJSON and CSV.

Source:
  - TIGER/Line 2024 ZCTA shapefile (national)
  - Download: https://www2.census.gov/geo/tiger/TIGER2024/ZCTA520/tl_2024_us_zcta520.zip

Outputs:
  - data/boundaries/census/us_zctas.geojson
  - data/boundaries/census/us_zctas.csv

GeoJSON is in WGS 84 (EPSG:4326), ready for Palantir Foundry import
via Pipeline Builder's parseGeoJsonV1 transform.

GEOID20 is the 5-digit ZCTA code (approximates USPS ZIP codes).
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

ZCTA_SHP = os.path.join(SOURCE_DIR, "tl_2024_us_zcta520", "tl_2024_us_zcta520.shp")

OUT_GEOJSON = os.path.join(BOUNDARY_DIR, "us_zctas.geojson")
OUT_CSV = os.path.join(BOUNDARY_DIR, "us_zctas.csv")

TARGET_CRS = "EPSG:4326"

GEOJSON_COLUMNS = [
    "ZCTA5CE20", "GEOID20", "ALAND20", "AWATER20", "INTPTLAT20", "INTPTLON20", "geometry",
]

CSV_COLUMNS = [
    "zcta5", "geoid", "aland", "awater", "intptlat", "intptlon", "geometry_wkt",
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
    print("Processing ZCTAs (national)...")
    gdf = gpd.read_file(ZCTA_SHP)
    gdf = gdf.to_crs(TARGET_CRS)
    gdf = fix_geometries(gdf)
    gdf = gdf[GEOJSON_COLUMNS].copy()
    gdf = gdf.sort_values("ZCTA5CE20").reset_index(drop=True)

    os.makedirs(BOUNDARY_DIR, exist_ok=True)
    gdf.to_file(OUT_GEOJSON, driver="GeoJSON")
    print(f"  {len(gdf)} ZCTAs -> {OUT_GEOJSON}")
    return gdf


def build_csv():
    print("Converting to CSV...")
    with open(OUT_GEOJSON, "r") as f:
        data = json.load(f)

    prop_keys = ["ZCTA5CE20", "GEOID20", "ALAND20", "AWATER20", "INTPTLAT20", "INTPTLON20"]

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
    print(f"  Sample ZCTAs: {gdf['ZCTA5CE20'].head(5).tolist()}")
    for path in [OUT_GEOJSON, OUT_CSV]:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  {os.path.basename(path)}: {size_mb:.1f} MB")


def main():
    if not os.path.exists(ZCTA_SHP):
        print(f"Error: {ZCTA_SHP} not found", file=sys.stderr)
        print("Download from: https://www2.census.gov/geo/tiger/TIGER2024/ZCTA520/tl_2024_us_zcta520.zip", file=sys.stderr)
        print(f"Extract to: {os.path.dirname(ZCTA_SHP)}/", file=sys.stderr)
        sys.exit(1)

    build_geojson()
    build_csv()
    validate()
    print("\nDone!")


if __name__ == "__main__":
    main()
