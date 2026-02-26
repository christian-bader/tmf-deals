# Property Listing Monitor

Tools for monitoring new real estate listings in target zip codes and extracting broker information.

## Components

1. **generate_redfin_urls.py** - Generates Redfin saved search URLs for all target zip codes
2. **parse_listing_emails.py** - Parses Redfin alert emails to extract listing data
3. **lookup_dre_license.py** - Looks up California DRE license info by number or name
4. **filter_dre_by_zip.py** - Filters CA DRE licensee database to target zip codes

## California DRE Licensee Database

The CA Department of Real Estate provides a **free daily-updated database** of all 437K+ real estate licensees in California:

**Source:** https://www.dre.ca.gov/Licensees/ExamineeLicenseeListDataFiles.html

**Files:**
- `CurrList.csv` - Full licensee database (updated daily)
- `new_licensees.xls` - New licensees (updated weekly on Monday)

**Data includes:**
| Field | Description |
|-------|-------------|
| `lic_number` | DRE license number |
| `lastname_primary`, `firstname_secondary` | Name |
| `lic_type` | Broker, Salesperson, Corporation, Officer |
| `lic_status` | Licensed, Expired, etc. |
| `address_1`, `city`, `state`, `zip_code` | Business address |
| `county_name` | County |
| `related_lic_number`, `related_lastname_primary` | Supervising broker (for salespersons) |

**Workflow:**
1. Download `CurrList.csv` from DRE website → save to `data/ca-dre/`
2. Run `filter_dre_by_zip.py` to filter to target markets
3. Cross-reference with listing agent DRE numbers from Redfin/Zillow

## Target Zip Codes

### San Diego Coastal/North (14)
92037, 92014, 92075, 92024, 92007, 92118, 92106, 92107, 92109, 92011, 92008, 92130, 92127, 92029

### Orange County Coastal (11)
92651, 92629, 92624, 92672, 92657, 92625, 92663, 92661, 92662, 92648, 92649

### LA South Bay / Palos Verdes (9)
90274, 90275, 90277, 90278, 90254, 90266, 90292, 90732, 90731

## Quick Start

### 1. Set up listing alerts (one-time)
```bash
python scripts/listings/generate_redfin_urls.py
# Open each URL → click "Save Search" → set to "Daily"
```

### 2. Download & filter DRE database (refresh weekly)
```bash
# Download CurrList.csv from:
# https://www.dre.ca.gov/Licensees/ExamineeLicenseeListDataFiles.html
# Save to data/ca-dre/CurrList.csv

python scripts/listings/filter_dre_by_zip.py
# Outputs:
#   data/ca-dre/target_licensees.csv (26K+ licensees)
#   data/ca-dre/brokers_by_zip.csv (6.5K+ brokers)
```

### 3. Process daily alerts
When you get Redfin email alerts:
1. Note the listing agent name + DRE number from listing page
2. Look up in `brokers_by_zip.csv` for contact info
3. Or run: `python scripts/listings/lookup_dre_license.py --license 01487611`

## Full Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  MONITORING                                                  │
├─────────────────────────────────────────────────────────────┤
│  Redfin Daily Alerts (34 zip codes)                         │
│         ↓                                                    │
│  New listing appears                                         │
│         ↓                                                    │
│  Extract: address, price, listing agent, DRE #               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  ENRICHMENT                                                  │
├─────────────────────────────────────────────────────────────┤
│  Cross-reference DRE # with target_licensees.csv            │
│         ↓                                                    │
│  Get: broker address, license status, expiration            │
│         ↓                                                    │
│  If salesperson → get supervising broker info               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  OUTREACH                                                    │
│  Contact listing broker with your value proposition          │
└─────────────────────────────────────────────────────────────┘
```

## Output Files

| File | Records | Description |
|------|---------|-------------|
| `target_licensees.csv` | 26,277 | All licensees in target zips |
| `brokers_by_zip.csv` | 6,589 | Brokers only, sorted by zip |

## Sample Broker Record

```csv
name,dre_number,address,city,zip,county,status,expires
Lowell Norman Brown,00025634,65 19TH ST,HERMOSA BEACH,90254,LOS ANGELES,Licensed,20280320
```
