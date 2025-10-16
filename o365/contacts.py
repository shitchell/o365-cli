"""
Contacts management commands for Office365

Search and list personal contacts and calendar owners.
"""

import sys
from .common import get_access_token, make_graph_request, GRAPH_API_BASE


def get_contacts(access_token):
    """Get all personal contacts"""
    contacts = []
    url = f"{GRAPH_API_BASE}/me/contacts?$top=999"

    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        for contact in result.get('value', []):
            email_addresses = contact.get('emailAddresses', [])
            email = email_addresses[0].get('address') if email_addresses else None

            if email:  # Only include contacts with email
                contacts.append({
                    'name': contact.get('displayName', ''),
                    'email': email.lower(),
                    'id': contact.get('id'),
                    'source': 'contact'
                })

        # Check for pagination
        url = result.get('@odata.nextLink')

    return contacts


def get_calendar_owners(access_token):
    """Get owners of shared calendars"""
    owners = []
    url = f"{GRAPH_API_BASE}/me/calendars"

    result = make_graph_request(url, access_token)
    if not result:
        return owners

    for calendar in result.get('value', []):
        owner = calendar.get('owner', {})
        owner_name = owner.get('name', '')
        owner_email = owner.get('address', '')

        if owner_email and owner_email.lower() not in [o['email'] for o in owners]:
            owners.append({
                'name': owner_name,
                'email': owner_email.lower(),
                'id': None,  # Calendar owners don't have contact IDs
                'source': 'calendar'
            })

    return owners


def get_unique_users(access_token):
    """Get all unique users (contacts + calendar owners)"""
    all_users = get_contacts(access_token) + get_calendar_owners(access_token)

    # Deduplicate by email
    seen_emails = set()
    unique_users = []
    for user in all_users:
        if user['email'] not in seen_emails:
            seen_emails.add(user['email'])
            unique_users.append(user)

    return unique_users


def search_users(query, access_token):
    """Search for users by name or email"""
    unique_users = get_unique_users(access_token)
    query_lower = query.lower()

    # Check if query is an email address
    if '@' in query and '.' in query:
        matches = [u for u in unique_users if u['email'] == query_lower]
        return matches

    # Search by name (case-insensitive, partial match)
    matches = []
    for user in unique_users:
        name_lower = user['name'].lower()
        # Check if query matches any part of the name
        if query_lower in name_lower or any(query_lower in part for part in name_lower.split()):
            matches.append(user)

    return matches


# Command handlers

def cmd_list(args):
    """Handle 'o365 contacts list' command"""
    access_token = get_access_token()
    unique_users = get_unique_users(access_token)

    # Sort by name
    unique_users.sort(key=lambda x: x['name'].lower())

    print(f"\n{'Name':<30} {'Email':<40} {'Source':<10}")
    print("=" * 80)
    for user in unique_users:
        print(f"{user['name'][:28]:<30} {user['email'][:38]:<40} {user['source']:<10}")
    print(f"\nTotal: {len(unique_users)} users\n")


def cmd_search(args):
    """Handle 'o365 contacts search' command"""
    access_token = get_access_token()
    matches = search_users(args.query, access_token)

    if not matches:
        print(f"No users found matching '{args.query}'", file=sys.stderr)
        sys.exit(1)

    if args.resolve:
        # Resolve mode - error if ambiguous
        if len(matches) > 1:
            print(f"Error: Ambiguous query '{args.query}' matches {len(matches)} users:", file=sys.stderr)
            for match in matches:
                print(f"  - {match['name']} ({match['email']})", file=sys.stderr)
            sys.exit(1)

        # Output just the email for scripting
        print(matches[0]['email'])
    else:
        # Interactive mode - show all matches
        if len(matches) == 1:
            user = matches[0]
            print(f"\n{user['name']}")
            print(f"Email: {user['email']}")
            print(f"Source: {user['source']}")
            print()
        else:
            print(f"\nFound {len(matches)} users matching '{args.query}':\n")
            print(f"{'Name':<30} {'Email':<40} {'Source':<10}")
            print("=" * 80)
            for user in matches:
                print(f"{user['name'][:28]:<30} {user['email'][:38]:<40} {user['source']:<10}")
            print()


# Setup and routing

def setup_parser(subparsers):
    """Setup argparse subcommands for contacts"""

    # o365 contacts list
    list_parser = subparsers.add_parser(
        'list',
        help='List all contacts and calendar owners',
        description='List all contacts and calendar owners.'
    )
    list_parser.set_defaults(func=cmd_list)

    # o365 contacts search
    search_parser = subparsers.add_parser(
        'search',
        help='Search for contacts by name or email',
        description='Search for contacts by name or email.',
        epilog="""
Examples:
  o365 contacts search john                   # Search for "john"
  o365 contacts search john.doe@example.com   # Search by email
  o365 contacts search john --resolve         # Get email only (script-friendly)

Notes:
  - Searches both personal contacts and shared calendar owners
  - Detects ambiguous matches (e.g., "john" matches multiple users)
  - Use --resolve in scripts to ensure single result
"""
    )
    search_parser.add_argument('query', help='Name or email to search for')
    search_parser.add_argument('--resolve', action='store_true',
                              help='Resolve to single user (error if ambiguous), output email only')
    search_parser.set_defaults(func=cmd_search)


def handle_command(args):
    """Route to appropriate contacts subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No contacts subcommand specified", file=sys.stderr)
        sys.exit(1)
