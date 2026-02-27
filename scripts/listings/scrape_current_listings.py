#!/usr/bin/env python3
"""
Scrape current Redfin listings for a zip code and extract broker info.

This script:
1. Takes a zip code and price range
2. Fetches all active listings from Redfin
3. Extracts listing details + broker/agent info
4. Outputs to CSV

Usage:
    python scrape_current_listings.py --zip 92037
    python scrape_current_listings.py --zip 92037 --min-price 1500000 --max-price 20000000
    python scrape_current_listings.py --all-zips --output current_listings.csv

Note: Use responsibly with rate limiting. For personal use only.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client, Client

# Load .env from repo root
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("VITE_SUPABASE_ANON_KEY")

# Fallback zip codes when not using Supabase config (e.g. imports by daily_pipeline)
TARGET_ZIPS = [
    "92037", "92014", "92075", "92024", "92007", "92118", "92106", "92107",
    "92109", "92011", "92008", "92130", "92127", "92029",
    "92651", "92629", "92624", "92672", "92657", "92625", "92663", "92661",
    "92662", "92648", "92649",
]


@dataclass
class ScraperConfig:
    """Scraping configuration from Supabase scrape_configuration (active row)."""
    zip_codes: list[str]
    min_price: int
    max_price: int
    config_id: Optional[int] = None  # scrape_configuration.id when loaded from DB


def get_supabase_client() -> Client:
    """Create Supabase client from environment variables."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError(
            "Missing SUPABASE_URL or SUPABASE_KEY (or VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY).\n"
            "Set them in .env or export for scrape config lookup."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_scrape_config() -> ScraperConfig:
    """
    Load the active row from Supabase scrape_configuration.
    Table columns: id, created_at, zipcodes (jsonb), minimum_listing_price, maximum_listing_price, active.
    """
    client = get_supabase_client()
    result = (
        client.table("scrape_configuration")
        .select("id, zipcodes, minimum_listing_price, maximum_listing_price")
        .eq("active", True)
        .limit(1)
        .execute()
    )
    if not result.data or len(result.data) == 0:
        raise ValueError(
            "No active scrape_configuration found in Supabase. "
            "Ensure one row has active = true."
        )
    row = result.data[0]
    # zipcodes: jsonb is either {"zipcodes": ["92037", ...]} or a raw array
    raw_zips = row.get("zipcodes")
    if isinstance(raw_zips, dict) and "zipcodes" in raw_zips:
        raw_zips = raw_zips["zipcodes"]
    raw_zips = raw_zips or []
    if isinstance(raw_zips, (list, tuple)):
        zip_codes = [str(z).strip() for z in raw_zips if z is not None]
    else:
        zip_codes = [str(raw_zips).strip()]
    min_p = row.get("minimum_listing_price")
    max_p = row.get("maximum_listing_price")
    min_price = int(min_p) if min_p is not None else 1_500_000
    max_price = int(max_p) if max_p is not None else 20_000_000
    config_id = row.get("id")
    if config_id is not None:
        config_id = int(config_id)
    return ScraperConfig(zip_codes=zip_codes, min_price=min_price, max_price=max_price, config_id=config_id)


@dataclass
class ListingRecord:
    """A single property listing with broker info."""
    redfin_url: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zipcode: str = ""
    price: str = ""
    beds: str = ""
    baths: str = ""
    sqft: str = ""
    lot_size: str = ""
    year_built: str = ""
    property_type: str = ""
    stories: str = ""
    garage_spaces: str = ""
    price_per_sqft: str = ""
    hoa_dues: str = ""
    listing_status: str = ""
    listing_date: str = ""
    listing_agent: str = ""
    agent_dre: str = ""
    brokerage: str = ""
    agent_phone: str = ""
    agent_email: str = ""
    # Co-listing agent (for properties listed by multiple agents)
    co_listing_agent: str = ""
    co_listing_agent_dre: str = ""
    co_listing_brokerage: str = ""
    co_listing_agent_phone: str = ""
    co_listing_agent_email: str = ""
    # Buyer's agent (for sold properties)
    buyer_agent: str = ""
    buyer_agent_dre: str = ""
    buyer_brokerage: str = ""
    buyer_agent_phone: str = ""
    buyer_agent_email: str = ""
    mls_number: str = ""
    days_on_market: str = ""
    description: str = ""
    is_co_listed: str = ""  # "true" if co-listed, empty otherwise
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
    scrape_instance_id: str = ""  # UUID of scrape_instances row for this run


