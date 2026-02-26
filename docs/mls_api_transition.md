# MLS API Transition Plan

## Overview

Transition from Redfin scraping to direct MLS API access for real-time listing data in San Diego and Orange County.

## Target MLSs

| MLS | Coverage | Data Platform | Contact |
|-----|----------|---------------|---------|
| **SDMLS** | San Diego County | MLS Router (RealtyFeed) | dataservices@sdmls.com |
| **CRMLS** | Orange County, LA, Inland Empire | CoreLogic Trestle | licensing@crmls.org |

### Quick Links

**SDMLS:**
- Website: https://sdmls.com
- Approved Vendors: https://sdmls.com/wp-content/uploads/2025/03/Approved-Vendor-List.pdf
- Data Access Agreement: https://sdmls.com (under "nmsubscribers/data-access")

**CRMLS:**
- Website: https://go.crmls.org
- IDX Resources: https://go.crmls.org/idx-resources/
- Data Licensing Request: https://go.crmls.org/crmls-data-licensing-request-form/
- Trestle Signup: https://trestle.corelogic.com/SubscriptionWizard/
- API Docs: https://devdocs.crmls.org/start/
- API Endpoints: `https://h.api.crmls.org/Reso/OData/` (prod), `https://staging.h.api.crmls.org/Reso/OData/` (staging)

## Access Paths by MLS

### SDMLS (San Diego)

#### Option A: Use an Existing Approved Vendor
```
Licensed Broker/Agent (MLS Member)
        ↓
Selects vendor from SDMLS Approved Vendor List
        ↓
Signs Master Data Access Agreement (names the vendor)
        ↓
Vendor provides data feed/API to you
```

**Approved vendors include:** iHomefinder, Luxury Presence, Showcase IDX, etc.  
**Full list:** https://sdmls.com/wp-content/uploads/2025/03/Approved-Vendor-List.pdf

**Pros:** Faster setup, vendor handles compliance  
**Cons:** May not offer raw API access, monthly fees to vendor, less control

#### Option B: Become an Approved Vendor
```
You apply as 3rd Party Vendor
        ↓
Sign Vendor Data Access Agreement
        ↓
Pay vendor fee ($349/mo)
        ↓
Licensed Broker signs Master Data Access Agreement (names you as vendor)
        ↓
You receive OAuth credentials for MLS Router API
```

**Pros:** Direct API access, full control  
**Cons:** $349/mo vendor fee, application process

---

### CRMLS (Orange County, LA, Inland Empire)

**Key Difference:** CRMLS uses **CoreLogic Trestle** for data distribution (not MLS Router like SDMLS).

#### Option A: Broker Back-Office Feed (Cheapest)
```
Licensed Broker (CRMLS Member)
        ↓
Requests Broker Back-Office feed via Trestle
        ↓
2 feeds included FREE with membership
        ↓
Additional feeds: $25/mo each
```

**Best for:** Internal use, private investment platforms (your use case)  
**Note:** Broker-level feeds include listing info tied to their office, but likely can request broader access.

#### Option B: Full IDX/Data Feed
```
You apply as Data Licensee/Vendor
        ↓
Submit Data Licensing Request Form
        ↓
Sign up for Trestle subscription
        ↓
Pay: $85/mo (Trestle) + $7/mo per URL (first 2 free)
```

**Contact:** licensing@crmls.org (new vendors)  
**Trestle Signup:** https://trestle.corelogic.com/SubscriptionWizard/

#### Option C: Broker Requests Feed on Your Behalf
```
Broker already has Trestle account
        ↓
Requests additional feed for your platform
        ↓
Third feed = $85/mo (IDX) or $25/mo (BBO)
```

This may be the **easiest path** if the broker already has CRMLS access.

---

### Cost Summary

| MLS | Path | Monthly Cost | Notes |
|-----|------|--------------|-------|
| **SDMLS** | Existing vendor | $50-200 (vendor pricing) | Fastest setup |
| **SDMLS** | Become vendor | $349/mo | Full control |
| **CRMLS** | Broker BBO feed | $0-25/mo | First 2 feeds free |
| **CRMLS** | Become vendor | ~$92/mo | $85 Trestle + $7/URL |
| **Both** | Full vendor setup | ~$450-500/mo | SDMLS expensive, CRMLS cheap |

---

## Email Template: SDMLS

**To:** dataservices@sdmls.com  
**CC:** idx@sdmls.com  
**Subject:** Vendor Application Inquiry - Private Lending Platform

---

Dear SDMLS Data Services Team,

