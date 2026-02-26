# TODO

## Scraper Improvements

- [x] **Buyer's agent extraction** - Add fields for buyer's agent (name, DRE, brokerage, phone, email) from "Bought with" section on Redfin listings
  - Usage: `python scrape_current_listings.py --all-zips --sold --output daily/recently_sold.csv`
- [ ] **Daily scraper pipeline** - Create logic to run scraper every day and append new results as well as update old ones

- [ ] **BUILD ROBUST SCRAPER** - Current scraper has data quality issues:
  - ~135/212 sold listings missing agent name
  - ~105/212 sold listings missing email  
  - Need better HTML parsing for different Redfin page layouts
  - Need fallback strategies when primary patterns fail
  - Consider using Selenium/Playwright for JS-rendered content
  - Add validation layer to flag suspicious data (Redfin corporate DRE, email-name mismatches)

  - CRITICAL: **Co-listing support** - Extract full info for both agents when property is co-listed

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


## Front end

- [ ] **Lite CRM** - Send last emails and view responses and activity from sent emails (functionally a lite CRM)

## Gmail

- [ ] **Gmail integration** - Send emails and look at the inbox 