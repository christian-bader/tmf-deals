#!/usr/bin/env python3
"""
Local analysis of corporate licenses in listing data.
Reads CSVs directly - no Supabase required.
"""

import csv
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
DRE_FILE = REPO_ROOT / 'data' / 'ca-dre' / 'CurrList.csv'
LISTINGS_FILE = REPO_ROOT / 'data' / 'listings' / 'daily' / 'all_listings_2026-02-25_enriched.csv'
SOLD_FILE = REPO_ROOT / 'data' / 'listings' / 'daily' / 'recently_sold.csv'


def load_dre_database():
    """Load DRE database into memory, indexed by license number.
    
    IMPORTANT: One license number can have multiple rows (e.g., Broker + Officer).
    We prefer Broker/Salesperson over Officer/Corporation.
    """
    print(f"Loading DRE database from {DRE_FILE}...")
    dre_by_license = {}  # license -> best record (prefer Broker/Salesperson)
    dre_all_by_license = defaultdict(list)  # license -> all records
    dre_by_name = defaultdict(list)  # last_name -> list of records
    
    # Priority: lower is better
    TYPE_PRIORITY = {
        'Broker': 1,
        'Salesperson': 2,
        'Officer': 3,
        'Corporation': 4,
    }
    
    with open(DRE_FILE, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lic_num = row.get('lic_number', '').strip()
            if not lic_num:
                continue
            
            record = {
                'license_number': lic_num,
                'first_name': row.get('firstname_secondary', '').strip(),
                'last_name': row.get('lastname_primary', '').strip(),
                'license_type': row.get('lic_type', '').strip(),
                'license_status': row.get('lic_status', '').strip(),
                'related_license': row.get('related_lic_number', '').strip(),
                'related_name': ' '.join(filter(None, [
                    row.get('related_firstname_secondary', '').strip(),
                    row.get('related_lastname_primary', '').strip()
                ])),
            }
            record['full_name'] = f"{record['first_name']} {record['last_name']}".strip()
            
            dre_all_by_license[lic_num].append(record)
            
            # Keep best record (prefer Broker/Salesperson over Officer)
            existing = dre_by_license.get(lic_num)
            if not existing:
                dre_by_license[lic_num] = record
            else:
                existing_priority = TYPE_PRIORITY.get(existing['license_type'], 99)
                new_priority = TYPE_PRIORITY.get(record['license_type'], 99)
                if new_priority < existing_priority:
                    dre_by_license[lic_num] = record
            
            # Index by last name for lookups (only Broker/Salesperson)
            if record['last_name'] and record['license_type'] in ('Broker', 'Salesperson'):
                dre_by_name[record['last_name'].lower()].append(record)
    
    # Stats on multi-row licenses
    multi_row = sum(1 for records in dre_all_by_license.values() if len(records) > 1)
    print(f"  Loaded {len(dre_by_license):,} unique licenses ({multi_row:,} have multiple rows)")
    
    return dre_by_license, dre_by_name


def is_corporate(record):
    """Check if a DRE record is a corporation."""
    lic_type = (record.get('license_type') or '').lower()
    return lic_type in ('corporation', 'officer')


def extract_name_from_email(email):
    """Try to extract first/last name from email."""
    if not email or '@' not in email:
        return None, None
    
    local = email.split('@')[0].lower()
    
    if '.' in local:
        parts = local.split('.')
        if len(parts) >= 2:
            return parts[0], parts[-1]
    elif '_' in local:
        parts = local.split('_')
        if len(parts) >= 2:
            return parts[0], parts[-1]
    
    return None, None


def find_individual(dre_by_license, dre_by_name, scraped_name, email):
    """Try to find the individual agent given scraped info."""
    candidates = []
    
    # Try scraped name
    if scraped_name:
        parts = scraped_name.split()
        if len(parts) >= 2:
            last = parts[-1].lower()
            first = parts[0].lower()
            
            for record in dre_by_name.get(last, []):
                if record['license_type'] in ('Salesperson', 'Broker') and record['license_status'] == 'Licensed':
                    if record['first_name'].lower().startswith(first[:3]):
                        candidates.append(('scraped_name', record))
    
    # Try email
    if email:
        first, last = extract_name_from_email(email)
        if first and last:
            for record in dre_by_name.get(last, []):
                if record['license_type'] in ('Salesperson', 'Broker') and record['license_status'] == 'Licensed':
                    if record['first_name'].lower().startswith(first[:3]):
                        candidates.append(('email', record))
    
    return candidates


def analyze_listings(csv_path, dre_by_license, dre_by_name, label):
    """Analyze a listings CSV for corporate license issues."""
    print(f"\n{'='*60}")
    print(f"Analyzing {label}: {csv_path.name}")
    print('='*60)
    
    corporate_cases = []
    
    with open(csv_path, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        
        for row in reader:
            address = row.get('ADDRESS') or row.get('address') or row.get('Address', '')
            
            # Detect column naming pattern
            # Sold listings: agent_dre, listing_agent, agent_email, buyer_agent_dre, etc.
            # Active listings: LISTING AGENT DRE#, LISTING AGENT NAME, etc.
            
            agent_configs = []
            
            # Check for sold listing format
            if 'agent_dre' in headers:
                agent_configs.append({
                    'dre': row.get('agent_dre', '').strip(),
                    'name': row.get('listing_agent', '').strip(),
                    'email': row.get('agent_email', '').strip(),
                    'role': 'listing_agent',
                })
            if 'buyer_agent_dre' in headers:
                agent_configs.append({
                    'dre': row.get('buyer_agent_dre', '').strip(),
                    'name': row.get('buyer_agent', '').strip(),
                    'email': row.get('buyer_agent_email', '').strip(),
                    'role': 'buyer_agent',
                })
            
            # Check for active listing format
            if 'LISTING AGENT DRE#' in headers:
                agent_configs.append({
                    'dre': row.get('LISTING AGENT DRE#', '').strip(),
                    'name': row.get('LISTING AGENT NAME', '').strip(),
                    'email': row.get('LISTING AGENT EMAIL', '').strip(),
                    'role': 'listing_agent',
                })
            
            for agent in agent_configs:
                lic_num = agent['dre']
                name = agent['name']
                email = agent['email']
                
                if not lic_num:
                    continue
                
                dre_info = dre_by_license.get(lic_num)
                if dre_info and is_corporate(dre_info):
                    individuals = find_individual(dre_by_license, dre_by_name, name, email)
                    corporate_cases.append({
                        'address': address,
                        'role': agent['role'],
                        'corp_license': lic_num,
                        'corp_name': dre_info['full_name'] or dre_info['last_name'],
                        'scraped_name': name,
                        'scraped_email': email,
                        'individuals_found': individuals,
                    })
    
    # Report
    print(f"\nFound {len(corporate_cases)} corporate license cases")
    
    if corporate_cases:
        # Group by corporate license
        by_corp = defaultdict(list)
        for case in corporate_cases:
            by_corp[case['corp_license']].append(case)
        
        print(f"\nUnique corporate licenses: {len(by_corp)}")
        
        for corp_lic, cases in sorted(by_corp.items(), key=lambda x: -len(x[1]))[:10]:
            corp_info = dre_by_license[corp_lic]
            print(f"\n  {corp_lic}: {corp_info['full_name'] or corp_info['last_name']} ({len(cases)} listings)")
            
            for case in cases[:3]:
                print(f"    - {case['address'][:50]}")
                print(f"      Scraped: {case['scraped_name']} <{case['scraped_email']}>")
                
                if case['individuals_found']:
                    for method, ind in case['individuals_found'][:2]:
                        print(f"      → Found via {method}: {ind['full_name']} (DRE {ind['license_number']})")
                else:
                    print(f"      → No individual found in DRE")
            
            if len(cases) > 3:
                print(f"      ... and {len(cases) - 3} more")
    
    # Stats
    resolved = sum(1 for c in corporate_cases if c['individuals_found'])
    print(f"\n  Resolved to individual: {resolved}/{len(corporate_cases)} ({100*resolved/len(corporate_cases):.1f}%)" if corporate_cases else "")
    
    return corporate_cases


def test_email_resolution(dre_by_license, dre_by_name):
    """Test email-to-individual resolution from actual conflict cases."""
    print("\n" + "="*60)
    print("TESTING EMAIL → INDIVIDUAL RESOLUTION")
    print("="*60)
    
    # Test cases from conflicts.json (corporate license 01521930 = Redfin)
    test_cases = [
        ("michelle.serafini@compass.com", "01411969"),  # Expected DRE
        ("jason@barryestates.com", "01147550"),
        ("tyson@lundteam.com", "01385039"),
        ("seth@sethchalnick.com", "01343733"),
    ]
    
    resolved = 0
    for email, expected_dre in test_cases:
        first, last = extract_name_from_email(email)
        print(f"\n  Email: {email}")
        print(f"  Parsed name: {first} {last}")
        
        if not first or not last:
            print(f"  → Could not parse name from email")
            continue
        
        candidates = []
        for record in dre_by_name.get(last.lower(), []):
            if record['license_status'] == 'Licensed':
                if record['first_name'].lower().startswith(first.lower()[:3]):
                    candidates.append(record)
        
        if candidates:
            best = candidates[0]
            for c in candidates:
                if c['first_name'].lower() == first.lower():
                    best = c
                    break
            
            match = "✓" if best['license_number'] == expected_dre else "✗"
            print(f"  → Found: {best['full_name']} (DRE {best['license_number']}) {match}")
            if best['license_number'] == expected_dre:
                resolved += 1
        else:
            print(f"  → No match found in DRE")
    
    print(f"\n  Resolution rate: {resolved}/{len(test_cases)}")


def main():
    dre_by_license, dre_by_name = load_dre_database()
    
    # Show some corporate examples
    print("\nSample corporate licenses in DRE:")
    corps = [r for r in dre_by_license.values() if is_corporate(r)][:5]
    for c in corps:
        print(f"  {c['license_number']}: {c['full_name'] or c['last_name']} ({c['license_type']})")
    
    # Test email resolution
    test_email_resolution(dre_by_license, dre_by_name)
    
    # Analyze listings
    all_cases = []
    
    if LISTINGS_FILE.exists():
        cases = analyze_listings(LISTINGS_FILE, dre_by_license, dre_by_name, "Active/Pending Listings")
        all_cases.extend(cases)
    
    if SOLD_FILE.exists():
        cases = analyze_listings(SOLD_FILE, dre_by_license, dre_by_name, "Recently Sold")
        all_cases.extend(cases)
    
    # Final summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(f"Total corporate license cases: {len(all_cases)}")
    resolved = sum(1 for c in all_cases if c['individuals_found'])
    print(f"Resolvable to individual: {resolved} ({100*resolved/len(all_cases):.1f}%)" if all_cases else "No cases found")


if __name__ == '__main__':
    main()
