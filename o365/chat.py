"""
Chat management commands for Office365

List, read, send, and search Microsoft Teams chats.
"""

import argparse
import sys
import re
import html
import urllib.parse
from datetime import datetime, timedelta, timezone

from .common import get_access_token, make_graph_request, GRAPH_API_BASE, global_parent_parser, is_json_mode, emit_json
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
    # Graph API limits $top to 50 for /me/chats
    page_size = min(count, 50)

    url = f"{GRAPH_API_BASE}/me/chats"
    params = {
        '$expand': 'members',
        '$top': str(page_size),
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


def find_chats_by_user_or_name(query, access_token):
    """Search through all chats (with pagination) to find matches by user or name.

    Unlike filter_chats_by_user_or_name which operates on a pre-fetched list,
    this paginates through all chats until matches are found or all chats are
    exhausted.

    Args:
        query: User name/email or chat topic to search for
        access_token: OAuth2 access token

    Returns:
        List of matching chat objects
    """
    # Resolve user emails upfront
    user_matches = search_users(query, access_token)
    user_emails = [u['email'].lower() for u in user_matches] if user_matches else []
    query_lower = query.lower()

    url = f"{GRAPH_API_BASE}/me/chats"
    params = {
        '$expand': 'members',
        '$top': '50',
        '$orderby': 'lastMessagePreview/createdDateTime desc'
    }
    url = f"{url}?{urllib.parse.urlencode(params)}"

    filtered = []
    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        for chat in result.get('value', []):
            if chat is None:
                continue

            # Check topic
            topic = (chat.get('topic') or '').lower()
            if query_lower in topic:
                filtered.append(chat)
                continue

            # Check members
            for member in chat.get('members', []):
                user_principal = (member.get('email') or '').lower()
                display_name = (member.get('displayName') or '').lower()
                if user_principal in user_emails or query_lower in display_name:
                    filtered.append(chat)
                    break

        # If we found 1:1 matches, stop early -- no need to keep paginating
        one_on_one = [c for c in filtered if c.get('chatType') == 'oneOnOne']
        if one_on_one:
            break

        url = result.get('@odata.nextLink')

    return filtered


def get_chat_display_name(chat):
    """Return a stable, human-readable label for a chat.

    Rules, in order:
      1. If the chat has an explicit topic (named group/meeting), use it.
      2. For oneOnOne chats, use the other participant's name.
      3. For group/meeting chats without a topic, return
         "Group(<n>): A, B, C +N more" listing non-self members sorted by
         name. This avoids the previous bug where Graph's member ordering
         varied between calls and a different participant was shown each
         time for the same chat.
    """
    if chat.get('topic'):
        return chat['topic']

    members = chat.get('members') or []
    others = [
        (m.get('displayName') or m.get('email') or 'Unknown')
        for m in members
        if m.get('userId') and not (m.get('displayName') or '').endswith('(You)')
    ]
    others_sorted = sorted(others, key=lambda s: s.lower())

    chat_type = chat.get('chatType') or ''
    if chat_type == 'oneOnOne':
        return others_sorted[0] if others_sorted else 'Unknown Chat'

    if not others_sorted:
        return 'Unknown Chat'

    total = len(others_sorted)
    shown_n = 3
    shown = others_sorted[:shown_n]
    label = ", ".join(shown)
    if total > shown_n:
        label += f" +{total - shown_n} more"

    # Use the total member count (including self) for the size indicator,
    # which matches how Teams shows participant counts.
    total_members = len([m for m in members if m.get('userId')])
    return f"Group({total_members}): {label}"


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


# Message formats accepted by `chat send`. Markdown is the default because it
# reads fine as plain text too: a message with no markdown syntax still comes
# out as paragraphs with its line breaks intact.
MESSAGE_FORMATS = ('markdown', 'html', 'plain')


def plain_to_html(text):
    """Escape plain text for an HTML body, keeping its line breaks."""
    return html.escape(text or '').replace('\n', '<br>')


def markdown_to_html(text):
    """Render markdown to the HTML subset Teams chat displays.

    CommonMark plus tables and ~~strikethrough~~. Single newlines become <br>
    (chat messages are written line by line, not reflowed prose), and raw HTML
    in the source is escaped rather than passed through; use --html for that.
    """
    from markdown_it import MarkdownIt

    md = MarkdownIt('commonmark', {'breaks': True, 'html': False})
    md.enable(['table', 'strikethrough'])
    rendered = md.render(text or '')
    # markdown-it puts a newline after every block tag. Teams can show those
    # as extra blank lines, so drop the ones between tags, but leave the
    # newlines inside <pre> blocks alone since they are the code's lines.
    parts = re.split(r'(<pre>.*?</pre>)', rendered, flags=re.DOTALL)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r'(^|>)\s*\n\s*', r'\1', parts[i])
    for i in range(1, len(parts), 2):
        parts[i] = parts[i].replace('\n</code></pre>', '</code></pre>')
    return ''.join(parts).strip()


