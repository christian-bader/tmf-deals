-- Migration: Add thread tracking to suggested_emails
-- Run this in Supabase SQL Editor

-- Add column to track which thread this email should reply to (for continuity)
ALTER TABLE suggested_emails 
ADD COLUMN IF NOT EXISTS reply_to_thread_id TEXT;

-- Add index for looking up by thread
CREATE INDEX IF NOT EXISTS idx_suggested_emails_thread 
ON suggested_emails(reply_to_thread_id) 
WHERE reply_to_thread_id IS NOT NULL;
