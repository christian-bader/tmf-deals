-- Migration: Add broker_emails junction table
-- Run this in Supabase SQL Editor
-- 
-- This migration:
-- 1. Creates the broker_emails junction table
-- 2. Migrates existing emails from brokers table
-- 3. Removes the email column from brokers
-- 4. Updates views to use the new structure

BEGIN;

-- ============================================
-- STEP 1: Create broker_emails table
-- ============================================

CREATE TABLE IF NOT EXISTS broker_emails (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_id UUID NOT NULL REFERENCES brokers(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  source_listing_id UUID REFERENCES listings(id) ON DELETE SET NULL,
  is_primary BOOLEAN DEFAULT false,
  first_seen_at TIMESTAMPTZ DEFAULT now(),
  last_seen_at TIMESTAMPTZ DEFAULT now(),
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(broker_id, email)
);

CREATE INDEX IF NOT EXISTS idx_broker_emails_broker ON broker_emails(broker_id);
CREATE INDEX IF NOT EXISTS idx_broker_emails_email ON broker_emails(email);

-- ============================================
-- STEP 2: Migrate existing emails (if any)
-- ============================================

-- Move existing emails from brokers table to broker_emails
-- Mark them as primary since they were the only email
INSERT INTO broker_emails (broker_id, email, is_primary, first_seen_at, last_seen_at)
SELECT id, email, true, created_at, updated_at
FROM brokers
WHERE email IS NOT NULL AND email != ''
ON CONFLICT (broker_id, email) DO NOTHING;

-- ============================================
-- STEP 3: Remove email column from brokers
-- ============================================

-- Drop the unique index on email first
DROP INDEX IF EXISTS idx_brokers_email;

-- Drop the email column
ALTER TABLE brokers DROP COLUMN IF EXISTS email;

-- ============================================
-- STEP 4: Update views
-- ============================================

-- Broker activity view
CREATE OR REPLACE VIEW broker_activity AS
SELECT 
  b.id as broker_id,
  b.name,
  b.phone,
  b.brokerage_name,
  b.license_number,
  (
    SELECT be.email FROM broker_emails be 
    WHERE be.broker_id = b.id 
    ORDER BY be.is_primary DESC, be.first_seen_at ASC 
    LIMIT 1
  ) as primary_email,
  (SELECT COUNT(*) FROM broker_emails be WHERE be.broker_id = b.id) as email_count,
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
GROUP BY b.id, b.name, b.phone, b.brokerage_name, b.license_number;

-- Outreach opportunities view
CREATE OR REPLACE VIEW outreach_opportunities AS
SELECT 
  b.id as broker_id,
  b.name,
  b.phone,
  b.brokerage_name,
  b.license_number,
  (
    SELECT be.email FROM broker_emails be 
    WHERE be.broker_id = b.id 
    ORDER BY be.is_primary DESC, be.first_seen_at ASC 
    LIMIT 1
  ) as primary_email,
  (
    SELECT COALESCE(json_agg(json_build_object(
      'email', be.email,
      'is_primary', be.is_primary,
      'first_seen_at', be.first_seen_at
    ) ORDER BY be.is_primary DESC, be.first_seen_at ASC), '[]'::json)
    FROM broker_emails be
    WHERE be.broker_id = b.id
  ) as all_emails,
  (SELECT COUNT(*) FROM broker_emails be WHERE be.broker_id = b.id) as email_count,
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
WHERE EXISTS (
    SELECT 1 FROM broker_emails be WHERE be.broker_id = b.id
  )
  AND NOT EXISTS (
    SELECT 1 FROM sent_email_logs sel 
    WHERE sel.broker_id = b.id 
    AND sel.time_sent > now() - interval '30 days'
  );

-- Email queue view
CREATE OR REPLACE VIEW email_queue AS
SELECT 
  se.id,
  se.broker_id,
  b.name as broker_name,
  (
    SELECT be.email FROM broker_emails be 
    WHERE be.broker_id = b.id 
    ORDER BY be.is_primary DESC, be.first_seen_at ASC 
    LIMIT 1
  ) as broker_email,
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

-- Broker email summary view (for identifying corporate licenses)
CREATE OR REPLACE VIEW broker_email_summary AS
SELECT 
  b.id as broker_id,
  b.license_number,
  b.name,
  b.brokerage_name,
  d.license_type as dre_license_type,
  COUNT(be.id) as email_count,
  ARRAY_AGG(be.email ORDER BY be.first_seen_at) as emails,
  CASE 
    WHEN COUNT(be.id) > 10 THEN 'likely_corporate'
    WHEN COUNT(be.id) > 3 THEN 'multiple_emails'
    ELSE 'normal'
  END as status_hint
FROM brokers b
LEFT JOIN broker_emails be ON b.id = be.broker_id
LEFT JOIN dre_licenses d ON b.dre_license_id = d.id
GROUP BY b.id, b.license_number, b.name, b.brokerage_name, d.license_type
ORDER BY COUNT(be.id) DESC;

COMMIT;

-- ============================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================

-- Check broker_emails was created and populated
-- SELECT COUNT(*) as total_broker_emails FROM broker_emails;

-- Check brokers no longer has email column
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'brokers';

-- View brokers with multiple emails
-- SELECT * FROM broker_email_summary WHERE email_count > 1 LIMIT 20;
