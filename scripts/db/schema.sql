-- TMF Deals - Supabase Schema
-- Run this in the Supabase SQL Editor

-- ============================================
-- REFERENCE TABLES
-- ============================================

-- CA DRE License Database (canonical source of truth)
CREATE TABLE IF NOT EXISTS dre_licenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  license_number TEXT NOT NULL UNIQUE,
  last_name TEXT,
  first_name TEXT,
  name_suffix TEXT,
  license_type TEXT,  -- 'Salesperson', 'Broker', 'Corporation', 'Officer'
  license_status TEXT,  -- 'Licensed', 'Expired', etc.
  license_effective_date DATE,
  license_expiration_date DATE,
  original_license_date DATE,
  related_license_number TEXT,  -- supervising broker or corporation
  related_name TEXT,
  related_license_type TEXT,
  address_1 TEXT,
  address_2 TEXT,
  city TEXT,
  state TEXT,
  zip_code TEXT,
  county_name TEXT,
  full_name TEXT GENERATED ALWAYS AS (
    TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '') || 
    CASE WHEN name_suffix IS NOT NULL AND name_suffix != '' 
         THEN ' ' || name_suffix ELSE '' END)
  ) STORED,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dre_last_name ON dre_licenses(last_name);
CREATE INDEX IF NOT EXISTS idx_dre_city ON dre_licenses(city);
CREATE INDEX IF NOT EXISTS idx_dre_zip ON dre_licenses(zip_code);
CREATE INDEX IF NOT EXISTS idx_dre_status ON dre_licenses(license_status);

-- ============================================
-- CORE TABLES
-- ============================================

-- All properties (active, pending, sold)
CREATE TABLE IF NOT EXISTS listings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  address TEXT NOT NULL,
  city TEXT,
  state TEXT,
  zip TEXT,
  price NUMERIC,
  beds INT2,
  baths NUMERIC,
  sqft INT4,
  lot_size TEXT,
  year_built INT2,
  property_type TEXT,
  stories INT2,
  garage_spaces INT2,
  price_per_sqft NUMERIC,
  hoa_dues NUMERIC,
  status TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'pending' | 'sold'
  listing_date DATE,
  sale_date DATE,
  mls_number TEXT,
  days_on_market INT4,
  description TEXT,
  source_url TEXT UNIQUE,
  source_platform TEXT DEFAULT 'redfin',  -- 'redfin' | 'zillow' | 'mls'
  scraped_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);
CREATE INDEX IF NOT EXISTS idx_listings_zip ON listings(zip);
CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);

-- Real estate agents/brokers (one row per DRE license)
CREATE TABLE IF NOT EXISTS brokers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  license_number TEXT NOT NULL UNIQUE,  -- DRE license number (primary identifier)
  name TEXT,
  email TEXT,  -- Primary contact email
  phone TEXT,
  brokerage_name TEXT,
  state_licensed TEXT DEFAULT 'CA',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_brokers_email ON brokers(email) WHERE email IS NOT NULL;

-- Junction: which broker represented which listing (and as buyer or seller)
CREATE TABLE IF NOT EXISTS broker_listings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_id UUID NOT NULL REFERENCES brokers(id) ON DELETE CASCADE,
  listing_id UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  role TEXT NOT NULL,  -- 'buyer' | 'seller'
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(broker_id, listing_id, role)
);

CREATE INDEX IF NOT EXISTS idx_broker_listings_broker ON broker_listings(broker_id);
CREATE INDEX IF NOT EXISTS idx_broker_listings_listing ON broker_listings(listing_id);

-- ============================================
-- OUTREACH TABLES
-- ============================================

