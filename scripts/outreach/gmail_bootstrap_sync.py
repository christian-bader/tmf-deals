#!/usr/bin/env python3
"""
Bootstrap sync: Import all historical Gmail conversations with known brokers.

Run this once to populate email_messages and email_threads tables.

Usage:
    python gmail_bootstrap_sync.py --dry-run     # Preview what would be synced
    python gmail_bootstrap_sync.py               # Actually sync
    python gmail_bootstrap_sync.py --limit 10    # Sync only first 10 brokers
"""

import argparse
import base64
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

from gmail_auth import get_gmail_service, USER_TO_IMPERSONATE

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_header(headers: list, name: str) -> Optional[str]:
    """Extract header value from Gmail message headers."""
    for h in headers:
        if h['name'].lower() == name.lower():
            return h['value']
    return None


def extract_email_address(header_value: str) -> Optional[str]:
    """Extract email address from header like 'Name <email@domain.com>'."""
    if not header_value:
        return None
    match = re.search(r'<([^>]+)>', header_value)
    if match:
        return match.group(1).lower()
    if '@' in header_value:
        return header_value.strip().lower()
    return None


def decode_body(payload: dict) -> tuple[Optional[str], Optional[str]]:
    """Extract plain text and HTML body from message payload."""
    body_text = None
    body_html = None
    
    def extract_parts(part):
        nonlocal body_text, body_html
        mime_type = part.get('mimeType', '')
        
        if 'body' in part and part['body'].get('data'):
            data = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
            if mime_type == 'text/plain' and not body_text:
                body_text = data
            elif mime_type == 'text/html' and not body_html:
                body_html = data
        
        if 'parts' in part:
            for p in part['parts']:
                extract_parts(p)
    
    extract_parts(payload)
    return body_text, body_html


def parse_gmail_message(msg: dict, our_email: str) -> dict:
    """Parse Gmail API message into our schema format."""
    headers = msg.get('payload', {}).get('headers', [])
    
    from_header = get_header(headers, 'From')
    to_header = get_header(headers, 'To')
    subject = get_header(headers, 'Subject')
    date_header = get_header(headers, 'Date')
    in_reply_to = get_header(headers, 'In-Reply-To')
    message_id = get_header(headers, 'Message-ID')
    
    from_address = extract_email_address(from_header)
    to_address = extract_email_address(to_header)
    
    direction = 'outbound' if from_address == our_email.lower() else 'inbound'
    
    internal_date = int(msg.get('internalDate', 0))
    sent_at = datetime.fromtimestamp(internal_date / 1000).isoformat()
    
    body_text, body_html = decode_body(msg.get('payload', {}))
    
    return {
        'gmail_thread_id': msg['threadId'],
        'gmail_message_id': msg['id'],
        'direction': direction,
        'from_address': from_address,
        'to_address': to_address,
        'subject': subject,
        'body_text': body_text,
        'body_html': body_html,
        'sent_at': sent_at,
        'in_reply_to': in_reply_to,
    }


def search_gmail_for_broker(service, broker_email: str) -> list[dict]:
    """Search Gmail for all messages to/from a broker email."""
    query = f'to:{broker_email} OR from:{broker_email}'
    messages = []
    page_token = None
    
    while True:
        result = service.users().messages().list(
            userId='me',
            q=query,
            pageToken=page_token,
            maxResults=100
        ).execute()
        
        if 'messages' in result:
            messages.extend(result['messages'])
        
        page_token = result.get('nextPageToken')
        if not page_token:
            break
    
    return messages


def get_full_message(service, message_id: str) -> dict:
    """Fetch full message content from Gmail."""
    return service.users().messages().get(
        userId='me',
        id=message_id,
        format='full'
    ).execute()


def upsert_thread(supabase: Client, broker_id: str, thread_id: str, messages: list[dict]):
    """Create or update email_threads record."""
    outbound = [m for m in messages if m['direction'] == 'outbound']
    inbound = [m for m in messages if m['direction'] == 'inbound']
    
    all_times = [m['sent_at'] for m in messages]
    first_msg = min(messages, key=lambda m: m['sent_at'])
    
    thread_data = {
        'broker_id': broker_id,
        'gmail_thread_id': thread_id,
        'subject': first_msg.get('subject'),
        'message_count': len(messages),
        'outbound_count': len(outbound),
        'inbound_count': len(inbound),
        'first_message_at': min(all_times),
        'last_message_at': max(all_times),
        'last_outbound_at': max([m['sent_at'] for m in outbound]) if outbound else None,
        'last_inbound_at': max([m['sent_at'] for m in inbound]) if inbound else None,
        'status': 'replied' if inbound else 'awaiting_reply',
    }
    
    supabase.table('email_threads').upsert(
        thread_data,
        on_conflict='gmail_thread_id'
    ).execute()


