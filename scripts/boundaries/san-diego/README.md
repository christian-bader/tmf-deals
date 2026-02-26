# San Diego County Parcel Scripts

Download parcel data (ownership, assessed values, boundaries) from the San Diego County Assessor.

## Source

**San Diego County PARCELS_ALL — Public ArcGIS FeatureServer**
`https://gis-public.sandiegocounty.gov/arcgis/rest/services/sdep_warehouse/PARCELS_ALL/FeatureServer/0`

Live county assessor data — updates as deeds are recorded. Contains 1M+ parcels with coordinates, assessed values, property details, and last recorded document info.

## Scripts

| Script | Output | Description |
|--------|--------|-------------|
| `download_parcels.py` | `parcels_san_diego.csv` | Parcel attributes (no geometry) — owner, values, characteristics |
| `download_parcel_shapes.py` | `parcels_san_diego_shapes.geojson` | Full polygon boundaries in WGS84, filtered to target ZIPs |

## Usage

```bash
# All parcels (attributes only)
python scripts/boundaries/san-diego/download_parcels.py

# Parcel boundary polygons (target ZIPs only)
caffeinate -i python scripts/boundaries/san-diego/download_parcel_shapes.py
```

## Target ZIPs

92037, 92014, 92075, 92024, 92007, 92118, 92106, 92107, 92109, 92011, 92008, 92130, 92127, 92029

## Output Location

`data/boundaries/san-diego/`

## Notes

- Coordinates in the CSV are State Plane NAD83 (feet), not WGS84 lat/lon
- The GeoJSON shapes script outputs WGS84 (EPSG:4326) ready for web mapping
- Does NOT contain actual sale prices — cross-reference with ATTOM or the Assessor's 408.1 property sales report
