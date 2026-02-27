-- Migration: Email tracking tables for Gmail sync
-- Run this in Supabase SQL Editor

BEGIN;

-- ============================================
-- EMAIL MESSAGES TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS email_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_id UUID REFERENCES brokers(id) ON DELETE SET NULL,
  gmail_thread_id TEXT NOT NULL,
  gmail_message_id TEXT NOT NULL UNIQUE,
  direction TEXT NOT NULL CHECK (direction IN ('outbound', 'inbound')),
  from_address TEXT,
  to_address TEXT,
  subject TEXT,
  body_text TEXT,
  body_html TEXT,
  sent_at TIMESTAMPTZ NOT NULL,
  in_reply_to TEXT,
  suggested_email_id UUID REFERENCES suggested_emails(id) ON DELETE SET NULL,
  raw_headers JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_email_messages_broker ON email_messages(broker_id);
CREATE INDEX IF NOT EXISTS idx_email_messages_thread ON email_messages(gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_email_messages_sent_at ON email_messages(sent_at);
CREATE INDEX IF NOT EXISTS idx_email_messages_direction ON email_messages(direction);

-- ============================================
-- EMAIL THREADS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS email_threads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  broker_id UUID REFERENCES brokers(id) ON DELETE SET NULL,
  gmail_thread_id TEXT NOT NULL UNIQUE,
  subject TEXT,
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'awaiting_reply', 'replied', 'closed')),
  message_count INT DEFAULT 0,
  outbound_count INT DEFAULT 0,
  inbound_count INT DEFAULT 0,
  first_message_at TIMESTAMPTZ,
  last_message_at TIMESTAMPTZ,
  last_inbound_at TIMESTAMPTZ,
  last_outbound_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_email_threads_broker ON email_threads(broker_id);
CREATE INDEX IF NOT EXISTS idx_email_threads_status ON email_threads(status);
CREATE INDEX IF NOT EXISTS idx_email_threads_last_message ON email_threads(last_message_at);

-- ============================================
-- GMAIL SYNC STATE TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS gmail_sync_state (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_email TEXT NOT NULL UNIQUE,
  last_history_id BIGINT,
  last_full_sync_at TIMESTAMPTZ,
  last_incremental_sync_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- ADD GMAIL SYNC TRACKING TO BROKERS
-- ============================================

ALTER TABLE brokers ADD COLUMN IF NOT EXISTS gmail_synced_at TIMESTAMPTZ;

-- ============================================
-- VIEWS
-- ============================================

-- Broker conversations summary
CREATE OR REPLACE VIEW broker_conversations AS
SELECT 
  b.id as broker_id,
  b.name,
  b.email,
  b.brokerage_name,
  b.gmail_synced_at,
  COUNT(DISTINCT et.id) as thread_count,
  COALESCE(SUM(et.message_count), 0) as total_messages,
  COALESCE(SUM(et.outbound_count), 0) as sent_count,
  COALESCE(SUM(et.inbound_count), 0) as received_count,
  MAX(et.last_message_at) as last_interaction,
  MAX(et.last_inbound_at) as last_reply_at,
  BOOL_OR(et.inbound_count > 0) as has_replied
FROM brokers b
LEFT JOIN email_threads et ON b.id = et.broker_id
GROUP BY b.id, b.name, b.email, b.brokerage_name, b.gmail_synced_at;

-- Thread details with broker info
CREATE OR REPLACE VIEW thread_details AS
SELECT 
  et.*,
  b.name as broker_name,
  b.email as broker_email,
  b.brokerage_name
FROM email_threads et
JOIN brokers b ON et.broker_id = b.id
ORDER BY et.last_message_at DESC;

-- ============================================
-- TRIGGER FOR UPDATED_AT
-- ============================================

DROP TRIGGER IF EXISTS update_email_threads_updated_at ON email_threads;
CREATE TRIGGER update_email_threads_updated_at
    BEFORE UPDATE ON email_threads
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_gmail_sync_state_updated_at ON gmail_sync_state;
CREATE TRIGGER update_gmail_sync_state_updated_at
    BEFORE UPDATE ON gmail_sync_state
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMIT;

-- ============================================
-- VERIFICATION QUERIES
-- ============================================

-- Check tables were created
-- SELECT table_name FROM information_schema.tables WHERE table_name IN ('email_messages', 'email_threads', 'gmail_sync_state');

-- Check brokers column was added
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'brokers' AND column_name = 'gmail_synced_at';
