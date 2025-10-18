"""
Mail management commands for Office365

Sync, read, archive, mark read, and send emails.
"""

import sys
import subprocess
import re
import html2text
import argparse
from pathlib import Path
from datetime import datetime

from .common import get_access_token, make_graph_request, GRAPH_API_BASE
from .calendar import parse_since_expression

# For now, some commands are implemented by calling existing scripts
# Later we can refactor these into pure Python if needed

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
    # Build URL
    url = f"{GRAPH_API_BASE}/me/mailFolders/{folder}/messages"

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
        # Only add $orderby when NOT using $search
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


def cmd_send(args):
    """Handle 'o365 mail send' command - calls trinoor.email module"""
    cmd = ['python', '-m', 'trinoor.email']

    # Pass through all arguments from sys.argv
    # We need to find where 'send' starts and pass everything after it
    import sys as sys_module
    try:
        send_idx = sys_module.argv.index('send')
        cmd.extend(sys_module.argv[send_idx + 1:])
    except ValueError:
        # Fallback: just run without args to show help
        pass

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: trinoor.email module not found", file=sys.stderr)
        print("Make sure the trinoor package is installed", file=sys.stderr)
        sys.exit(1)


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
        help='Send email via SMTP',
        description='Send emails via SMTP with automatic signature support. '
                   'This is a wrapper around the trinoor.email module.',
        epilog="""
Examples:
  echo "<p>Hello!</p>" | o365 mail send -r user@example.com -S "Subject" -H -
  o365 mail send -r user@example.com -S "Report" -H - -A report.pdf < msg.html
  o365 mail send -r user1@example.com -r user2@example.com -S "Update" -H - < msg.html

For full options, see: python -m trinoor.email --help
"""
    )
    # Note: We're not adding arguments here because we pass everything through to trinoor.email
    # This allows trinoor.email to handle its own argument parsing
    send_parser.set_defaults(func=cmd_send)

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
