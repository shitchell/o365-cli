"""
Chat management commands for Office365

List, read, send, and search Microsoft Teams chats.
"""

import sys
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

from .common import get_access_token, make_graph_request, GRAPH_API_BASE
from .contacts import search_users
from .calendar import parse_since_expression

# Get local timezone
LOCAL_TZ = datetime.now().astimezone().tzinfo


def parse_graph_datetime(dt_str):
    """Parse Microsoft Graph datetime format"""
    # Normalize fractional seconds to exactly 6 digits (pad or truncate)
    match = re.search(r'\.(\d+)', dt_str)
    if match:
        frac_seconds = match.group(1)
        if len(frac_seconds) > 6:
            # Truncate to 6 digits
            dt_str = re.sub(r'\.(\d{6})\d*', r'.\1', dt_str)
        elif len(frac_seconds) < 6:
            # Pad to 6 digits
            dt_str = re.sub(r'\.(\d+)', lambda m: '.' + m.group(1).ljust(6, '0'), dt_str)
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

    query_string = urllib.parse.urlencode(params)
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
        # Skip None entries
        if chat is None:
            continue

        # Check if chat topic matches query (for group chats)
        # Note: topic can be explicitly None for 1:1 chats
        topic = (chat.get('topic') or '').lower()
        if query.lower() in topic:
            filtered.append(chat)
            continue

        # Check if any member matches the user
        members = chat.get('members', [])
        for member in members:
            user_principal = (member.get('email') or '').lower()
            display_name = (member.get('displayName') or '').lower()

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


def get_chat_messages(access_token, chat_id, count=50, since=None, fetch_all=False):
    """Get messages from a chat

    Args:
        access_token: OAuth2 access token
        chat_id: Chat ID
        count: Maximum number of messages to retrieve (None for unlimited if fetch_all=True)
        since: Optional datetime to filter messages after
        fetch_all: If True, fetch all messages with pagination (ignores count limit)

    Returns:
        List of message objects
    """
    url = f"{GRAPH_API_BASE}/chats/{chat_id}/messages"

    # Use max allowed page size (API limit is 50)
    page_size = 50
    params = {
        '$top': str(page_size),
        '$orderby': 'createdDateTime desc'
    }

    # Note: Chat messages API doesn't support $filter by createdDateTime or body content
    # We fetch messages and filter locally instead

    query_string = urllib.parse.urlencode(params)
    url = f"{url}?{query_string}"

    messages = []
    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        for msg in result.get('value', []):
            # Apply local date filter
            if since:
                msg_date = parse_graph_datetime(msg['createdDateTime'])
                if msg_date < since:
                    continue
            messages.append(msg)

            # Check count limit only if not fetching all
            if not fetch_all and count and len(messages) >= count:
                break

        url = result.get('@odata.nextLink')

        # Stop if we've reached count limit (only when not fetching all)
        if not fetch_all and count and len(messages) >= count:
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


def search_messages_via_api(access_token, query, count=50, chat_id=None, since=None):
    """Search for messages using Microsoft Graph Search API

    Uses POST /search/query endpoint which searches server-side and is much faster
    than fetching all messages locally. If chat_id is specified, filters results
    to only that chat.

    Args:
        access_token: OAuth2 access token
        query: Search query string
        count: Maximum number of matching results to return
        chat_id: Optional chat ID to filter results to
        since: Optional datetime to filter messages after

    Returns:
        List of (chat_id, message) tuples
    """
    # Search API for chatMessages requires beta endpoint
    url = "https://graph.microsoft.com/beta/search/query"

    results = []
    from_index = 0
    page_size = 25  # Graph API default for search

    # Keep fetching until we have enough matching results
    while len(results) < count:
        # Build search request
        search_request = {
            "requests": [{
                "entityTypes": ["chatMessage"],
                "query": {
                    "queryString": query
                },
                "from": from_index,
                "size": page_size
            }]
        }

        # Make search request
        search_result = make_graph_request(url, access_token, method='POST', data=search_request)

        if not search_result:
            # Return None to indicate failure (likely permissions issue)
            return None

        # Extract hits from response
        hits_containers = search_result.get('value', [{}])[0].get('hitsContainers', [])
        if not hits_containers:
            break

        hits = hits_containers[0].get('hits', [])
        if not hits:
            break  # No more results

        # Process each hit
        for hit in hits:
            resource = hit.get('resource', {})
            msg_chat_id = resource.get('chatId')

            # Filter by chat_id if specified
            if chat_id and msg_chat_id != chat_id:
                continue

            # Filter by date if specified
            if since:
                created_str = resource.get('createdDateTime')
                if created_str:
                    created = parse_graph_datetime(created_str)
                    if created < since:
                        continue

            # Add to results
            results.append((msg_chat_id, resource))

            if len(results) >= count:
                break

        # Check if there might be more results
        more_results_available = hits_containers[0].get('moreResultsAvailable', False)
        if not more_results_available:
            break

        # Move to next page
        from_index += page_size

    return results[:count]


