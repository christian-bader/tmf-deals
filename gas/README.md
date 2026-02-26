# TMF Deals - Google Apps Script

Email outreach automation using Google Apps Script with Supabase and Anthropic Claude.

## Setup

### 1. Create Apps Script Project

1. Go to [script.google.com](https://script.google.com)
2. Click "New Project"
3. Name it "TMF Outreach"

### 2. Add Script Files

Copy each `.gs` file from this folder into your Apps Script project:

- `Config.gs` - Configuration helpers
- `Supabase.gs` - Supabase REST API wrapper
- `Anthropic.gs` - Claude API integration
- `Templates.gs` - Email templates
- `Gmail.gs` - Gmail draft creation
- `Code.gs` - Main entry points

### 3. Set Script Properties

1. In Apps Script, go to **File > Project Settings**
2. Scroll to **Script Properties**
3. Add these properties:

| Property | Value |
|----------|-------|
| `SUPABASE_URL` | `https://your-project.supabase.co` |
| `SUPABASE_KEY` | Your Supabase anon key |
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |

### 4. Test Configuration

Run these functions in order to verify setup:

```
testConfig()      // Verify all properties are set
testSupabase()    // Test Supabase connection
testAnthropic()   // Test Claude API
```

## Usage

### Workflow

1. **Generate suggestions**: Run `generateSuggestedEmails()`
   - Fetches brokers from `outreach_opportunities` view
   - Uses Claude to personalize email openers
   - Inserts into `suggested_emails` table with `status: 'draft'`

2. **Review & approve**: In Supabase (or React app)
   - Review suggested emails
   - Set `status = 'approved'` for ones to send

3. **Create drafts**: Run `createDraftsFromApproved()`
   - Creates Gmail drafts for approved emails
   - Logs to `sent_email_logs` table
   - Updates `suggested_emails` status to `'sent'`

4. **Send**: Review drafts in Gmail and send manually

### Functions

| Function | Description |
|----------|-------------|
| `generateSuggestedEmails(limit)` | Generate LLM-personalized email suggestions |
| `createDraftsFromApproved(limit)` | Create Gmail drafts from approved suggestions |
| `previewEmail(brokerId)` | Preview what email would be generated |
| `testConfig()` | Verify script properties |
| `testSupabase()` | Test Supabase connection |
| `testAnthropic()` | Test Anthropic API |

### Running from Sheets (Optional)

If you bind this script to a Google Sheet:

1. Open a Google Sheet
2. Go to **Extensions > Apps Script**
3. Paste the code files
4. Refresh the Sheet
5. Use the **TMF Outreach** menu

## Template Types

| Type | Target | Trigger |
|------|--------|---------|
| `sale-listing` | Seller's agent | Active listing |
| `sale-pending` | Seller's agent | Pending/contingent listing |
| `buyer-closed` | Buyer's agent | Recently sold, represented buyer |

## Troubleshooting

### "Missing script properties"
Set all three properties in File > Project Settings > Script Properties.

### "Supabase error 401"
Check your `SUPABASE_KEY` is correct and hasn't expired.

### "Anthropic error 401"
Check your `ANTHROPIC_API_KEY` is correct.

### Rate Limits
The script includes 500ms delays between API calls. If you hit rate limits, increase the delay in `Code.gs`.