I'm Dan McColl, Director of Construction Lending at Trinity Mortgage Fund, a private real estate lender serving coastal Southern California. I'm reaching out to inquire about obtaining MLS data access for our internal deal sourcing platform.

**About Trinity Mortgage Fund:**
We're a San Diego-based private lender providing construction and bridge financing for residential properties across coastal Southern California. We work closely with licensed brokers who are SDMLS members.

**Our use case:**
- Monitor new residential listings in San Diego coastal zip codes (92037, 92014, 92075, 92024, etc.)
- Price range: $1.5M - $20M
- Purpose: Internal deal sourcing and market intelligence (not a public-facing website or IDX display)
- Data needed: Active listings, listing agent contact info, property details

**Questions:**
1. For our use case (internal private lending platform, not public IDX display), should we apply as a 3rd Party Vendor, or is there a more appropriate access tier?
2. I see the vendor fee is $349/month - are there any other fees for our use case?
3. Once approved as a vendor, we understand a broker would sign the Master Data Access Agreement naming us as the vendor. Is that correct?
4. Does the vendor/technology provider need to be a California-registered entity, or can out-of-state companies apply?
5. Is there a sandbox/test environment available during integration?
6. What is the typical approval timeline for vendor applications?

We're prepared to integrate with MLS Router API (RESO Web API 2.0) and comply with all data handling requirements.

Would a brief call be helpful to discuss our use case before we submit the formal application?

Thank you for your time.

Best regards,  
Dan McColl  
Director of Construction Lending  
Trinity Mortgage Fund  
(858) 775-0962  
dan@trinitysd.com

---

## Email Template: CRMLS

**To:** licensing@crmls.org  
**Subject:** Data Licensing Inquiry - Private Lending Platform (Orange County)

---

Dear CRMLS Data Licensing Team,

I'm Dan McColl, Director of Construction Lending at Trinity Mortgage Fund, a private real estate lender serving coastal Southern California. I'm reaching out to inquire about obtaining MLS data access for our internal deal sourcing platform.

**About Trinity Mortgage Fund:**
We're a San Diego-based private lender providing construction and bridge financing for residential properties across coastal Southern California. We work closely with licensed brokers who are CRMLS members.

**Our use case:**
- Monitor new residential listings in Orange County coastal zip codes (92651, 92629, 92657, 92663, etc.)
- Price range: $1.5M - $20M
- Purpose: Internal deal sourcing and market intelligence (not a public-facing website or IDX display)
- Data needed: Active listings, listing agent contact info, property details

**Questions:**
1. For our use case (internal private lending platform, not public IDX display), would a Broker Back-Office feed be appropriate? Or do we need to apply as a Data Licensee/Vendor?
2. I understand CRMLS uses CoreLogic Trestle for data distribution. Would we register through the Trestle subscription wizard, or is there a different process for non-IDX use cases?
3. If a broker requests the feed on our behalf as a "technology provider," what is the process?
4. Does the vendor/technology provider need to be a California-registered entity, or can out-of-state companies apply?
5. Is there a staging/sandbox environment available? (I see staging.h.api.crmls.org mentioned in the dev docs)
6. Approximately how long is the approval timeline?

We're prepared to integrate with your RESO Web API (OData) endpoint and comply with all CRMLS Rules and Regulations.

Would a brief call be helpful to discuss our use case before we submit a formal application?

Thank you,  
Dan McColl  
Director of Construction Lending  
Trinity Mortgage Fund  
(858) 775-0962  
dan@trinitysd.com

---

## Transition Timeline

### Phase 1: Current (Scraping) ✓
- Daily Redfin scrape via `daily_pipeline.py`
- Cross-reference with DRE database
- Works today, no dependencies

### Phase 2: MLS Outreach (This Week)
- [ ] Confirm licensed professional's MLS memberships
- [ ] Send emails to SDMLS and CRMLS
- [ ] Schedule intro calls if needed

### Phase 3: Agreement & Setup (2-4 weeks)
- [ ] Licensed professional signs Master Data Access Agreement(s)
- [ ] Receive OAuth credentials for MLS Router API
- [ ] Set up sandbox testing

### Phase 4: Integration (1-2 weeks)
- [ ] Build MLS API client (RESO Web API 2.0)
- [ ] Implement webhook subscriptions for new listings
- [ ] Test against sandbox

### Phase 5: Cutover
- [ ] Run MLS API and scraper in parallel for 1 week
- [ ] Verify data parity
- [ ] Deprecate scraper, switch to MLS API only

---

## API Integration Preview

