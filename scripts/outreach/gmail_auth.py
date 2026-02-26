"""
Gmail API authentication and email sending.

First run will open browser for OAuth. Token is cached in token.json.

Usage:
    from gmail_auth import send_email, get_gmail_service
    
    # Send a single email
    send_email(
        to="agent@example.com",
        subject="Investment Opportunity",
        body="Hello, I noticed..."
    )
"""

import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
]

SCRIPT_DIR = Path(__file__).parent
CREDENTIALS_FILE = SCRIPT_DIR / 'credentials.json'
TOKEN_FILE = SCRIPT_DIR / 'token.json'


def get_gmail_service():
    """Get authenticated Gmail API service."""
    creds = None
    
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_FILE}\n"
                    "Follow gmail_setup.md to download OAuth credentials from Google Cloud."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        TOKEN_FILE.write_text(creds.to_json())
        print(f"Token saved to {TOKEN_FILE}")
    
    return build('gmail', 'v1', credentials=creds)


def create_message(to: str, subject: str, body: str, 
                   cc: str = None, bcc: str = None,
                   html: bool = False) -> dict:
    """Create email message for Gmail API."""
    if html:
        message = MIMEMultipart('alternative')
        message.attach(MIMEText(body, 'html'))
    else:
        message = MIMEText(body)
    
    message['to'] = to
    message['subject'] = subject
    
    if cc:
        message['cc'] = cc
    if bcc:
        message['bcc'] = bcc
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}


def send_email(to: str, subject: str, body: str,
               cc: str = None, bcc: str = None,
               html: bool = False,
               dry_run: bool = False) -> dict:
    """
    Send an email via Gmail API.
    
    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body (plain text or HTML)
        cc: CC recipients (comma-separated)
        bcc: BCC recipients (comma-separated)
        html: If True, body is treated as HTML
        dry_run: If True, print but don't send
    
    Returns:
        Gmail API response dict with message ID and thread ID
    """
    if dry_run:
        print(f"[DRY RUN] Would send to: {to}")
        print(f"  Subject: {subject}")
        print(f"  Body preview: {body[:100]}...")
        return {'id': 'dry_run', 'threadId': 'dry_run'}
    
    service = get_gmail_service()
    message = create_message(to, subject, body, cc, bcc, html)
    
    result = service.users().messages().send(
        userId='me', body=message
    ).execute()
    
    print(f"Email sent to {to} - Message ID: {result['id']}")
    return result


def get_profile() -> dict:
    """Get authenticated user's email profile."""
    service = get_gmail_service()
    return service.users().getProfile(userId='me').execute()


if __name__ == '__main__':
    print("Testing Gmail API authentication...")
    profile = get_profile()
    print(f"Authenticated as: {profile['emailAddress']}")
    print(f"Total messages: {profile['messagesTotal']}")
    print("\nGmail API is ready to use!")