def render_message(text, fmt='markdown'):
    """Turn message text into a Graph chatMessage body.

    Args:
        text: Message text as the user wrote it
        fmt: One of MESSAGE_FORMATS

    Returns:
        (content_type, content) tuple for the Graph 'body' object
    """
    if fmt == 'html':
        return 'html', text or ''
    if fmt == 'plain':
        return 'text', text or ''
    return 'html', markdown_to_html(text)


# --- @mentions -------------------------------------------------------------
#
# `@[Display Name]` in a markdown or --html message becomes a real Teams
# mention: `<at id="N">Display Name</at>` in the body plus a matching entry in
# the message's `mentions` array. The brackets keep a bare `@` in ordinary text
# (emails, handles) untouched. Names resolve against the target chat's members.

MENTION_RE = re.compile(r'@\[([^\]\n]+)\]')

# Private-use characters mark where a mention was while markdown renders, so
# markdown-it neither escapes the <at> tag nor reads the name as markdown.
_PH_OPEN, _PH_CLOSE = '', ''
_PH_RE = re.compile(_PH_OPEN + r'(\d+)' + _PH_CLOSE)
_CODE_RE = re.compile(r'(<pre\b.*?</pre>|<code\b.*?</code>)', re.DOTALL | re.IGNORECASE)


class MentionError(Exception):
    """A mention could not be resolved to exactly one chat member."""


def get_chat_members(access_token, chat_id):
    """List a chat's human members as [{'userId', 'displayName', 'email'}]."""
    url = f"{GRAPH_API_BASE}/chats/{chat_id}/members"
    members, seen = [], set()
    while url:
        result = make_graph_request(url, access_token)
        if result is None:
            raise MentionError(f"could not list members of chat {chat_id}")
        for m in result.get('value', []):
            uid = m.get('userId')
            if uid and uid not in seen:
                seen.add(uid)
                members.append({
                    'userId': uid,
                    'displayName': m.get('displayName') or '',
                    'email': m.get('email') or '',
                })
        url = result.get('@odata.nextLink')
    return members


def resolve_mention(name, members):
    """Find the single chat member a mention name refers to.

    Tried in order, case-insensitively, stopping at the first tier with any
    hit: exact display name or email (or email local part), then a prefix of
    the display name ("Luke" -> "Luke Hands"), then a prefix of any word in it
    ("Hands" -> "Luke Hands"). More than one hit in a tier is an error.
    """
    want = ' '.join(name.split()).casefold()
    if not want:
        raise MentionError("empty mention @[]")

    def exact(m):
        email = m['email'].casefold()
        return (m['displayName'].casefold() == want or email == want
                or (email and email.split('@')[0] == want))

    def prefix(m):
        return m['displayName'].casefold().startswith(want)

    def word_prefix(m):
        return any(w.startswith(want) for w in m['displayName'].casefold().split())

    for tier in (exact, prefix, word_prefix):
        hits = [m for m in members if tier(m)]
        if len(hits) == 1:
            return hits[0]
        if hits:
            names = ', '.join(sorted(m['displayName'] for m in hits))
            raise MentionError(f"@[{name}] is ambiguous, matches: {names}")
    known = ', '.join(sorted(m['displayName'] for m in members)) or '(none)'
    raise MentionError(f"@[{name}] matches no member of this chat. Members: {known}")


def _extract_mentions(text):
    """Swap each @[Name] for a placeholder. Returns (text, [names])."""
    names = []

    def sub(match):
        names.append(match.group(1))
        return f'{_PH_OPEN}{len(names) - 1}{_PH_CLOSE}'

    return MENTION_RE.sub(sub, text), names


def _restore_mentions(rendered, names, members_fn):
    """Turn placeholders back into <at> tags and build the mentions array.

    Placeholders inside <code>/<pre> are restored as the literal `@[Name]`
    text, so code samples are not turned into mentions. `members_fn` is only
    called when there is at least one real mention to resolve.
    """
    parts = _CODE_RE.split(rendered)
    for i in range(1, len(parts), 2):
        parts[i] = _PH_RE.sub(
            lambda m: html.escape(f'@[{names[int(m.group(1))]}]', quote=False),
            parts[i])

    wanted = [int(n) for i in range(0, len(parts), 2)
              for n in _PH_RE.findall(parts[i])]
    if not wanted:
        return ''.join(parts), []

    members = members_fn()
    mentions = []
    tags = {}
    for idx in wanted:
        member = resolve_mention(names[idx], members)
        mention_id = len(mentions)
        display = member['displayName']
        mentions.append({
            'id': mention_id,
            'mentionText': display,
            'mentioned': {
                'user': {
                    'id': member['userId'],
                    'displayName': display,
                    'userIdentityType': 'aadUser',
                }
            },
        })
        tags[idx] = f'<at id="{mention_id}">{html.escape(display, quote=False)}</at>'
    for i in range(0, len(parts), 2):
        parts[i] = _PH_RE.sub(lambda m: tags[int(m.group(1))], parts[i])
    return ''.join(parts), mentions


