-- Migration: Simplify broker schema
-- Run this in Supabase SQL Editor

-- 1. Drop the old partial unique index on license_number
DROP INDEX IF EXISTS idx_brokers_license;

-- 2. Clean up any NULL license_numbers (shouldn't exist, but just in case)
DELETE FROM brokers WHERE license_number IS NULL;

-- 3. Add proper UNIQUE constraint on license_number
ALTER TABLE brokers 
  ALTER COLUMN license_number SET NOT NULL,
  ADD CONSTRAINT brokers_license_number_unique UNIQUE (license_number);

-- 4. Add index on email for lookups
CREATE INDEX IF NOT EXISTS idx_brokers_email ON brokers(email) WHERE email IS NOT NULL;

-- 5. Drop broker_emails table if it exists (we're simplifying to one email per broker)
DROP TABLE IF EXISTS broker_emails CASCADE;

-- 6. Update views to use brokers.email directly

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
