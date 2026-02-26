"""
Export all qualified sales from the ATTOM SQLite DB to CSV.

Input:  data/attom/attom_sales_transactions.db
Output: data/analysis/all_qualified_sales.csv
"""

import csv
import os
import sqlite3

DB_PATH = "data/attom/attom_sales_transactions.db"
OUTPUT_PATH = "data/analysis/all_qualified_sales.csv"

COLUMNS = [
    "attom_id", "address", "city", "zip", "property_type",
    "sale_amt", "sale_date", "sale_trans_type", "buyer_name", "seller_name",
]


def export():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cur = conn.execute("""
        SELECT attom_id, address, city, zip, property_type,
               sale_amt, sale_date, sale_trans_type, buyer_name, seller_name
        FROM sales
        ORDER BY sale_date DESC
    """)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        count = 0
        for row in cur:
            writer.writerow(dict(row))
            count += 1

    conn.close()
    print(f"Exported {count:,} sales to {OUTPUT_PATH}")


if __name__ == "__main__":
    export()
