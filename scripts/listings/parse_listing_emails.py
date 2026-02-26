#!/usr/bin/env python3
"""
Parse Redfin listing alert emails and extract property/broker data.

This script can:
1. Connect to Gmail via IMAP and fetch Redfin alert emails
2. Parse HTML emails to extract listing data  
3. Optionally fetch full listing pages to get broker details
4. Output structured CSV data

Setup:
1. Enable IMAP in Gmail settings
2. Create an App Password: https://myaccount.google.com/apppasswords
3. Set environment variables:
   - GMAIL_ADDRESS=your-email@gmail.com
   - GMAIL_APP_PASSWORD=your-app-password

Usage:
    # Parse emails from the last 7 days
    python parse_listing_emails.py --days 7

    # Parse and also fetch broker details from listing pages
    python parse_listing_emails.py --days 7 --fetch-brokers

    # Output to CSV
    python parse_listing_emails.py --days 7 --output listings.csv
"""

import argparse
import csv
import imaplib
import email
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from email.header import decode_header
from typing import Optional
from bs4 import BeautifulSoup
import requests


@dataclass
class ListingData:
    """Structured listing data extracted from emails/pages."""
    url: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zipcode: str = ""
    price: str = ""
    beds: str = ""
    baths: str = ""
    sqft: str = ""
    listing_agent: str = ""
    agent_dre: str = ""
    brokerage: str = ""
    agent_phone: str = ""
    date_found: str = field(default_factory=lambda: datetime.now().isoformat())


def connect_gmail() -> imaplib.IMAP4_SSL:
    """Connect to Gmail via IMAP."""
    email_addr = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    
    if not email_addr or not app_password:
        raise ValueError(
            "Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables.\n"
            "Create an App Password at: https://myaccount.google.com/apppasswords"
        )
    
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(email_addr, app_password)
    return mail


def fetch_redfin_emails(mail: imaplib.IMAP4_SSL, days: int = 7) -> list[tuple[str, str]]:
    """Fetch Redfin alert emails from the last N days. Returns list of (subject, html_body)."""
    mail.select("inbox")
    
    since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
    
    # Search for emails from Redfin
    search_criteria = f'(FROM "redfin.com" SINCE {since_date})'
    _, message_ids = mail.search(None, search_criteria)
    
    emails = []
    for msg_id in message_ids[0].split():
        _, msg_data = mail.fetch(msg_id, "(RFC822)")
        email_body = msg_data[0][1]
        msg = email.message_from_bytes(email_body)
        
        subject = decode_header(msg["subject"])[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode()
        
        html_body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_body = part.get_payload(decode=True).decode()
                    break
        else:
            if msg.get_content_type() == "text/html":
                html_body = msg.get_payload(decode=True).decode()
        
        if html_body:
            emails.append((subject, html_body))
    
    return emails


def parse_redfin_email(subject: str, html: str) -> list[ListingData]:
    """Parse a Redfin alert email and extract listing data."""
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    
    # Redfin emails typically have listing cards with links
    # Look for property links
    for link in soup.find_all("a", href=True):
        href = link["href"]
        
        # Filter to actual property listing URLs
        if "redfin.com/CA/" not in href and "redfin.com/home/" not in href:
            continue
        if "/filter/" in href or "/zipcode/" in href:
            continue
            
        listing = ListingData(url=href)
        
        # Try to extract address from link text or nearby elements
        link_text = link.get_text(strip=True)
        if link_text and not link_text.startswith("http"):
            # Could be address or price
            if "$" in link_text:
                listing.price = link_text
            else:
                listing.address = link_text
        
        # Look for price in parent/sibling elements
        parent = link.parent
        if parent:
            parent_text = parent.get_text(" ", strip=True)
            price_match = re.search(r'\$[\d,]+', parent_text)
            if price_match and not listing.price:
                listing.price = price_match.group()
            
            # Look for beds/baths
            beds_match = re.search(r'(\d+)\s*(?:bd|bed|BR)', parent_text, re.I)
            baths_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ba|bath)', parent_text, re.I)
            sqft_match = re.search(r'([\d,]+)\s*(?:sq\s*ft|sqft)', parent_text, re.I)
            
            if beds_match:
                listing.beds = beds_match.group(1)
            if baths_match:
                listing.baths = baths_match.group(1)
            if sqft_match:
                listing.sqft = sqft_match.group(1).replace(",", "")
        
        # Extract zipcode from URL if possible
        zip_match = re.search(r'/(\d{5})(?:/|$)', href)
        if zip_match:
            listing.zipcode = zip_match.group(1)
        
        if listing.url:
            listings.append(listing)
    
    # Dedupe by URL
    seen_urls = set()
    unique_listings = []
    for l in listings:
        if l.url not in seen_urls:
            seen_urls.add(l.url)
            unique_listings.append(l)
    
    return unique_listings