def search_messages(access_token, query, chats=None, count=50, since=None, fetch_all_from_chat=False):
    """Search for messages containing query

    Note: Graph API doesn't support $filter by body content for chat messages,
    so we fetch messages from chats and filter locally.

    Args:
        access_token: OAuth2 access token
        query: Search query string
        chats: Optional list of chats to search in (if None, searches all)
        count: Maximum number of results to return
        since: Optional datetime to filter messages after
        fetch_all_from_chat: If True, fetch all messages from each chat (for single chat searches)

    Returns:
        List of (chat, message) tuples
    """
    if chats is None:
        chats = get_chats(access_token, count=50)

    results = []
    query_lower = query.lower()

    for chat in chats:
        # Fetch messages from this chat
        # If searching a single specific chat, fetch all messages with pagination
        messages = get_chat_messages(access_token, chat['id'], count=None if fetch_all_from_chat else 50, since=None, fetch_all=fetch_all_from_chat)

        for msg in messages:
            # Apply local date filter
            if since:
                msg_date = parse_graph_datetime(msg['createdDateTime'])
                if msg_date < since:
                    continue

            body = msg.get('body', {}).get('content', '').lower()
            if query_lower in body:
                results.append((chat, msg))

                if len(results) >= count:
                    return results

    return results


# ============================================================================
# STRUCTURED DATA FUNCTIONS (for MCP and programmatic access)
# ============================================================================

def get_chats_structured(access_token, count=50):
    """
    Get user's chats as structured data (for MCP/programmatic use).

    Args:
        access_token: OAuth2 access token
        count: Maximum number of chats to retrieve

    Returns:
        list[dict]: List of chat dictionaries with schema:
            {
                'id': str,
                'chat_type': str,
                'topic': str,
                'display_name': str,
                'members': list[dict],
                'last_message_datetime': str (ISO 8601),
                'last_message_preview': str
            }
    """
    chats = get_chats(access_token, count)

    structured_chats = []
    for chat in chats:
        members = []
        for member in chat.get('members', []):
            members.append({
                'display_name': member.get('displayName', ''),
                'email': member.get('email', ''),
                'user_id': member.get('userId', '')
            })

        last_msg_preview = chat.get('lastMessagePreview', {})

        structured_chats.append({
            'id': chat.get('id', ''),
            'chat_type': chat.get('chatType', ''),
            'topic': chat.get('topic', ''),
            'display_name': get_chat_display_name(chat),
            'members': members,
            'last_message_datetime': last_msg_preview.get('createdDateTime', ''),
            'last_message_preview': last_msg_preview.get('body', {}).get('content', '')
        })

    return structured_chats


def get_chat_messages_structured(access_token, chat_id, count=50, since=None):
    """
    Get messages from a chat as structured data (for MCP/programmatic use).

    Args:
        access_token: OAuth2 access token
        chat_id: Chat ID
        count: Maximum number of messages to retrieve
        since: Optional datetime to filter messages after

    Returns:
        list[dict]: List of message dictionaries with schema:
            {
                'id': str,
                'created_datetime': str (ISO 8601),
                'sender_name': str,
                'sender_email': str,
                'content': str,
                'content_type': str,
                'attachments': list[dict]
            }
    """
    messages = get_chat_messages(access_token, chat_id, count, since)

    structured_messages = []
    for msg in messages:
        sender = msg.get('from', {}).get('user', {})
        body = msg.get('body', {})

        # Clean HTML content
        content = body.get('content', '')
        content_type = body.get('contentType', 'text')
        if content_type == 'html':
            # Simple HTML stripping
            content = re.sub(r'<[^>]+>', '', content)

        structured_messages.append({
            'id': msg.get('id', ''),
            'created_datetime': msg.get('createdDateTime', ''),
            'sender_name': sender.get('displayName', ''),
            'sender_email': sender.get('userPrincipalName', ''),
            'content': content,
            'content_type': content_type,
            'attachments': msg.get('attachments', [])
        })

    return structured_messages


