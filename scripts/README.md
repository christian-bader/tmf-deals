# Data Architecture and Guide to Geodata

## Guide to Geodata

### Geographic Hierarchy

Every point in the US falls within a nested set of administrative boundaries. From broadest to most granular:

```
State  →  County  →  Place (municipality/CDP)  →  ZIP (ZCTA)  →  Census Tract  →  Parcel
```

Each layer has an official identifier (GeoID/FIPS code) that serves as a foreign key across datasets.

### Census Geography

The U.S. Census Bureau maintains standardized boundary files for the entire country through the TIGER/Line program. These are the authoritative source for administrative boundaries and are updated annually.

**Available for all 50 states + DC + territories:**

| Layer | GeoID Format | Count | Description |
|-------|--------------|-------|-------------|
| State | 2-digit STATEFP | 56 | States + DC + territories |
| County | 5-digit (STATEFP + COUNTYFP) | ~3,200 | Counties, parishes, boroughs |
| Place | 7-digit (STATEFP + PLACEFP) | ~30,000 | Cities, towns, CDPs |
| ZCTA | 5-digit | ~33,800 | ZIP Code Tabulation Areas |
| Census Tract | 11-digit (state + county + tract) | ~85,000 | Statistical neighborhoods (~4,000 people each) |
| Block Group | 12-digit (tract + block group) | ~240,000 | Sub-tract areas (~1,500 people each) |

**FIPS codes** (Federal Information Processing Standards) are the numeric identifiers. Examples:
- `06` = California, `13` = Georgia
- `06073` = San Diego County (state `06` + county `073`)
- `0644000` = City of Los Angeles (state `06` + place `44000`)

**GeoIDs** are the full composite codes. A Census tract GeoID like `06073017403` means: state `06` + county `073` + tract `017403`.

### Places: Incorporated vs CDP

Census "places" include two types:

| Type | CLASSFP | What it is | Governance | Example |
|------|---------|------------|------------|---------|
| Incorporated place | C1, C2, C5 | City, town, village, borough | Has its own government | Coronado, Encinitas, Del Mar |
| CDP (Census Designated Place) | U1, U2 | Recognized unincorporated community | No own government, part of county | La Jolla, Rancho Santa Fe, Cardiff |

Both are useful. CDPs represent neighborhoods and communities that people recognize even though they're not separate cities. In San Diego County, La Jolla is a CDP within the City of San Diego — it's not a municipality, but it's a critical geographic boundary for real estate.

Filter on `CLASSFP` to get only incorporated places when needed.

### ZIP Codes vs ZCTAs

USPS ZIP codes are delivery routes, not geographic areas — they can cross county/state lines and change over time. The Census Bureau creates **ZCTAs (ZIP Code Tabulation Areas)** as approximate geographic representations of ZIP codes. They're close enough for most analysis but don't perfectly match USPS delivery boundaries.

Join key: match 5-digit ZIP to ZCTA `ZCTA5CE20`.

### Assessor's Parcel Number (APN)

Every parcel of land has an **APN** assigned by the county assessor. APNs are the definitive property identifier within a county. Format varies by county:

| County | APN Format | Example |
|--------|-----------|---------|
| San Diego | 10 digits, no dashes | `3461721200` |
| ATTOM (normalized) | 10 digits with dashes | `346-172-12-00` |

To join ATTOM → county parcels: strip dashes from the ATTOM APN.

APNs are **only unique within a county** — two different counties can have the same APN. Always pair APN with county FIPS for a globally unique key.

### ATTOM Data Model

ATTOM (a commercial property data aggregator) provides property-level data via API. Key identifiers in ATTOM records:

| Field | What it is | Example |
|-------|-----------|---------|
| `attom_id` | ATTOM's internal property ID | `156786314` |
| `identifier.apn` | County APN (dashed) | `346-172-12-00` |
| `identifier.fips` | County FIPS | `06073` |
| `address.oneLine` | Standardized address | `2260 CALLE FRESCOTA, LA JOLLA, CA 92037` |
| `location.geoid` | Census GeoIDs | `CO06073, PL0666000, ZI92037` |
| `location.latitude/longitude` | Coordinates (WGS84) | `32.857470, -117.254315` |

