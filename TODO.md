# TODO

## Scraper Improvements

- [x] **Buyer's agent extraction** - Add fields for buyer's agent (name, DRE, brokerage, phone, email) from "Bought with" section on Redfin listings
  - Usage: `python scrape_current_listings.py --all-zips --sold --output daily/recently_sold.csv`

## Contact Enrichment

**Current (POC):**
- [x] Brokerage pattern inference (`enrich_emails.py`) - +329 emails (50% → 74%)

**Future (MLS access):**
- [ ] SDMLS API integration - agent emails via MLS Router
- [ ] CRMLS API integration - agent emails via Trestle
- [ ] DRE lookup by email (reverse match)

## Parcel Data

- [ ] **Orange County parcel shapefiles** - Need to find data source for OC parcels (zips: 92651, 92629, 92624, 92672, 92657, 92625, 92663, 92661, 92662, 92648, 92649)
- [ ] **LA County parcel shapefiles** - Need to find data source for LA parcels (zips: 90274, 90275, 90277, 90278, 90254, 90266, 90292, 90732, 90731)

## Data Linking

- [ ] Link listings to parcel shapes (see investigation notes below)