def send_message_structured(access_token, chat_id, content):
    """
    Send a message to a chat and return status (for MCP/programmatic use).

    Args:
        access_token: OAuth2 access token
        chat_id: Chat ID to send to
        content: Message content (plain text)

    Returns:
        dict: Status dictionary with schema:
            On success:
                {
                    'status': 'success',
                    'message': str,
                    'message_id': str,
                    'created_datetime': str
                }
            On error:
                {
                    'status': 'error',
                    'message': str,
                    'error': str
                }
    """
    try:
        result = send_message(access_token, chat_id, content)

        if result:
            return {
                'status': 'success',
                'message': 'Message sent successfully',
                'message_id': result.get('id', ''),
                'created_datetime': result.get('createdDateTime', '')
            }
        else:
            return {
                'status': 'error',
                'message': 'Failed to send message',
                'error': 'Send operation returned None'
            }

    except Exception as e:
        return {
            'status': 'error',
            'message': 'Failed to send message',
            'error': str(e)
        }


def search_messages_structured(access_token, query, chats=None, count=50, since=None):
    """
    Search for messages as structured data (for MCP/programmatic use).

    Uses fast server-side Search API when possible, with automatic fallback
    to local search if Search API requires additional permissions.

    Args:
        access_token: OAuth2 access token
        query: Search query string
        chats: Optional list of chats to search in
        count: Maximum number of results
        since: Optional datetime to filter messages after

    Returns:
        list[dict]: List of search result dictionaries with schema:
            {
                'chat_id': str,
                'chat_name': str,
                'message_id': str,
                'created_datetime': str,
                'sender_name': str,
                'sender_email': str,
                'content': str,
                'content_type': str
            }
    """
    # Try fast Search API first (only when not filtering by specific chats)
    results = None
    if chats is None:
        results = search_messages_via_api(
            access_token,
            query,
            count=count,
            chat_id=None,
            since=since
        )

    # Fall back to local search if Search API failed or chats filter specified
    if results is None:
        results = search_messages(access_token, query, chats, count, since)

    structured_results = []

    # Handle both Search API results (chat_id, msg) and local search results (chat, msg)
    for item1, msg in results:
        # Determine if this is from Search API (chat_id is string) or local search (chat is dict)
        if isinstance(item1, str):
            # Search API result: item1 is chat_id string
            chat_id = item1
            # Need to fetch chat details for display name
            chat_url = f"{GRAPH_API_BASE}/chats/{chat_id}"
            chat = make_graph_request(chat_url, access_token)
            chat_name = get_chat_display_name(chat) if chat else chat_id
        else:
            # Local search result: item1 is chat dict
            chat = item1
            chat_id = chat.get('id', '')
            chat_name = get_chat_display_name(chat)

        sender = msg.get('from', {}).get('user', {})
        body = msg.get('body', {})

        # Clean HTML content
        content = body.get('content', '')
        content_type = body.get('contentType', 'text')
        if content_type == 'html':
            content = re.sub(r'<[^>]+>', '', content)

        structured_results.append({
            'chat_id': chat_id,
            'chat_name': chat_name,
            'message_id': msg.get('id', ''),
            'created_datetime': msg.get('createdDateTime', ''),
            'sender_name': sender.get('displayName', ''),
            'sender_email': sender.get('userPrincipalName', ''),
            'content': content,
            'content_type': content_type
        })

    return structured_results