def main():
    parser = argparse.ArgumentParser(description='Bootstrap Gmail sync for known brokers')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing to DB')
    parser.add_argument('--limit', type=int, help='Limit number of brokers to sync')
    parser.add_argument('--broker-email', type=str, help='Sync only a specific broker email')
    args = parser.parse_args()
    
    print(f"Gmail Bootstrap Sync")
    print(f"{'='*50}")
    print(f"Gmail account: {USER_TO_IMPERSONATE}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()
    
    supabase = get_supabase_client()
    service = get_gmail_service()
    
    profile = service.users().getProfile(userId='me').execute()
    print(f"Authenticated as: {profile['emailAddress']}")
    our_email = profile['emailAddress']
    print()
    
    if args.broker_email:
        result = supabase.table('brokers').select('id, email, name').eq('email', args.broker_email).execute()
    else:
        query = supabase.table('brokers').select('id, email, name').not_.is_('email', 'null')
        if args.limit:
            query = query.limit(args.limit)
        result = query.execute()
    
    brokers = result.data or []
    print(f"Found {len(brokers)} brokers with email addresses")
    print()
    
    stats = {
        'brokers_processed': 0,
        'brokers_with_history': 0,
        'total_messages': 0,
        'total_threads': 0,
        'messages_inserted': 0,
    }
    
    for broker in brokers:
        broker_id = broker['id']
        broker_email = broker['email']
        broker_name = broker.get('name', 'Unknown')
        
        print(f"Processing: {broker_name} <{broker_email}>")
        
        message_refs = search_gmail_for_broker(service, broker_email)
        
        if not message_refs:
            print(f"  No Gmail history found")
            stats['brokers_processed'] += 1
            continue
        
        print(f"  Found {len(message_refs)} messages")
        stats['brokers_with_history'] += 1
        stats['total_messages'] += len(message_refs)
        
        threads = {}
        
        for ref in message_refs:
            time.sleep(0.1)
            
            try:
                full_msg = get_full_message(service, ref['id'])
                parsed = parse_gmail_message(full_msg, our_email)
                parsed['broker_id'] = broker_id
                
                thread_id = parsed['gmail_thread_id']
                if thread_id not in threads:
                    threads[thread_id] = []
                threads[thread_id].append(parsed)
                
            except Exception as e:
                print(f"  Error fetching message {ref['id']}: {e}")
                continue
        
        print(f"  Organized into {len(threads)} threads")
        stats['total_threads'] += len(threads)
        
        if args.dry_run:
            for thread_id, messages in threads.items():
                outbound = sum(1 for m in messages if m['direction'] == 'outbound')
                inbound = sum(1 for m in messages if m['direction'] == 'inbound')
                subj = messages[0].get('subject', '(no subject)')[:50]
                print(f"    Thread: {subj}... ({outbound} out, {inbound} in)")
        else:
            for thread_id, messages in threads.items():
                for msg in messages:
                    try:
                        supabase.table('email_messages').upsert(
                            msg,
                            on_conflict='gmail_message_id'
                        ).execute()
                        stats['messages_inserted'] += 1
                    except Exception as e:
                        print(f"    Error inserting message: {e}")
                
                upsert_thread(supabase, broker_id, thread_id, messages)
            
            supabase.table('brokers').update({
                'gmail_synced_at': datetime.now().isoformat()
            }).eq('id', broker_id).execute()
        
        stats['brokers_processed'] += 1
        print()
    
    print(f"{'='*50}")
    print(f"SUMMARY")
    print(f"{'='*50}")
    print(f"Brokers processed: {stats['brokers_processed']}")
    print(f"Brokers with Gmail history: {stats['brokers_with_history']}")
    print(f"Total messages found: {stats['total_messages']}")
    print(f"Total threads: {stats['total_threads']}")
    if not args.dry_run:
        print(f"Messages inserted: {stats['messages_inserted']}")
    
    if not args.dry_run:
        supabase.table('gmail_sync_state').upsert({
            'account_email': our_email,
            'last_full_sync_at': datetime.now().isoformat(),
        }, on_conflict='account_email').execute()
        print(f"\nSync state updated for {our_email}")


if __name__ == '__main__':
    main()
