"""
Gmail API authentication and email sending.

Uses Service Account with Domain-Wide Delegation for Google Workspace.

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

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
]

SCRIPT_DIR = Path(__file__).parent
SERVICE_ACCOUNT_FILE = SCRIPT_DIR / 'service_account.json'
USER_TO_IMPERSONATE = os.environ.get('GMAIL_USER', 'dan@trinitysd.com')


def get_gmail_service(user_email: str = None):
    """Get authenticated Gmail API service using service account."""
    user = user_email or USER_TO_IMPERSONATE
    
    if not SERVICE_ACCOUNT_FILE.exists():
        raise FileNotFoundError(
            f"service_account.json not found at {SERVICE_ACCOUNT_FILE}\n"
            "Follow gmail_setup.md to create a service account and download the JSON key."
        )
    
    credentials = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
    )
    delegated_creds = credentials.with_subject(user)
    
    return build('gmail', 'v1', credentials=delegated_creds)


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
