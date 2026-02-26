"""
Identify repeat buyers from qualified sales data.

Input:  data/analysis/all_qualified_sales.csv
Output: data/analysis/repeat_buyers_with_transactions.csv   (aggregated by buyer)
        data/analysis/repeat_buyers_enriched.csv            (with buyer type classification)
        data/analysis/repeat_buyers_all_transactions.csv    (individual transactions for repeat buyers)

A "repeat buyer" is any buyer_name appearing in 2+ purchase transactions.
"""

import csv
import os
from collections import defaultdict

INPUT_PATH = "data/analysis/all_qualified_sales.csv"
OUTPUT_DIR = "data/analysis"

MIN_PURCHASES = 2


def classify_buyer(name):
    name_upper = (name or "").upper()
    if any(kw in name_upper for kw in ["LLC", "INC", "CORP", "LP", "PARTNERS", "HOLDINGS", "CAPITAL", "GROUP", "FUND"]):
        return "ENTITY"
    if any(kw in name_upper for kw in ["TRUST", "REVOCABLE", "IRREVOCABLE", "FAMILY"]):
        return "INDIVIDUAL/TRUST"
    return "INDIVIDUAL"


def run():
    with open(INPUT_PATH, newline="", encoding="utf-8") as f:
        sales = list(csv.DictReader(f))

    buyer_txns = defaultdict(list)
    for sale in sales:
        buyer = (sale.get("buyer_name") or "").strip()
        if not buyer:
            continue
        buyer_txns[buyer].append(sale)

    repeat_buyers = {b: txns for b, txns in buyer_txns.items() if len(txns) >= MIN_PURCHASES}
    print(f"Total buyers: {len(buyer_txns):,}")
    print(f"Repeat buyers (>={MIN_PURCHASES} purchases): {len(repeat_buyers):,}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Aggregated summary
    summary_path = os.path.join(OUTPUT_DIR, "repeat_buyers_with_transactions.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Owner", "Purchase_Count", "Total_Volume", "Avg_Purchase",
                         "Earliest", "Latest", "ZIPs", "Sample_Purchases"])
        for buyer, txns in sorted(repeat_buyers.items(), key=lambda x: len(x[1]), reverse=True):
            amounts = [float(t["sale_amt"]) for t in txns if t.get("sale_amt")]
            dates = sorted([t["sale_date"] for t in txns if t.get("sale_date")])
            zips = sorted(set(t["zip"] for t in txns if t.get("zip")))
            total = sum(amounts)
            avg = total / len(amounts) if amounts else 0
            sample = "; ".join(f"{t['sale_date']}: ${float(t['sale_amt']):,.0f}" for t in sorted(txns, key=lambda x: x.get("sale_date", ""), reverse=True)[:3])
            writer.writerow([buyer, len(txns), f"${total:,.0f}", f"${avg:,.0f}",
                             dates[0] if dates else "", dates[-1] if dates else "",
                             ", ".join(zips), sample])
    print(f"  -> {summary_path}")

    # Enriched with buyer type
    enriched_path = os.path.join(OUTPUT_DIR, "repeat_buyers_enriched.csv")
    with open(enriched_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Buyer_Type", "Owner", "Purchase_Count", "Total_Volume", "Avg_Purchase",
                         "Earliest", "Latest", "ZIPs", "ZIP_Count", "Sample_Purchases"])
        for buyer, txns in sorted(repeat_buyers.items(), key=lambda x: len(x[1]), reverse=True):
            amounts = [float(t["sale_amt"]) for t in txns if t.get("sale_amt")]
            dates = sorted([t["sale_date"] for t in txns if t.get("sale_date")])
            zips = sorted(set(t["zip"] for t in txns if t.get("zip")))
            total = sum(amounts)
            avg = total / len(amounts) if amounts else 0
            sample = "; ".join(f"{t['sale_date']}: ${float(t['sale_amt']):,.0f}" for t in sorted(txns, key=lambda x: x.get("sale_date", ""), reverse=True)[:3])
            writer.writerow([classify_buyer(buyer), buyer, len(txns), f"${total:,.0f}", f"${avg:,.0f}",
                             dates[0] if dates else "", dates[-1] if dates else "",
                             ", ".join(zips), len(zips), sample])
    print(f"  -> {enriched_path}")

    # All individual transactions for repeat buyers
    all_txns_path = os.path.join(OUTPUT_DIR, "repeat_buyers_all_transactions.csv")
    with open(all_txns_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Owner", "Address", "City", "ZIP", "Sale_Price", "Sale_Date",
                         "Trans_Type", "Property_Type", "APN"])
        for buyer, txns in sorted(repeat_buyers.items(), key=lambda x: len(x[1]), reverse=True):
            for t in sorted(txns, key=lambda x: x.get("sale_date", "")):
                writer.writerow([buyer, t.get("address", ""), t.get("city", ""), t.get("zip", ""),
                                 t.get("sale_amt", ""), t.get("sale_date", ""),
                                 t.get("sale_trans_type", ""), t.get("property_type", ""), ""])
    print(f"  -> {all_txns_path}")


if __name__ == "__main__":
    run()