def fetch_broker_details(listing: ListingData, session: requests.Session) -> ListingData:
    """Fetch the full listing page and extract broker details."""
    if not listing.url:
        return listing
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        resp = session.get(listing.url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Extract address from page title or header
        title = soup.find("title")
        if title:
            title_text = title.get_text()
            # Redfin titles are like "123 Main St, City, CA 90210 | Redfin"
            addr_match = re.match(r'^(.+?)\s*\|', title_text)
            if addr_match:
                full_addr = addr_match.group(1).strip()
                listing.address = full_addr
                
                # Parse city, state, zip
                parts = full_addr.split(",")
                if len(parts) >= 2:
                    listing.city = parts[-2].strip() if len(parts) > 2 else ""
                    state_zip = parts[-1].strip()
                    state_zip_match = re.match(r'([A-Z]{2})\s*(\d{5})', state_zip)
                    if state_zip_match:
                        listing.state = state_zip_match.group(1)
                        listing.zipcode = state_zip_match.group(2)
        
        # Look for listing agent info
        # Redfin shows "Listed by [Agent Name]" or similar
        page_text = soup.get_text(" ", strip=True)
        
        # Look for "Listed by" pattern
        listed_by_match = re.search(
            r'Listed by\s+([A-Za-z\s\-\']+?)(?:\s*[•·]\s*DRE\s*#?\s*(\d+))?',
            page_text
        )
        if listed_by_match:
            listing.listing_agent = listed_by_match.group(1).strip()
            if listed_by_match.group(2):
                listing.agent_dre = listed_by_match.group(2)
        
        # Look for DRE number
        dre_match = re.search(r'DRE\s*#?\s*(\d{7,8})', page_text)
        if dre_match and not listing.agent_dre:
            listing.agent_dre = dre_match.group(1)
        
        # Look for brokerage
        brokerage_patterns = [
            r'(?:Coldwell Banker|Compass|Keller Williams|RE/MAX|Century 21|Sotheby\'s|eXp Realty|Berkshire Hathaway)[^,\n]*',
        ]
        for pattern in brokerage_patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                listing.brokerage = match.group().strip()
                break
        
        # Look for phone number
        phone_match = re.search(r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})', page_text)
        if phone_match:
            listing.agent_phone = phone_match.group(1)
        
        # Price from page
        price_elem = soup.find(class_=re.compile(r'price|Price'))
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            if "$" in price_text:
                listing.price = price_text
        
    except Exception as e:
        print(f"  Warning: Could not fetch {listing.url}: {e}", file=sys.stderr)
    
    return listing


def main():
    parser = argparse.ArgumentParser(
        description="Parse Redfin listing alert emails"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=7,
        help="Fetch emails from the last N days (default: 7)"
    )
    parser.add_argument(
        "--fetch-brokers", "-f",
        action="store_true",
        help="Fetch full listing pages to get broker details (slower)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output CSV file path"
    )
    parser.add_argument(
        "--test-html",
        help="Test with a local HTML file instead of fetching emails"
    )
    
    args = parser.parse_args()
    
    all_listings = []
    
    if args.test_html:
        # Test mode with local HTML file
        with open(args.test_html) as f:
            html = f.read()
        listings = parse_redfin_email("Test", html)
        all_listings.extend(listings)
    else:
        # Fetch from Gmail
        print(f"Connecting to Gmail...", file=sys.stderr)
        try:
            mail = connect_gmail()
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        
        print(f"Fetching Redfin emails from the last {args.days} days...", file=sys.stderr)
        emails = fetch_redfin_emails(mail, args.days)
        print(f"Found {len(emails)} emails", file=sys.stderr)
        
        for subject, html in emails:
            print(f"  Parsing: {subject[:60]}...", file=sys.stderr)
            listings = parse_redfin_email(subject, html)
            all_listings.extend(listings)
        
        mail.logout()
    
    print(f"Extracted {len(all_listings)} unique listings", file=sys.stderr)
    
    # Optionally fetch broker details
    if args.fetch_brokers and all_listings:
        print(f"Fetching broker details from listing pages...", file=sys.stderr)
        session = requests.Session()
        for i, listing in enumerate(all_listings):
            print(f"  [{i+1}/{len(all_listings)}] {listing.url[:60]}...", file=sys.stderr)
            fetch_broker_details(listing, session)
            time.sleep(1)  # Be nice to Redfin
    
    # Output
    if args.output:
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(asdict(ListingData()).keys()))
            writer.writeheader()
            for listing in all_listings:
                writer.writerow(asdict(listing))
        print(f"Wrote {len(all_listings)} listings to {args.output}", file=sys.stderr)
    else:
        # Print to stdout as CSV
        writer = csv.DictWriter(sys.stdout, fieldnames=list(asdict(ListingData()).keys()))
        writer.writeheader()
        for listing in all_listings:
            writer.writerow(asdict(listing))


if __name__ == "__main__":
    main()
