#!/usr/bin/env python3
"""
Find repeat transactors in coastal SoCal real estate ($1M-$10M range).
These are qualified leads for hard money lending.
"""
import os
import sys
import requests
import json
import csv
import time
import sqlite3
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ATTOM_API_KEY")
BASE_URL = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"

HEADERS = {
    "Accept": "application/json",
    "APIKey": API_KEY
}

# Target ZIP codes (coastal SoCal)
ZIP_CODES = [
    # San Diego County
    92037, 92014, 92075, 92024, 92007, 92118, 92106, 92107, 92109, 92011,
    92008, 92130, 92127, 92029,
    # Orange County
    92651, 92629, 92624, 92672, 92657, 92625, 92663, 92661, 92662, 92648, 92649,
    # LA County (South Bay / Beach Cities)
    90274, 90275, 90277, 90278, 90254, 90266, 90292, 90732, 90731
]

# Price range for hard money sweet spot
MIN_SALE_AMT = 1000000  # $1M
MAX_SALE_AMT = 10000000  # $10M

# Date range (10 years)
START_DATE = "2016/01/01"
END_DATE = "2026/02/24"

DB_FILE = "data/attom/attom_sales_transactions.db"
OUTPUT_CSV = "data/analysis/repeat_transactors.csv"
ALL_SALES_CSV = "data/analysis/all_qualified_sales.csv"

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def init_database():
    """Initialize SQLite database for storing transactions."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attom_id TEXT,
            transaction_id TEXT UNIQUE,
            address TEXT,
            city TEXT,
            zip TEXT,
            property_type TEXT,
            sale_amt REAL,
            sale_date TEXT,
            sale_record_date TEXT,
            sale_trans_type TEXT,
            buyer_name TEXT,
            seller_name TEXT,
            fetched_at TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fetch_progress (
            zip_code TEXT PRIMARY KEY,
            pages_fetched INTEGER,
            total_records INTEGER,
            completed INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    return conn

def get_fetch_progress(conn, zip_code):
    """Get progress for a ZIP code."""
    cursor = conn.cursor()
    cursor.execute("SELECT pages_fetched, completed FROM fetch_progress WHERE zip_code = ?", (str(zip_code),))
    row = cursor.fetchone()
    if row:
        return row[0], row[1]
    return 0, 0

def save_fetch_progress(conn, zip_code, pages_fetched, total_records, completed=0):
    """Save progress for a ZIP code."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO fetch_progress (zip_code, pages_fetched, total_records, completed)
        VALUES (?, ?, ?, ?)
    """, (str(zip_code), pages_fetched, total_records, completed))
    conn.commit()

def save_transaction(conn, transaction):
    """Save a transaction to the database."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO sales 
            (attom_id, transaction_id, address, city, zip, property_type, 
             sale_amt, sale_date, sale_record_date, sale_trans_type, 
             buyer_name, seller_name, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            transaction.get('attom_id'),
            transaction.get('transaction_id'),
            transaction.get('address'),
            transaction.get('city'),
            transaction.get('zip'),
            transaction.get('property_type'),
            transaction.get('sale_amt'),
            transaction.get('sale_date'),
            transaction.get('sale_record_date'),
            transaction.get('sale_trans_type'),
            transaction.get('buyer_name'),
            transaction.get('seller_name'),
            datetime.now().isoformat()
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Duplicate

def fetch_sales_for_zip(conn, zip_code, page_size=100):
    """Fetch all sales for a ZIP code within price range and date range."""
    pages_fetched, completed = get_fetch_progress(conn, zip_code)
    
    if completed:
        log(f"  ZIP {zip_code} already completed, skipping...")
        return 0
    
    page = pages_fetched + 1
    total_fetched = 0
    new_records = 0
    
    while True:
        url = f"{BASE_URL}/sale/snapshot"
        params = {
            "postalCode": zip_code,
            "minSaleAmt": MIN_SALE_AMT,
            "maxSaleAmt": MAX_SALE_AMT,
            "startSaleSearchDate": START_DATE,
            "endSaleSearchDate": END_DATE,
            "page": page,
            "pageSize": page_size
        }
        
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=60)
            
            if response.status_code != 200:
                log(f"  ERROR: {response.status_code} - {response.text[:200]}")
                break
            
            data = response.json()
            status = data.get("status", {})
            total = status.get("total", 0)
            
            if "property" not in data or not data["property"]:
                if page == 1:
                    log(f"  No sales found in ${MIN_SALE_AMT/1e6:.0f}M-${MAX_SALE_AMT/1e6:.0f}M range")
                break
            
            properties = data["property"]
            
            for prop in properties:
                sale = prop.get("sale", {})
                amount_data = sale.get("amount", {})
                identifier = prop.get("identifier", {})
                address = prop.get("address", {})
                summary = prop.get("summary", {})
                
                transaction = {
                    'attom_id': identifier.get('attomId'),
                    'transaction_id': sale.get('transactionIdent') or f"{identifier.get('attomId')}_{amount_data.get('salerecdate', '')}",
                    'address': address.get('oneLine'),
                    'city': address.get('locality'),
                    'zip': address.get('postal1'),
                    'property_type': summary.get('proptype'),
                    'sale_amt': amount_data.get('saleamt'),
                    'sale_date': sale.get('salesearchdate'),
                    'sale_record_date': amount_data.get('salerecdate'),
                    'sale_trans_type': amount_data.get('saletranstype'),
                    'buyer_name': sale.get('buyerName', ''),
                    'seller_name': sale.get('sellerName', '')
                }
                
                if save_transaction(conn, transaction):
                    new_records += 1
                total_fetched += 1
            
            log(f"  Page {page}: {len(properties)} sales (total: {total_fetched}/{total}, new: {new_records})")
            
            save_fetch_progress(conn, zip_code, page, total)
            
            if total_fetched >= total or len(properties) < page_size:
                save_fetch_progress(conn, zip_code, page, total, completed=1)
                break
            
            page += 1
            time.sleep(0.3)  # Rate limiting
            
        except Exception as e:
            log(f"  ERROR on page {page}: {e}")
            save_fetch_progress(conn, zip_code, page - 1, 0)
            break
    
    return new_records

