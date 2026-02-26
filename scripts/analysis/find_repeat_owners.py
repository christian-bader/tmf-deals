"""
Identify multi-property owners from SD County parcel data.

Input:  data/boundaries/california/san-diego/parcels/parcels_san_diego_filtered.csv
Output: data/analysis/repeat_owners_from_parcels.csv      (aggregated by owner)
        data/analysis/repeat_owners_properties_detail.csv  (individual parcels)
        data/analysis/hard_money_leads.csv                 (ranked leads)

A "repeat owner" is any OWN_NAME1 appearing on 2+ parcels.
"""

import csv
import os
from collections import defaultdict

INPUT_PATH = "data/boundaries/california/san-diego/parcels/parcels_san_diego_filtered.csv"
OUTPUT_DIR = "data/analysis"

MIN_PROPERTIES = 2


def run():
    with open(INPUT_PATH, newline="", encoding="utf-8") as f:
        parcels = list(csv.DictReader(f))

    owner_parcels = defaultdict(list)
    for p in parcels:
        owner = (p.get("OWN_NAME1") or "").strip()
        if not owner:
            continue
        owner_parcels[owner].append(p)

    repeat_owners = {o: ps for o, ps in owner_parcels.items() if len(ps) >= MIN_PROPERTIES}
    print(f"Total owners: {len(owner_parcels):,}")
    print(f"Repeat owners (>={MIN_PROPERTIES} properties): {len(repeat_owners):,}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Aggregated summary
    summary_path = os.path.join(OUTPUT_DIR, "repeat_owners_from_parcels.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Owner_Name", "Property_Count", "Total_Est_Value", "Avg_Property_Value",
                         "ZIPs_Active", "ZIP_Count", "Sample_Properties"])
        for owner, ps in sorted(repeat_owners.items(), key=lambda x: len(x[1]), reverse=True):
            values = [int(p["ASR_TOTAL"]) for p in ps if p.get("ASR_TOTAL") and p["ASR_TOTAL"] != "0"]
            total_val = sum(values)
            avg_val = total_val // len(values) if values else 0
            zips = sorted(set(p.get("SITUS_ZIP", "").strip()[:5] for p in ps if p.get("SITUS_ZIP", "").strip()))
            sample = "; ".join(
                f"{p.get('FULL_SITUS_ADDRESS', '?')} ({p.get('SITUS_ZIP', '').strip()[:5]})"
                for p in ps[:3]
            )
            writer.writerow([owner, len(ps), f"${total_val:,}", f"${avg_val:,}",
                             ", ".join(zips), len(zips), sample])
    print(f"  -> {summary_path}")

    # Detail: individual parcels per owner
    detail_path = os.path.join(OUTPUT_DIR, "repeat_owners_properties_detail.csv")
    with open(detail_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Owner_Name", "APN", "Address", "City", "ZIP", "Assessed_Value",
                         "Est_Market_Value", "Beds", "Baths", "SqFt", "Doc_Date", "Doc_Num"])
        for owner, ps in sorted(repeat_owners.items(), key=lambda x: len(x[1]), reverse=True):
            for p in ps:
                writer.writerow([
                    owner, p.get("APN", ""), p.get("FULL_SITUS_ADDRESS", ""),
                    p.get("SITUS_COMMUNITY", ""), p.get("SITUS_ZIP", "").strip()[:5],
                    p.get("ASR_TOTAL", ""), p.get("ASR_TOTAL", ""),
                    p.get("BEDROOMS", ""), p.get("BATHS", ""), p.get("TOTAL_LVG_AREA", ""),
                    p.get("DOCDATE", ""), p.get("DOCNMBR", ""),
                ])
    print(f"  -> {detail_path}")

    # Hard money leads: ranked by property count, with value
    leads_path = os.path.join(OUTPUT_DIR, "hard_money_leads.csv")
    with open(leads_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Rank", "Owner_Name", "Property_Count", "Total_Est_Value",
                         "ZIPs_Active", "ZIP_Count", "Sample_Properties"])
        ranked = sorted(repeat_owners.items(), key=lambda x: len(x[1]), reverse=True)
        for rank, (owner, ps) in enumerate(ranked, 1):
            values = [int(p["ASR_TOTAL"]) for p in ps if p.get("ASR_TOTAL") and p["ASR_TOTAL"] != "0"]
            total_val = sum(values)
            zips = sorted(set(p.get("SITUS_ZIP", "").strip()[:5] for p in ps if p.get("SITUS_ZIP", "").strip()))
            sample = "; ".join(
                f"{p.get('FULL_SITUS_ADDRESS', '?')} ({p.get('SITUS_ZIP', '').strip()[:5]})"
                for p in ps[:3]
            )
            writer.writerow([rank, owner, len(ps), f"${total_val:,}",
                             ", ".join(zips), len(zips), sample])
    print(f"  -> {leads_path}")


if __name__ == "__main__":
    run()