def has_mentions(text):
    """True if text contains any @[Name] mention syntax."""
    return bool(MENTION_RE.search(text or ''))


def render_message_with_mentions(text, fmt, members_fn):
    """Like render_message(), but resolves @[Name] mentions.

    Args:
        text: Message text as the user wrote it
        fmt: One of MESSAGE_FORMATS ('plain' never carries mentions)
        members_fn: Zero-arg callable returning the chat's members (see
            get_chat_members); only called if the message has mentions

    Returns:
        (content_type, content, mentions) where mentions is the Graph
        `mentions` array (empty if none)

    Raises:
        MentionError: a mention matched no member, or more than one
    """
    if fmt == 'plain' or not has_mentions(text):
        content_type, content = render_message(text, fmt)
        return content_type, content, []
    marked, names = _extract_mentions(text)
    _, rendered = render_message(marked, fmt)
    content, mentions = _restore_mentions(rendered, names, members_fn)
    return 'html', content, mentions


def build_message(content, attachments=None, content_type='text', mentions=None):
    """Build the Graph chatMessage request body.

    Args:
        content: Message content, interpreted per content_type
        attachments: Optional list of attachment dicts, each with keys:
            'id' (GUID), 'name' (filename), 'web_url' (OneDrive webUrl).
        content_type: 'text' (plain) or 'html'. See render_message().
        mentions: Optional Graph `mentions` array matching <at id="N"> tags
            already in an html content.
    """
    if attachments:
        # Teams requires HTML body referencing each attachment by its GUID,
        # plus a parallel attachments array with contentType=reference.
        body_html = content if content_type == 'html' else plain_to_html(content)
        attach_html = ''.join(
            f'<attachment id="{a["id"]}"></attachment>' for a in attachments
        )
        message = {
            'body': {
                'contentType': 'html',
                'content': f'{body_html or ""}{attach_html}',
            },
            'attachments': [
                {
                    'id': a['id'],
                    'contentType': 'reference',
                    'contentUrl': a['web_url'],
                    'name': a['name'],
                }
                for a in attachments
            ],
        }
    else:
        message = {
            'body': {
                'contentType': content_type,
                'content': content,
            }
        }
    if mentions:
        message['mentions'] = mentions
    return message


def send_message(access_token, chat_id, content, attachments=None,
                 content_type='text', mentions=None):
    """Send a message to a chat

    Args:
        access_token: OAuth2 access token
        chat_id: Chat ID to send to
        content: Message content, interpreted per content_type
        attachments: Optional list of attachment dicts, see build_message()
        content_type: 'text' (plain) or 'html'. See render_message().
        mentions: Optional Graph `mentions` array, see build_message()

    Returns:
        Created message object or None on error
    """
    url = f"{GRAPH_API_BASE}/chats/{chat_id}/messages"
    message = build_message(content, attachments, content_type, mentions)
    return make_graph_request(url, access_token, method='POST', data=message)


def _fetch_preceding_messages(access_token, chat_id, hit_time_str, n):
    """Fetch up to n messages immediately preceding hit_time in the chat.

    Used by `chat search --context N`. One Graph call per hit (worst
    case); skips silently on failure so a single dropped lookup doesn't
    sink the whole results display.
    """
    if n <= 0:
        return []
    hit_time = parse_graph_datetime(hit_time_str)

    # Pull a small window and filter locally — Graph chat-message $filter
    # support is limited, so it's simpler to grab the recent batch and
    # walk it. We need slightly more than n because the hit itself is in
    # the response and other messages after the hit may be in the window.
    url = f"{GRAPH_API_BASE}/me/chats/{chat_id}/messages?$top={max(n * 3, 20)}"
    resp = make_graph_request(url, access_token)
    if not resp:
        return []

    preceding = []
    for m in resp.get('value', []):
        mt_str = m.get('createdDateTime')
        if not mt_str:
            continue
        try:
            mt = parse_graph_datetime(mt_str)
        except Exception:
            continue
        if mt < hit_time:
            preceding.append((mt, m))

    # Sort ascending, take the last n (closest to the hit)
    preceding.sort(key=lambda x: x[0])
    return [m for _, m in preceding[-n:]]


def _normalize_search_hit(hit):
    """Convert a Search API hit to the shape /me/chats/{id}/messages returns.

    The Search API uses `from.emailAddress.name/address` (mail-style),
    omits `body`, and gives a relevance-snippet in `summary`. Local
    messages use `from.user.displayName/id`, full HTML body, no summary.
    Normalize to the local shape — using `summary` as the body content
    (which is actually nicer for search results, since it's already
    excerpted around the match) — so downstream display + JSON code
    doesn't have to switch on origin.
    """
    resource = hit.get('resource', {})
    from_addr = (resource.get('from') or {}).get('emailAddress') or {}
    return {
        'id': resource.get('id'),
        'createdDateTime': resource.get('createdDateTime'),
        'from': {
            'user': {
                'displayName': from_addr.get('name'),
                'id': None,
                'userPrincipalName': from_addr.get('address'),
            }
        },
        'body': {
            'contentType': 'text',
            'content': hit.get('summary') or '',
        },
        'webLink': resource.get('webLink'),
        'chatId': resource.get('chatId'),
        '_from_search_api': True,
    }