def analyze_repeat_transactors(conn):
    """Analyze database to find repeat buyers and sellers."""
    cursor = conn.cursor()
    
    # Get all transactions
    cursor.execute("""
        SELECT buyer_name, seller_name, address, city, zip, sale_amt, sale_date, sale_trans_type
        FROM sales
        WHERE sale_amt IS NOT NULL
        ORDER BY sale_date DESC
    """)
    
    rows = cursor.fetchall()
    
    # Track transactions by party name
    party_transactions = defaultdict(list)
    
    for row in rows:
        buyer, seller, address, city, zip_code, amt, date, trans_type = row
        
        # Track buyer
        if buyer and buyer.strip():
            buyer_clean = buyer.strip().upper()
            party_transactions[buyer_clean].append({
                'role': 'BUYER',
                'address': address,
                'city': city,
                'zip': zip_code,
                'amount': amt,
                'date': date,
                'trans_type': trans_type
            })
        
        # Track seller
        if seller and seller.strip():
            seller_clean = seller.strip().upper()
            party_transactions[seller_clean].append({
                'role': 'SELLER',
                'address': address,
                'city': city,
                'zip': zip_code,
                'amount': amt,
                'date': date,
                'trans_type': trans_type
            })
    
    # Find repeat transactors (2+ transactions)
    repeat_transactors = []
    
    for name, transactions in party_transactions.items():
        if len(transactions) >= 2:
            # Skip obvious non-leads
            skip_keywords = ['BANK', 'TRUST COMPANY', 'MORTGAGE', 'FEDERAL', 'FANNIE', 'FREDDIE', 
                           'HUD', 'SECRETARY', 'FORECLOSURE', 'SHERIFF', 'COUNTY OF', 'CITY OF',
                           'STATE OF', 'UNITED STATES', 'WELLS FARGO', 'CHASE', 'JPMORGAN',
                           'BANK OF AMERICA', 'CITIBANK', 'US BANK']
            
            if any(kw in name for kw in skip_keywords):
                continue
            
            total_volume = sum(t['amount'] for t in transactions if t['amount'])
            buy_count = sum(1 for t in transactions if t['role'] == 'BUYER')
            sell_count = sum(1 for t in transactions if t['role'] == 'SELLER')
            zips = list(set(t['zip'] for t in transactions if t['zip']))
            dates = [t['date'] for t in transactions if t['date']]
            latest_date = max(dates) if dates else None
            earliest_date = min(dates) if dates else None
            
            repeat_transactors.append({
                'name': name,
                'total_transactions': len(transactions),
                'buy_count': buy_count,
                'sell_count': sell_count,
                'total_volume': total_volume,
                'avg_deal_size': total_volume / len(transactions) if transactions else 0,
                'zips_active': ', '.join(zips),
                'zip_count': len(zips),
                'latest_transaction': latest_date,
                'earliest_transaction': earliest_date,
                'transactions': transactions
            })
    
    # Sort by total transactions descending
    repeat_transactors.sort(key=lambda x: x['total_transactions'], reverse=True)
    
    return repeat_transactors

