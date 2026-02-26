"""Re-run ATTOM scraper for San Diego County only."""
import sys
sys.path.insert(0, ".")
from scripts.attom_sales_scraper import scrape_county
from pathlib import Path

output_dir = Path("data")
output_dir.mkdir(exist_ok=True)

print("Re-running San Diego County scraper...")
scrape_county(
    county_name="san_diego",
    county_geo_id="CO06073",
    start_date="2021/02/24",
    end_date="2026/02/24",
    output_dir=str(output_dir),
    min_sale=1_000_000,
    max_sale=10_000_000,
)
