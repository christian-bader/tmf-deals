# TMF Deals - Backend Architecture Briefing

We're building a real estate agent outreach system for Trinity Mortgage Fund (hard money lender). Here's the backend architecture so you can build the React frontend.

## System Overview

```
Python Scraper → Supabase (PostgreSQL) → Google Apps Script → Gmail
                      ↑
              React App (you're building this)
```

## Supabase Schema (6 tables)

### Core Data

```sql
-- All properties (active, pending, sold)
listings (
  id UUID PK,
  address TEXT,
  city TEXT,
  state TEXT,
  zip TEXT,
  price NUMERIC,
  beds INT2,
  baths NUMERIC,
  sqft INT4,
  status TEXT,  -- 'active' | 'pending' | 'sold'
  sale_date DATE,
  source_url TEXT UNIQUE,
  source_platform TEXT,  -- 'redfin' | 'zillow' | 'mls'
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ
)

-- Real estate agents
brokers (
  id UUID PK,
  name TEXT,
  email TEXT UNIQUE,
  phone TEXT,
  brokerage_name TEXT,
  license_number TEXT,
  state_licensed TEXT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)

-- Junction: which broker represented which listing (and as buyer or seller)
broker_listings (
  id UUID PK,
  broker_id UUID FK → brokers,
  listing_id UUID FK → listings,
  role TEXT,  -- 'buyer' | 'seller'
  created_at TIMESTAMPTZ
)
```

### Outreach Workflow

```sql
-- LLM-generated email drafts (queue for review)
suggested_emails (
  id UUID PK,
  broker_id UUID FK → brokers,
  new_listing_ids UUID[],  -- array of listing IDs that triggered this
  subject TEXT,
  body_content TEXT,
  tone_instruction TEXT,
  prior_contact_context JSONB,
  is_first_contact BOOLEAN,
  status TEXT,  -- 'draft' | 'approved' | 'sent' | 'skipped'
  created_at TIMESTAMPTZ
)

-- Audit log of actually sent emails
sent_email_logs (
  id UUID PK,
  suggested_email_id UUID FK → suggested_emails,
  broker_id UUID FK → brokers,
  gmail_message_id TEXT UNIQUE,
  gmail_thread_id TEXT,
  time_sent TIMESTAMPTZ,
  body_snapshot TEXT,
  listing_ids_included UUID[],
  send_status TEXT,  -- 'sent' | 'failed'
  created_at TIMESTAMPTZ
)

-- Why we didn't email someone (audit trail)
outreach_suppression_logs (
  id UUID PK,
  broker_id UUID FK → brokers,
  checked_at TIMESTAMPTZ,
  reason TEXT,  -- 'no_new_listings' | 'too_recent'
  days_since_last_contact INT4,
  new_listing_count INT4,
  created_at TIMESTAMPTZ
)
```

### Key View

```sql
-- Brokers eligible for outreach (not contacted in 30 days, has email)
CREATE VIEW outreach_opportunities AS
SELECT 
  b.id as broker_id,
  b.name,
  b.email,
  b.brokerage_name,
  (SELECT json_agg(...) FROM broker_listings...) as listings,
  (SELECT MAX(time_sent) FROM sent_email_logs...) as last_contacted_at
FROM brokers b
WHERE b.email IS NOT NULL
  AND NOT EXISTS (contacted in last 30 days);
```

## What the React App Should Do

### Primary Use Cases

1. **Dashboard** - Overview stats (total brokers, pending drafts, sent this week)

2. **Opportunities View** - Browse `outreach_opportunities` view
   - Filter by: listing status, price range, zip code, brokerage
   - Show broker's recent listings with their role (buyer/seller)
   - "Generate Email" button → calls Anthropic to create suggested_email

3. **Email Queue** - Manage `suggested_emails` table
   - List emails by status (draft/approved/sent/skipped)
   - Edit subject/body before approving
   - Bulk approve selected drafts
   - Status change: draft → approved (triggers Apps Script to create Gmail drafts)

4. **Broker Detail** - Single broker view
   - All their listings (with role)
   - Outreach history (sent_email_logs)
   - Suppression history

5. **Listings Browser** - Browse all listings
   - Filter by status, price, location
   - Click through to see which brokers are attached

## Tech Stack Suggestion

- **pnpm + Vite + React**
- **Supabase JS client** for data fetching
- **TanStack Query** for caching/state
- **Tailwind** for styling
- **Anthropic API** for LLM calls (email personalization can happen client-side)

## Supabase Connection

```typescript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)

// Fetch opportunities
const { data } = await supabase
  .from('outreach_opportunities')
  .select('*')
  .limit(50)

// Update email status
await supabase
  .from('suggested_emails')
  .update({ status: 'approved' })
  .eq('id', emailId)
```

## Email Templates (3 types)

| Template | Target | Pitch |
|----------|--------|-------|
| `sale-listing` | Active listing, seller's agent | "fast financing for your buyer" |
| `sale-pending` | Pending/contingent, seller's agent | "backup lender if financing falls through" |
| `buyer-closed` | Recently sold, buyer's agent | "renovation/bridge financing for your client" |

Templates live in `templates/*.md` in the repo.

## Trinity Mortgage Fund Value Prop

- $1M–$10M loan amounts
- Up to 75% of market value
- No appraisals, personal financials, or guarantees
- Close in as little as 5–10 days
- 12–24 month terms
- Interest-only payments

Contact: Dan McColl, dan@trinitysd.com, (858) 775-0962