-- LLM-generated email drafts (queue for review)
CREATE TABLE IF NOT EXISTS suggested_emails (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_id UUID NOT NULL REFERENCES brokers(id) ON DELETE CASCADE,
  new_listing_ids UUID[],  -- array of listing IDs that triggered this
  subject TEXT,
  body_content TEXT,
  tone_instruction TEXT,
  prior_contact_context JSONB,
  is_first_contact BOOLEAN DEFAULT true,
  status TEXT DEFAULT 'draft',  -- 'draft' | 'approved' | 'sent' | 'skipped'
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_suggested_emails_broker ON suggested_emails(broker_id);
CREATE INDEX IF NOT EXISTS idx_suggested_emails_status ON suggested_emails(status);

-- Audit log of actually sent emails (written by Apps Script)
CREATE TABLE IF NOT EXISTS sent_email_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  suggested_email_id UUID REFERENCES suggested_emails(id) ON DELETE SET NULL,
  broker_id UUID NOT NULL REFERENCES brokers(id) ON DELETE CASCADE,
  gmail_message_id TEXT UNIQUE,
  gmail_thread_id TEXT,
  time_sent TIMESTAMPTZ DEFAULT now(),
  body_snapshot TEXT,
  listing_ids_included UUID[],
  send_status TEXT DEFAULT 'sent',  -- 'sent' | 'failed'
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sent_email_logs_broker ON sent_email_logs(broker_id);
CREATE INDEX IF NOT EXISTS idx_sent_email_logs_thread ON sent_email_logs(gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_sent_email_logs_time ON sent_email_logs(time_sent);

-- Why we didn't email someone (audit trail)
CREATE TABLE IF NOT EXISTS outreach_suppression_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_id UUID NOT NULL REFERENCES brokers(id) ON DELETE CASCADE,
  checked_at TIMESTAMPTZ DEFAULT now(),
  reason TEXT,  -- 'no_new_listings' | 'too_recent' | 'no_email' | 'manual_skip'
  days_since_last_contact INT4,
  new_listing_count INT4,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_suppression_broker ON outreach_suppression_logs(broker_id);

-- ============================================
-- VIEWS
-- ============================================

-- Brokers with their listing activity (for dashboard/browse)
CREATE OR REPLACE VIEW broker_activity AS
SELECT 
  b.id as broker_id,
  b.name,
  b.email,
  b.phone,
  b.brokerage_name,
  b.license_number,
  COUNT(DISTINCT bl.listing_id) as total_listings,
  COUNT(DISTINCT CASE WHEN l.status = 'active' THEN bl.listing_id END) as active_listings,
  COUNT(DISTINCT CASE WHEN l.status = 'pending' THEN bl.listing_id END) as pending_listings,
  COUNT(DISTINCT CASE WHEN l.status = 'sold' THEN bl.listing_id END) as sold_listings,
  COUNT(DISTINCT CASE WHEN bl.role = 'buyer' THEN bl.listing_id END) as buyer_deals,
  COUNT(DISTINCT CASE WHEN bl.role = 'seller' THEN bl.listing_id END) as seller_deals,
  MAX(l.scraped_at) as latest_activity
FROM brokers b
LEFT JOIN broker_listings bl ON b.id = bl.broker_id
LEFT JOIN listings l ON bl.listing_id = l.id
GROUP BY b.id, b.name, b.email, b.phone, b.brokerage_name, b.license_number;

-- Brokers eligible for outreach (not contacted in 30 days, has email)
CREATE OR REPLACE VIEW outreach_opportunities AS
SELECT 
  b.id as broker_id,
  b.name,
  b.email,
  b.phone,
  b.brokerage_name,
  b.license_number,
  (
    SELECT COALESCE(json_agg(json_build_object(
      'listing_id', l.id,
      'address', l.address,
      'city', l.city,
      'zip', l.zip,
      'price', l.price,
      'status', l.status,
      'role', bl.role,
      'listing_date', l.listing_date,
      'sale_date', l.sale_date
    ) ORDER BY l.scraped_at DESC), '[]'::json)
    FROM broker_listings bl
    JOIN listings l ON bl.listing_id = l.id
    WHERE bl.broker_id = b.id
  ) as listings,
  (
    SELECT MAX(sel.time_sent) 
    FROM sent_email_logs sel 
    WHERE sel.broker_id = b.id
  ) as last_contacted_at,
  (
    SELECT COUNT(*) 
    FROM sent_email_logs sel 
    WHERE sel.broker_id = b.id
  ) as total_emails_sent
FROM brokers b
WHERE b.email IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM sent_email_logs sel 
    WHERE sel.broker_id = b.id 
    AND sel.time_sent > now() - interval '30 days'
  );

-- Email queue view (suggested emails with broker info)
CREATE OR REPLACE VIEW email_queue AS
SELECT 
  se.id,
  se.broker_id,
  b.name as broker_name,
  b.email as broker_email,
  b.brokerage_name,
  se.subject,
  se.body_content,
  se.new_listing_ids,
  se.is_first_contact,
  se.status,
  se.created_at,
  (
    SELECT json_agg(json_build_object(
      'address', l.address,
      'price', l.price,
      'status', l.status
    ))
    FROM listings l
    WHERE l.id = ANY(se.new_listing_ids)
  ) as listing_details
FROM suggested_emails se
JOIN brokers b ON se.broker_id = b.id
ORDER BY se.created_at DESC;

-- ============================================
-- ROW LEVEL SECURITY (optional, enable if needed)
-- ============================================

-- For now, we'll use the anon key which has full access
-- Enable RLS and add policies if you need to restrict access

-- ALTER TABLE listings ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE brokers ENABLE ROW LEVEL SECURITY;
-- etc.

-- ============================================
-- FUNCTIONS
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables with updated_at
DROP TRIGGER IF EXISTS update_listings_updated_at ON listings;
CREATE TRIGGER update_listings_updated_at
    BEFORE UPDATE ON listings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_brokers_updated_at ON brokers;
CREATE TRIGGER update_brokers_updated_at
    BEFORE UPDATE ON brokers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_suggested_emails_updated_at ON suggested_emails;
CREATE TRIGGER update_suggested_emails_updated_at
    BEFORE UPDATE ON suggested_emails
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
