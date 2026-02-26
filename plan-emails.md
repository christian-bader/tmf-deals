# Email System Architecture

## Overview

Gmail API integration for sending outreach emails and tracking full conversation history with brokers. This enables AI agents to read past interactions and generate contextually appropriate responses.

## Goals

1. **Send emails** to leads from `dan@trinitysd.com`
2. **Track all email history** (sent + received) with brokers in our database
3. **Prevent embarrassing mistakes** — never send "intro" email to someone we've already talked to
4. **Enable AI-powered responses** — agents can read conversation history and suggest organic follow-ups

## Implementation Status

| Component | Status |
|-----------|--------|
| Gmail service account auth | ✅ Done |
| Bootstrap sync (historical emails) | ✅ Done |
| email_messages / email_threads tables | ✅ Done |
| LLM-powered outreach evaluation | ✅ Done |
| Used-listing tracking (avoid duplicate outreach) | ✅ Done |
| Incremental sync (poll for replies) | ⏳ TODO |
| Send script (Gmail API) | ⏳ TODO |
| Frontend review UI | ⏳ TODO |

---

## Gmail Setup

**Authentication**: Service Account with Domain-Wide Delegation (Google Workspace)

- Service account JSON: `scripts/outreach/service_account.json`
- Impersonating: `dan@trinitysd.com`
- Scopes:
  - `gmail.send` — send emails
  - `gmail.readonly` — read inbox
  - `gmail.modify` — labels, drafts

---

## Database Schema

### `email_messages`

Unified table for all messages (sent and received).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `broker_id` | UUID | FK to brokers (nullable if unmatched) |
| `gmail_thread_id` | TEXT | Gmail thread ID |
| `gmail_message_id` | TEXT | Gmail message ID (unique) |
| `direction` | TEXT | `'outbound'` or `'inbound'` |
| `from_address` | TEXT | Sender email |
| `to_address` | TEXT | Recipient email |
| `subject` | TEXT | Email subject |
| `body_text` | TEXT | Plain text body |
| `body_html` | TEXT | HTML body (if available) |
| `sent_at` | TIMESTAMPTZ | When the email was sent |
| `in_reply_to` | TEXT | Parent message ID |
| `suggested_email_id` | UUID | FK if sent from our system |
| `created_at` | TIMESTAMPTZ | When we imported it |

### `email_threads`

Thread-level summary for quick lookups.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `broker_id` | UUID | FK to brokers |
| `gmail_thread_id` | TEXT | Gmail thread ID (unique) |
| `subject` | TEXT | From first message |
| `status` | TEXT | `'active'`, `'awaiting_reply'`, `'replied'`, `'closed'` |
| `message_count` | INT | Total messages in thread |
| `outbound_count` | INT | Messages we sent |
| `inbound_count` | INT | Messages they sent |
| `first_message_at` | TIMESTAMPTZ | Thread start |
| `last_message_at` | TIMESTAMPTZ | Most recent message |
| `last_inbound_at` | TIMESTAMPTZ | When they last replied |
| `last_outbound_at` | TIMESTAMPTZ | When we last sent |

### `gmail_sync_state`

Track sync progress for incremental updates.

| Column | Type | Description |
|--------|------|-------------|
| `account_email` | TEXT | Gmail account (unique) |
| `last_history_id` | BIGINT | For Gmail history API |
| `last_full_sync_at` | TIMESTAMPTZ | Last bootstrap run |
| `last_incremental_sync_at` | TIMESTAMPTZ | Last incremental sync |

### Brokers table addition

```sql
ALTER TABLE brokers ADD COLUMN gmail_synced_at TIMESTAMPTZ;
```

---

## Sync Strategy

### Bootstrap (One-Time)

Run once to import all historical emails with known brokers.

```
1. SELECT DISTINCT email FROM brokers WHERE email IS NOT NULL
2. For each broker email:
   - Gmail search: "to:{email} OR from:{email}"
   - Fetch full message content
   - Insert into email_messages (skip duplicates via gmail_message_id UNIQUE)
   - Upsert email_threads
3. UPDATE brokers SET gmail_synced_at = now() WHERE email = {email}
```

### Before Sending Outreach

```
1. SELECT * FROM email_threads WHERE broker_id = {broker_id}
2. If threads exist:
   - Load full conversation: SELECT * FROM email_messages WHERE gmail_thread_id IN (...)
   - Pass to AI for context-aware response
   - NOT a first contact — use follow-up tone
3. If no threads:
   - First contact — use intro template
```

### Ongoing Sync (Cron)

