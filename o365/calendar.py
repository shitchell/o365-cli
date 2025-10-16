"""
Calendar management commands for Office365

List and manage calendar events with flexible filtering.
"""

import sys
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

from .common import get_access_token, make_graph_request, GRAPH_API_BASE
from .contacts import search_users

# Get local timezone
LOCAL_TZ = datetime.now().astimezone().tzinfo


def parse_since_expression(timestring):
    """Parse git-style time expressions

    Supports relative times (e.g., "2 days ago", "1 week") and absolute dates
    (e.g., "2025-01-15", "December 20, 2024").

    Adapted from countdown.py's parse_timestring function.
    Returns timezone-aware datetime in local timezone.
    """
    from dateutil.parser import parse as dateutil_parse

    if not timestring:
        return None

    # Lowercase for easier matching
    timestring = timestring.lower().strip()

    # Get current time in local timezone
    now_local = datetime.now(LOCAL_TZ)

    # Keyword substitutions for common relative terms
    _substitutions = [
        ("yesterday", (now_local - timedelta(days=1)).strftime("%Y-%m-%d")),
        ("today", now_local.strftime("%Y-%m-%d")),
        ("tomorrow", (now_local + timedelta(days=1)).strftime("%Y-%m-%d")),
    ]

    # Check if timestring is relative format: [+/-]N UNIT [ago]
    relative_match = re.match(
        r'^([+-])?\s*(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks|M|month|months|y|yr|yrs|year|years)\s*(?:ago)?$',
        timestring,
        re.IGNORECASE
    )

    if relative_match:
        sign, num, unit = relative_match.groups()

        # Default to minus (past) if no sign given for --since
        if not sign:
            sign = '-'

        # Convert unit to seconds
        unit = unit.lower()
        if unit in ('s', 'sec', 'secs', 'second', 'seconds'):
            seconds = int(num)
        elif unit in ('m', 'min', 'mins', 'minute', 'minutes'):
            seconds = int(num) * 60
        elif unit in ('h', 'hr', 'hrs', 'hour', 'hours'):
            seconds = int(num) * 3600
        elif unit in ('d', 'day', 'days'):
            seconds = int(num) * 86400
        elif unit in ('w', 'wk', 'wks', 'week', 'weeks'):
            seconds = int(num) * 604800
        elif unit in ('M', 'month', 'months'):
            seconds = int(num) * 2629743  # Average month in seconds
        elif unit in ('y', 'yr', 'yrs', 'year', 'years'):
            seconds = int(num) * 31556926  # Average year in seconds
        else:
            raise ValueError(f"Invalid time unit: {unit}")

        # Apply sign
        if sign == '-':
            seconds = -seconds

        return now_local + timedelta(seconds=seconds)

    # Apply keyword substitutions
    for keyword, substitution in _substitutions:
        timestring = re.sub(keyword, substitution, timestring, flags=re.IGNORECASE)

    # Fall back to dateutil.parser for absolute dates
    try:
        dt = dateutil_parse(timestring)
        # Make timezone-aware if naive (assume local timezone)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        return dt
    except Exception as e:
        raise ValueError(
            f"Invalid date expression: '{timestring}'. "
            f"Use git-style formats like '2 days ago', '1 week', or ISO dates like '2025-01-15'."
        ) from e


def parse_graph_datetime(dt_str):
    """Parse Microsoft Graph datetime format"""
    # Remove excess fractional seconds (keep max 6 digits)
    dt_str = re.sub(r'\.(\d{6})\d*', r'.\1', dt_str)
    # Handle timezone
    if not dt_str.endswith('Z') and '+' not in dt_str and '-' not in dt_str[-6:]:
        dt_str += 'Z'
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def resolve_user(user_query, access_token):
    """Resolve user query to email using contacts module"""
    matches = search_users(user_query, access_token)

    if not matches:
        print(f"Error: No users found matching '{user_query}'", file=sys.stderr)
        sys.exit(1)

    if len(matches) > 1:
        print(f"Error: Ambiguous query '{user_query}' matches {len(matches)} users:", file=sys.stderr)
        for match in matches:
            print(f"  - {match['name']} ({match['email']})", file=sys.stderr)
        sys.exit(1)

    return matches[0]['email']


def get_calendar_id_for_user(email, access_token):
    """Get the calendar ID for a shared calendar by owner email"""
    url = f"{GRAPH_API_BASE}/me/calendars"
    result = make_graph_request(url, access_token)

    if not result:
        return None

    for calendar in result.get('value', []):
        owner = calendar.get('owner', {})
        owner_email = owner.get('address', '').lower()

        if owner_email == email.lower():
            return calendar.get('id')

    return None


def list_events(access_token, start_date, end_date, user_email=None):
    """List calendar events within date range"""

    # Convert to UTC for Graph API
    start_utc = start_date.astimezone(timezone.utc)
    end_utc = end_date.astimezone(timezone.utc)

    # Format dates for Graph API
    start_str = start_utc.strftime('%Y-%m-%dT%H:%M:%S')
    end_str = end_utc.strftime('%Y-%m-%dT%H:%M:%S')

    # Build endpoint based on user
    if user_email:
        # Get calendar ID for the user
        calendar_id = get_calendar_id_for_user(user_email, access_token)
        if not calendar_id:
            print(f"Error: No shared calendar found for {user_email}", file=sys.stderr)
            print("Make sure their calendar is shared with you.", file=sys.stderr)
            sys.exit(1)

        endpoint = f"/me/calendars/{calendar_id}/calendarView"
    else:
        endpoint = "/me/calendarView"

    # Add query parameters
    params = {
        'startDateTime': f'{start_str}Z',
        'endDateTime': f'{end_str}Z',
        '$orderby': 'start/dateTime'
    }

    url = f"{GRAPH_API_BASE}{endpoint}?{urllib.parse.urlencode(params)}"

    # Handle pagination
    events = []
    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        events.extend(result.get('value', []))

        # Check for pagination
        url = result.get('@odata.nextLink')

    return events


