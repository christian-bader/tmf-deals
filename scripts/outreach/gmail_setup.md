# Gmail API Setup

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name it: `idi-outreach` (or similar)
4. Click "Create"

## Step 2: Enable Gmail API

1. In your new project, go to **APIs & Services → Library**
2. Search for "Gmail API"
3. Click on it → Click **Enable**

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Select **External** (unless you have Google Workspace)
3. Fill in:
   - App name: `IDI Outreach`
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue**
5. Scopes: Click **Add or Remove Scopes**
   - Add: `https://www.googleapis.com/auth/gmail.send`
   - Add: `https://www.googleapis.com/auth/gmail.readonly` (optional, for checking sent)
6. Click **Save and Continue**
7. Test users: Add your Gmail address
8. Click **Save and Continue**

## Step 4: Create OAuth Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Name: `IDI Outreach Desktop`
5. Click **Create**
6. Click **Download JSON**
7. Save as `credentials.json` in this folder (`scripts/outreach/`)

## Step 5: First Run

```bash
cd scripts/outreach
python gmail_auth.py
```

This will:
1. Open a browser for Google OAuth
2. You'll authorize the app
3. Save token to `token.json` (reused for future runs)

## Files

- `credentials.json` - OAuth client credentials (from Google Cloud, DO NOT COMMIT)
- `token.json` - Your auth token (created after first login, DO NOT COMMIT)
- `gmail_auth.py` - Auth helper + send functions

## Security

Add to `.gitignore`:
```
scripts/outreach/credentials.json
scripts/outreach/token.json
```
