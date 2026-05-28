"""
Mail management commands for Office365

Sync, read, archive, mark read, and send emails.
"""

import sys
import re
import base64
import urllib.error
import urllib.request
import html2text
import argparse
from email.utils import getaddresses
from pathlib import Path
from datetime import datetime

from .common import get_access_token, make_graph_request, GRAPH_API_BASE
from .calendar import parse_since_expression

# Mail storage location
MAILDIR_BASE = Path.home() / ".mail" / "office365"

# Get local timezone
LOCAL_TZ = datetime.now().astimezone().tzinfo

# Cache for user's email domain
_USER_DOMAIN = None


def get_user_domain(access_token):
    """Get the logged-in user's email domain"""
    global _USER_DOMAIN
    if _USER_DOMAIN is None:
        user = make_graph_request('/me', access_token)
        if user:
            email = user.get('mail') or user.get('userPrincipalName', '')
            if '@' in email:
                _USER_DOMAIN = email.split('@')[1].lower()
            else:
                _USER_DOMAIN = ''
        else:
            _USER_DOMAIN = ''
    return _USER_DOMAIN


def is_external_sender(sender_email, user_domain):
    """Check if sender is from outside the organization"""
    if not sender_email or not user_domain:
        return False

    if '@' not in sender_email:
        return False

    sender_domain = sender_email.split('@')[1].lower()
    return sender_domain != user_domain


def parse_graph_datetime(dt_str):
    """Parse Microsoft Graph datetime format"""
    import re
    # Remove excess fractional seconds (keep max 6 digits)
    dt_str = re.sub(r'\.(\d{6})\d*', r'.\1', dt_str)
    # Handle timezone
    if not dt_str.endswith('Z') and '+' not in dt_str and '-' not in dt_str[-6:]:
        dt_str += 'Z'
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def get_messages_stream(access_token, folder='Inbox', max_count=None, since=None, unread=None, search=None):
    """Get messages from a mail folder, yielding pages as they're fetched

    Args:
        access_token: OAuth2 access token
        folder: Folder name (default: Inbox)
        max_count: Maximum number of messages (None for unlimited)
        since: Optional datetime to filter messages after
        unread: Optional filter for unread (True), read (False), or all (None)
        search: Optional search query

    Yields:
        Lists of message objects (one list per page)
    """
    # Build URL - use /me/messages for search to search all folders, otherwise use specific folder
    if search:
        # When searching, search all messages across all folders
        url = f"{GRAPH_API_BASE}/me/messages"
    else:
        # When not searching, use the specified folder
        import urllib.parse
        folder_encoded = urllib.parse.quote(folder)
        url = f"{GRAPH_API_BASE}/me/mailFolders/{folder_encoded}/messages"

    # Build query parameters - use a reasonable page size for streaming
    # Graph API default is 10, but we'll use 50 for better performance
    page_size = 50
    params = {
        '$top': str(page_size),
        '$select': 'id,subject,from,receivedDateTime,isRead,body,bodyPreview,hasAttachments',
        '$expand': 'attachments($select=id,name,contentType,size,isInline)'
    }

    # Add filters
    filters = []
    if since:
        since_str = since.strftime('%Y-%m-%dT%H:%M:%SZ')
        filters.append(f"receivedDateTime ge {since_str}")
    if unread is not None:
        filters.append(f"isRead eq {str(not unread).lower()}")
    if search:
        # Use $search for full-text search across subject, body, etc.
        # Note: $orderby is not supported with $search in Graph API
        params['$search'] = f'"{search}"'
    else:
        # Only add $orderby when not using $search
        params['$orderby'] = 'receivedDateTime desc'

    if filters:
        params['$filter'] = ' and '.join(filters)

    # Build query string
    import urllib.parse
    query_string = urllib.parse.urlencode(params)
    url = f"{url}?{query_string}"

    # Fetch messages with pagination, yielding each page
    total_fetched = 0
    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        page_messages = result.get('value', [])

        # If max_count is set, truncate this page if needed
        if max_count is not None:
            remaining = max_count - total_fetched
            if remaining <= 0:
                break
            if len(page_messages) > remaining:
                page_messages = page_messages[:remaining]

        total_fetched += len(page_messages)

        # Yield this page of messages
        if page_messages:
            yield page_messages

        # Check for pagination
        url = result.get('@odata.nextLink')

        # Stop if we've hit the limit
        if max_count is not None and total_fetched >= max_count:
            break


