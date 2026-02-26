# TMF Deal Data Pipeline

Processing scripts for Trinity Mortgage Fund loan/deal data. Merges the web-facing deal records with the internal loan history spreadsheet, normalizes formats, and geocodes addresses.

## Data Sources

- **deals_rows** — Exported from Supabase (website deal cards with address, amount, date, product type, images)
- **Loan History.csv** — Excel export from TMF internal tracking (status, due dates, interest rates, funding breakdowns, borrower/broker info)

## Pipeline

Run from the project root in this order:

```bash
# 1. Merge deals with loan history (matches on address + location)
python scripts/tmf/merge_deals_loans.py

# 2. Rename columns to descriptive names, merge address fields
python scripts/tmf/clean_columns.py

# 3. Normalize dates (ISO), money (raw numbers), booleans
python scripts/tmf/normalize_data.py

# 4. Geocode addresses (requires GOOGLE_GEOCODING_API_KEY in .env)
python scripts/geopoints/google/geocode_deals.py

# 5. Add Census GeoIDs (state, county, tract FIPS codes)
python scripts/geopoints/census-geoid/census_geoids.py
```

## Output

`data/tmf/deals_rows.csv` — 140 deals, 33 columns including coordinates and Census GeoIDs.

## Required Keys

- `GOOGLE_GEOCODING_API_KEY` in `.env` for step 4
