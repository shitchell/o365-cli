"""
Chat management commands for Office365

List, read, send, and search Microsoft Teams chats.
"""

import sys
import re
from datetime import datetime, timedelta, timezone

from .common import get_access_token, make_graph_request, GRAPH_API_BASE
from .contacts import search_users
from .calendar import parse_since_expression

# Get local timezone
LOCAL_TZ = datetime.now().astimezone().tzinfo


def parse_graph_datetime(dt_str):
    """Parse Microsoft Graph datetime format"""
    # Remove excess fractional seconds (keep max 6 digits)
    dt_str = re.sub(r'\.(\d{6})\d*', r'.\1', dt_str)
    # Handle timezone
    if not dt_str.endswith('Z') and '+' not in dt_str and '-' not in dt_str[-6:]:
        dt_str += 'Z'
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def get_chats(access_token, count=50):
    """Get user's chats with members expanded

    Args:
        access_token: OAuth2 access token
        count: Maximum number of chats to retrieve

    Returns:
        List of chat objects with members
    """
    url = f"{GRAPH_API_BASE}/me/chats"
    params = {
        '$expand': 'members',
        '$top': str(count),
        '$orderby': 'lastMessagePreview/createdDateTime desc'
    }

    query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
    url = f"{url}?{query_string}"

    chats = []
    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        chats.extend(result.get('value', []))
        url = result.get('@odata.nextLink')

        # Respect count limit
        if len(chats) >= count:
            chats = chats[:count]
            break

    return chats


def filter_chats_by_user_or_name(chats, query, access_token):
    """Filter chats by user email/name or group chat name

    Args:
        chats: List of chat objects
        query: User name/email or chat topic to search for
        access_token: OAuth2 access token

    Returns:
        Filtered list of chats
    """
    # Try to resolve as a user via contacts
    user_matches = search_users(query, access_token)
    user_emails = [u['email'].lower() for u in user_matches] if user_matches else []

    filtered = []
    for chat in chats:
        # Check if chat topic matches query (for group chats)
        topic = chat.get('topic', '').lower()
        if query.lower() in topic:
            filtered.append(chat)
            continue

        # Check if any member matches the user
        members = chat.get('members', [])
        for member in members:
            user_principal = member.get('email', '').lower()
            display_name = member.get('displayName', '').lower()

            if user_principal in user_emails or query.lower() in display_name:
                filtered.append(chat)
                break

    return filtered


def get_chat_display_name(chat):
    """Get a human-readable name for a chat

    For group chats: use topic
    For 1:1 chats: use other participant's name
    """
    # Group chat with topic
    if chat.get('topic'):
        return chat['topic']

    # 1:1 chat - find the other participant
    members = chat.get('members', [])
    for member in members:
        # Skip yourself
        if member.get('userId') and not member.get('displayName', '').endswith('(You)'):
            return member.get('displayName', 'Unknown')

    return 'Unknown Chat'


def get_chat_messages(access_token, chat_id, count=50, since=None):
    """Get messages from a chat

    Args:
        access_token: OAuth2 access token
        chat_id: Chat ID
        count: Maximum number of messages to retrieve
        since: Optional datetime to filter messages after

    Returns:
        List of message objects
    """
    url = f"{GRAPH_API_BASE}/chats/{chat_id}/messages"
    params = {
        '$top': str(count),
        '$orderby': 'createdDateTime desc'
    }

    if since:
        since_utc = since.astimezone(timezone.utc)
        since_str = since_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        params['$filter'] = f"createdDateTime gt {since_str}"

    query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
    url = f"{url}?{query_string}"

    messages = []
    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        messages.extend(result.get('value', []))
        url = result.get('@odata.nextLink')

        # Respect count limit
        if len(messages) >= count:
            messages = messages[:count]
            break

    # Reverse to show oldest first
    return list(reversed(messages))


def send_message(access_token, chat_id, content):
    """Send a message to a chat

    Args:
        access_token: OAuth2 access token
        chat_id: Chat ID to send to
        content: Message content (plain text)

    Returns:
        Created message object or None on error
    """
    url = f"{GRAPH_API_BASE}/chats/{chat_id}/messages"

    message = {
        'body': {
            'contentType': 'text',
            'content': content
        }
    }

    return make_graph_request(url, access_token, method='POST', data=message)


def search_messages(access_token, query, chats=None, count=50):
    """Search for messages containing query

    Note: Graph API doesn't have a direct message search endpoint,
    so we fetch messages from chats and filter locally.

    Args:
        access_token: OAuth2 access token
        query: Search query string
        chats: Optional list of chats to search in (if None, searches all)
        count: Maximum number of results

    Returns:
        List of (chat, message) tuples
    """
    if chats is None:
        chats = get_chats(access_token, count=50)

    results = []
    query_lower = query.lower()

    for chat in chats:
        messages = get_chat_messages(access_token, chat['id'], count=50)

        for msg in messages:
            body = msg.get('body', {}).get('content', '').lower()
            if query_lower in body:
                results.append((chat, msg))

                if len(results) >= count:
                    return results

    return results


