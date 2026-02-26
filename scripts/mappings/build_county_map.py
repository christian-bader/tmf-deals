#!/usr/bin/env python3
"""
Build county-to-municipality mapping from TIGER/Line geospatial data.

Derives the mapping via spatial join (place centroids within county polygons)
so the JSON is guaranteed consistent with the GeoJSON boundary files.

Sources:
  - data/boundaries/census/us_counties.geojson (filtered to GA)
  - National places shapefile (not yet sourced)

Output:
  - data/mappings/county_municipality_map.json
"""

import json
import os
import re
import sys
import warnings

import geopandas as gpd

warnings.filterwarnings("ignore", message=".*geographic CRS.*")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

GEODATA_DIR = os.path.join(PROJECT_ROOT, "data", "geodata")
COUNTIES_GEOJSON = os.path.join(GEODATA_DIR, "boundaries", "ga_counties.geojson")
PLACES_GEOJSON = os.path.join(GEODATA_DIR, "boundaries", "ga_places.geojson")
OUTPUT_PATH = os.path.join(GEODATA_DIR, "mappings", "county_municipality_map.json")


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = s.replace(".", "").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def main():
    for path in [COUNTIES_GEOJSON, PLACES_GEOJSON]:
        if not os.path.exists(path):
            print(f"Error: {path} not found. Run build_boundary_geodata.py first.", file=sys.stderr)
            sys.exit(1)

    print("Loading geospatial data...")
    counties = gpd.read_file(COUNTIES_GEOJSON)
    places = gpd.read_file(PLACES_GEOJSON)
    print(f"  {len(counties)} counties, {len(places)} places")

    print("Spatial join (place centroids -> counties)...")
    places_pts = places.copy()
    places_pts["geometry"] = places_pts.geometry.centroid
    joined = gpd.sjoin(places_pts, counties, how="left", predicate="within")

    print("Building map...")
    result = {}

    for _, row in counties.iterrows():
        county_geoid = row["GEOID"]
        county_name = row["NAME"]
        county_slug = slugify(county_name) + "-county"

        county_places = joined[joined["GEOID_right"] == county_geoid]

        municipalities = []
        for _, p in county_places.iterrows():
            place_name = p["NAME_left"]
            place_geoid = p["GEOID_left"]
            lsad = p["LSAD_left"]

            if lsad == "25":
                place_type = "city"
            elif lsad == "43":
                place_type = "town"
            elif lsad in ("UG", "CG"):
                place_type = "consolidated"
            else:
                place_type = "other"

            municipalities.append({
                "name": place_name,
                "slug": slugify(place_name),
                "geoid": place_geoid,
                "type": place_type,
                "aland": int(p["ALAND_left"]),
            })

        municipalities.sort(key=lambda m: m["name"])

        result[county_slug] = {
            "county_name": county_name,
            "slug": county_slug,
            "geoid": county_geoid,
            "aland": int(row["ALAND"]),
            "awater": int(row["AWATER"]),
            "num_municipalities": len(municipalities),
            "municipalities": municipalities,
        }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    total_munis = sum(c["num_municipalities"] for c in result.values())
    counties_with_munis = sum(1 for c in result.values() if c["num_municipalities"] > 0)

    print(f"\nDone! Wrote {OUTPUT_PATH}")
    print(f"  Counties: {len(result)}")
    print(f"  Total municipalities: {total_munis}")
    print(f"  Counties with municipalities: {counties_with_munis}")
    print(f"  Counties with none: {len(result) - counties_with_munis}")


if __name__ == "__main__":
    main()
