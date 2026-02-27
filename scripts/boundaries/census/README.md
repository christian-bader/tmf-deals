# Census Boundary Scripts

Build national boundary datasets from TIGER/Line shapefiles published by the U.S. Census Bureau.

## Source

**TIGER/Line Shapefiles (2024)**
https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html

Downloaded from:
- States: `https://www2.census.gov/geo/tiger/TIGER2024/STATE/tl_2024_us_state.zip`
- Counties: `https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip`
- ZCTAs: `https://www2.census.gov/geo/tiger/TIGER2024/ZCTA520/tl_2024_us_zcta520.zip`

## Scripts

| Script | Output | Description |
|--------|--------|-------------|
| `build_state_geodata.py` | `us_states.geojson` + `.csv` | All US state boundaries |
| `build_county_geodata.py` | `us_counties.geojson` + `.csv` | All US county boundaries |
| `build_zcta_geodata.py` | `us_zctas.geojson` + `.csv` | All US ZIP Code Tabulation Areas |
| `build_socal_zctas.py` | `frontend/public/socal_zctas.geojson` | SoCal ZCTAs only (for Search Configuration map) |

## Usage

1. Download and extract the TIGER/Line zip into `data/boundaries/census/source/`
2. Run the build script from the project root:

```bash
python scripts/boundaries/census/build_county_geodata.py
```

## Output Format

- GeoJSON in WGS84 (EPSG:4326)
- CSV includes WKT geometry column for database import
- State-specific subsets can be filtered from the national datasets using STATEFP (e.g., `06` = California, `13` = Georgia)