def display_message_summary(msg, user_domain):
    """Display a single message in list format"""
    # Parse date
    received = parse_graph_datetime(msg['receivedDateTime']).astimezone(LOCAL_TZ)
    date_str = received.strftime('%Y-%m-%d %H:%M')

    # Get sender
    from_field = msg.get('from', {}).get('emailAddress', {})
    sender = from_field.get('name') or from_field.get('address', 'Unknown')
    sender_email = from_field.get('address', '')

    # Get subject
    subject = msg.get('subject', '(No subject)')

    # Add [external] prefix if sender is from outside the organization
    if is_external_sender(sender_email, user_domain):
        subject = f"[external] {subject}"

    # Mark unread with indicator
    unread_mark = '●' if not msg.get('isRead', True) else ' '

    # Check for real attachments (not inline images)
    has_real_attachments = False
    for att in msg.get('attachments', []):
        if not att.get('isInline', False):
            has_real_attachments = True
            break
    attachment_mark = '📎' if has_real_attachments else ''

    # Full message ID
    msg_id = msg['id']

    print(f"{unread_mark} [{date_str}] {sender}")
    print(f"  Subject: {subject} {attachment_mark}")
    print(f"  ID: {msg_id}")
    print()


def display_message(msg, html=False):
    """Display a single message with full details"""
    # Parse date
    received = parse_graph_datetime(msg['receivedDateTime']).astimezone(LOCAL_TZ)
    date_str = received.strftime('%Y-%m-%d %H:%M:%S')

    # Get sender
    from_field = msg.get('from', {}).get('emailAddress', {})
    sender_name = from_field.get('name', '')
    sender_email = from_field.get('address', '')
    sender = f"{sender_name} <{sender_email}>" if sender_name else sender_email

    # Get recipients
    to_addresses = msg.get('toRecipients', [])
    to_list = [r.get('emailAddress', {}).get('address', '') for r in to_addresses]
    to_str = ', '.join(to_list)

    # Print header
    print("\n" + "=" * 80)
    print(f"From:    {sender}")
    print(f"To:      {to_str}")
    print(f"Date:    {date_str}")
    print(f"Subject: {msg.get('subject', '(No subject)')}")
    print(f"ID:      {msg['id']}")

    # Show attachments if present
    attachments = msg.get('attachments', [])
    if attachments:
        # Separate into real attachments vs inline images
        real_attachments = []
        inline_attachments = []

        for att in attachments:
            if att.get('isInline', False):
                inline_attachments.append(att)
            else:
                real_attachments.append(att)

        # Show real attachments first
        if real_attachments:
            print(f"\nAttachments ({len(real_attachments)}):")
            for att in real_attachments:
                name = att.get('name', 'Unknown')
                size = att.get('size', 0)
                att_id = att.get('id', 'Unknown')
                size_str = format_size(size)
                print(f"  📎 {name} ({size_str})")
                print(f"     ID: {att_id}")

        # Show inline attachments separately (collapsed by default)
        if inline_attachments:
            print(f"\nInline Images ({len(inline_attachments)}) - signatures, embedded content:")
            for att in inline_attachments:
                name = att.get('name', 'Unknown')
                size = att.get('size', 0)
                att_id = att.get('id', 'Unknown')
                content_id = att.get('contentId', '')
                size_str = format_size(size)
                # Show CID if available (useful for debugging)
                cid_str = f" [cid:{content_id}]" if content_id else ""
                print(f"  🖼️  {name} ({size_str}){cid_str}")
                print(f"     ID: {att_id}")

    print("=" * 80 + "\n")

    # Print body
    body = msg.get('body', {})
    content_type = body.get('contentType', 'text')
    content = body.get('content', '')

    if content_type == 'html' and not html:
        # Convert HTML to plain text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        content = h.handle(content)

    print(content)
    print("\n" + "=" * 80 + "\n")


