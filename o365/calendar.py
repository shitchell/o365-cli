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


def parse_duration(duration_str):
    """Parse duration string like '1h', '30m', '1h30m' into timedelta

    Supports formats like:
    - 30m, 1h, 2h30m
    - 1.5h (decimal hours)
    - Combinations: 1h 30m
    """
    if not duration_str:
        return None

    duration_str = duration_str.lower().strip()
    total_seconds = 0

    # Try simple decimal hours first (e.g., "1.5h")
    decimal_match = re.match(r'^([\d.]+)h?$', duration_str)
    if decimal_match and '.' in decimal_match.group(1):
        hours = float(decimal_match.group(1))
        return timedelta(hours=hours)

    # Parse hour and minute components
    hour_match = re.search(r'(\d+)\s*h', duration_str)
    min_match = re.search(r'(\d+)\s*m', duration_str)

    if hour_match:
        total_seconds += int(hour_match.group(1)) * 3600
    if min_match:
        total_seconds += int(min_match.group(1)) * 60

    if total_seconds == 0:
        raise ValueError(f"Invalid duration format: '{duration_str}'. Use formats like '1h', '30m', '1h30m'")

    return timedelta(seconds=total_seconds)


def create_event(access_token, title, start_time, duration, required_attendees=None,
                 optional_attendees=None, description=None, location=None, online_meeting=False):
    """Create a calendar event via Microsoft Graph API

    Args:
        access_token: OAuth2 access token
        title: Event subject/title
        start_time: datetime object for event start (timezone-aware)
        duration: timedelta object for event duration
        required_attendees: List of email addresses (required attendees)
        optional_attendees: List of email addresses (optional attendees)
        description: Event body/description
        location: Event location string
        online_meeting: If True, create as Teams online meeting

    Returns:
        Created event object from Graph API
    """
    # Calculate end time
    end_time = start_time + duration

    # Convert to UTC for Graph API
    start_utc = start_time.astimezone(timezone.utc)
    end_utc = end_time.astimezone(timezone.utc)

    # Build event payload
    event = {
        'subject': title,
        'start': {
            'dateTime': start_utc.strftime('%Y-%m-%dT%H:%M:%S'),
            'timeZone': 'UTC'
        },
        'end': {
            'dateTime': end_utc.strftime('%Y-%m-%dT%H:%M:%S'),
            'timeZone': 'UTC'
        }
    }

    # Add attendees
    attendees = []
    if required_attendees:
        for email in required_attendees:
            attendees.append({
                'emailAddress': {'address': email},
                'type': 'required'
            })
    if optional_attendees:
        for email in optional_attendees:
            attendees.append({
                'emailAddress': {'address': email},
                'type': 'optional'
            })

    if attendees:
        event['attendees'] = attendees

    # Add description
    if description:
        event['body'] = {
            'contentType': 'text',
            'content': description
        }

    # Add location
    if location:
        event['location'] = {
            'displayName': location
        }

    # Add online meeting
    if online_meeting:
        event['isOnlineMeeting'] = True
        event['onlineMeetingProvider'] = 'teamsForBusiness'

    # Create the event
    url = f"{GRAPH_API_BASE}/me/events"
    result = make_graph_request(url, access_token, method='POST', data=event)

    return result


def delete_event(access_token, event_id):
    """Delete a calendar event by ID

    Args:
        access_token: OAuth2 access token
        event_id: Event ID to delete

    Returns:
        True if successful, False otherwise
    """
    url = f"{GRAPH_API_BASE}/me/events/{event_id}"
    # DELETE returns empty body on success, {} on success, None on error
    result = make_graph_request(url, access_token, method='DELETE')
    return result is not None


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


