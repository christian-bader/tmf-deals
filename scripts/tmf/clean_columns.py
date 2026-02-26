import csv

FILE = "data/tmf/deals_rows.csv"

COLUMN_RENAMES = {
    "id": "id",
    "display_address": "display_name",
    "address": "address",
    "location": "city_state",
    "status": "loan_status",
    "amount": "deal_amount",
    "date": "date_funding",
    "due_date": "date_due",
    "loan_commitment": "loan_commitment",
    "interest_rate": "interest_rate",
    "tam1_funded": "tam1_funded",
    "tof_funded": "tof_funded",
    "tpl_funded": "tpl_funded",
    "third_party_funded": "third_party_funded",
    "tmf_funded": "tmf_funded",
    "tmf_loan_paydowns": "tmf_loan_paydowns",
    "remaining_holdback": "remaining_holdback",
    "monthly_to_tmf": "monthly_to_tmf",
    "geographic_dist": "geographic_district",
    "product": "product_type",
    "borrower_concent": "borrower_concentration",
    "broker_production": "broker_production",
    "image": "image_url",
    "video_link": "has_video",
    "created_at": "created_at",
    "latitude": "latitude",
    "longitude": "longitude",
}

with open(FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

for row in rows:
    row["address"] = row["full_address"]

OUTPUT_FIELDS = list(COLUMN_RENAMES.values())

with open(FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
    writer.writeheader()
    for row in rows:
        out = {}
        for old_key, new_key in COLUMN_RENAMES.items():
            out[new_key] = row.get(old_key, "")
        writer.writerow(out)

print(f"Updated {FILE}")
print(f"Columns ({len(OUTPUT_FIELDS)}): {', '.join(OUTPUT_FIELDS)}")
print(f"Rows: {len(rows)}")