def display_events(events, start_date, end_date, user_email=None):
    """Display events in a formatted table"""
    # Check if date range is a single day
    single_day = start_date.date() == end_date.date()

    if not events:
        user_str = f" for {user_email}" if user_email else ""
        if single_day:
            print(f"No events found{user_str} on {start_date.strftime('%Y-%m-%d')}")
        else:
            print(f"No events found{user_str} between {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}")
        return

    user_str = f" - {user_email}" if user_email else ""
    if single_day:
        date_range_str = start_date.strftime('%Y-%m-%d')
    else:
        date_range_str = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

    print(f"\n📅 Events{user_str} ({date_range_str}):\n")
    print(f"{'Date':<12} {'Time':<15} {'Subject':<40} {'Location':<30}")
    print("=" * 100)

    for event in events:
        subject = event.get('subject', '(No subject)')
        location = event.get('location', {}).get('displayName', '')

        # Parse UTC time from Graph API and convert to local
        start_dt = parse_graph_datetime(event['start']['dateTime']).astimezone(LOCAL_TZ)
        end_dt = parse_graph_datetime(event['end']['dateTime']).astimezone(LOCAL_TZ)

        date_str = start_dt.strftime('%Y-%m-%d')
        time_str = f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"

        print(f"{date_str:<12} {time_str:<15} {subject[:38]:<40} {location[:28]:<30}")

    print(f"\nTotal: {len(events)} events\n")


# Command handlers

def cmd_list(args):
    """Handle 'o365 calendar list' command"""
    access_token = get_access_token()

    # Determine date range (using local timezone)
    now = datetime.now(LOCAL_TZ)

    if args.today:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif args.week:
        # Get Monday of current week
        days_since_monday = now.weekday()
        start_date = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        # Get Sunday of current week
        end_date = (start_date + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif args.month:
        # Get first day of month
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Get last day of month
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        end_date = (next_month - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        # Manual date range
        if args.after:
            try:
                start_date = parse_since_expression(args.after)
            except ValueError as e:
                print(f"Error in --after: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Default to today if no start specified
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if args.before:
            try:
                # For --before, we want future dates to work naturally
                expr = args.before
                # If expression starts with a number without +/-, treat it as future
                if re.match(r'^\d+\s+(day|week|month|year)', expr, re.IGNORECASE):
                    expr = '+' + expr
                end_date = parse_since_expression(expr)
            except ValueError as e:
                print(f"Error in --before: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Default to 7 days from start if no end specified
            end_date = start_date + timedelta(days=7)

    # Resolve user if specified
    user_email = None
    if args.user:
        user_email = resolve_user(args.user, access_token)

    # Fetch and display events
    events = list_events(access_token, start_date, end_date, user_email)

    # TODO: Apply additional filters here (title regex, attendees, etc.)
    # filtered_events = apply_filters(events, args)

    display_events(events, start_date, end_date, user_email)


# Setup and routing

def setup_parser(subparsers):
    """Setup argparse subcommands for calendar"""

    # o365 calendar list
    list_parser = subparsers.add_parser(
        'list',
        help='List calendar events',
        description='List calendar events from Office365 with flexible filtering.',
        epilog="""
Time Format:
  All time expressions support git-style formats:
    - Relative: "2 days ago", "1 week", "5h", "yesterday"
    - Absolute: "2025-01-15", "December 20, 2024"
    - Times: "2025-10-15 14:00" (interpreted as local timezone)

Timezone Behavior:
  - All times are displayed in local timezone
  - All queries use local timezone (e.g., "4pm" means local 4pm, not UTC)
  - Times are automatically converted to UTC for API queries

Examples:
  o365 calendar list --today                          # Today's events
  o365 calendar list --week                           # This week's events
  o365 calendar list --after "3 days ago"             # Events from last 3 days
  o365 calendar list --after "2025-10-01" --before "2025-10-15"  # Date range
  o365 calendar list --user quinn --today             # View Quinn's calendar
  o365 calendar list --user roman --week              # View Roman's calendar
"""
    )

    # Date range options (mutually exclusive convenience shortcuts)
    date_group = list_parser.add_mutually_exclusive_group()
    date_group.add_argument('--today', action='store_true',
                           help='Show today\'s events')
    date_group.add_argument('--week', action='store_true',
                           help='Show this week\'s events (Mon-Sun)')
    date_group.add_argument('--month', action='store_true',
                           help='Show this month\'s events')

    # Manual date range
    list_parser.add_argument('--after', type=str, metavar='EXPR',
                            help='Show events after this time (git-style: "2 days ago", "1 week", "2025-01-15")')
    list_parser.add_argument('--before', type=str, metavar='EXPR',
                            help='Show events before this time (git-style format)')

    # User filter
    list_parser.add_argument('--user', type=str, metavar='USER',
                            help='View another user\'s calendar (name, email, or user ID)')

    # Future filter placeholders (for easy extension)
    # list_parser.add_argument('--title', type=str, help='Filter by title regex')
    # list_parser.add_argument('--attendee', type=str, help='Filter by attendee')
    # list_parser.add_argument('--location', type=str, help='Filter by location regex')

    list_parser.set_defaults(func=cmd_list)


def handle_command(args):
    """Route to appropriate calendar subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No calendar subcommand specified", file=sys.stderr)
        sys.exit(1)