def get_headers():
    """Return headers that mimic a real browser."""
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def format_price(price: int) -> str:
    """Format price for Redfin URL (e.g., 1500000 -> 1.5M)."""
    if price >= 1_000_000:
        m = price / 1_000_000
        return f"{m:g}M" if m == int(m) else f"{m}M"
    elif price >= 1_000:
        k = price / 1_000
        return f"{k:g}k" if k == int(k) else f"{k}k"
    return str(price)


def fetch_redfin_search(zipcode: str, min_price: int = 1_500_000, max_price: int = 20_000_000, status: str = "all", sort: str = "", existing_urls: set = None, sold: bool = False) -> list[str]:
    """Fetch listing URLs from a Redfin search page (with pagination).
    
    If existing_urls is provided, filters out URLs we already have (fast pagination, then filter).
    If sold is True, scrapes recently sold properties (last 1 week) instead of active listings.
    """
    # Build filters
    if sold:
        # Recently sold mode (last 1 week)
        status_filter = ",include=sold-1wk"
    elif status == "all":
        status_filter = ",status=active+comingsoon+contingent+pending"
    elif status == "active":
        status_filter = ""  # Default Redfin behavior
    else:
        status_filter = f",status={status}"
    sort_filter = f",sort={sort}" if sort else ""
    min_fmt = format_price(min_price)
    max_fmt = format_price(max_price)
    base_url = f"https://www.redfin.com/zipcode/{zipcode}/filter/property-type=house+condo+townhouse,min-price={min_fmt},max-price={max_fmt}{status_filter}{sort_filter}"
    
    print(f"  Fetching search: {zipcode}...", file=sys.stderr)
    
    existing_urls = existing_urls or set()
    all_urls = []  # All URLs found during pagination
    page = 1
    max_pages = 10  # Safety limit
    
    # Phase 1: Fast pagination to collect all URLs
    while page <= max_pages:
        url = base_url if page == 1 else f"{base_url}/page-{page}"
        
        try:
            resp = requests.get(url, headers=get_headers(), timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"    Error fetching search page {page}: {e}", file=sys.stderr)
            break
        
        soup = BeautifulSoup(resp.text, "html.parser")
        page_urls = []
        
        # Find all property links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Redfin property URLs contain /home/ followed by a property ID
            if re.search(r'/home/\d+', href) and href.startswith('/'):
                full_url = f"https://www.redfin.com{href}"
                if full_url not in all_urls:
                    page_urls.append(full_url)
                    all_urls.append(full_url)
        
        if not page_urls:
            # No new listings found, we've reached the end
            break
        
        print(f"    Page {page}: found {len(page_urls)} listings", file=sys.stderr)
        page += 1
        time.sleep(0.5)  # Brief delay between pages (pagination is fast)
    
    # Phase 2: Filter out existing URLs (the smart part)
    if existing_urls:
        new_urls = [u for u in all_urls if u not in existing_urls]
        skipped = len(all_urls) - len(new_urls)
        print(f"    Total: {len(all_urls)} listings, {skipped} already in DB, {len(new_urls)} new to scrape", file=sys.stderr)
        return new_urls
    else:
        print(f"    Total: {len(all_urls)} listings to scrape", file=sys.stderr)
        return all_urls