Both MLSs support RESO Web API 2.0 (OData), but have different endpoints:

### SDMLS (MLS Router)

```python
import requests

# Authenticate
auth_response = requests.post(
    "https://api.realtyfeed.com/oauth/token",
    data={
        "grant_type": "client_credentials",
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
    }
)
token = auth_response.json()["access_token"]

# Query active listings in a zip code
response = requests.get(
    "https://api.realtyfeed.com/reso/odata/Property",
    headers={"Authorization": f"Bearer {token}"},
    params={
        "$filter": "StandardStatus eq 'Active' and PostalCode eq '92037' and ListPrice ge 1500000 and ListPrice le 20000000",
        "$expand": "Member,Office",
        "$top": 100,
    }
)
```

### CRMLS (Trestle / Direct API)

```python
import requests

# CRMLS uses their own API endpoints
# Production (read-only): https://h.api.crmls.org/Reso/OData/
# Staging (read/write):   https://staging.h.api.crmls.org/Reso/OData/

# Auth flow TBD after receiving credentials from licensing@crmls.org

response = requests.get(
    "https://h.api.crmls.org/Reso/OData/Property",
    headers={"Authorization": f"Bearer {token}"},
    params={
        "$filter": "StandardStatus eq 'Active' and PostalCode eq '92651' and ListPrice ge 1500000 and ListPrice le 20000000",
        "$expand": "Member,Office",
        "$top": 100,
    }
)

listings = response.json()["value"]
for listing in listings:
    print(f"{listing['StreetAddress']} - ${listing['ListPrice']}")
    print(f"  Agent: {listing['ListAgentFullName']} ({listing['ListAgentMlsId']})")
    print(f"  Office: {listing['ListOfficeName']}")
```

**Note:** Both APIs follow RESO Data Dictionary standards, so the field names should be consistent.

---

## Cost Comparison

| Approach | Setup | Monthly Cost | Data Quality | Reliability |
|----------|-------|--------------|--------------|-------------|
| **Redfin Scraping** | None | $0 | Good | ToS risk |
| **SDMLS via existing vendor** | Broker signs agreement | $50-200 | Authoritative | Guaranteed |
| **SDMLS become vendor** | Vendor application | $349/mo | Authoritative | Guaranteed |
| **CRMLS Broker BBO feed** | Broker requests | $0-25/mo | Authoritative | Guaranteed |
| **CRMLS become vendor** | Data licensing application | ~$92/mo | Authoritative | Guaranteed |
| **Both MLSs (cheapest)** | SDMLS vendor + CRMLS BBO | ~$375/mo | Authoritative | Guaranteed |
| **Both MLSs (most control)** | Become vendor in both | ~$450/mo | Authoritative | Guaranteed |

## Recommendation

CRMLS is **much cheaper** than SDMLS:
- CRMLS: ~$25-92/mo (possibly $0 if broker has free feeds remaining)
- SDMLS: $349/mo as vendor, or $50-200/mo via existing vendor

**Best Strategy:**
1. **CRMLS (Orange County):** Ask broker if they already have Trestle access with unused feeds. If yes, this could be ~$0-25/mo. If no, apply as data licensee for ~$92/mo.
2. **SDMLS (San Diego):** Check if an existing approved vendor offers raw API passthrough first. If not, apply as vendor ($349/mo).

**Total expected cost:** $375-450/mo for both MLSs with direct API access.

---

## Questions for Licensed Professional

Before sending the emails, confirm:

1. Are they currently a member of **SDMLS**? **CRMLS**? Both?
2. Are they a **Broker** or **Salesperson**? (Brokers can sign agreements directly; Salespersons need their supervising broker)
3. **For CRMLS:** Do they already have a **Trestle account**? How many feeds have they used? (First 2 are free)
4. Are they willing to sign the **Master Data Access Agreement** (SDMLS) and/or authorize a data connection via Trestle (CRMLS)?

---

## Summary: What You Need to Apply

### SDMLS
- [ ] Broker signs **Master Data Access Agreement** naming you/your company as vendor
- [ ] You pay **$349/mo vendor fee**
- [ ] You receive MLS Router OAuth credentials

### CRMLS
- [ ] Submit **Data Licensing Request Form** (https://go.crmls.org/crmls-data-licensing-request-form/)
- [ ] Sign up for **Trestle subscription** (https://trestle.corelogic.com/SubscriptionWizard/)
- [ ] OR have broker request additional feed for you (~$25-85/mo)
- [ ] You receive Trestle/CRMLS API credentials
