"""
Common utilities for Office365 CLI

Shared constants, API helpers, and utility functions used across all commands.
"""

import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

# Configuration
TOKEN_FILE = Path.home() / ".o365-tokens.json"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

# OAuth Configuration
CLIENT_ID = "79e622ea-fbd8-47c3-b02a-6b777b5cbf3c"
TENANT = "fd5a5762-9274-4086-aefb-aca071a100b3"
SCOPES = [
    "https://graph.microsoft.com/Calendars.Read",
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/Calendars.ReadWrite.Shared",
    "https://graph.microsoft.com/Contacts.Read",
    "https://graph.microsoft.com/Contacts.ReadWrite",
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/MailboxSettings.Read",
    "https://graph.microsoft.com/User.Read",
    "offline_access"
]


def load_tokens():
    """Load OAuth2 tokens from file"""
    if not TOKEN_FILE.exists():
        print("Error: OAuth2 tokens not found. Please run: o365 auth login", file=sys.stderr)
        sys.exit(1)

    with open(TOKEN_FILE) as f:
        return json.load(f)


def save_tokens(tokens):
    """Save OAuth2 tokens to file"""
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    TOKEN_FILE.chmod(0o600)


def get_access_token():
    """Get the current access token"""
    tokens = load_tokens()
    access_token = tokens.get('access_token')

    if not access_token:
        print("Error: No access token found. Please run: o365 auth login", file=sys.stderr)
        sys.exit(1)

    return access_token


def make_graph_request(url, access_token, method="GET", data=None):
    """
    Make a request to Microsoft Graph API

    Args:
        url: Full URL or endpoint (if starts with /, prepends GRAPH_API_BASE)
        access_token: OAuth2 access token
        method: HTTP method (GET, POST, PATCH, DELETE)
        data: Optional data dict for POST/PATCH requests

    Returns:
        Response data as dict, or None on error
    """
    # Handle relative endpoints
    if url.startswith('/'):
        url = GRAPH_API_BASE + url

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    request_data = json.dumps(data).encode() if data else None

    req = urllib.request.Request(url, data=request_data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Graph API Error: {e.code} - {error_body}", file=sys.stderr)
        return None


def make_oauth_request(endpoint, data):
    """
    Make a request to OAuth2 endpoint

    Args:
        endpoint: OAuth2 endpoint path (e.g., /devicecode, /token)
        data: Dict of form data

    Returns:
        Response data as dict
    """
    encoded_data = urllib.parse.urlencode(data).encode()

    req = urllib.request.Request(
        f'https://login.microsoftonline.com/{TENANT}/oauth2/v2.0{endpoint}',
        data=encoded_data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())
