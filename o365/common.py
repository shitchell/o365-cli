"""
Common utilities for Office365 CLI

Shared constants, API helpers, and utility functions used across all commands.
"""

import json
import sys
import os
import urllib.request
import urllib.parse
from pathlib import Path
from configparser import ConfigParser

# Graph API base URL
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

# Default configuration paths
CONFIG_DIR = Path.home() / ".config" / "o365"
CONFIG_FILE = CONFIG_DIR / "config"
DEFAULT_TOKEN_FILE = CONFIG_DIR / "tokens.json"
DEFAULT_MAIL_DIR = Path.home() / ".mail" / "office365"

# Default scopes (if not configured)
DEFAULT_SCOPES = [
    "https://graph.microsoft.com/Calendars.Read",
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/Calendars.ReadWrite.Shared",
    "https://graph.microsoft.com/Contacts.Read",
    "https://graph.microsoft.com/Contacts.ReadWrite",
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/MailboxSettings.Read",
    "https://graph.microsoft.com/Chat.Read",
    "https://graph.microsoft.com/Chat.ReadWrite",
    "https://graph.microsoft.com/ChatMessage.Send",
    "https://graph.microsoft.com/User.Read",
    "offline_access"
]


def load_config():
    """
    Load configuration from environment variables and config file.

    Priority: Environment variables > Config file > Defaults

    Environment variables:
    - O365_CLIENT_ID: Azure AD application ID
    - O365_TENANT: Azure AD tenant ID (or "common")
    - O365_SCOPES: Comma-separated list of scopes
    - O365_TOKEN_FILE: Path to token file
    - O365_MAIL_DIR: Path to local mail directory

    Config file (~/.config/o365/config):
    [auth]
    client_id = your-client-id
    tenant = your-tenant-id

    [scopes]
    # Enable/disable command groups
    mail = true
    calendar = true
    contacts = true

    # Or specify custom scopes
    # custom = Mail.Read,Contacts.Read,User.Read,offline_access

    [paths]
    token_file = ~/.config/o365/tokens.json
    mail_dir = ~/.mail/office365/

    Returns:
        dict with keys: client_id, tenant, scopes, token_file, mail_dir
    """
    config = {
        'client_id': None,
        'tenant': None,
        'scopes': DEFAULT_SCOPES.copy(),
        'token_file': DEFAULT_TOKEN_FILE,
        'mail_dir': DEFAULT_MAIL_DIR
    }

    # Load from config file if it exists
    if CONFIG_FILE.exists():
        parser = ConfigParser()
        parser.read(CONFIG_FILE)

        # Auth section
        if parser.has_option('auth', 'client_id'):
            config['client_id'] = parser.get('auth', 'client_id')
        if parser.has_option('auth', 'tenant'):
            config['tenant'] = parser.get('auth', 'tenant')

        # Scopes section
        if parser.has_section('scopes'):
            if parser.has_option('scopes', 'custom'):
                # Custom scopes specified
                custom_scopes = parser.get('scopes', 'custom')
                config['scopes'] = [s.strip() for s in custom_scopes.split(',')]
            else:
                # Build scopes from enabled command groups
                scopes = []

                if parser.getboolean('scopes', 'mail', fallback=True):
                    scopes.extend([
                        "https://graph.microsoft.com/Mail.ReadWrite",
                        "https://graph.microsoft.com/Mail.Send",
                        "https://graph.microsoft.com/MailboxSettings.Read"
                    ])

                if parser.getboolean('scopes', 'calendar', fallback=True):
                    scopes.extend([
                        "https://graph.microsoft.com/Calendars.Read",
                        "https://graph.microsoft.com/Calendars.ReadWrite",
                        "https://graph.microsoft.com/Calendars.ReadWrite.Shared"
                    ])

                if parser.getboolean('scopes', 'contacts', fallback=True):
                    scopes.extend([
                        "https://graph.microsoft.com/Contacts.Read",
                        "https://graph.microsoft.com/Contacts.ReadWrite"
                    ])

                if parser.getboolean('scopes', 'chat', fallback=True):
                    scopes.extend([
                        "https://graph.microsoft.com/Chat.Read",
                        "https://graph.microsoft.com/Chat.ReadWrite",
                        "https://graph.microsoft.com/ChatMessage.Send"
                    ])

                # Always include User.Read and offline_access
                scopes.extend([
                    "https://graph.microsoft.com/User.Read",
                    "offline_access"
                ])

                if scopes:
                    config['scopes'] = scopes

        # Paths section
        if parser.has_option('paths', 'token_file'):
            config['token_file'] = Path(parser.get('paths', 'token_file')).expanduser()
        if parser.has_option('paths', 'mail_dir'):
            config['mail_dir'] = Path(parser.get('paths', 'mail_dir')).expanduser()

    # Override with environment variables
    if os.environ.get('O365_CLIENT_ID'):
        config['client_id'] = os.environ['O365_CLIENT_ID']
    if os.environ.get('O365_TENANT'):
        config['tenant'] = os.environ['O365_TENANT']
    if os.environ.get('O365_SCOPES'):
        config['scopes'] = [s.strip() for s in os.environ['O365_SCOPES'].split(',')]
    if os.environ.get('O365_TOKEN_FILE'):
        config['token_file'] = Path(os.environ['O365_TOKEN_FILE']).expanduser()
    if os.environ.get('O365_MAIL_DIR'):
        config['mail_dir'] = Path(os.environ['O365_MAIL_DIR']).expanduser()

    # Validate required fields
    if not config['client_id']:
        print("Error: OAuth client_id not configured.", file=sys.stderr)
        print("Please set O365_CLIENT_ID environment variable or add to ~/.config/o365/config:", file=sys.stderr)
        print("  [auth]", file=sys.stderr)
        print("  client_id = your-azure-ad-app-id", file=sys.stderr)
        sys.exit(1)

    if not config['tenant']:
        print("Error: OAuth tenant not configured.", file=sys.stderr)
        print("Please set O365_TENANT environment variable or add to ~/.config/o365/config:", file=sys.stderr)
        print("  [auth]", file=sys.stderr)
        print("  tenant = your-tenant-id", file=sys.stderr)
        print("  # Or use: tenant = common", file=sys.stderr)
        sys.exit(1)

    return config