def cmd_create(args):
    """Handle 'o365 calendar create' command"""
    access_token = get_access_token()

    # Parse the start time
    try:
        start_time = parse_since_expression(args.when)
    except ValueError as e:
        print(f"Error in --when: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse duration (default to 1 hour)
    try:
        duration = parse_duration(args.duration or "1h")
    except ValueError as e:
        print(f"Error in --duration: {e}", file=sys.stderr)
        sys.exit(1)

    # Resolve required attendees
    required_attendees = []
    if args.required:
        for user_query in args.required:
            email = resolve_user(user_query, access_token)
            required_attendees.append(email)

    # Resolve optional attendees
    optional_attendees = []
    if args.optional:
        for user_query in args.optional:
            email = resolve_user(user_query, access_token)
            optional_attendees.append(email)

    # Create the event
    print(f"Creating event '{args.title}'...")

    event = create_event(
        access_token,
        title=args.title,
        start_time=start_time,
        duration=duration,
        required_attendees=required_attendees if required_attendees else None,
        optional_attendees=optional_attendees if optional_attendees else None,
        description=args.description,
        location=args.location,
        online_meeting=args.online_meeting
    )

    if not event:
        print("Error: Failed to create event", file=sys.stderr)
        sys.exit(1)

    # Display confirmation
    end_time = start_time + duration
    print(f"\nEvent created successfully!")
    print(f"  Title: {args.title}")
    print(f"  When: {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%H:%M')} (local time)")
    print(f"  Duration: {args.duration or '1h'}")

    if required_attendees:
        print(f"  Required attendees: {', '.join(required_attendees)}")
    if optional_attendees:
        print(f"  Optional attendees: {', '.join(optional_attendees)}")
    if args.location:
        print(f"  Location: {args.location}")
    if args.online_meeting:
        print(f"  Teams meeting: Yes")
        if event.get('onlineMeeting', {}).get('joinUrl'):
            print(f"  Join URL: {event['onlineMeeting']['joinUrl']}")
    if args.description:
        print(f"  Description: {args.description}")

    print(f"\nEvent ID: {event.get('id')}")


def cmd_delete(args):
    """Handle 'o365 calendar delete' command"""
    access_token = get_access_token()

    for event_id in args.event_ids:
        print(f"Deleting event {event_id}...")

        success = delete_event(access_token, event_id)

        if success:
            print(f"  Event deleted successfully")
        else:
            print(f"  Error: Failed to delete event", file=sys.stderr)
            sys.exit(1)


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
  o365 calendar list --user john --today              # View John's calendar
  o365 calendar list --user john --week               # View John's calendar
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

    # o365 calendar create
    create_parser = subparsers.add_parser(
        'create',
        help='Create a calendar event',
        description='Create a new calendar event in Office365.',
        epilog="""
Time Format:
  All time expressions support git-style formats:
    - Relative: "2 hours", "tomorrow at 3pm", "next monday at 10am"
    - Absolute: "2025-10-15 14:00", "December 20, 2024 at 9am"
    - Times without dates default to today

Duration Format:
  Supports flexible duration formats:
    - Hours: "1h", "2h", "1.5h"
    - Minutes: "30m", "45m"
    - Combined: "1h30m", "2h 15m"

Examples:
  # Simple event
  o365 calendar create -t "Team Meeting" -w "tomorrow at 2pm" -d 1h

  # With attendees
  o365 calendar create -t "Sprint Planning" -w "next monday at 10am" -d 2h \\
    -r john -r jane -o smith

  # With location and description
  o365 calendar create -t "Client Review" -w "2025-02-20 14:00" -d 1h30m \\
    -l "Conference Room A" -D "Q1 review with client"

  # Teams online meeting
  o365 calendar create -t "Standup" -w "tomorrow at 9am" -d 30m \\
    -r team@example.com --online-meeting
"""
    )

    # Required arguments
    create_parser.add_argument('-t', '--title', type=str, required=True,
                              help='Event title/subject (required)')
    create_parser.add_argument('-w', '--when', type=str, required=True,
                              help='When the event occurs (required, git-style format)')

    # Optional arguments
    create_parser.add_argument('-d', '--duration', type=str, metavar='DURATION',
                              help='Event duration (default: 1h, format: "1h", "30m", "1h30m")')
    create_parser.add_argument('-r', '--required', type=str, action='append', metavar='USER',
                              help='Required attendee (name, email, or user ID, can be used multiple times)')
    create_parser.add_argument('-o', '--optional', type=str, action='append', metavar='USER',
                              help='Optional attendee (name, email, or user ID, can be used multiple times)')
    create_parser.add_argument('-D', '--description', type=str,
                              help='Event description/body')
    create_parser.add_argument('-l', '--location', type=str,
                              help='Event location')
    create_parser.add_argument('--online-meeting', action='store_true', default=True,
                              help='Create as Teams online meeting (default: True)')
    create_parser.add_argument('--no-online-meeting', dest='online_meeting', action='store_false',
                              help='Create as regular in-person event (disables Teams meeting)')

    create_parser.set_defaults(func=cmd_create)

    # o365 calendar delete
    delete_parser = subparsers.add_parser(
        'delete',
        help='Delete a calendar event',
        description='Delete one or more calendar events by ID.',
        epilog="""
Examples:
  # Delete single event
  o365 calendar delete AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3ZmRhYmQwNTI4MA...

  # Delete multiple events
  o365 calendar delete EVENT_ID1 EVENT_ID2 EVENT_ID3
"""
    )

    delete_parser.add_argument('event_ids', nargs='+', metavar='EVENT_ID',
                              help='One or more event IDs to delete')

    delete_parser.set_defaults(func=cmd_delete)


def handle_command(args):
    """Route to appropriate calendar subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No calendar subcommand specified", file=sys.stderr)
        sys.exit(1)
