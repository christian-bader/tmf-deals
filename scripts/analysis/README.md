# Analysis Scripts

Derived datasets that combine raw data sources to surface leads and patterns.

## Data Lineage

```
ATTOM DB (data/attom/attom_sales_transactions.db)
  └─ all_qualified_sales.csv         Export of all sales
      └─ repeat_buyers_with.csv      Group by buyer_name, 2+ purchases
          └─ repeat_buyers_enriched  Add buyer type classification
          └─ repeat_buyers_all       Expand back to individual transactions

SD Parcels (data/boundaries/california/san-diego/parcels/)
  └─ repeat_owners_parcels.csv       Group by OWN_NAME1, 2+ properties
      └─ repeat_owners_detail.csv    Expand to individual parcels
  └─ hard_money_leads.csv            Ranked multi-property owners
```

## Scripts

| Script | Input | Output | Description |
|--------|-------|--------|-------------|
| `export_qualified_sales.py` | ATTOM DB | `all_qualified_sales.csv` | Export all sales from SQLite |
| `find_repeat_buyers.py` | `all_qualified_sales.csv` | `repeat_buyers_*.csv` | Identify repeat buyers from sales |
| `find_repeat_owners.py` | SD parcels CSV | `repeat_owners_*.csv`, `hard_money_leads.csv` | Identify multi-property owners from assessor data |

## Output

All outputs go to `data/analysis/`.