# Command handlers

def cmd_list(args):
    """Handle 'o365 chat list' command"""
    access_token = get_access_token()

    # Get chats
    chats = get_chats(access_token, count=args.count or 50)

    if not chats:
        print("No chats found")
        return

    # Apply --with filter
    if args.with_user:
        chats = filter_chats_by_user_or_name(chats, args.with_user, access_token)

        if not chats:
            print(f"No chats found with '{args.with_user}'")
            return

    # Apply --since filter
    if args.since:
        try:
            since_date = parse_since_expression(args.since)
            filtered = []
            for chat in chats:
                last_msg = chat.get('lastMessagePreview')
                if last_msg and last_msg.get('createdDateTime'):
                    msg_date = parse_graph_datetime(last_msg['createdDateTime'])
                    if msg_date >= since_date:
                        filtered.append(chat)
            chats = filtered
        except ValueError as e:
            print(f"Error in --since: {e}", file=sys.stderr)
            sys.exit(1)

    # Display chats
    print(f"\n💬 Chats ({len(chats)} shown):\n")
    print(f"{'ID':<10} {'Type':<8} {'Name':<40} {'Last Message':<30}")
    print("=" * 90)

    for chat in chats:
        chat_id = chat['id'][:8] + '...'
        chat_type = chat.get('chatType', 'unknown')
        name = get_chat_display_name(chat)[:38]

        # Get last message preview
        last_msg_preview = chat.get('lastMessagePreview', {})
        last_msg_time = last_msg_preview.get('createdDateTime')
        if last_msg_time:
            dt = parse_graph_datetime(last_msg_time).astimezone(LOCAL_TZ)
            last_msg_str = dt.strftime('%Y-%m-%d %H:%M')
        else:
            last_msg_str = ''

        print(f"{chat_id:<10} {chat_type:<8} {name:<40} {last_msg_str:<30}")

    print(f"\nUse 'o365 chat read <chat-id>' to read messages")
    print("(Full chat IDs are in the output above)")


def cmd_read(args):
    """Handle 'o365 chat read' command"""
    access_token = get_access_token()

    # Resolve chat ID
    if args.chat_id:
        chat_id = args.chat_id
    elif args.with_user:
        # Find chat with user
        chats = get_chats(access_token, count=50)
        filtered = filter_chats_by_user_or_name(chats, args.with_user, access_token)

        if not filtered:
            print(f"Error: No chat found with '{args.with_user}'", file=sys.stderr)
            sys.exit(1)

        if len(filtered) > 1:
            print(f"Error: Multiple chats found with '{args.with_user}':", file=sys.stderr)
            for chat in filtered:
                print(f"  - {chat['id']}: {get_chat_display_name(chat)}", file=sys.stderr)
            print("\nUse 'o365 chat read <chat-id>' with specific ID", file=sys.stderr)
            sys.exit(1)

        chat_id = filtered[0]['id']
    else:
        print("Error: Must specify --chat or --with", file=sys.stderr)
        sys.exit(1)

    # Parse --since
    since = None
    if args.since:
        try:
            since = parse_since_expression(args.since)
        except ValueError as e:
            print(f"Error in --since: {e}", file=sys.stderr)
            sys.exit(1)

    # Get messages
    messages = get_chat_messages(access_token, chat_id, count=args.count or 50, since=since)

    if not messages:
        print("No messages found")
        return

    # Display messages
    print(f"\n💬 Messages ({len(messages)} shown):\n")

    for msg in messages:
        sender = msg.get('from', {}).get('user', {}).get('displayName', 'Unknown')
        created = parse_graph_datetime(msg['createdDateTime']).astimezone(LOCAL_TZ)
        time_str = created.strftime('%Y-%m-%d %H:%M:%S')

        body = msg.get('body', {}).get('content', '')

        # Clean up HTML if present
        if msg.get('body', {}).get('contentType') == 'html':
            # Simple HTML stripping
            body = re.sub(r'<[^>]+>', '', body)

        print(f"[{time_str}] {sender}")
        print(f"  {body}")
        print()


def cmd_send(args):
    """Handle 'o365 chat send' command"""
    access_token = get_access_token()

    # Resolve chat ID
    if args.chat_id:
        chat_id = args.chat_id
    elif args.to:
        # Find chat with user
        chats = get_chats(access_token, count=50)
        filtered = filter_chats_by_user_or_name(chats, args.to, access_token)

        if not filtered:
            print(f"Error: No chat found with '{args.to}'", file=sys.stderr)
            sys.exit(1)

        if len(filtered) > 1:
            print(f"Error: Multiple chats found with '{args.to}':", file=sys.stderr)
            for chat in filtered:
                print(f"  - {chat['id']}: {get_chat_display_name(chat)}", file=sys.stderr)
            print("\nUse 'o365 chat send --chat <chat-id>' with specific ID", file=sys.stderr)
            sys.exit(1)

        chat_id = filtered[0]['id']
    else:
        print("Error: Must specify --chat or --to", file=sys.stderr)
        sys.exit(1)

    # Send message
    result = send_message(access_token, chat_id, args.message)

    if result:
        print("✓ Message sent successfully")
    else:
        print("Error: Failed to send message", file=sys.stderr)
        sys.exit(1)