ATTOM's `location.geoid` string contains census identifiers with prefixes: `CO` = county, `CS` = county subdivision, `PL` = place, `ZI` = ZIP, `DB` = school district. This gives you the parcel-to-census linkage in a single lookup.

### Spatial Joins

A **spatial join** links data based on geographic relationships (contains, intersects, nearest) rather than shared keys. Common patterns in this project:

| Operation | What it does | Example |
|-----------|-------------|---------|
| Point-in-polygon | Find which boundary a point falls within | Deal lat/lon → which parcel polygon contains it |
| Centroid containment | Assign a polygon to a larger boundary | Parcel centroid → which place/city is it in |
| Buffer/proximity | Find features within a distance | All parcels within 1 mile of a deal |

Tools: GeoPandas (`sjoin`), PostGIS (`ST_Contains`), Turf.js (browser), or any GIS tool.

**Coordinate Reference Systems (CRS):** All our GeoJSON outputs use WGS84 (EPSG:4326) — standard lat/lon. Some source data (like SD parcel CSV coordinates) use State Plane NAD83 (feet) which needs conversion. The GeoJSON shapefile outputs handle this automatically.

### Geocoding Pipeline

To go from a raw address to a fully linked record:

```
Raw address (e.g., "1170 Pine St, Coronado, CA")
  │
  ├─ 1. Google Geocoding API → lat/lon (handles fuzzy addresses well)
  │
  ├─ 2. Spatial join (lat/lon against parcel polygons) → APN
  │
  ├─ 3. APN → county assessor record (ownership, values, characteristics)
  │
  └─ 4. APN → ATTOM property details (sales history, standardized address)
         └─ ATTOM returns census GeoIDs for free (county, place, ZIP, tract)
```

Google Geocoding resolves fuzzy/informal addresses (neighborhood names, missing suffixes, typos). The Census Geocoder is free but strict — fails on neighborhoods like "Pacific Beach" or new streets. Use Google for address resolution, Census for bulk FIPS lookups on coordinates.

---

## Layer Hierarchy

```
State  →  County  →  Place  →  ZIP (ZCTA)  →  Parcel
```

| Layer | Source | GeoID Format | Example |
|-------|--------|--------------|---------|
| State | Census TIGER/Line | 2-digit FIPS | `06` (California) |
| County | Census TIGER/Line | 5-digit FIPS | `06073` (San Diego) |
| Place | Census TIGER/Line | 7-digit GEOID | `0644000` (Los Angeles) |
| ZIP (ZCTA) | Census TIGER/Line | 5-digit ZCTA | `92037` |
| Parcel | County assessor | APN (varies by county) | `3461721200` |

Census layers are **national and standardized** — one download covers the whole US.
Parcels are **county-specific** — each county assessor publishes differently.

## Data Layout

```
data/
├── boundaries/
│   ├── census/                  # National standardized (TIGER/Line)
│   │   ├── us_states.*          # 50 states + territories
│   │   ├── us_counties.*       # ~3,200 counties
│   │   ├── us_zctas.*          # ~33,800 ZIP code areas
│   │   ├── ca_places.*         # California municipalities (482 incorporated + CDPs)
│   │   └── source/             # Raw .shp files
│   ├── california/
│   │   ├── san-diego/parcels/  # SD County assessor (1M+ parcels, polygon shapes)
│   │   └── los-angeles/parcels/ # LA County assessor (limited public data)
│   └── georgia/                # GA-specific boundaries
│
├── attom/                      # Raw ATTOM API property/sales data
├── analysis/                   # Derived datasets (repeat buyers, leads)
├── tmf/                        # Trinity Mortgage Fund deal data
├── idi/                        # IDI industrial property data
└── mappings/                   # Crosswalk/junction tables
```

## Join Keys

How datasets connect to each other:

```
  Raw Address (fuzzy)
       │
       ├─ Google Geocoding API ─────────────────────┐
       │                                             ▼
       │                                    lat/lon (WGS84)
       │                                             │
       │    ┌──────────────┐                         │ spatial join
       │    │ Census       │◄────── GeoID (FIPS) ────┤
       │    │ Boundaries   │        ZIP code         │
       │    └──────────────┘                         │
       │                                             │ point-in-polygon
       │                                             ▼
       │                                    ┌──────────────┐
       │                                    │ County       │
       │                                    │ Parcels      │ ← APN, polygon geometry
       │                                    └──────┬───────┘
       │                                           │ APN (strip dashes)
       │                                           ▼
       │                                    ┌──────────────┐
       └──── address (standardized) ──────► │ ATTOM        │ ← attom_id, sales, GeoIDs
                                            │ Properties   │
                                            └──────────────┘
```

