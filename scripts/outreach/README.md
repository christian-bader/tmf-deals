# Agent Outreach

Send personalized outreach emails to listing agents from recently sold properties.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Gmail API:**
   Follow `gmail_setup.md` to:
   - Create Google Cloud project
   - Enable Gmail API
   - Download OAuth credentials

3. **First-time authentication:**
   ```bash
   python gmail_auth.py
   ```
   This opens a browser for Google OAuth. Your token is saved for future runs.

## Usage

### Dry Run (Preview)

```bash
python send_outreach.py
```

Shows what emails would be sent without actually sending.

### Send Emails

```bash
# Send up to 10 emails
python send_outreach.py --send

# Send up to 5 emails
python send_outreach.py --send --limit 5

# Adjust delay between emails (seconds)
python send_outreach.py --send --delay 10
```

### Tracking

Sent emails are logged to `sent_emails.csv` to avoid contacting the same agent twice.

## Files

| File | Description |
|------|-------------|
| `gmail_auth.py` | Gmail API authentication and send functions |
| `gmail_setup.md` | Setup guide for Google Cloud / Gmail API |
| `send_outreach.py` | Main outreach script |
| `sent_emails.csv` | Log of sent emails (auto-created) |
| `credentials.json` | OAuth credentials (from Google Cloud, not committed) |
| `token.json` | Auth token (auto-created after first login, not committed) |

## Workflow

1. Run `scrape_current_listings.py` to get recent sales
2. Review `data/listings/daily/recently_sold.csv`
3. Run `send_outreach.py` in dry-run mode to preview
4. Run `send_outreach.py --send` to send emails
