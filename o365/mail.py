"""
Mail management commands for Office365

Sync, read, archive, mark read, and send emails.
"""

import sys
import subprocess
import re
import html2text
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


def parse_graph_datetime(dt_str):
    """Parse Microsoft Graph datetime format"""
    import re
    # Remove excess fractional seconds (keep max 6 digits)
    dt_str = re.sub(r'\.(\d{6})\d*', r'.\1', dt_str)
    # Handle timezone
    if not dt_str.endswith('Z') and '+' not in dt_str and '-' not in dt_str[-6:]:
        dt_str += 'Z'
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def get_messages(access_token, folder='Inbox', count=10, since=None, unread=None, search=None):
    """Get messages from a mail folder

    Args:
        access_token: OAuth2 access token
        folder: Folder name (default: Inbox)
        count: Maximum number of messages
        since: Optional datetime to filter messages after
        unread: Optional filter for unread (True), read (False), or all (None)
        search: Optional search query

    Returns:
        List of message objects
    """
    # Build URL
    url = f"{GRAPH_API_BASE}/me/mailFolders/{folder}/messages"

    # Build query parameters
    params = {
        '$top': str(count),
        '$orderby': 'receivedDateTime desc',
        '$select': 'id,subject,from,receivedDateTime,isRead,body,bodyPreview'
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
        params['$search'] = f'"{search}"'

    if filters:
        params['$filter'] = ' and '.join(filters)

    # Build query string
    import urllib.parse
    query_string = urllib.parse.urlencode(params)
    url = f"{url}?{query_string}"

    # Fetch messages with pagination
    messages = []
    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        messages.extend(result.get('value', []))

        # Check for pagination
        url = result.get('@odata.nextLink')

        # Respect count limit
        if len(messages) >= count:
            messages = messages[:count]
            break

    return messages


def display_message_list(messages):
    """Display a list of messages in tabular format"""
    if not messages:
        print("No messages found")
        return

    print(f"\n📧 Messages ({len(messages)} shown):\n")
    print(f"{'#':<4} {'Date':<12} {'From':<25} {'Subject':<40} {'ID':<60}")
    print("=" * 145)

    for i, msg in enumerate(messages, 1):
        # Parse date
        received = parse_graph_datetime(msg['receivedDateTime']).astimezone(LOCAL_TZ)
        date_str = received.strftime('%Y-%m-%d')

        # Get sender
        from_field = msg.get('from', {}).get('emailAddress', {})
        sender = from_field.get('name') or from_field.get('address', 'Unknown')

        # Get subject
        subject = msg.get('subject', '(No subject)')

        # Mark unread with indicator
        unread_mark = '●' if not msg.get('isRead', True) else ' '

        # Get message ID (truncate for display)
        msg_id = msg['id'][:58]  # Truncate to fit column

        print(f"{i:<4} {date_str:<12} {sender[:23]:<25} {unread_mark} {subject[:38]:<40} {msg_id:<60}")

    print(f"\nUse 'o365 mail read <ID>' or 'o365 mail read -r <#>' to read a specific message")


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


def cmd_sync(args):
    """Handle 'o365 mail sync' command - calls o365-mail-sync.py"""
    # TODO: HIGH PRIORITY - Switch to pure Python using Graph API instead of calling external script
    # This currently depends on ~/bin/o365-mail-sync.py which may not be portable
    cmd = [str(Path.home() / "bin" / "o365-mail-sync.py")]

    # Pass through all arguments
    if args.folders:
        cmd.extend(['--folders'] + args.folders)
    if args.count:
        cmd.extend(['--count', str(args.count)])
    if args.since:
        cmd.extend(['--since', args.since])
    if args.all:
        cmd.append('--all')
    if args.focused_inbox:
        cmd.append('--focused-inbox')
    if args.list_folders:
        cmd.append('--list-folders')

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: o365-mail-sync.py not found", file=sys.stderr)
        sys.exit(1)


def cmd_read(args):
    """Handle 'o365 mail read' command using Graph API"""
    access_token = get_access_token()

    # If specific message IDs provided, fetch and display those messages
    if args.ids:
        for msg_id in args.ids:
            url = f"{GRAPH_API_BASE}/me/messages/{msg_id}"
            msg = make_graph_request(url, access_token)
            if not msg:
                print(f"Error: Message not found: {msg_id}", file=sys.stderr)
                sys.exit(1)
            display_message(msg, html=args.html)
        return

    # Otherwise, list messages with filters
    folder = args.folder or 'Inbox'
    count = args.count or 10

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

    # Get messages
    messages = get_messages(
        access_token,
        folder=folder,
        count=count,
        since=since,
        unread=unread_filter,
        search=args.search
    )

    # If --read-email specified, display that specific message by index
    if args.read_email:
        if args.read_email < 1 or args.read_email > len(messages):
            print(f"Error: Invalid message number: {args.read_email} (must be 1-{len(messages)})", file=sys.stderr)
            sys.exit(1)
        msg = messages[args.read_email - 1]
        display_message(msg, html=args.html)
    else:
        # Display list
        display_message_list(messages)


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

    # o365 mail sync
    sync_parser = subparsers.add_parser(
        'sync',
        help='Sync emails from Office365 to local Maildir',
        description='Sync emails from Office365 to local Maildir format.',
        epilog="""
Examples:
  o365 mail sync                              # Sync default folders
  o365 mail sync --folders Inbox --count 50   # Sync last 50 from Inbox
  o365 mail sync --all                        # Sync all folders
"""
    )
    sync_parser.add_argument('--folders', nargs='+', metavar='FOLDER',
                            help='Sync specific folders (e.g., Inbox SentItems Drafts)')
    sync_parser.add_argument('--count', type=int, metavar='N',
                            help='Maximum number of messages to fetch per folder')
    sync_parser.add_argument('--since', type=str, metavar='DATE',
                            help='Sync messages since date (ISO 8601 format)')
    sync_parser.add_argument('--all', action='store_true',
                            help='Sync all available folders')
    sync_parser.add_argument('--focused-inbox', action='store_true',
                            help='Split Inbox into INBOX.Focused and INBOX.Other')
    sync_parser.add_argument('--list-folders', action='store_true',
                            help='List all available mail folders')
    sync_parser.set_defaults(func=cmd_sync)

    # o365 mail read
    read_parser = subparsers.add_parser(
        'read',
        help='List and read emails from local Maildir',
        description='List and read emails from local Maildir.',
        epilog="""
Examples:
  o365 mail read                          # List 10 most recent emails
  o365 mail read --unread                 # Show only unread emails
  o365 mail read --since "2 days ago"     # Show emails from last 2 days
  o365 mail read -r 3                     # Read email #3 from list
  o365 mail read 48608adc f1486a8d        # Read emails by ID
  o365 mail read -s "payment"             # Search for "payment" in subject
"""
    )
    read_parser.add_argument('ids', nargs='*', metavar='ID',
                            help='Email IDs to read (8-character hex strings)')
    read_parser.add_argument('-n', '--count', type=int, metavar='N',
                            help='Number of emails to list (default: 10)')
    read_parser.add_argument('-f', '--folder', type=str, metavar='FOLDER',
                            help='Folder to read from (default: INBOX)')
    read_parser.add_argument('-r', '--read-email', type=int, metavar='N',
                            help='Read email number N from the list')
    read_parser.add_argument('-s', '--search', type=str, metavar='PATTERN',
                            help='Search emails by pattern (regex)')
    read_parser.add_argument('--field', type=str, choices=['subject', 'from', 'to'],
                            help='Field to search in (default: subject)')
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
        description='Archive emails from Inbox to Archive folder (both locally and on server).',
        epilog="""
Examples:
  o365 mail archive 60d1969a                    # Archive single email
  o365 mail archive 60d1969a 4ab19245 8be667d8  # Archive multiple emails
  o365 mail archive --dry-run 60d1969a          # Preview without archiving
"""
    )
    archive_parser.add_argument('ids', nargs='+', metavar='ID',
                               help='One or more email IDs (8-character hex strings)')
    archive_parser.add_argument('--dry-run', action='store_true',
                               help='Show what would be archived without actually doing it')
    archive_parser.set_defaults(func=cmd_archive)

    # o365 mail mark-read
    mark_read_parser = subparsers.add_parser(
        'mark-read',
        help='Mark emails as read',
        description='Mark emails as read (both locally and on server).',
        epilog="""
Examples:
  o365 mail mark-read f1486a8d                      # Mark single email as read
  o365 mail mark-read f1486a8d 0bc59901 01c77910    # Mark multiple emails
  o365 mail mark-read --dry-run f1486a8d            # Preview without marking
"""
    )
    mark_read_parser.add_argument('ids', nargs='+', metavar='ID',
                                 help='One or more email IDs (8-character hex strings)')
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


def handle_command(args):
    """Route to appropriate mail subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No mail subcommand specified", file=sys.stderr)
        sys.exit(1)