# ============================================================================
# CLI COMMAND FUNCTIONS
# ============================================================================

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
    print(f"{'Type':<5} {'Name':<40} {'ID':<50}")
    print("=" * 100)

    for chat in chats:
        chat_id = chat['id']
        chat_type = chat.get('chatType', 'unknown')
        name = get_chat_display_name(chat)[:38]

        # Map chat type to emoji
        type_emoji = {
            'oneOnOne': '👤',
            'group': '👥',
            'meeting': '📅',
        }.get(chat_type, '❓')

        # Get last message preview
        last_msg_preview = chat.get('lastMessagePreview', {})
        last_msg_time = last_msg_preview.get('createdDateTime')
        if last_msg_time:
            dt = parse_graph_datetime(last_msg_time).astimezone(LOCAL_TZ)
            last_msg_str = dt.strftime('%Y-%m-%d %H:%M')
        else:
            last_msg_str = ''

        print(f"{type_emoji:<5} {name:<40} {chat_id:<50}")

    print(f"\nUse 'o365 chat read <chat-id>' to read messages")


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

    # Parse --since filter
    since_date = None
    if args.since:
        try:
            since_date = parse_since_expression(args.since)
        except ValueError as e:
            print(f"Error in --since: {e}", file=sys.stderr)
            sys.exit(1)

    # Determine search count
    search_count = args.count or 50

    # Try Search API first if --chat is specified or no --with filter
    # Search API is much faster but requires ChannelMessage.Read.All permission
    # Fall back to local search if Search API fails due to permissions
    use_local_search = False

    if args.chat_id or not args.with_user:
        # Validate chat ID exists if specified
        if args.chat_id:
            url = f"{GRAPH_API_BASE}/chats/{args.chat_id}"
            chat = make_graph_request(url, access_token)
            if not chat:
                print(f"Error: Chat not found: {args.chat_id}", file=sys.stderr)
                sys.exit(1)

        # Try Search API (fast server-side search)
        results = search_messages_via_api(
            access_token,
            args.query,
            count=search_count,
            chat_id=args.chat_id,
            since=since_date
        )

        # If Search API returns empty list, it might have failed - fall back to local search
        # (Note: make_graph_request returns None on error, which causes empty results)
        if results is None or (args.chat_id and len(results) == 0):
            # Likely failed due to permissions, fall back to local search
            print(f"Note: Search API requires ChannelMessage.Read.All permission. Using slower local search...", file=sys.stderr)
            use_local_search = True
            results = None

    if use_local_search or args.with_user:
        # Use local search when filtering by --with (need to get specific chats first)
        if args.chat_id:
            # If --chat was specified but Search API failed, use that specific chat
            chats = [chat]
        else:
            chats = get_chats(access_token, count=50)
            if args.with_user:
                chats = filter_chats_by_user_or_name(chats, args.with_user, access_token)

        if not chats:
            print(f"No chats found with '{args.with_user}'")
            return

        # When searching a specific chat, fetch all messages for thorough search
        fetch_all = bool(args.chat_id)
        results = search_messages(access_token, args.query, chats=chats, count=search_count, since=since_date, fetch_all_from_chat=fetch_all)

    # Resolve --from user if specified
    from_user = None
    if args.from_user:
        matches = search_users(args.from_user, access_token)

        if not matches:
            print(f"Error: No user found matching '{args.from_user}'", file=sys.stderr)
            sys.exit(1)

        if len(matches) > 1:
            print(f"Error: Ambiguous --from '{args.from_user}' matches {len(matches)} users:", file=sys.stderr)
            for match in matches:
                print(f"  - {match['name']} ({match['email']})", file=sys.stderr)
            sys.exit(1)

        from_user = matches[0]

    # Filter by --from user if specified
    if from_user:
        filtered_results = []
        from_email = from_user['email'].lower()
        from_name = from_user['name'].lower()

        for item in results:
            # Handle both formats: (chat_id, msg) from Search API or (chat, msg) from local search
            if isinstance(item[0], str):
                chat_id, msg = item
            else:
                chat, msg = item

            sender_info = msg.get('from', {}).get('user', {})
            sender_email = sender_info.get('userPrincipalName', '').lower()
            sender_name = sender_info.get('displayName', '').lower()

            # Match by email or name
            if sender_email == from_email or sender_name == from_name:
                filtered_results.append(item)

        results = filtered_results

    if not results:
        if args.from_user:
            print(f"No messages found matching '{args.query}' from {from_user['name']}")
        else:
            print(f"No messages found matching '{args.query}'")
        return

    # Display results
    print(f"\n🔍 Search results for '{args.query}' ({len(results)} found):\n")

    for i, item in enumerate(results):
        # Handle both formats: (chat_id, msg) from Search API or (chat, msg) from local search
        if isinstance(item[0], str):
            chat_id, msg = item
            chat_name = "Unknown Chat"  # Search API doesn't provide chat details
        else:
            chat, msg = item
            chat_id = chat['id']
            chat_name = get_chat_display_name(chat)
        sender = msg.get('from', {}).get('user', {}).get('displayName', 'Unknown')
        created = parse_graph_datetime(msg['createdDateTime']).astimezone(LOCAL_TZ)
        time_str = created.strftime('%Y-%m-%d %H:%M:%S')

        body = msg.get('body', {}).get('content', '')

        # Clean up HTML if present
        if msg.get('body', {}).get('contentType') == 'html':
            body = re.sub(r'<[^>]+>', '', body)

        # Truncate long messages
        if len(body) > 200:
            body = body[:197] + '...'

        print(f"ID:   {chat_id}")
        print(f"Date: {time_str}")
        print(f"Name: {chat_name}")
        print(f"From: {sender}")
        print(body)

        # Add separator between results (but not after the last one)
        if i < len(results) - 1:
            print("---")


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
    search_parser.add_argument('--chat', dest='chat_id', type=str, metavar='CHAT_ID',
                              help='Search only in specific chat ID')
    search_parser.add_argument('--with', dest='with_user', type=str, metavar='USER',
                              help='Search only chats with specific user or group chat name')
    search_parser.add_argument('--from', dest='from_user', type=str, metavar='USER',
                              help='Filter messages from specific user (name or email)')
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
