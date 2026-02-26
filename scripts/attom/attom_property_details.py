#!/usr/bin/env python3
"""
Fetch comprehensive property details from ATTOM API for a specific property.
"""
import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ATTOM_API_KEY")
BASE_URL = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"

HEADERS = {
    "Accept": "application/json",
    "APIKey": API_KEY
}

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def fetch_endpoint(endpoint, attom_id):
    """Fetch data from a specific ATTOM endpoint."""
    url = f"{BASE_URL}/{endpoint}"
    params = {"attomId": attom_id}
    
    log(f"Fetching: {endpoint}")
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            log(f"  ✓ Success")
            return data
        else:
            log(f"  ✗ Error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        log(f"  ✗ Exception: {e}")
        return None

def format_currency(value):
    if value is None:
        return "N/A"
    try:
        return f"${int(value):,}"
    except:
        return str(value)

def format_date(value):
    if not value:
        return "N/A"
    return value

def main():
    attom_id = 156786314
    address = "2260 CALLE FRESCOTA, LA JOLLA, CA 92037"
    
    log("=" * 70)
    log("ATTOM COMPREHENSIVE PROPERTY REPORT")
    log("=" * 70)
    log(f"ATTOM ID: {attom_id}")
    log(f"Address:  {address}")
    log("=" * 70)
    
    all_data = {}
    
    # Fetch from multiple endpoints
    endpoints = [
        "property/detailmortgageowner",  # Most comprehensive - details + mortgage + owner
        "property/expandedprofile",       # Expanded profile with more details
        "sale/detail",                    # Recent sale info
        "saleshistory/detail",            # Sales history
        "avm/detail",                     # Automated valuation model
        "assessment/detail",              # Tax assessment
        "property/buildingpermits",       # Building permits
    ]
    
    log("")
    log("FETCHING DATA FROM ATTOM API...")
    log("-" * 70)
    
    for endpoint in endpoints:
        data = fetch_endpoint(endpoint, attom_id)
        if data:
            all_data[endpoint] = data
    
    # Save raw data
    with open(f"attom_property_{attom_id}_raw.json", "w") as f:
        json.dump(all_data, f, indent=2)
    log("")
    log(f"Raw data saved to: attom_property_{attom_id}_raw.json")
    
    # Parse and display results
    log("")
    log("=" * 70)
    log("PROPERTY REPORT")
    log("=" * 70)
    
    # Property Details
    if "property/detailmortgageowner" in all_data:
        prop_data = all_data["property/detailmortgageowner"]
        if "property" in prop_data and prop_data["property"]:
            prop = prop_data["property"][0]
            
            # Address
            addr = prop.get("address", {})
            log("")
            log("📍 ADDRESS")
            log(f"   {addr.get('oneLine', 'N/A')}")
            
            # Location
            loc = prop.get("location", {})
            log(f"   Coordinates: {loc.get('latitude', 'N/A')}, {loc.get('longitude', 'N/A')}")
            
            # Lot Info
            lot = prop.get("lot", {})
            log("")
            log("🏞️  LOT INFORMATION")
            log(f"   Lot Size (acres): {lot.get('lotSize1', 'N/A')}")
            log(f"   Lot Size (sqft):  {lot.get('lotSize2', 'N/A')}")
            log(f"   Pool:             {lot.get('poolType', 'None/Unknown')}")
            
            # Building Info
            building = prop.get("building", {})
            size = building.get("size", {})
            rooms = building.get("rooms", {})
            interior = building.get("interior", {})
            
            log("")
            log("🏠 BUILDING INFORMATION")
            log(f"   Year Built:       {building.get('yearBuilt', 'N/A')}")
            log(f"   Living Area:      {size.get('livingSize', 'N/A')} sqft")
            log(f"   Universal Size:   {size.get('universalSize', 'N/A')} sqft")
            log(f"   Gross Size:       {size.get('grossSize', 'N/A')} sqft")
            log(f"   Bedrooms:         {rooms.get('beds', 'N/A')}")
            log(f"   Bathrooms Full:   {rooms.get('bathsFull', 'N/A')}")
            log(f"   Bathrooms Half:   {rooms.get('bathsHalf', 'N/A')}")
            log(f"   Total Bathrooms:  {rooms.get('bathsTotal', 'N/A')}")
            log(f"   Total Rooms:      {rooms.get('roomsTotal', 'N/A')}")
            log(f"   Stories:          {building.get('summary', {}).get('levels', 'N/A')}")
            log(f"   Property Type:    {building.get('summary', {}).get('propClass', 'N/A')}")
            log(f"   Construction:     {building.get('construction', {}).get('constructionType', 'N/A')}")
            log(f"   Roof Type:        {building.get('construction', {}).get('roofCover', 'N/A')}")
            log(f"   Fireplace:        {interior.get('fplcCount', 'N/A')}")
            
            # Owner Information
            owner = prop.get("owner", {})
            log("")
            log("👤 OWNER INFORMATION")
            log(f"   Owner 1:          {owner.get('owner1', {}).get('fullName', 'N/A')}")
            log(f"   Owner 2:          {owner.get('owner2', {}).get('fullName', 'N/A') if owner.get('owner2') else 'N/A'}")
            log(f"   Owner Type:       {owner.get('corporateIndicator', 'Individual' if not owner.get('corporateIndicator') else 'Corporate')}")
            log(f"   Absentee Owner:   {owner.get('absenteeOwnerStatus', 'N/A')}")
            
            mail_addr = owner.get("mailingAddressOneLine", "N/A")
            log(f"   Mailing Address:  {mail_addr}")
            
            # Mortgage Information
            mortgage = prop.get("mortgage", {})
            if mortgage:
                log("")
                log("🏦 MORTGAGE INFORMATION")
                
                first = mortgage.get("FirstConcurrent", {})
                if first:
                    log("   First Mortgage:")
                    log(f"      Amount:        {format_currency(first.get('amount'))}")
                    log(f"      Loan Type:     {first.get('loanType', 'N/A')}")
                    log(f"      Interest Rate: {first.get('interestRate', 'N/A')}")
                    log(f"      Term:          {first.get('term', 'N/A')} months")
                    log(f"      Due Date:      {format_date(first.get('dueDate'))}")
                    log(f"      Lender:        {first.get('lenderName', 'N/A')}")
                
                second = mortgage.get("SecondConcurrent", {})
                if second and second.get("amount"):
                    log("   Second Mortgage:")
                    log(f"      Amount:        {format_currency(second.get('amount'))}")
                    log(f"      Loan Type:     {second.get('loanType', 'N/A')}")
    
    # Assessment / Tax Info
    if "assessment/detail" in all_data:
        assess_data = all_data["assessment/detail"]
        if "property" in assess_data and assess_data["property"]:
            assess = assess_data["property"][0].get("assessment", {})
            
            log("")
            log("📊 TAX ASSESSMENT")
            
            assessed = assess.get("assessed", {})
            log(f"   Assessed Value:   {format_currency(assessed.get('assdTtlValue'))}")
            log(f"   Land Value:       {format_currency(assessed.get('assdLandValue'))}")
            log(f"   Improvement:      {format_currency(assessed.get('assdImprValue'))}")
            
            market = assess.get("market", {})
            log(f"   Market Value:     {format_currency(market.get('mktTtlValue'))}")
            log(f"   Market Land:      {format_currency(market.get('mktLandValue'))}")
            log(f"   Market Improve:   {format_currency(market.get('mktImprValue'))}")
            
            tax = assess.get("tax", {})
            log(f"   Tax Amount:       {format_currency(tax.get('taxAmt'))}")
            log(f"   Tax Year:         {tax.get('taxYear', 'N/A')}")
    
    # AVM (Automated Valuation)
    if "avm/detail" in all_data:
        avm_data = all_data["avm/detail"]
        if "property" in avm_data and avm_data["property"]:
            avm = avm_data["property"][0].get("avm", {})
            
            log("")
            log("💰 AUTOMATED VALUATION MODEL (AVM)")
            log(f"   Estimated Value:  {format_currency(avm.get('amount', {}).get('value'))}")
            log(f"   Value High:       {format_currency(avm.get('amount', {}).get('high'))}")
            log(f"   Value Low:        {format_currency(avm.get('amount', {}).get('low'))}")
            log(f"   Confidence Score: {avm.get('amount', {}).get('scr', 'N/A')}")
            log(f"   Calculation Date: {avm.get('eventDate', 'N/A')}")
    
    # Sale Information
    if "sale/detail" in all_data:
        sale_data = all_data["sale/detail"]
        if "property" in sale_data and sale_data["property"]:
            sale = sale_data["property"][0].get("sale", {})
            
            log("")
            log("🏷️  MOST RECENT SALE")
            
            amount = sale.get("amount", {})
            log(f"   Sale Price:       {format_currency(amount.get('saleAmt'))}")
            log(f"   Sale Date:        {format_date(amount.get('saleRecDate'))}")
            log(f"   Sale Type:        {sale.get('saleTransType', 'N/A')}")
            
            seller = sale.get("sellerName", "N/A")
            log(f"   Seller:           {seller}")
    
    # Sales History
    if "saleshistory/detail" in all_data:
        hist_data = all_data["saleshistory/detail"]
        if "property" in hist_data and hist_data["property"]:
            prop = hist_data["property"][0]
            history = prop.get("saleHistory", [])
            
            if history:
                log("")
                log("📜 SALES HISTORY")
                for i, sale in enumerate(history, 1):
                    amount = sale.get("amount", {})
                    price = format_currency(amount.get("saleAmt"))
                    date = format_date(amount.get("saleRecDate"))
                    trans_type = sale.get("saleTransType", "N/A")
                    
                    log(f"   {i}. {date}: {price} ({trans_type})")
                    
                    # Buyer/Seller if available
                    buyer = sale.get("buyerName")
                    seller = sale.get("sellerName")
                    if buyer:
                        log(f"      Buyer:  {buyer}")
                    if seller:
                        log(f"      Seller: {seller}")
    
    # Building Permits
    if "property/buildingpermits" in all_data:
        permit_data = all_data["property/buildingpermits"]
        if "property" in permit_data and permit_data["property"]:
            permits = permit_data["property"][0].get("buildingPermits", [])
            
            if permits:
                log("")
                log("🔨 BUILDING PERMITS")
                for i, permit in enumerate(permits[:10], 1):  # Show up to 10
                    date = permit.get("effectiveDate", "N/A")
                    desc = permit.get("description", "N/A")
                    ptype = permit.get("permitType", "N/A")
                    status = permit.get("status", "N/A")
                    value = format_currency(permit.get("jobValue"))
                    
                    log(f"   {i}. {date}: {ptype}")
                    log(f"      Description: {desc}")
                    log(f"      Status: {status}, Job Value: {value}")
    
    log("")
    log("=" * 70)
    log("END OF REPORT")
    log("=" * 70)

if __name__ == "__main__":
    main()
