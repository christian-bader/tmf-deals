import csv
import re

DEALS_FILE = "data/tmf/deals_rows.csv"
LOAN_FILE = "Loan History.csv"
OUTPUT_FILE = "data/tmf/deals_rows.csv"


def parse_loan_history(path):
    """Parse the messy spreadsheet-export CSV, skipping header/footer rows."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        all_rows = list(reader)

    # Data rows start at row index 7 (0-based), header info is in rows 5-6
    data = []
    for row in all_rows[7:]:
        if not row or not row[0].strip():
            break
        try:
            int(row[0].strip())
        except ValueError:
            break

        entry = {
            "loan_number": row[0].strip(),
            "status": row[1].strip(),
            "loan_description": row[2].strip(),
            "location": row[3].strip(),
            "funding_date": row[4].strip(),
            "due_date": row[5].strip(),
            "loan_commitment": row[6].strip(),
            "tam1_funded": row[7].strip(),
            "tof_funded": row[8].strip(),
            "tpl_funded": row[9].strip(),
            "third_party_funded": row[10].strip(),
            "tmf_funded": row[11].strip(),
            "tmf_loan_paydowns": row[12].strip(),
            "remaining_holdback": row[13].strip(),
            "interest_rate": row[14].strip(),
            "monthly_to_tmf": row[15].strip(),
            "geographic_dist": row[16].strip(),
            "product_type": row[17].strip(),
            "borrower_concent": row[18].strip(),
            "broker_production": row[19].strip(),
        }
        data.append(entry)
    return data


def normalize(s):
    return re.sub(r'[\s,.\-#]+', '', s).lower()


def match_loans_to_deals(deals, loans):
    """Match loan history rows to deals by address+location, with duplicate handling."""
    # Group loans by normalized address+location to handle duplicates
    from collections import defaultdict
    loan_groups = defaultdict(list)
    for loan in loans:
        key = normalize(loan["loan_description"]) + "|" + normalize(loan["location"])
        loan_groups[key].append(loan)

    loan_by_num = {loan["loan_number"]: loan for loan in loans}

    matched = 0
    unmatched_deals = []
    for deal in deals:
        loc_field = "location" if "location" in deal else "city_state"
        addr_key = normalize(deal["address"]) + "|" + normalize(deal[loc_field])
        candidates = loan_groups.get(addr_key, [])

        loan = None
        if len(candidates) == 1:
            loan = candidates[0]
        elif len(candidates) > 1:
            # Multiple loans at same address — match by closest loan number to deal id
            for c in candidates:
                if c["loan_number"] == deal["id"]:
                    loan = c
                    break
            if not loan:
                # Fall back to funding date proximity
                loan = min(candidates, key=lambda c: abs(int(c["loan_number"]) - int(deal["id"])))
            print(f"  [dup] deal {deal['id']} ({deal['address']}) → loan #{loan['loan_number']}")

        if not loan:
            loan = loan_by_num.get(deal["id"])

        if loan:
            deal["_loan"] = loan
            matched += 1
        else:
            unmatched_deals.append(deal)
            deal["_loan"] = None

    print(f"Matched: {matched}/{len(deals)}")
    if unmatched_deals:
        print("Unmatched deals:")
        for d in unmatched_deals:
            print(f"  [{d['id']}] {d['address']}, {d['location']}")

    return deals


with open(DEALS_FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    deals = list(reader)

loans = parse_loan_history(LOAN_FILE)
print(f"Loaded {len(deals)} deals, {len(loans)} loans\n")

deals = match_loans_to_deals(deals, loans)

LOAN_FIELDS = [
    "status", "due_date", "loan_commitment",
    "tam1_funded", "tof_funded", "tpl_funded", "third_party_funded",
    "tmf_funded", "tmf_loan_paydowns", "remaining_holdback",
    "interest_rate", "monthly_to_tmf",
    "geographic_dist", "borrower_concent", "broker_production",
]

OUTPUT_FIELDS = [
    "id", "display_address", "address", "location", "full_address",
    "status", "amount", "date", "due_date",
    "loan_commitment", "interest_rate",
    "tam1_funded", "tof_funded", "tpl_funded", "third_party_funded",
    "tmf_funded", "tmf_loan_paydowns", "remaining_holdback", "monthly_to_tmf",
    "geographic_dist", "product", "borrower_concent", "broker_production",
    "image", "video_link", "created_at",
    "latitude", "longitude",
]

output_rows = []
for deal in deals:
    row = {k: deal.get(k, "") for k in OUTPUT_FIELDS}
    loan = deal.get("_loan")
    if loan:
        for field in LOAN_FIELDS:
            row[field] = loan.get(field, "")
    output_rows.append(row)

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
    writer.writeheader()
    writer.writerows(output_rows)

print(f"\nWritten {len(output_rows)} rows to {OUTPUT_FILE}")
print(f"Columns: {len(OUTPUT_FIELDS)}")