```
1. Get last_history_id from gmail_sync_state
2. Call Gmail history.list API
3. For each new message:
   - Check if from/to matches a broker email
   - If yes, import into email_messages
   - Update email_threads
4. Update last_history_id
```

---

## Views

### `broker_conversations`

Aggregate view for dashboard.

```sql
SELECT 
  b.id as broker_id,
  b.name,
  b.email,
  COUNT(DISTINCT et.id) as thread_count,
  SUM(CASE WHEN em.direction = 'outbound' THEN 1 ELSE 0 END) as sent_count,
  SUM(CASE WHEN em.direction = 'inbound' THEN 1 ELSE 0 END) as received_count,
  MAX(em.sent_at) as last_interaction,
  BOOL_OR(em.direction = 'inbound') as has_replied
FROM brokers b
LEFT JOIN email_threads et ON b.id = et.broker_id
LEFT JOIN email_messages em ON et.gmail_thread_id = em.gmail_thread_id
GROUP BY b.id, b.name, b.email;
```

---

## Scripts

| Script | Status | Purpose |
|--------|--------|---------|
| `gmail_auth.py` | ✅ | Service account auth, send/read helpers |
| `gmail_bootstrap_sync.py` | ✅ | One-time historical import |
| `evaluate_outreach.py` | ✅ | LLM-powered decision engine |
| `gmail_incremental_sync.py` | ⏳ TODO | Cron job for ongoing reply sync |
| `send_outreach.py` | ⏳ TODO | Send approved emails via Gmail API |

---

## LLM-Powered Outreach Decision Engine

### North Star Goal
**Close hard money loan deals.** Brokers have the clients — build relationships so they think of Trinity when their investor clients need fast capital.

### How It Works

Instead of a complex rule-based template system, the LLM gets full context and decides:

1. **Should we email this broker?**
2. **If yes, what should we say?**
3. **If no, why?** (logged for audit)

### Context Provided to LLM

- Broker info (name, brokerage, email)
- **New listings** (ones not yet used in any outreach — the trigger)
- **Used listings** (already emailed about — for context only)
- Full email conversation history (last 10 messages)
- Conversation summary (threads, sent/received counts, last contact date)
- Template examples (to learn Dan's voice and Trinity's value prop)

### Used-Listing Tracking

Each listing can only trigger outreach **once**. When a `suggested_email` is created, the listing IDs are stored in `new_listing_ids`. Future evaluations filter these out, ensuring:
- No duplicate outreach about the same property
- System handles continuous operation naturally
- New scrapes → new listings → new outreach opportunities

### Decision Outputs

**If SEND:**
```json
{
  "decision": "send",
  "reason": "No prior contact, new listing is a good conversation starter",
  "email": {
    "subject": "383 Westbourne",
    "body": "Hi Mia, Saw your listing..."
  }
}
```

**If SKIP:**
```json
{
  "decision": "skip",
  "reason": "Already emailed 5 days ago, too soon to follow up",
  "email": null
}
```

### Tone Calibration by Relationship

The LLM automatically adjusts tone based on relationship history:

| Relationship | Tone |
|--------------|------|
| **Cold** (no history) | Introduce Trinity, mention listing |
| **Outbound only** (sent, no reply) | Don't re-intro, reference new listing as reconnect reason |
| **Engaged** (they've replied) | Casual, warm, reference past conversation |
| **Client** (heavy back-and-forth) | Super minimal — "saw this, nice" energy |

### Thread Continuity

`suggested_emails` includes `reply_to_thread_id` to maintain conversation threading. When sending follow-ups, use Gmail's `In-Reply-To` header to chain properly.

### Benefits

- No template maze — LLM adapts to any relationship stage
- Transparent reasoning — audit log shows why each decision was made
- Handles edge cases — clients, active convos, weird timing
- Easy to tune — update the prompt, not code

---

## Migration Path

1. Create `email_messages`, `email_threads`, `gmail_sync_state` tables
2. Add `gmail_synced_at` to brokers
3. Run bootstrap sync
4. Backfill from existing `sent_email_logs` (optional)
5. Update scripts to use new tables
6. Deprecate `sent_email_logs` after verification

---

## Remaining Work

1. **Incremental sync** — Poll Gmail for new replies to existing threads
2. **Send script** — Actually send approved emails via Gmail API
3. **Frontend UI** — Review/approve/reject suggested emails

## Resolved Questions

- **Rate limiting**: 1 second delay between LLM calls; 0.1s between Gmail fetches
- **Thread status**: Auto-set based on inbound/outbound counts during sync
- **Email bodies**: Storing both `body_text` and `body_html` for flexibility