def format_size(bytes_size):
    """Format byte size to human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f}TB"


# ============================================================================
# STRUCTURED DATA FUNCTIONS (for MCP and programmatic access)
# ============================================================================

def get_messages_structured(access_token, folder='Inbox', unread=None, since=None,
                           search=None, limit=None):
    """
    Get messages as structured data (for MCP/programmatic use).

    Args:
        access_token: OAuth2 access token
        folder: Mail folder name (default: 'Inbox')
        unread: Filter by read status - True (unread only), False (read only), None (all)
        since: Datetime object or None - filter messages received after this time
        search: Search query string
        limit: Maximum number of messages to return

    Returns:
        list[dict]: List of message dictionaries with schema:
            {
                'id': str,
                'subject': str,
                'from_email': str,
                'from_name': str,
                'received_datetime': str (ISO 8601),
                'is_read': bool,
                'has_attachments': bool,
                'has_real_attachments': bool,  # Excludes inline images
                'body_preview': str,
                'is_external': bool,
                'attachments': list[dict]  # Only if has_real_attachments
            }
    """
    # Get user domain for external sender detection
    user_domain = get_user_domain(access_token)

    messages = []
    for page in get_messages_stream(
        access_token,
        folder=folder,
        max_count=limit,
        since=since,
        unread=unread,
        search=search
    ):
        for msg in page:
            # Parse sender info
            from_field = msg.get('from', {}).get('emailAddress', {})
            from_email = from_field.get('address', '')
            from_name = from_field.get('name', '')

            # Check if sender is external
            is_ext = is_external_sender(from_email, user_domain)

            # Check for real attachments (not inline images)
            has_real_atts = False
            real_attachments = []
            for att in msg.get('attachments', []):
                if not att.get('isInline', False):
                    has_real_atts = True
                    real_attachments.append({
                        'id': att.get('id'),
                        'name': att.get('name'),
                        'content_type': att.get('contentType'),
                        'size': att.get('size', 0),
                        'is_inline': False
                    })

            # Build structured message
            structured_msg = {
                'id': msg['id'],
                'subject': msg.get('subject', '(No subject)'),
                'from_email': from_email,
                'from_name': from_name,
                'received_datetime': msg['receivedDateTime'],
                'is_read': msg.get('isRead', True),
                'has_attachments': msg.get('hasAttachments', False),
                'has_real_attachments': has_real_atts,
                'body_preview': msg.get('bodyPreview', ''),
                'is_external': is_ext
            }

            # Only include attachments array if there are real attachments
            if has_real_atts:
                structured_msg['attachments'] = real_attachments

            messages.append(structured_msg)

    return messages


def get_message_by_id_structured(access_token, message_id):
    """
    Get a single message by ID as structured data.

    Args:
        access_token: OAuth2 access token
        message_id: Graph API message ID

    Returns:
        dict: Message dictionary with full body content and attachments
    """
    url = f"{GRAPH_API_BASE}/me/messages/{message_id}?$expand=attachments"
    msg = make_graph_request(url, access_token)

    if not msg:
        return None

    # Parse sender
    from_field = msg.get('from', {}).get('emailAddress', {})
    from_email = from_field.get('address', '')
    from_name = from_field.get('name', '')

    # Parse recipients
    to_recipients = []
    for r in msg.get('toRecipients', []):
        to_recipients.append({
            'email': r.get('emailAddress', {}).get('address', ''),
            'name': r.get('emailAddress', {}).get('name', '')
        })

    # Get user domain
    user_domain = get_user_domain(access_token)
    is_ext = is_external_sender(from_email, user_domain)

    # Parse body
    body = msg.get('body', {})
    body_content = body.get('content', '')
    body_type = body.get('contentType', 'text')

    # Parse attachments
    all_attachments = []
    real_attachments = []
    inline_attachments = []

    for att in msg.get('attachments', []):
        att_dict = {
            'id': att.get('id'),
            'name': att.get('name'),
            'content_type': att.get('contentType'),
            'size': att.get('size', 0),
            'is_inline': att.get('isInline', False),
            'content_id': att.get('contentId', '')
        }

        all_attachments.append(att_dict)

        if att_dict['is_inline']:
            inline_attachments.append(att_dict)
        else:
            real_attachments.append(att_dict)

    return {
        'id': msg['id'],
        'subject': msg.get('subject', '(No subject)'),
        'from_email': from_email,
        'from_name': from_name,
        'to_recipients': to_recipients,
        'received_datetime': msg['receivedDateTime'],
        'is_read': msg.get('isRead', True),
        'is_external': is_ext,
        'body_content': body_content,
        'body_type': body_type,
        'attachments': real_attachments,
        'inline_attachments': inline_attachments,
        'has_attachments': len(all_attachments) > 0,
        'has_real_attachments': len(real_attachments) > 0
    }


def send_email_structured(access_token, to_addresses, subject, body,
                          cc_addresses=None, bcc_addresses=None, is_html=True):
    """
    Send an email and return status (for MCP/programmatic use).

    Args:
        access_token: OAuth2 access token
        to_addresses: List of recipient email addresses
        subject: Email subject
        body: Email body content
        cc_addresses: Optional list of CC addresses
        bcc_addresses: Optional list of BCC addresses
        is_html: Whether body is HTML (default: True)

    Returns:
        dict: Status dictionary with:
            {
                'status': 'success' | 'error',
                'message': str,
                'error': str (only if status='error')
            }
    """
    # Build message
    message = {
        'subject': subject,
        'body': {
            'contentType': 'HTML' if is_html else 'Text',
            'content': body
        },
        'toRecipients': [
            {'emailAddress': {'address': addr}}
            for addr in to_addresses
        ]
    }

    if cc_addresses:
        message['ccRecipients'] = [
            {'emailAddress': {'address': addr}}
            for addr in cc_addresses
        ]

    if bcc_addresses:
        message['bccRecipients'] = [
            {'emailAddress': {'address': addr}}
            for addr in bcc_addresses
        ]

    # Send via Graph API
    url = f"{GRAPH_API_BASE}/me/sendMail"
    result = make_graph_request(url, access_token, method='POST', data={'message': message})

    if result is False:  # make_graph_request returns False on error
        return {
            'status': 'error',
            'message': 'Failed to send email',
            'error': 'Graph API request failed'
        }

    return {
        'status': 'success',
        'message': f'Email sent to {", ".join(to_addresses)}'
    }


# ============================================================================
# CLI COMMAND FUNCTIONS
# ============================================================================

def cmd_read(args):
    """Handle 'o365 mail read' command using Graph API"""
    access_token = get_access_token()

    # If specific message IDs provided, fetch and display those messages
    if args.ids:
        for msg_id in args.ids:
            url = f"{GRAPH_API_BASE}/me/messages/{msg_id}?$expand=attachments"
            msg = make_graph_request(url, access_token)
            if not msg:
                print(f"Error: Message not found: {msg_id}", file=sys.stderr)
                sys.exit(1)
            display_message(msg, html=args.html)
        return

    # Otherwise, list messages with filters
    folder = args.folder or 'Inbox'
    # If -n not specified, show all messages (None = unlimited)
    max_count = args.count

    # Parse --since if specified
    since = None
    if args.since:
        try:
            since = parse_since_expression(args.since)
        except ValueError as e:
            print(f"Error in --since: {e}", file=sys.stderr)
            sys.exit(1)

    # Determine unread filter
    unread_filter = None
    if args.unread:
        unread_filter = True
    elif args.read:
        unread_filter = False

    # Get user's domain for external sender detection
    user_domain = get_user_domain(access_token)

    # Stream and display messages as they're fetched
    total_displayed = 0
    for page in get_messages_stream(
        access_token,
        folder=folder,
        max_count=max_count,
        since=since,
        unread=unread_filter,
        search=args.search
    ):
        for msg in page:
            display_message_summary(msg, user_domain)
            total_displayed += 1

    if total_displayed == 0:
        print("No messages found")
    else:
        print(f"\nUse 'o365 mail read <ID>' to read a specific message")


def cmd_archive(args):
    """Handle 'o365 mail archive' command using Graph API"""
    access_token = get_access_token()

    # Get Archive folder ID
    archive_url = f"{GRAPH_API_BASE}/me/mailFolders"
    folders_result = make_graph_request(archive_url, access_token)

    if not folders_result:
        print("Error: Could not fetch mail folders", file=sys.stderr)
        sys.exit(1)

    # Find Archive folder
    archive_folder_id = None
    for folder in folders_result.get('value', []):
        if folder.get('displayName', '').lower() == 'archive':
            archive_folder_id = folder['id']
            break

    if not archive_folder_id:
        print("Error: Archive folder not found", file=sys.stderr)
        sys.exit(1)

    # Archive each message
    for msg_id in args.ids:
        if args.dry_run:
            # Just fetch and display what would be archived
            url = f"{GRAPH_API_BASE}/me/messages/{msg_id}"
            msg = make_graph_request(url, access_token)
            if msg:
                subject = msg.get('subject', '(No subject)')
                print(f"Would archive: {subject} (ID: {msg_id})")
            else:
                print(f"Warning: Message not found: {msg_id}", file=sys.stderr)
        else:
            # Move message to Archive folder
            move_url = f"{GRAPH_API_BASE}/me/messages/{msg_id}/move"
            move_data = {'destinationId': archive_folder_id}

            result = make_graph_request(move_url, access_token, method='POST', data=move_data)

            if result:
                subject = result.get('subject', '(No subject)')
                print(f"✓ Archived: {subject}")
            else:
                print(f"Error: Failed to archive message: {msg_id}", file=sys.stderr)
                sys.exit(1)


def cmd_mark_read(args):
    """Handle 'o365 mail mark-read' command using Graph API"""
    access_token = get_access_token()

    # Mark each message as read
    for msg_id in args.ids:
        if args.dry_run:
            # Just fetch and display what would be marked
            url = f"{GRAPH_API_BASE}/me/messages/{msg_id}"
            msg = make_graph_request(url, access_token)
            if msg:
                subject = msg.get('subject', '(No subject)')
                is_read = msg.get('isRead', False)
                status = "already read" if is_read else "would mark as read"
                print(f"{subject} ({status}) (ID: {msg_id})")
            else:
                print(f"Warning: Message not found: {msg_id}", file=sys.stderr)
        else:
            # Update message isRead property
            update_url = f"{GRAPH_API_BASE}/me/messages/{msg_id}"
            update_data = {'isRead': True}

            result = make_graph_request(update_url, access_token, method='PATCH', data=update_data)

            if result:
                subject = result.get('subject', '(No subject)')
                print(f"✓ Marked as read: {subject}")
            else:
                print(f"Error: Failed to mark message as read: {msg_id}", file=sys.stderr)
                sys.exit(1)


def cmd_search(args):
    """Handle 'o365 mail search' command - dedicated search without filter conflicts"""
    access_token = get_access_token()

    # Build search query
    query = args.query

    # Parse --since if specified
    since = None
    if args.since:
        try:
            since = parse_since_expression(args.since)
        except ValueError as e:
            print(f"Error in --since: {e}", file=sys.stderr)
            sys.exit(1)

    # Note: We cannot combine $search with $filter in Graph API
    # So we do post-filtering on the results for --since
    # This is less efficient but works around the API limitation

    # Get user's domain for external sender detection
    user_domain = get_user_domain(access_token)

    # Stream and display messages as they're fetched
    total_displayed = 0
    total_filtered = 0

    for page in get_messages_stream(
        access_token,
        folder='Inbox',  # Search will search all folders anyway when search param is set
        max_count=args.count,
        since=None,  # Don't pass since to API - we'll filter locally
        unread=None,  # Don't filter by read status to avoid API conflicts
        search=query
    ):
        for msg in page:
            # Apply local filtering for --since if needed
            if since:
                received = parse_graph_datetime(msg['receivedDateTime'])
                if received < since:
                    total_filtered += 1
                    continue

            # Apply local filtering for --unread if needed
            if args.unread and msg.get('isRead', True):
                total_filtered += 1
                continue
            elif args.read and not msg.get('isRead', False):
                total_filtered += 1
                continue

            display_message_summary(msg, user_domain)
            total_displayed += 1

    if total_displayed == 0:
        if total_filtered > 0:
            print(f"No messages found (filtered out {total_filtered} results)")
        else:
            print("No messages found")
    else:
        print(f"\nShowing {total_displayed} result(s)")
        if total_filtered > 0:
            print(f"(Filtered out {total_filtered} older/read messages)")
        print(f"\nUse 'o365 mail read <ID>' to read a specific message")


def cmd_download_attachment(args):
    """Handle 'o365 mail download-attachment' command using Graph API"""
    access_token = get_access_token()

    # Download the attachment
    url = f"{GRAPH_API_BASE}/me/messages/{args.message_id}/attachments/{args.attachment_id}"
    attachment = make_graph_request(url, access_token)

    if not attachment:
        print(f"Error: Attachment not found", file=sys.stderr)
        sys.exit(1)

    # Get attachment details
    name = attachment.get('name', 'attachment')
    content_bytes = attachment.get('contentBytes')

    if not content_bytes:
        print(f"Error: Attachment has no content", file=sys.stderr)
        sys.exit(1)

    # Decode base64 content
    import base64
    content = base64.b64decode(content_bytes)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
        if output_path.is_dir():
            output_path = output_path / name
    else:
        output_path = Path.cwd() / name

    # Check if file exists
    if output_path.exists() and not args.overwrite:
        print(f"Error: File exists: {output_path}", file=sys.stderr)
        print("Use --overwrite to overwrite existing files", file=sys.stderr)
        sys.exit(1)

    # Write attachment to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)

    print(f"✓ Downloaded: {name}")
    print(f"  Saved to: {output_path}")
    print(f"  Size: {format_size(len(content))}")


# Graph caps /me/sendMail at ~4MB total. We keep a safety margin so that
# headers + base64 overhead don't push us over.
_SEND_INLINE_LIMIT_BYTES = 3 * 1024 * 1024

# Chunk size for resumable attachment uploads. Graph requires a multiple of
# 320 KiB; 10 MiB keeps memory + per-chunk latency reasonable.
_ATTACHMENT_CHUNK_SIZE = 10 * 1024 * 1024


def cmd_send(args):
    """Send email via Microsoft Graph /me/sendMail.

    Uses the inline path when total attachment size is small; otherwise
    creates a draft, uploads attachments via resumable session, then sends.
    """
    if args.raw:
        print(
            "Error: --raw (raw MIME) is not supported by the Graph backend. "
            "Use -H/-T with body content or '-' for stdin.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not args.recipient:
        print("Error: at least one recipient (-r/--recipient) is required", file=sys.stderr)
        sys.exit(2)

    html_body, text_body = _resolve_send_body(args)
    if html_body is None and text_body is None:
        print(
            "Error: provide a body via -H/--html or -T/--text (use '-' to read from stdin)",
            file=sys.stderr,
        )
        sys.exit(2)

    message = {
        "subject": args.subject or "",
        "body": _build_send_body(html_body, text_body),
        "toRecipients": _parse_send_recipients(args.recipient),
    }
    if args.cc:
        message["ccRecipients"] = _parse_send_recipients(args.cc)
    if args.bcc:
        message["bccRecipients"] = _parse_send_recipients(args.bcc)
    if args.header:
        headers = _parse_send_headers(args.header)
        if headers:
            message["internetMessageHeaders"] = headers
    if args.from_addr:
        message["from"] = {"emailAddress": {"address": args.from_addr}}

    attachments = []
    for path in (args.attachment or []):
        att = _prepare_send_attachment(path)
        if att is None:
            sys.exit(1)
        attachments.append(att)

    access_token = get_access_token()

    has_large = any(a['size'] > _SEND_INLINE_LIMIT_BYTES for a in attachments)
    total_size = sum(a['size'] for a in attachments)
    use_draft_flow = has_large or total_size > _SEND_INLINE_LIMIT_BYTES

    if not use_draft_flow:
        if attachments:
            message['attachments'] = [_inline_send_attachment(a) for a in attachments]
        payload = {"message": message, "saveToSentItems": not args.no_save}
        result = make_graph_request('/me/sendMail', access_token, method='POST', data=payload)
        if result is None:
            sys.exit(1)
    else:
        draft = make_graph_request('/me/messages', access_token, method='POST', data=message)
        if not draft or 'id' not in draft:
            print("Error: failed to create draft message", file=sys.stderr)
            sys.exit(1)
        message_id = draft['id']

        for att in attachments:
            if att['size'] > _SEND_INLINE_LIMIT_BYTES:
                if not _upload_large_attachment(access_token, message_id, att):
                    sys.exit(1)
            else:
                small = _inline_send_attachment(att)
                r = make_graph_request(
                    f'/me/messages/{message_id}/attachments',
                    access_token, method='POST', data=small,
                )
                if r is None:
                    sys.exit(1)

        result = make_graph_request(
            f'/me/messages/{message_id}/send',
            access_token, method='POST', data={},
        )
        if result is None:
            sys.exit(1)

    n_to = len(args.recipient)
    n_cc = len(args.cc or [])
    n_bcc = len(args.bcc or [])
    total_rcpts = n_to + n_cc + n_bcc
    summary = f"✓ Email sent to {total_rcpts} recipient{'s' if total_rcpts != 1 else ''}"
    if attachments:
        summary += f" with {len(attachments)} attachment{'s' if len(attachments) != 1 else ''}"
    print(summary)


def _resolve_send_body(args):
    """Return (html_body, text_body), reading stdin once if either flag is '-'."""
    stdin_data = None
    if args.html == '-' or args.text == '-':
        stdin_data = sys.stdin.read()

    html_body = stdin_data if args.html == '-' else args.html
    text_body = stdin_data if args.text == '-' else args.text

    if html_body is not None and text_body is None:
        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_links = False
        text_body = h.handle(html_body)

    return html_body, text_body


def _build_send_body(html_body, text_body):
    """Build Graph 'body' object. Prefers HTML when both are provided."""
    if html_body is not None:
        return {"contentType": "html", "content": html_body}
    return {"contentType": "text", "content": text_body or ""}


def _parse_send_recipients(items):
    """Parse strings like 'a@x.com' or 'Name <a@x.com>' (each may be comma-separated)."""
    parsed = getaddresses(items)
    recipients = []
    for name, addr in parsed:
        if not addr:
            continue
        entry = {"emailAddress": {"address": addr}}
        if name:
            entry["emailAddress"]["name"] = name
        recipients.append(entry)
    return recipients


def _parse_send_headers(items):
    """Parse 'Header: Value' strings. Graph requires custom headers to start with x-/X-."""
    headers = []
    for item in items:
        if ':' not in item:
            print(f"Warning: skipping malformed header (no colon): {item!r}", file=sys.stderr)
            continue
        name, _, value = item.partition(':')
        name = name.strip()
        value = value.strip()
        if not name.lower().startswith('x-'):
            print(
                f"Warning: Graph only accepts custom headers prefixed 'x-'; rewriting {name!r} to 'x-{name}'",
                file=sys.stderr,
            )
            name = 'x-' + name
        headers.append({"name": name, "value": value})
    return headers


def _prepare_send_attachment(path):
    """Validate an attachment path and return a metadata dict."""
    p = Path(path).expanduser()
    if not p.exists():
        print(f"Error: attachment not found: {path}", file=sys.stderr)
        return None
    if not p.is_file():
        print(f"Error: attachment is not a regular file: {path}", file=sys.stderr)
        return None
    return {'name': p.name, 'size': p.stat().st_size, 'path': p}


def _inline_send_attachment(att):
    """Build a Graph fileAttachment dict with the file contents base64-encoded."""
    with open(att['path'], 'rb') as f:
        data = f.read()
    return {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": att['name'],
        "contentBytes": base64.b64encode(data).decode('ascii'),
    }


def _upload_large_attachment(access_token, message_id, att):
    """Attach a file >= _SEND_INLINE_LIMIT_BYTES to a draft via createUploadSession."""
    session_data = {
        "AttachmentItem": {
            "attachmentType": "file",
            "name": att['name'],
            "size": att['size'],
        }
    }
    session = make_graph_request(
        f'/me/messages/{message_id}/attachments/createUploadSession',
        access_token, method='POST', data=session_data,
    )
    if not session or 'uploadUrl' not in session:
        print(f"Error: failed to create upload session for {att['name']}", file=sys.stderr)
        return False
    upload_url = session['uploadUrl']
    file_size = att['size']

    try:
        with open(att['path'], 'rb') as f:
            offset = 0
            while offset < file_size:
                chunk = f.read(_ATTACHMENT_CHUNK_SIZE)
                end = offset + len(chunk) - 1
                req = urllib.request.Request(
                    upload_url, data=chunk,
                    headers={
                        'Content-Length': str(len(chunk)),
                        'Content-Range': f'bytes {offset}-{end}/{file_size}',
                    },
                    method='PUT',
                )
                try:
                    urllib.request.urlopen(req)
                except urllib.error.HTTPError as e:
                    err = e.read().decode(errors='replace')[:500]
                    print(
                        f"Error: HTTP {e.code} uploading chunk of {att['name']}: {err}",
                        file=sys.stderr,
                    )
                    return False
                pct = (end + 1) * 100.0 / file_size
                print(f"  {att['name']}: {pct:.1f}%", file=sys.stderr)
                offset += len(chunk)
    except Exception as e:
        print(f"Error during upload of {att['name']}: {e}", file=sys.stderr)
        return False
    return True


# Setup and routing

def setup_parser(subparsers):
    """Setup argparse subcommands for mail"""

    # o365 mail read
    read_parser = subparsers.add_parser(
        'read',
        help='List and read emails via Graph API',
        description='List and read emails via Microsoft Graph API.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  o365 mail read                          # List all emails (streams results)
  o365 mail read -n 20                    # List only 20 most recent emails
  o365 mail read --unread                 # Show all unread emails
  o365 mail read --since "2 days ago"     # Show emails from last 2 days
  o365 mail read <MESSAGE_ID>             # Read specific email by ID
  o365 mail read -s "payment"             # Search for "payment" in emails
"""
    )
    read_parser.add_argument('ids', nargs='*', metavar='ID',
                            help='Email IDs to read (Graph API message IDs)')
    read_parser.add_argument('-n', '--count', type=int, metavar='N',
                            help='Number of emails to list (default: all, fetched in pages of 50)')
    read_parser.add_argument('-f', '--folder', type=str, metavar='FOLDER',
                            help='Folder to read from (default: Inbox)')
    read_parser.add_argument('-s', '--search', type=str, metavar='PATTERN',
                            help='Search emails by pattern (searches across subject, body, sender, etc.)')
    read_parser.add_argument('--since', type=str, metavar='EXPR',
                            help='Only show emails since this time (git-style format)')
    read_parser.add_argument('--unread', action='store_true',
                            help='Show only unread emails')
    read_parser.add_argument('--read', action='store_true',
                            help='Show only read emails')
    read_parser.add_argument('--html', action='store_true',
                            help='Display HTML content as-is (default: convert to text)')
    read_parser.set_defaults(func=cmd_read)

    # o365 mail archive
    archive_parser = subparsers.add_parser(
        'archive',
        help='Archive emails to Archive folder',
        description='Archive emails to Archive folder using Graph API.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  o365 mail archive <MESSAGE_ID>                     # Archive single email
  o365 mail archive <MESSAGE_ID_1> <MESSAGE_ID_2>    # Archive multiple emails
  o365 mail archive --dry-run <MESSAGE_ID>           # Preview without archiving
"""
    )
    archive_parser.add_argument('ids', nargs='+', metavar='ID',
                               help='One or more email IDs (Graph API message IDs)')
    archive_parser.add_argument('--dry-run', action='store_true',
                               help='Show what would be archived without actually doing it')
    archive_parser.set_defaults(func=cmd_archive)

    # o365 mail mark-read
    mark_read_parser = subparsers.add_parser(
        'mark-read',
        help='Mark emails as read',
        description='Mark emails as read using Graph API.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  o365 mail mark-read <MESSAGE_ID>                   # Mark single email as read
  o365 mail mark-read <MESSAGE_ID_1> <MESSAGE_ID_2>  # Mark multiple emails
  o365 mail mark-read --dry-run <MESSAGE_ID>         # Preview without marking
"""
    )
    mark_read_parser.add_argument('ids', nargs='+', metavar='ID',
                                 help='One or more email IDs (Graph API message IDs)')
    mark_read_parser.add_argument('--dry-run', action='store_true',
                                 help='Show what would be marked without actually doing it')
    mark_read_parser.set_defaults(func=cmd_mark_read)

    # o365 mail send
    send_parser = subparsers.add_parser(
        'send',
        help='Send email via Microsoft Graph',
        description='Send email via Microsoft Graph (/me/sendMail). '
                   'Sends as the authenticated user; no SMTP credentials needed. '
                   'Attachments are inlined when small and uploaded via resumable '
                   'sessions when large (Graph caps inline sendMail at ~4MB).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  echo "<p>Hello!</p>" | o365 mail send -r user@example.com -S "Subject" -H -
  o365 mail send -r user@example.com -S "Report" -A report.pdf -H - < msg.html
  o365 mail send -r user1@example.com -r user2@example.com -S "Update" -H - < msg.html
  o365 mail send -r "Jane Doe <jane@example.com>" -c team@example.com -S "FYI" -T "see below"

Body:
  -H/--html and -T/--text accept either literal content or '-' for stdin.
  If only -H is given, a text fallback is auto-generated via html2text.

Recipients:
  -r/--recipient (and -c/-b) may be repeated and may contain comma-separated
  addresses or "Name <addr@x>" forms.
"""
    )
    send_parser.add_argument('-r', '--recipient', dest='recipient',
                            action='append', metavar='ADDR',
                            help='To recipient (may be repeated; "Name <a@x>" allowed)')
    send_parser.add_argument('-c', '--cc', dest='cc',
                            action='append', metavar='ADDR',
                            help='Cc recipient (may be repeated)')
    send_parser.add_argument('-b', '--bcc', dest='bcc',
                            action='append', metavar='ADDR',
                            help='Bcc recipient (may be repeated)')
    send_parser.add_argument('-S', '--subject', dest='subject', metavar='SUBJECT',
                            help='Email subject')
    send_parser.add_argument('-A', '--attachment', dest='attachment',
                            action='append', metavar='PATH',
                            help='File to attach (may be repeated)')
    send_parser.add_argument('-H', '--html', dest='html', metavar='HTML',
                            help='HTML body (or "-" to read from stdin)')
    send_parser.add_argument('-T', '--text', dest='text', metavar='TEXT',
                            help='Text body (or "-" to read from stdin)')
    send_parser.add_argument('--header', dest='header',
                            action='append', metavar='HEADER',
                            help='Custom header "Name: Value" (Graph requires x- prefix)')
    send_parser.add_argument('-f', '--from', dest='from_addr', metavar='ADDR',
                            help='From address (requires Send-As permission on that mailbox; '
                                 'omit to send as the authenticated user)')
    send_parser.add_argument('--no-save', dest='no_save', action='store_true',
                            help="Don't save a copy to Sent Items")
    send_parser.add_argument('--raw', dest='raw', metavar='PATH',
                            help='[unsupported] Raw MIME mode (SMTP-only; not routed through Graph)')
    send_parser.set_defaults(func=cmd_send)

    # o365 mail search
    search_parser = subparsers.add_parser(
        'search',
        help='Search emails across all folders',
        description='Search emails using Microsoft Graph full-text search. '
                   'This searches across subject, body, sender, and recipients. '
                   'Unlike "read -s", this command works around Graph API limitations '
                   'by doing local filtering for --since and --unread flags.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  o365 mail search "HSP-5077"                      # Search all emails for ticket number
  o365 mail search "payment invoice"               # Search for multiple keywords
  o365 mail search "project update" --since "1 week ago"  # Recent emails only
  o365 mail search "meeting" --unread              # Unread emails matching search
  o365 mail search "report" -n 50                  # Limit to 50 results

Notes:
  - Searches across all folders (not just Inbox)
  - Searches subject, body, sender, and recipients
  - --since and --unread do local filtering (less efficient but works)
  - Results are not sorted by date when using search (Graph API limitation)
"""
    )
    search_parser.add_argument('query', metavar='QUERY',
                              help='Search query (searches subject, body, sender, recipients)')
    search_parser.add_argument('-n', '--count', type=int, metavar='N',
                              help='Maximum number of results to show (default: unlimited)')
    search_parser.add_argument('--since', type=str, metavar='EXPR',
                              help='Only show emails since this time (filtered locally)')
    search_parser.add_argument('--unread', action='store_true',
                              help='Show only unread emails (filtered locally)')
    search_parser.add_argument('--read', action='store_true',
                              help='Show only read emails (filtered locally)')
    search_parser.set_defaults(func=cmd_search)

    # o365 mail download-attachment
    download_attachment_parser = subparsers.add_parser(
        'download-attachment',
        help='Download an email attachment',
        description='Download an attachment from an email using Graph API.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  o365 mail download-attachment <MESSAGE_ID> <ATTACHMENT_ID>                 # Download to current directory
  o365 mail download-attachment <MESSAGE_ID> <ATTACHMENT_ID> -o ~/Downloads/ # Download to specific location
  o365 mail download-attachment <MESSAGE_ID> <ATTACHMENT_ID> --overwrite     # Overwrite existing file
"""
    )
    download_attachment_parser.add_argument('message_id', metavar='MESSAGE_ID',
                                           help='Message ID containing the attachment')
    download_attachment_parser.add_argument('attachment_id', metavar='ATTACHMENT_ID',
                                           help='Attachment ID to download')
    download_attachment_parser.add_argument('-o', '--output', type=str, metavar='PATH',
                                           help='Output file or directory (default: current directory)')
    download_attachment_parser.add_argument('--overwrite', action='store_true',
                                           help='Overwrite existing file')
    download_attachment_parser.set_defaults(func=cmd_download_attachment)


def handle_command(args):
    """Route to appropriate mail subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No mail subcommand specified", file=sys.stderr)
        sys.exit(1)