def _build_chat_kql(query, from_user=None, since=None):
    """Build a KQL query string for the Graph Search API.

    `query` may be empty/None — we substitute "*" so Graph still accepts
    the request, enabling pure filter-only searches like "all messages
    from Luke this week".

    Sender filter uses KQL `from:"..."`. Date filter uses `sent>=YYYY-MM-DD`
    (Graph's keyword is `sent`, not `created`/`received` — confirmed
    empirically; `created>=` returns 0 hits even when there are matches).
    """
    parts = []
    parts.append(query.strip() if query and query.strip() else '*')
    if from_user:
        parts.append(f'from:"{from_user}"')
    if since is not None:
        parts.append(f'sent>={since.strftime("%Y-%m-%d")}')
    return ' '.join(parts)


def search_messages_via_api(access_token, query, count=50, chat_id=None,
                            since=None, from_user=None):
    """Search for messages using Microsoft Graph Search API (POST /search/query).

    Requires ChannelMessage.Read.All. With that scope, this is ~25-100x
    faster than the local fallback because the search is server-side and
    supports KQL: wildcards (release*), boolean (client OR release),
    phrases ("client release"), and property filters (from:, sent>=,
    subject:).

    `from_user` and `since` are translated into KQL operators and pushed
    server-side rather than post-filtered. `chat_id` is still applied
    client-side because Graph's KQL doesn't expose a chat-ID filter.

    Returns:
        List of (chat_id, message) tuples, or None on HTTP error.
    """
    url = "https://graph.microsoft.com/beta/search/query"

    results = []
    from_index = 0
    page_size = 25
    query_string = _build_chat_kql(query, from_user=from_user, since=since)

    while len(results) < count:
        search_request = {
            "requests": [{
                "entityTypes": ["chatMessage"],
                "query": {
                    "queryString": query_string,
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

        # Process each hit. Normalize to the same shape as messages from
        # /me/chats/{id}/messages so the downstream display + JSON code
        # doesn't need a second case.
        for hit in hits:
            resource = hit.get('resource', {})
            msg_chat_id = resource.get('chatId')

            if chat_id and msg_chat_id != chat_id:
                continue
            if since:
                created_str = resource.get('createdDateTime')
                if created_str:
                    created = parse_graph_datetime(created_str)
                    if created < since:
                        continue

            normalized = _normalize_search_hit(hit)
            results.append((msg_chat_id, normalized))

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
        sender = (msg.get('from') or {}).get('user') or {}
        body = msg.get('body') or {}

        # Clean HTML content
        content = body.get('content', '')
        content_type = body.get('contentType', 'text')
        if content_type == 'html':
            # Simple HTML stripping
            content = html.unescape(re.sub(r'<[^>]+>', '', content))

        structured_messages.append({
            'id': msg.get('id', ''),
            'created_datetime': msg.get('createdDateTime', ''),
            'sender_name': sender.get('displayName', '') or 'System',
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

        sender = (msg.get('from') or {}).get('user') or {}
        body = msg.get('body') or {}

        # Clean HTML content
        content = body.get('content', '')
        content_type = body.get('contentType', 'text')
        if content_type == 'html':
            content = html.unescape(re.sub(r'<[^>]+>', '', content))

        structured_results.append({
            'chat_id': chat_id,
            'chat_name': chat_name,
            'message_id': msg.get('id', ''),
            'created_datetime': msg.get('createdDateTime', ''),
            'sender_name': sender.get('displayName', '') or 'System',
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

    # Get chats (use deep search when filtering by user)
    if args.with_user:
        chats = find_chats_by_user_or_name(args.with_user, access_token)

        if not chats:
            print(f"No chats found with '{args.with_user}'")
            return
    else:
        chats = get_chats(access_token, count=args.count or 50)

        if not chats:
            print("No chats found")
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

    if is_json_mode(args):
        emit_json({
            'chats': [_serialize_chat(c) for c in chats],
            'count': len(chats),
        })
        return

    # Display chats
    print(f"\n💬 Chats ({len(chats)} shown):\n")
    print(f"{'Type':<5} {'Name':<40} {'ID':<50}")
    print("=" * 100)

    for chat in chats:
        chat_id = chat['id']
        chat_type = chat.get('chatType', 'unknown')
        name = get_chat_display_name(chat)[:38]
        type_emoji = {
            'oneOnOne': '👤',
            'group': '👥',
            'meeting': '📅',
        }.get(chat_type, '❓')
        print(f"{type_emoji:<5} {name:<40} {chat_id:<50}")

    print(f"\nUse 'o365 chat read <chat-id>' to read messages")


def _serialize_chat(chat):
    """Serialize a Graph chat object for --json output."""
    members = [
        {
            'display_name': m.get('displayName'),
            'email': m.get('email'),
            'user_id': m.get('userId'),
        }
        for m in (chat.get('members') or [])
    ]
    last = chat.get('lastMessagePreview') or {}
    return {
        'id': chat.get('id'),
        'type': chat.get('chatType'),
        'topic': chat.get('topic'),
        'display_name': get_chat_display_name(chat),
        'members': members,
        'last_message_at': last.get('createdDateTime'),
    }


def _serialize_chat_message(msg):
    """Serialize a Graph chat message for --json output."""
    body_obj = msg.get('body') or {}
    body_content = body_obj.get('content') or ''
    if body_obj.get('contentType') == 'html':
        body_content = html.unescape(re.sub(r'<[^>]+>', '', body_content))
    sender = ((msg.get('from') or {}).get('user') or {}) or {}
    return {
        'id': msg.get('id'),
        'created': msg.get('createdDateTime'),
        'sender': {
            'display_name': sender.get('displayName'),
            'id': sender.get('id'),
        },
        'body': body_content,
        'body_content_type': body_obj.get('contentType'),
    }


def cmd_read(args):
    """Handle 'o365 chat read' command"""
    access_token = get_access_token()

    # Resolve chat ID (positional first, then --chat flag form)
    chat_id_from_flag = getattr(args, 'chat_id_flag', None)
    if args.chat_id and chat_id_from_flag and args.chat_id != chat_id_from_flag:
        print("Error: provide chat ID via positional OR --chat, not both", file=sys.stderr)
        sys.exit(2)
    if args.chat_id:
        chat_id = args.chat_id
    elif chat_id_from_flag:
        chat_id = chat_id_from_flag
    elif args.with_user:
        # Find chat with user (searches through all chats via pagination)
        filtered = find_chats_by_user_or_name(args.with_user, access_token)

        if not filtered:
            print(f"Error: No chat found with '{args.with_user}'", file=sys.stderr)
            sys.exit(1)

        # Prefer 1:1 chats over group/meeting chats
        one_on_one = [c for c in filtered if c.get('chatType') == 'oneOnOne']
        if one_on_one:
            filtered = one_on_one

        if len(filtered) > 1:
            print(f"Multiple chats found with '{args.with_user}':", file=sys.stderr)
            for chat in filtered:
                chat_type = chat.get('chatType', 'unknown')
                print(f"  - [{chat_type}] {get_chat_display_name(chat)}: {chat['id']}", file=sys.stderr)
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

    if is_json_mode(args):
        emit_json({
            'chat_id': chat_id,
            'messages': [_serialize_chat_message(m) for m in messages],
            'count': len(messages),
        })
        return

    if not messages:
        print("No messages found")
        return

    # Display messages
    print(f"\n💬 Messages ({len(messages)} shown):\n")

    for msg in messages:
        sender = ((msg.get('from') or {}).get('user') or {}).get('displayName') or 'System'
        created = parse_graph_datetime(msg['createdDateTime']).astimezone(LOCAL_TZ)
        time_str = created.strftime('%Y-%m-%d %H:%M:%S')

        body_obj = msg.get('body') or {}
        body = body_obj.get('content', '')

        # Clean up HTML if present
        if body_obj.get('contentType') == 'html':
            body = html.unescape(re.sub(r'<[^>]+>', '', body))

        print(f"[{time_str}] {sender}")
        print(f"  {body}")
        print()


def _read_message_arg(value):
    """Resolve -m: '-' reads the message from stdin, else it is literal text."""
    if value == '-':
        return sys.stdin.read()
    return value


def cmd_send(args):
    """Handle 'o365 chat send' command"""
    import uuid
    from pathlib import Path
    from .files import upload_file

    access_token = get_access_token()

    files = args.files or []
    dry_run = getattr(args, 'dry_run', False) is True
    extra_mentions = getattr(args, 'mentions', None)
    extra_mentions = extra_mentions if isinstance(extra_mentions, list) else []
    message = _read_message_arg(args.message)
    if not message and not files and not extra_mentions:
        print("Error: Must specify -m/--message and/or -f/--file", file=sys.stderr)
        sys.exit(1)
    fmt = getattr(args, 'format', None) or 'markdown'

    if extra_mentions:
        if fmt == 'plain':
            print("Error: --mention needs a rich-text message; drop --plain",
                  file=sys.stderr)
            sys.exit(1)
        lead = ' '.join(f'@[{name}]' for name in extra_mentions)
        message = f'{lead} {message}' if message else lead
    if fmt == 'plain' and has_mentions(message):
        print("Warning: --plain sends @[Name] as literal text, not a mention",
              file=sys.stderr)

    # Resolve chat ID
    if args.chat_id:
        chat_id = args.chat_id
    elif args.to:
        # Find chat with user (searches through all chats via pagination)
        filtered = find_chats_by_user_or_name(args.to, access_token)

        if not filtered:
            print(f"Error: No chat found with '{args.to}'", file=sys.stderr)
            sys.exit(1)

        # Prefer 1:1 chats over group/meeting chats
        one_on_one = [c for c in filtered if c.get('chatType') == 'oneOnOne']
        if one_on_one:
            filtered = one_on_one

        if len(filtered) > 1:
            print(f"Multiple chats found with '{args.to}':", file=sys.stderr)
            for chat in filtered:
                chat_type = chat.get('chatType', 'unknown')
                print(f"  - [{chat_type}] {get_chat_display_name(chat)}: {chat['id']}", file=sys.stderr)
            print("\nUse 'o365 chat send --chat <chat-id>' with specific ID", file=sys.stderr)
            sys.exit(1)

        chat_id = filtered[0]['id']
    else:
        print("Error: Must specify --chat or --to", file=sys.stderr)
        sys.exit(1)

    # Render the message, resolving any @[Name] mentions against the chat's
    # members (only looked up when the message actually mentions someone).
    mentions = []
    if message:
        try:
            content_type, content, mentions = render_message_with_mentions(
                message, fmt, lambda: get_chat_members(access_token, chat_id))
        except MentionError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        content_type, content = 'text', ''

    # Upload any attached files to OneDrive (Teams convention: place them in
    # "Microsoft Teams Chat Files/" so they live alongside files the Teams
    # client itself uploads), then build reference attachments for the message.
    attachments = []
    for local_path in files:
        src = Path(local_path)
        if not src.exists():
            print(f"Error: File not found: {local_path}", file=sys.stderr)
            sys.exit(1)

        if dry_run:
            # Nothing is uploaded on a dry run; show where the link would go.
            attachments.append({
                'id': str(uuid.uuid4()),
                'name': src.name,
                'web_url': f'<sharing link for {src.name}, created on send>',
            })
            continue

        print(f"Uploading {src.name}...", file=sys.stderr)
        uploaded = upload_file(
            access_token,
            str(src),
            'Microsoft Teams Chat Files',
            overwrite=True,
        )
        if not uploaded or not uploaded.get('id'):
            print(f"Error: Failed to upload {src.name}", file=sys.stderr)
            sys.exit(1)

        # Teams attachment cards require a sharing-link URL, not the raw
        # driveItem webUrl, or clicking the file gives "File Not Found".
        item_id = uploaded['id']
        drive_id = uploaded.get('parentReference', {}).get('driveId')
        link_path = (
            f"/drives/{drive_id}/items/{item_id}/createLink"
            if drive_id else f"/me/drive/items/{item_id}/createLink"
        )
        link = make_graph_request(
            link_path, access_token, method='POST',
            data={'type': 'view', 'scope': 'organization'},
        )
        share_url = (link or {}).get('link', {}).get('webUrl')
        if not share_url:
            print(f"Error: Failed to create sharing link for {src.name}", file=sys.stderr)
            sys.exit(1)

        attachments.append({
            'id': str(uuid.uuid4()),
            'name': uploaded.get('name', src.name),
            'web_url': share_url,
        })

    if dry_run:
        import json
        print(json.dumps({
            'method': 'POST',
            'url': f"{GRAPH_API_BASE}/chats/{chat_id}/messages",
            'body': build_message(content, attachments, content_type, mentions),
        }, indent=2, ensure_ascii=False))
        return

    # Send message (with attachments if any)
    result = send_message(access_token, chat_id, content,
                          attachments=attachments, content_type=content_type,
                          mentions=mentions)

    if result:
        if attachments:
            print(f"✓ Message sent successfully ({len(attachments)} attachment(s))")
        else:
            print("✓ Message sent successfully")
    else:
        print("Error: Failed to send message", file=sys.stderr)
        sys.exit(1)


def cmd_search(args):
    """Handle 'o365 chat search' command."""
    access_token = get_access_token()

    since_date = None
    if args.since:
        try:
            since_date = parse_since_expression(args.since)
        except ValueError as e:
            print(f"Error in --since: {e}", file=sys.stderr)
            sys.exit(1)

    search_count = args.count or 50

    # Require *some* filter — empty positional + no --from + no --since
    # would dump the entire chat history with KQL '*', which is rarely
    # what anyone wants and would burn quota.
    if not args.query and not args.from_user and not args.since and not args.with_user and not args.chat_id:
        print("Error: provide a query, or --from / --since / --with / --chat filter.",
              file=sys.stderr)
        sys.exit(2)

    results = None
    used_local = False

    # Path 1: Search API (fast, server-side KQL). Used unless --with_user
    # is specified, since that needs a chat-membership filter that KQL
    # doesn't expose.
    if args.chat_id or not args.with_user:
        if args.chat_id:
            url = f"{GRAPH_API_BASE}/chats/{args.chat_id}"
            chat = make_graph_request(url, access_token)
            if not chat:
                print(f"Error: Chat not found: {args.chat_id}", file=sys.stderr)
                sys.exit(1)

        results = search_messages_via_api(
            access_token,
            args.query,
            count=search_count,
            chat_id=args.chat_id,
            since=since_date,
            from_user=args.from_user,
        )

        # `None` = actual HTTP error (typically 403 because
        # ChannelMessage.Read.All isn't granted). An empty *list* is a
        # legitimate "no matches" result; don't fall back on that.
        if results is None:
            print(
                "Note: Graph Search API unavailable (likely missing "
                "ChannelMessage.Read.All admin grant). Falling back to "
                "local enumeration — this is much slower.",
                file=sys.stderr,
            )
            used_local = True

    if used_local or args.with_user:
        if args.chat_id:
            chats = [chat]
        elif args.with_user:
            chats = find_chats_by_user_or_name(args.with_user, access_token)
        else:
            chats = get_chats(access_token, count=50)

        if not chats:
            print(f"No chats found with '{args.with_user}'")
            return

        fetch_all = bool(args.chat_id)
        results = search_messages(
            access_token, args.query or '', chats=chats,
            count=search_count, since=since_date, fetch_all_from_chat=fetch_all,
        )

        # Local path doesn't push --from to KQL; apply the post-filter here
        # using the resolved user (catches both displayName + email matches).
        if args.from_user and results:
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
            from_email = from_user['email'].lower()
            from_name = from_user['name'].lower()
            filtered = []
            for item in results:
                msg = item[1]
                sender_info = (msg.get('from') or {}).get('user') or {}
                sender_email = sender_info.get('userPrincipalName', '').lower()
                sender_name = sender_info.get('displayName', '').lower()
                if sender_email == from_email or sender_name == from_name:
                    filtered.append(item)
            results = filtered

    # Search API hits arrive with chat_id only; build a name map so output
    # is human-readable. One /me/chats call covers the common case.
    chat_name_map = {}
    if any(isinstance(item[0], str) for item in results):
        chats_resp = get_chats(access_token, count=50)
        chat_name_map = {c['id']: get_chat_display_name(c) for c in chats_resp}

    def _name_for(item):
        if isinstance(item[0], str):
            return chat_name_map.get(item[0]) or 'Unknown Chat'
        return get_chat_display_name(item[0])

    if is_json_mode(args):
        json_items = []
        for item in results:
            chat_id = item[0] if isinstance(item[0], str) else item[0]['id']
            msg = item[1]
            entry = _serialize_chat_message(msg)
            entry['chat_id'] = chat_id
            entry['chat_name'] = _name_for(item)
            json_items.append(entry)
        emit_json({
            'query': args.query,
            'matches': json_items,
            'count': len(json_items),
        })
        return

    if not results:
        if args.from_user:
            print(f"No messages found matching '{args.query}' from {from_user['name']}")
        else:
            print(f"No messages found matching '{args.query}'")
        return

    # Display results
    print(f"\n🔍 Search results for '{args.query}' ({len(results)} found):\n")

    for i, item in enumerate(results):
        chat_id = item[0] if isinstance(item[0], str) else item[0]['id']
        msg = item[1]
        chat_name = _name_for(item)
        sender = ((msg.get('from') or {}).get('user') or {}).get('displayName') or 'System'
        created = parse_graph_datetime(msg['createdDateTime']).astimezone(LOCAL_TZ)
        time_str = created.strftime('%Y-%m-%d %H:%M:%S')

        body = (msg.get('body') or {}).get('content', '')

        # Clean up HTML if present
        if (msg.get('body') or {}).get('contentType') == 'html':
            body = html.unescape(re.sub(r'<[^>]+>', '', body))

        # Search API `summary` snippets pack attachment names against body
        # text with long runs of whitespace (e.g. "WCDE.apk1        client
        # 2.5.8"). Collapse 2+ whitespace into a single space — snippets
        # are display-only so we don't need to preserve original spacing.
        if msg.get('_from_search_api'):
            body = re.sub(r'\s{2,}', ' ', body).strip()

        # Truncate long messages
        if len(body) > 200:
            body = body[:197] + '...'

        print(f"ID:   {chat_id}")
        print(f"Date: {time_str}")
        print(f"Name: {chat_name}")
        print(f"From: {sender}")
        print(body)

        # Context: N preceding messages from the same chat
        if getattr(args, 'context', 0):
            ctx = _fetch_preceding_messages(
                access_token, chat_id, msg['createdDateTime'], args.context,
            )
            if ctx:
                print()
                print(f"  --- {len(ctx)} preceding message(s) ---")
                for cm in ctx:
                    csender = ((cm.get('from') or {}).get('user') or {}).get('displayName') or 'System'
                    ctime = parse_graph_datetime(cm['createdDateTime']).astimezone(LOCAL_TZ)
                    cbody = (cm.get('body') or {}).get('content', '')
                    if (cm.get('body') or {}).get('contentType') == 'html':
                        cbody = html.unescape(re.sub(r'<[^>]+>', '', cbody))
                    cbody = re.sub(r'\s+', ' ', cbody).strip()
                    if len(cbody) > 120:
                        cbody = cbody[:117] + '...'
                    print(f"  [{ctime:%H:%M:%S}] {csender}: {cbody}")

        # Add separator between results (but not after the last one)
        if i < len(results) - 1:
            print("---")


# Setup and routing

def setup_parser(subparsers):
    """Setup argparse subcommands for chat"""

    _parent = global_parent_parser()

    # o365 chat list
    list_parser = subparsers.add_parser(
        'list',
        parents=[_parent],
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
        parents=[_parent],
        help='Read messages from a chat',
        description='Read messages from a Microsoft Teams chat.'
    )

    read_parser.add_argument('chat_id', nargs='?', help='Chat ID to read from')
    read_parser.add_argument('--chat', dest='chat_id_flag', type=str, metavar='CHAT_ID',
                            help='Chat ID (flag form, mirrors `chat send --chat`)')
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
        parents=[_parent],
        help='Send a message to a chat',
        description='Send a message to a Microsoft Teams chat.\n\n'
                    'The message is markdown, sent as rich text (bold, lists,\n'
                    'headings, tables, code blocks). Line breaks are kept as\n'
                    'written, so plain text comes through unchanged.\n\n'
                    'Mentions: write @[Name] to @mention a chat member. Name is\n'
                    'their display name, email, or a unique prefix of either\n'
                    'the name or one word of it (@[Luke] for Luke Hands).\n'
                    'Works with --html too; not with --plain. A bare @ is\n'
                    'left alone, and @[...] inside `code` is not a mention.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  o365 chat send --to "Luke Hands" -m "**done**, see below"
  o365 chat send --chat <id> -m - < notes.md      # markdown from stdin
  cat <<'EOF' | o365 chat send --chat <id> -m -   # no shell quoting needed
  o365 chat send --chat <id> -m "see attached" -f report.pdf
  o365 chat send --chat <id> -m "@[Luke] can you review?"
  o365 chat send --chat <id> --mention Luke --mention Roman -m "deployed"
  o365 chat send --chat <id> -m "@[Luke] hi" --dry-run   # print, don't send
"""
    )

    send_parser.add_argument('--chat', dest='chat_id', type=str, metavar='CHAT_ID',
                            help='Chat ID to send to')
    send_parser.add_argument('--to', type=str, metavar='USER',
                            help='Send to chat with specific user or group chat name')
    send_parser.add_argument('-m', '--message', type=str, metavar='TEXT',
                            help="Message in markdown, or '-' to read it from "
                                 "stdin (optional if -f is given)")
    send_parser.add_argument('-f', '--file', dest='files', action='append',
                            metavar='PATH',
                            help='Attach a local file (repeatable). '
                                 'Uploaded to "Microsoft Teams Chat Files/" in your OneDrive.')
    fmt_group = send_parser.add_argument_group(
        'format overrides (default: render markdown)')
    fmt_group = fmt_group.add_mutually_exclusive_group()
    fmt_group.add_argument('--plain', dest='format', action='store_const',
                           const='plain', help='Send the text as-is, no markdown')
    fmt_group.add_argument('--html', dest='format', action='store_const',
                           const='html', help='Message is already Teams HTML')
    send_parser.set_defaults(format='markdown')
    send_parser.add_argument('--mention', dest='mentions', action='append',
                            metavar='NAME', default=[],
                            help='@mention a chat member at the start of the '
                                 'message (repeatable); same as writing @[NAME]')
    send_parser.add_argument('--dry-run', action='store_true',
                            help='Print the Graph request as JSON instead of '
                                 'sending it (no files are uploaded)')

    send_parser.set_defaults(func=cmd_send)

    # o365 chat search
    search_parser = subparsers.add_parser(
        'search',
        parents=[_parent],
        help='Search chat messages',
        description='Search for messages in Microsoft Teams chats. '
                    'Uses the Graph Search API (server-side KQL) when '
                    'ChannelMessage.Read.All is granted; falls back to '
                    'local enumeration otherwise. KQL operators '
                    '(release*, "exact phrase", a OR b, from:luke, '
                    'sent>=2026-05-25, subject:"...") work in the query '
                    'string when on the Search API path. Note: Graph uses '
                    '`sent`, not `created` or `received`, for the date '
                    'keyword.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  o365 chat search "deployment"
  o365 chat search "release*"                  # KQL wildcard
  o365 chat search --from "Luke Hands"         # filter-only (no query needed)
  o365 chat search --from luke --since "1 week ago"
  o365 chat search "build OR deploy" --from luke
  o365 chat search "rollout" --context 3       # show 3 preceding msgs per hit

Sort order: results are newest-first (Graph relevance + recency).
"""
    )

    # query is optional — `--from`/`--since` alone are a valid search now.
    search_parser.add_argument('query', nargs='?', default=None,
                              help='Search query (KQL when Search API is available; '
                                   'literal substring on local fallback). Optional — '
                                   'omit to filter by --from/--since only.')
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
    search_parser.add_argument('--context', type=int, default=0, metavar='N',
                              help='Show N messages immediately preceding each '
                                   'hit (for thread context). Default: 0. Adds '
                                   'one Graph call per hit.')

    search_parser.set_defaults(func=cmd_search)


def handle_command(args):
    """Route to appropriate chat subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No chat subcommand specified", file=sys.stderr)
        sys.exit(1)