def fetch_listing_details(url: str) -> Optional[ListingRecord]:
    """Fetch a single listing page and extract all details."""
    try:
        resp = requests.get(url, headers=get_headers(), timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    Error fetching {url}: {e}", file=sys.stderr)
        return None
    
    soup = BeautifulSoup(resp.text, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    
    record = ListingRecord(redfin_url=url)
    
    # Extract address from title
    title = soup.find("title")
    if title:
        title_text = title.get_text()
        # Format: "123 Main St, La Jolla, CA 92037 | Redfin"
        addr_match = re.match(r'^(.+?)\s*\|', title_text)
        if addr_match:
            full_addr = addr_match.group(1).strip()
            record.address = full_addr
            
            parts = full_addr.split(",")
            if len(parts) >= 3:
                record.city = parts[-2].strip()
                state_zip = parts[-1].strip()
                state_zip_match = re.match(r'([A-Z]{2})\s*(\d{5})', state_zip)
                if state_zip_match:
                    record.state = state_zip_match.group(1)
                    record.zipcode = state_zip_match.group(2)
    
    # Extract price
    price_match = re.search(r'\$[\d,]+(?:,\d{3})*', page_text)
    if price_match:
        record.price = price_match.group()
    
    # Extract beds/baths/sqft from stats
    beds_match = re.search(r'(\d+)\s*(?:Beds?|bd|BR)', page_text, re.I)
    baths_match = re.search(r'([\d.]+)\s*(?:Baths?|ba)', page_text, re.I)
    sqft_match = re.search(r'([\d,]+)\s*(?:Sq\.?\s*Ft\.?|sqft)', page_text, re.I)
    
    if beds_match:
        record.beds = beds_match.group(1)
    if baths_match:
        record.baths = baths_match.group(1)
    if sqft_match:
        record.sqft = sqft_match.group(1).replace(",", "")
    
    # Store raw HTML for JSON extraction
    html_content = resp.text
    
    # Year Built
    year_match = re.search(r'(?:Year Built|Built in)[:\s]+(\d{4})', page_text, re.I)
    if year_match:
        record.year_built = year_match.group(1)
    
    # Lot Size
    lot_match = re.search(r'Lot Size[:\s]+([\d,]+)\s*(?:sq|SF|square)', page_text, re.I)
    if lot_match:
        record.lot_size = lot_match.group(1).replace(",", "")
    
    # Property Type (from JSON)
    prop_type_match = re.search(r'"propertyType"[:\s]*"([^"]+)"', html_content, re.I)
    if prop_type_match:
        record.property_type = prop_type_match.group(1)
    
    # Stories
    stories_match = re.search(r'Stories?[:\s]+(\d+)', page_text, re.I)
    if stories_match:
        record.stories = stories_match.group(1)
    
    # Garage Spaces
    garage_match = re.search(r'Garage Spaces?[:\s]+(\d+)', page_text, re.I)
    if garage_match:
        record.garage_spaces = garage_match.group(1)
    
    # Price per sqft
    ppsf_match = re.search(r'\$([\d,]+)/sq\.?\s?ft', page_text, re.I)
    if ppsf_match:
        record.price_per_sqft = ppsf_match.group(1).replace(",", "")
    
    # HOA Dues
    hoa_match = re.search(r'HOA Dues?[:\s]+\$?([\d,]+)', page_text, re.I)
    if hoa_match:
        record.hoa_dues = hoa_match.group(1).replace(",", "")
    
    # Listing Status (from JSON)
    status_match = re.search(r'"listingStatus"[:\s]*"([^"]+)"', html_content, re.I)
    if status_match:
        record.listing_status = status_match.group(1)
    
    # Listing Date - look for dates in the page
    date_matches = re.findall(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})', page_text)
    if date_matches:
        for d in date_matches:
            if "2025" in d or "2026" in d:
                record.listing_date = d
                break
    
    # Description (first 200 chars)
    desc_match = re.search(r'"description"[:\s]*"([^"]{0,200})', html_content)
    if desc_match:
        record.description = desc_match.group(1).replace("\\n", " ").strip()
    
    # Extract listing agent info
    # Format: "Listed by Carol Mundell • DRE # 00863002 • Century 21 Affiliated • 858-967-7331"
    # Note: Properties can be co-listed by multiple agents
    # Parse each "Listed by" block separately to handle co-listings correctly
    
    def parse_agent_block(block: str) -> dict:
        """Parse a single 'Listed by' block into agent info."""
        result = {'name': '', 'dre': '', 'brokerage': '', 'phone': '', 'email': ''}
        
        # Parse name + DRE (handles names like O'Brien, OByrne, etc.)
        name_dre = re.search(
            r"Listed by\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,3})\s*[•·]\s*DRE\s*#?\s*(\d{7,8})",
            block
        )
        if not name_dre:
            return result
        
        result['name'] = name_dre.group(1).strip()
        result['dre'] = name_dre.group(2).strip()
        
        # Parse brokerage (text after DRE #, before phone/email/end)
        after_dre = block[name_dre.end():]
        brokerage_match = re.match(r"\s*[•·]\s*([A-Za-z][A-Za-z0-9\s\-&'\.,]+?)(?:\s*[•·]|$)", after_dre)
        if brokerage_match:
            brokerage_raw = brokerage_match.group(1).strip()
            # Clean up - stop at common suffixes
            brokerage_clean = re.split(r'\s+Listing\s+|\s+Details\s+', brokerage_raw)[0]
            result['brokerage'] = brokerage_clean.strip()
        
        # Parse phone
        phone_match = re.search(r'(\d{3}[-.\s]\d{3}[-.\s]\d{4})', block)
        if phone_match:
            result['phone'] = phone_match.group(1)
        
        # Parse email
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', block)
        if email_match:
            result['email'] = email_match.group(1).lower()
        
        return result
    
    # Split by 'Listed by' and parse each block
    agent_blocks = re.split(r'(?=Listed by)', page_text)
    agent_blocks = [b for b in agent_blocks if b.startswith('Listed by')]
    
    all_agents = [parse_agent_block(b) for b in agent_blocks]
    all_agents = [a for a in all_agents if a['dre']]  # Filter out failed parses
    
    if all_agents:
        # Use the first agent as primary
        primary = all_agents[0]
        record.listing_agent = primary['name']
        record.agent_dre = primary['dre']
        record.brokerage = primary['brokerage']
        record.agent_phone = primary['phone']
        record.agent_email = primary['email']
        
        # Store co-listing agent info (if any) - we capture the first co-listing agent
        if len(all_agents) > 1:
            co_agent = all_agents[1]
            record.is_co_listed = "true"
            record.co_listing_agent = co_agent['name']
            record.co_listing_agent_dre = co_agent['dre']
            record.co_listing_brokerage = co_agent['brokerage']
            record.co_listing_agent_phone = co_agent['phone']
            record.co_listing_agent_email = co_agent['email']
    
    # Fallback: Try simpler pattern if complex one didn't match
    if not record.agent_dre:
        simple_match = re.search(
            r"Listed by\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,3})\s*[•·]\s*DRE\s*#?\s*(\d{7,8})",
            page_text
        )
        if simple_match:
            record.listing_agent = simple_match.group(1).strip()
            record.agent_dre = simple_match.group(2).strip()
    
    # Last resort: Try to find DRE separately if not found
    if not record.agent_dre:
        dre_match = re.search(r'DRE\s*#?\s*(\d{7,8})', page_text)
        if dre_match:
            record.agent_dre = dre_match.group(1)
    
    # Fallback: Look for common brokerages if not found
    if not record.brokerage:
        brokerage_patterns = [
            r'[•·]\s*(Coldwell Banker[A-Za-z\s]*?)(?:\s*[•·]|\s+\d{3})',
            r'[•·]\s*(Compass)(?:\s*[•·]|\s+\d{3}|\s+Details)',
            r'[•·]\s*(Keller Williams[A-Za-z\s]*?)(?:\s*[•·]|\s+\d{3})',
            r'[•·]\s*(RE/MAX[A-Za-z\s]*?)(?:\s*[•·]|\s+\d{3})',
            r'[•·]\s*(Century 21[A-Za-z\s]*?)(?:\s*[•·]|\s+\d{3})',
            r'[•·]\s*(Sotheby\'s[A-Za-z\s]*?)(?:\s*[•·]|\s+\d{3})',
            r'[•·]\s*(Pacific Sotheby\'s[A-Za-z\s]*?)(?:\s*[•·]|\s+\d{3})',
            r'[•·]\s*(eXp Realty[A-Za-z\s]*?)(?:\s*[•·]|\s+\d{3})',
            r'[•·]\s*(Berkshire Hathaway[A-Za-z\s]*?)(?:\s*[•·]|\s+\d{3})',
            r'[•·]\s*(Douglas Elliman[A-Za-z\s]*?)(?:\s*[•·]|\s+\d{3})',
            r'[•·]\s*(Willis Allen[A-Za-z\s]*?)(?:\s*[•·]|\s+\d{3})',
            r'[•·]\s*(Barry Estates[A-Za-z\s]*?)(?:\s*[•·]|\s+\d{3})',
        ]
        for pattern in brokerage_patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                record.brokerage = match.group(1).strip()
                break
    
    # Extract MLS number (handles both SDMLS format and CRMLS format with prefixes)
    # SDMLS: 260004250 (9 digits)
    # CRMLS: OC25123456, NP25041234, LG25012345 (2 letters + 8 digits)
    mls_match = re.search(r'MLS#?\s*:?\s*([A-Z]{0,2}\d{6,12})', page_text, re.I)
    if mls_match:
        record.mls_number = mls_match.group(1)
    
    # Also try to find CRMLS-style IDs in JSON
    if not record.mls_number:
        crmls_match = re.search(r'"listingId"[:\s]*"?([A-Z]{2}\d{8})"?', html_content)
        if crmls_match:
            record.mls_number = crmls_match.group(1)
    
    # Extract days on market
    dom_match = re.search(r'(\d+)\s*days?\s+on\s+Redfin', page_text, re.I)
    if dom_match:
        record.days_on_market = dom_match.group(1)
    
    # Extract phone number (listing agent) - only if not already found in Listed by block
    if not record.agent_phone:
        phone_match = re.search(r'(\(\d{3}\)\s*\d{3}[-.\s]?\d{4}|\d{3}[-.\s]\d{3}[-.\s]\d{4})', page_text)
        if phone_match:
            record.agent_phone = phone_match.group(1)

    # Extract buyer's agent info (for sold properties)
    # Format: "Bought with Robert Brown • DRE # 01796328 • Fantastik Realty • 858-397-3108 (agent) • RobBrownVegas@gmail.com"
    bought_with_match = re.search(
        r'Bought with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*[•·]\s*DRE\s*#?\s*(\d{7,8})\s*[•·]\s*([^•·]+?)(?:\s*[•·]|$)',
        page_text
    )
    if bought_with_match:
        record.buyer_agent = bought_with_match.group(1).strip()
        record.buyer_agent_dre = bought_with_match.group(2).strip()
        brokerage_raw = bought_with_match.group(3).strip()
        brokerage_clean = re.split(r'\s+\d{3}[-.\s]|\s+Details\s+provided', brokerage_raw)[0]
        record.buyer_brokerage = brokerage_clean.strip()
    
    # Extract buyer's agent phone
    bought_phone_match = re.search(r'Bought with.{0,150}?(\d{3}[-.\s]\d{3}[-.\s]\d{4})', page_text)
    if bought_phone_match:
        record.buyer_agent_phone = bought_phone_match.group(1)
    
    # Extract buyer's agent email
    bought_email_match = re.search(r'Bought with.{0,200}?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', page_text)
    if bought_email_match:
        record.buyer_agent_email = bought_email_match.group(1).lower()

    # Extract agent email - multiple strategies
    # Note: For co-listings, we need to ensure the email matches the PRIMARY agent
    
    # Skip if already found in Listed by block
    if not record.agent_email:
        # Strategy 1: Look for "Contact:" pattern often used by Redfin
        contact_email_match = re.search(r'Contact:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', page_text, re.I)
        if contact_email_match:
            record.agent_email = contact_email_match.group(1).lower()
        
        # Strategy 2: Look for email in JSON data (agentEmail, email, listingAgentEmail fields)
        if not record.agent_email:
            json_email_patterns = [
                r'"agentEmail"[:\s]*"([^"]+@[^"]+)"',
                r'"listingAgentEmail"[:\s]*"([^"]+@[^"]+)"',
                r'"email"[:\s]*"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"',
            ]
            for pattern in json_email_patterns:
                match = re.search(pattern, html_content, re.I)
                if match:
                    record.agent_email = match.group(1).lower()
                    break
        
        # Strategy 3: Look for email near agent name or DRE number
        # Be strict - only match if it contains agent's first name to avoid co-listing mixups
        if not record.agent_email and record.listing_agent:
            agent_first_name = record.listing_agent.split()[0].lower()
            agent_last_name = record.listing_agent.split()[-1].lower() if len(record.listing_agent.split()) > 1 else ''
            
            # Find all emails on page
            all_emails = re.findall(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', page_text)
            excluded_prefixes = ['support', 'info', 'privacy', 'contact', 'help', 'admin', 'noreply', 'no-reply', 'sales', 'marketing']
            
            for email in all_emails:
                email_lower = email.lower()
                prefix = email_lower.split('@')[0]
                
                # Skip system emails and redfin emails
                if any(prefix.startswith(ex) for ex in excluded_prefixes) or 'redfin.com' in email_lower:
                    continue
                
                # Prefer emails that contain agent's name
                if agent_first_name in prefix or agent_last_name in prefix:
                    record.agent_email = email_lower
                    break
            
            # Fallback: use first non-excluded email only if there's exactly one agent
            # (no co-listing detected) to avoid mixups
            if not record.agent_email and not hasattr(record, 'notes'):
                for email in all_emails:
                    email_lower = email.lower()
                    prefix = email_lower.split('@')[0]
                    if not any(prefix.startswith(ex) for ex in excluded_prefixes) and 'redfin.com' not in email_lower:
                        record.agent_email = email_lower
                        break
    
    return record


def main():
    config = fetch_scrape_config()
    parser = argparse.ArgumentParser(
        description="Scrape current Redfin listings and extract broker info"
    )
    parser.add_argument(
        "--zip", "-z",
        help="Single zip code to scrape (overrides config zip codes)"
    )
    parser.add_argument(
        "--all-zips", "-a",
        action="store_true",
        help="Scrape all zip codes from active scrape_configuration"
    )
    parser.add_argument(
        "--min-price",
        type=int,
        default=config.min_price,
        help=f"Minimum price (default from config: {config.min_price})"
    )
    parser.add_argument(
        "--max-price",
        type=int,
        default=config.max_price,
        help=f"Maximum price (default from config: {config.max_price})"
    )
    parser.add_argument(
        "--output", "-o",
        default="current_listings.csv",
        help="Output CSV file (default: current_listings.csv)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between requests in seconds (default: 2.0)"
    )
    parser.add_argument(
        "--status",
        default="all",
        help="Listing status filter: 'all' (active+comingsoon+contingent+pending), 'active', 'pending', or custom (default: all)"
    )
    parser.add_argument(
        "--sold",
        action="store_true",
        help="Scrape recently sold properties (last 1 week). Gets buyer's agent info."
    )
    parser.add_argument(
        "--sort",
        default="",
        help="Sort order: 'lo-days' (newest first), 'hi-days' (oldest first), '' (default Redfin sort)"
    )
    parser.add_argument(
        "--incremental",
        metavar="FILE",
        help="Incremental mode: stop when we find a URL already in FILE (use with --sort=lo-days)"
    )
    
    args = parser.parse_args()
    
    if not args.zip and not args.all_zips:
        parser.error("Must specify either --zip or --all-zips")
    
    zips_to_scrape = config.zip_codes if args.all_zips else [args.zip]
    
    # Create a scrape_instances row for this run (if we have a config id from Supabase)
    scrape_instance_id = None
    if config.config_id is not None:
        try:
            client = get_supabase_client()
            result = (
                client.table("scrape_instances")
                .insert({
                    "scrape_configuration_id": config.config_id,
                    "listings_count": 0,
                })
                .execute()
            )
            if result.data and len(result.data) > 0:
                scrape_instance_id = result.data[0]["id"]
                print(f"Created scrape instance: {scrape_instance_id}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: could not create scrape_instances row: {e}", file=sys.stderr)
    
    all_listings = []
    
    # Load existing URLs for incremental mode
    existing_urls = set()
    urls_missing_buyer = set()  # URLs that exist but don't have buyer's agent yet
    if args.incremental:
        incremental_path = Path(args.incremental)
        if incremental_path.exists():
            with open(incremental_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("redfin_url"):
                        existing_urls.add(row["redfin_url"])
                        # Track URLs missing buyer's agent (for --sold mode re-scraping)
                        if not row.get("buyer_agent"):
                            urls_missing_buyer.add(row["redfin_url"])
            print(f"Loaded {len(existing_urls)} existing URLs for incremental mode", file=sys.stderr)
            if args.sold and urls_missing_buyer:
                print(f"  ({len(urls_missing_buyer)} missing buyer's agent - will re-scrape if found)", file=sys.stderr)
        else:
            print(f"Warning: incremental file not found: {args.incremental}", file=sys.stderr)
    
    # For --sold mode, only skip URLs that already have buyer's agent data
    if args.sold:
        existing_urls = existing_urls - urls_missing_buyer

    print(f"Scraping {len(zips_to_scrape)} zip code(s)...", file=sys.stderr)

    # Set up output file for incremental writes
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path(__file__).parent.parent.parent / "data" / "listings" / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write header and open file for incremental appends
    fieldnames = list(asdict(ListingRecord()).keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
    
    print(f"Writing incrementally to: {output_path}", file=sys.stderr)

    for zipcode in zips_to_scrape:
        listing_urls = fetch_redfin_search(zipcode, args.min_price, args.max_price, args.status, args.sort, existing_urls, args.sold)

        for i, url in enumerate(listing_urls):
            print(f"    [{i+1}/{len(listing_urls)}] Fetching: {url[:60]}...", file=sys.stderr)
            record = fetch_listing_details(url)
            if record:
                if scrape_instance_id:
                    record.scrape_instance_id = str(scrape_instance_id)
                all_listings.append(record)
                # Write immediately to file (incremental save)
                with open(output_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writerow(asdict(record))
            time.sleep(args.delay)

        # Longer delay between zip codes
        if len(zips_to_scrape) > 1:
            time.sleep(5)

    print(f"\nTotal listings scraped: {len(all_listings)}", file=sys.stderr)
    
    # Update scrape_instances with final count
    if scrape_instance_id is not None:
        try:
            client = get_supabase_client()
            client.table("scrape_instances").update(
                {"listings_count": len(all_listings)}
            ).eq("id", scrape_instance_id).execute()
        except Exception as e:
            print(f"Warning: could not update scrape_instances count: {e}", file=sys.stderr)
    
    print(f"Wrote {len(all_listings)} listings to {output_path}", file=sys.stderr)
    
    # Print summary
    with_dre = sum(1 for r in all_listings if r.agent_dre)
    with_brokerage = sum(1 for r in all_listings if r.brokerage)
    with_phone = sum(1 for r in all_listings if r.agent_phone)
    with_email = sum(1 for r in all_listings if r.agent_email)
    with_buyer_agent = sum(1 for r in all_listings if r.buyer_agent)
    with_buyer_email = sum(1 for r in all_listings if r.buyer_agent_email)
    print(f"\nSummary:", file=sys.stderr)
    print(f"  Listing Agent:", file=sys.stderr)
    print(f"    - With DRE #: {with_dre}/{len(all_listings)}", file=sys.stderr)
    print(f"    - With Brokerage: {with_brokerage}/{len(all_listings)}", file=sys.stderr)
    print(f"    - With Phone: {with_phone}/{len(all_listings)}", file=sys.stderr)
    print(f"    - With Email: {with_email}/{len(all_listings)}", file=sys.stderr)
    if with_buyer_agent > 0:
        print(f"  Buyer's Agent:", file=sys.stderr)
        print(f"    - With Name: {with_buyer_agent}/{len(all_listings)}", file=sys.stderr)
        print(f"    - With Email: {with_buyer_email}/{len(all_listings)}", file=sys.stderr)


if __name__ == "__main__":
    main()