def export_results(repeat_transactors):
    """Export results to CSV."""
    os.makedirs("data", exist_ok=True)
    
    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Name', 'Total_Transactions', 'Buy_Count', 'Sell_Count',
            'Total_Volume', 'Avg_Deal_Size', 'ZIPs_Active', 'ZIP_Count',
            'Latest_Transaction', 'Earliest_Transaction'
        ])
        
        for rt in repeat_transactors:
            writer.writerow([
                rt['name'],
                rt['total_transactions'],
                rt['buy_count'],
                rt['sell_count'],
                f"${rt['total_volume']:,.0f}",
                f"${rt['avg_deal_size']:,.0f}",
                rt['zips_active'],
                rt['zip_count'],
                rt['latest_transaction'],
                rt['earliest_transaction']
            ])
    
    log(f"Exported {len(repeat_transactors)} repeat transactors to {OUTPUT_CSV}")

def export_all_sales(conn):
    """Export all sales to CSV for reference."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT attom_id, address, city, zip, property_type, sale_amt, 
               sale_date, sale_trans_type, buyer_name, seller_name
        FROM sales
        ORDER BY sale_date DESC
    """)
    
    with open(ALL_SALES_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'attom_id', 'address', 'city', 'zip', 'property_type',
            'sale_amt', 'sale_date', 'sale_trans_type', 'buyer_name', 'seller_name'
        ])
        writer.writerows(cursor.fetchall())
    
    log(f"Exported all sales to {ALL_SALES_CSV}")

def main():
    log("=" * 70)
    log("ATTOM REPEAT TRANSACTOR FINDER")
    log("=" * 70)
    log(f"Target: Buyers/Sellers with 2+ transactions")
    log(f"Price Range: ${MIN_SALE_AMT/1e6:.0f}M - ${MAX_SALE_AMT/1e6:.0f}M")
    log(f"Date Range: {START_DATE} to {END_DATE}")
    log(f"ZIP Codes: {len(ZIP_CODES)} coastal SoCal areas")
    log("=" * 70)
    
    conn = init_database()
    
    # Phase 1: Fetch sales data
    log("")
    log("PHASE 1: Fetching sales data from ATTOM API...")
    log("-" * 70)
    
    total_new = 0
    for i, zip_code in enumerate(ZIP_CODES, 1):
        log(f"[{i:2}/{len(ZIP_CODES)}] Processing ZIP {zip_code}...")
        new_records = fetch_sales_for_zip(conn, zip_code)
        total_new += new_records
    
    # Get total count
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sales")
    total_sales = cursor.fetchone()[0]
    
    log("")
    log(f"PHASE 1 COMPLETE: {total_sales:,} total sales in database ({total_new:,} new)")
    
    # Phase 2: Analyze for repeat transactors
    log("")
    log("PHASE 2: Analyzing for repeat transactors...")
    log("-" * 70)
    
    repeat_transactors = analyze_repeat_transactors(conn)
    
    log(f"Found {len(repeat_transactors):,} repeat transactors (2+ deals)")
    
    # Show top 20
    log("")
    log("TOP 20 REPEAT TRANSACTORS:")
    log("-" * 70)
    
    for i, rt in enumerate(repeat_transactors[:20], 1):
        log(f"{i:2}. {rt['name'][:50]:<50}")
        log(f"    Transactions: {rt['total_transactions']} (Buy: {rt['buy_count']}, Sell: {rt['sell_count']})")
        log(f"    Volume: ${rt['total_volume']:,.0f} | Avg: ${rt['avg_deal_size']:,.0f}")
        log(f"    Active in: {rt['zips_active']}")
        log(f"    Latest: {rt['latest_transaction']}")
    
    # Export results
    log("")
    log("PHASE 3: Exporting results...")
    log("-" * 70)
    
    export_results(repeat_transactors)
    export_all_sales(conn)
    
    conn.close()
    
    log("")
    log("=" * 70)
    log("COMPLETE!")
    log(f"  Total Sales: {total_sales:,}")
    log(f"  Repeat Transactors: {len(repeat_transactors):,}")
    log(f"  Output: {OUTPUT_CSV}")
    log("=" * 70)

if __name__ == "__main__":
    main()