| From | To | Join Key | Notes |
|------|----|----------|-------|
| Any geocoded point | Census boundaries | `county_geoid`, `tract_geoid`, ZIP | Point-in-polygon or direct FIPS match |
| TMF deals | Census counties | `county_geoid` (e.g., `06073`) | Already on each deal row |
| TMF deals | Parcels | Spatial join (lat/lon → parcel polygon) | Google geocode → point-in-polygon against parcel shapes → get APN |
| Parcels | ATTOM properties | APN | Strip dashes from ATTOM `identifier.apn` (e.g., `346-172-12-00` → `3461721200`) to match parcel `APN` |
| ATTOM properties | Census boundaries | `location.geoid` | ATTOM returns GeoIDs: `CO06073` (county), `PL0666000` (place), `ZI92037` (ZIP) |
| Parcels | Census ZCTAs | `SITUS_ZIP` ↔ ZCTA `ZCTA5CE20` | Match on 5-digit ZIP |
| Parcels | Census places | Spatial join (parcel centroid in place polygon) | Or fuzzy match `SITUS_COMMUNITY` to place `NAME` |

## Scripts Layout

```
scripts/
├── boundaries/
│   ├── census/             # Build national boundary layers from TIGER/Line
│   ├── california/
│   │   └── los-angeles/    # LA County parcel downloads
│   ├── san-diego/          # SD County parcel downloads
│   └── georgia/            # GA county parcel downloads
├── geopoints/              # Geocoding pipelines
│   ├── google/             # Google Geocoding API (address → lat/lon)
│   └── census-geoid/       # Census reverse geocode (lat/lon → FIPS codes)
├── analysis/               # Derived analysis (repeat buyers, leads)
├── attom/                  # ATTOM API data fetching
├── tmf/                    # TMF deal data pipeline
└── mappings/               # County-municipality mapping builders
```

Each folder has its own `README.md` with source URLs, API requirements, and usage.

## Data Sources Summary

| Source | What it provides | Access | Cost |
|--------|-----------------|--------|------|
| [Census TIGER/Line](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) | State, county, ZIP, place boundaries | Free download | Free |
| [Census Geocoder](https://geocoding.geo.census.gov/) | Address → coordinates, FIPS codes | Free API | Free |
| [SD County Assessor](https://gis-public.sandiegocounty.gov/arcgis/rest/services/sdep_warehouse/PARCELS_ALL/FeatureServer/0) | Parcel ownership, values, boundaries | Free ArcGIS API | Free |
| [LA County Assessor](https://services3.arcgis.com/GVgbJbqm8hXASVYi/arcgis/rest/services/LA_County_Parcels/FeatureServer/0) | Parcel values, use codes (no owner names) | Free ArcGIS API | Free |
| OC County Assessor | Parcel data | No public API | Paid (ParcelQuest, roll file request) |
| [Google Geocoding](https://developers.google.com/maps/documentation/geocoding) | Address → coordinates (robust) | API key required | ~$5/1K requests |
| [ATTOM Data](https://api.gateway.attomdata.com/) | Property details, sales history | API key required | Paid subscription |

## Known Gaps

- **Orange County parcels**: No free public API. Need ParcelQuest subscription or assessor roll file request.
- **APN format normalization**: ATTOM uses dashed APNs (`346-172-12-00`), SD parcels use plain digits (`3461721200`). Strip dashes to join. The sales DB (`attom_sales_transactions.db`) lacks APN — use the property detail endpoint or `attom_properties_*.json` bulk files which include it.
- **Census tract boundaries**: Deals have `tract_geoid` but no tract shapefile downloaded yet. Available from TIGER/Line when needed.
- **Municipal assignment for parcels**: Parcels have `SITUS_COMMUNITY` but not a Census place GEOID. Use spatial join against `ca_places.geojson` to assign.