def cmd_search(args):
    """Handle 'o365 chat search' command"""
    access_token = get_access_token()

    # Get chats (optionally filtered by --with)
    chats = get_chats(access_token, count=50)

    if args.with_user:
        chats = filter_chats_by_user_or_name(chats, args.with_user, access_token)

        if not chats:
            print(f"No chats found with '{args.with_user}'")
            return

    # Apply --since filter
    if args.since:
        try:
            since_date = parse_since_expression(args.since)
            # Note: We'll filter messages by date during search
        except ValueError as e:
            print(f"Error in --since: {e}", file=sys.stderr)
            sys.exit(1)

    # Search messages
    results = search_messages(access_token, args.query, chats=chats, count=args.count or 50)

    if not results:
        print(f"No messages found matching '{args.query}'")
        return

    # Display results
    print(f"\n🔍 Search results for '{args.query}' ({len(results)} found):\n")

    for chat, msg in results:
        chat_name = get_chat_display_name(chat)
        sender = msg.get('from', {}).get('user', {}).get('displayName', 'Unknown')
        created = parse_graph_datetime(msg['createdDateTime']).astimezone(LOCAL_TZ)
        time_str = created.strftime('%Y-%m-%d %H:%M')

        body = msg.get('body', {}).get('content', '')

        # Clean up HTML if present
        if msg.get('body', {}).get('contentType') == 'html':
            body = re.sub(r'<[^>]+>', '', body)

        # Truncate long messages
        if len(body) > 100:
            body = body[:97] + '...'

        print(f"[{time_str}] {chat_name} - {sender}")
        print(f"  {body}")
        print()


# Setup and routing

def setup_parser(subparsers):
    """Setup argparse subcommands for chat"""

    # o365 chat list
    list_parser = subparsers.add_parser(
        'list',
        help='List chats',
        description='List Microsoft Teams chats.'
    )

    list_parser.add_argument('-n', '--count', type=int, metavar='N',
                            help='Number of chats to show (default: 50)')
    list_parser.add_argument('--with', dest='with_user', type=str, metavar='USER',
                            help='Filter to chats with specific user or group chat name')
    list_parser.add_argument('--since', type=str, metavar='EXPR',
                            help='Show chats with activity since this time (git-style format)')

    list_parser.set_defaults(func=cmd_list)

    # o365 chat read
    read_parser = subparsers.add_parser(
        'read',
        help='Read messages from a chat',
        description='Read messages from a Microsoft Teams chat.'
    )

    read_parser.add_argument('chat_id', nargs='?', help='Chat ID to read from')
    read_parser.add_argument('--with', dest='with_user', type=str, metavar='USER',
                            help='Read chat with specific user or group chat name')
    read_parser.add_argument('-n', '--count', type=int, metavar='N',
                            help='Number of messages to show (default: 50)')
    read_parser.add_argument('--since', type=str, metavar='EXPR',
                            help='Show messages since this time (git-style format)')

    read_parser.set_defaults(func=cmd_read)

    # o365 chat send
    send_parser = subparsers.add_parser(
        'send',
        help='Send a message to a chat',
        description='Send a message to a Microsoft Teams chat.'
    )

    send_parser.add_argument('--chat', dest='chat_id', type=str, metavar='CHAT_ID',
                            help='Chat ID to send to')
    send_parser.add_argument('--to', type=str, metavar='USER',
                            help='Send to chat with specific user or group chat name')
    send_parser.add_argument('-m', '--message', type=str, required=True,
                            help='Message content to send')

    send_parser.set_defaults(func=cmd_send)

    # o365 chat search
    search_parser = subparsers.add_parser(
        'search',
        help='Search chat messages',
        description='Search for messages in Microsoft Teams chats.'
    )

    search_parser.add_argument('query', help='Search query string')
    search_parser.add_argument('--with', dest='with_user', type=str, metavar='USER',
                              help='Search only chats with specific user or group chat name')
    search_parser.add_argument('--since', type=str, metavar='EXPR',
                              help='Search messages since this time (git-style format)')
    search_parser.add_argument('-n', '--count', type=int, metavar='N',
                              help='Number of results to show (default: 50)')

    search_parser.set_defaults(func=cmd_search)


def handle_command(args):
    """Route to appropriate chat subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No chat subcommand specified", file=sys.stderr)
        sys.exit(1)
