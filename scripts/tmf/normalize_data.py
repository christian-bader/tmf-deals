import csv
from datetime import datetime

FILE = "data/tmf/deals_rows.csv"

MONEY_COLS = [
    "deal_amount", "loan_commitment",
    "tam1_funded", "tof_funded", "tpl_funded", "third_party_funded",
    "tmf_funded", "tmf_loan_paydowns", "remaining_holdback", "monthly_to_tmf",
]


def parse_money(s):
    s = s.strip().replace("$", "").replace(",", "").replace(" ", "")
    if not s or s == "-":
        return ""
    neg = "(" in s
    s = s.replace("(", "").replace(")", "")
    val = float(s)
    if neg:
        val = -val
    if val == int(val):
        return str(int(val))
    return f"{val:.2f}"


def normalize_date_us(s):
    """Convert M/D/YY to YYYY-MM-DD."""
    s = s.strip()
    if not s:
        return ""
    try:
        dt = datetime.strptime(s, "%m/%d/%y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return s


with open(FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    old_fields = reader.fieldnames
    rows = list(reader)

DROP_COLS = {"created_at"}
new_fields = [f for f in old_fields if f not in DROP_COLS]

for row in rows:
    # Normalize dates to ISO
    row["date_funding"] = normalize_date_us(row["date_funding"])
    row["date_due"] = normalize_date_us(row["date_due"])

    # Normalize money columns to raw numbers
    for col in MONEY_COLS:
        row[col] = parse_money(row[col])

    # Normalize has_video to boolean
    row["has_video"] = "true" if row["has_video"].strip().lower() == "true" else "false"

with open(FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=new_fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

print(f"Updated {FILE}")
print(f"Columns ({len(new_fields)}): {', '.join(new_fields)}")
print(f"Dropped: {DROP_COLS}")
print(f"Rows: {len(rows)}")

# Verify
with open(FILE) as f:
    sample = list(csv.DictReader(f))
r = sample[0]
print(f"\nSample row 1:")
print(f"  date_funding={r['date_funding']}  date_due={r['date_due']}")
print(f"  deal_amount={r['deal_amount']}  loan_commitment={r['loan_commitment']}  tmf_funded={r['tmf_funded']}")
print(f"  has_video={r['has_video']}")