# Load configuration once at module import
_CONFIG = load_config()
CLIENT_ID = _CONFIG['client_id']
TENANT = _CONFIG['tenant']
SCOPES = _CONFIG['scopes']
TOKEN_FILE = _CONFIG['token_file']
MAIL_DIR = _CONFIG['mail_dir']


def load_tokens():
    """Load OAuth2 tokens from file"""
    if not TOKEN_FILE.exists():
        print("Error: OAuth2 tokens not found. Please run: o365 auth login", file=sys.stderr)
        sys.exit(1)

    with open(TOKEN_FILE) as f:
        return json.load(f)


def save_tokens(tokens):
    """Save OAuth2 tokens to file with timestamp"""
    # Create directory if it doesn't exist
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Add timestamp for expiry tracking
    from time import time
    tokens['_saved_at'] = time()

    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    TOKEN_FILE.chmod(0o600)


def get_access_token():
    """Get the current access token, automatically refreshing if expired"""
    tokens = load_tokens()

    # Check if token is expired or close to expiring (within 5 minutes)
    if '_saved_at' in tokens and 'expires_in' in tokens:
        from time import time
        saved_at = tokens['_saved_at']
        expires_in = tokens['expires_in']
        time_elapsed = time() - saved_at
        time_remaining = expires_in - time_elapsed

        # If token expires in less than 5 minutes, refresh it
        if time_remaining < 300:  # 5 minutes buffer
            if tokens.get('refresh_token'):
                try:
                    # Attempt to refresh
                    new_tokens = make_oauth_request('/token', {
                        'client_id': CLIENT_ID,
                        'grant_type': 'refresh_token',
                        'refresh_token': tokens['refresh_token'],
                        'scope': ' '.join(SCOPES)
                    })
                    save_tokens(new_tokens)
                    tokens = new_tokens
                except Exception:
                    # If refresh fails, continue with existing token
                    # (it might still work, or command will fail with proper error)
                    pass

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
            body = response.read()
            # DELETE requests typically return empty responses
            if not body:
                return {}
            return json.loads(body)
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
