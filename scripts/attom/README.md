# ATTOM API Scripts

Property data and sales transaction scripts using the ATTOM Data Solutions API.

## Source

**ATTOM Data Solutions API**
`https://api.gateway.attomdata.com/propertyapi/v1.0.0`

Requires `ATTOM_API_KEY` in `.env`.

## Scripts

| Script | Description |
|--------|-------------|
| `attom_sales_scraper.py` | Bulk download sale transactions by county, date range, and price filters. Paginates in quarterly batches. |
| `attom_fetch.py` | Low-level API fetch utility |
| `attom_property_details.py` | Fetch detailed property info by ATTOM ID |
| `attom_find_repeat_transactors.py` | Identify repeat buyers/sellers across transactions |
| `attom_estimate_scale.py` | Estimate total available records for planning API usage |
| `attom_rerun_sandiego.py` | Re-run San Diego county sales pull |
| `test_attom.py` | API connectivity test |
| `test_attom_key.py` | API key validation |

## Usage

```bash
# Test API key
python scripts/attom/test_attom_key.py

# Pull sales for a county
python scripts/attom/attom_sales_scraper.py
```

## Notes

- ATTOM API has rate limits — scripts include `RATE_LIMIT_PAUSE` between requests
- Sales data is best used for targeted parcel-level lookups, not bulk analysis
- County codes: San Diego = `CO06073`, Solano = `CO06095`
