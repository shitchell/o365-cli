"""
Common utilities for Office365 CLI

Shared constants, API helpers, and utility functions used across all commands.
"""

import argparse
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
    "https://graph.microsoft.com/Files.Read",
    "https://graph.microsoft.com/Files.ReadWrite",
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

                # Optional .All scope (requires admin consent). Unlocks
                # server-side chat search via POST /search/query; without it
                # `chat search` falls back to slow local enumeration.
                if parser.getboolean('scopes', 'chat.all', fallback=False):
                    scopes.append(
                        "https://graph.microsoft.com/ChannelMessage.Read.All"
                    )

                # Files scopes: base scopes if files=true OR files.all=true
                files_enabled = parser.getboolean('scopes', 'files', fallback=True)
                files_all_enabled = parser.getboolean('scopes', 'files.all', fallback=False)

                if files_enabled or files_all_enabled:
                    scopes.extend([
                        "https://graph.microsoft.com/Files.Read",
                        "https://graph.microsoft.com/Files.ReadWrite"
                    ])

                    # Optional .All scopes (may require admin consent)
                    if files_all_enabled:
                        scopes.extend([
                            "https://graph.microsoft.com/Files.Read.All",
                            "https://graph.microsoft.com/Files.ReadWrite.All"
                        ])

                # Sites scopes: only if sites.all=true
                if parser.getboolean('scopes', 'sites.all', fallback=False):
                    scopes.extend([
                        "https://graph.microsoft.com/Sites.Read.All",
                        "https://graph.microsoft.com/Sites.ReadWrite.All"
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


def get_access_token(refresh_if_expires_within=300, force_refresh=False):
    """Return a valid access token, refreshing transparently when needed.

    The Graph access token is valid for ~1 hour. The CLI itself calls this
    once per invocation, so most users never see token expiry. Long-running
    callers that hold a token value (rather than re-calling this) will hit
    401 InvalidAuthenticationToken after the token expires — for those,
    re-call get_access_token() periodically (cheap when the token is still
    fresh) instead of caching the string.

    Args:
        refresh_if_expires_within: Refresh if the token expires within this
            many seconds. Default 300 (5 min) matches the CLI's existing
            behavior. Pass a larger value (e.g. 1800) from long-running
            scripts to refresh proactively.
        force_refresh: If True, refresh unconditionally even if the current
            token is still valid. Useful after a 401 to confirm the cause
            isn't a stale local token.

    Returns:
        str: A valid Graph access token.
    """
    tokens = load_tokens()

    needs_refresh = force_refresh
    if not needs_refresh and '_saved_at' in tokens and 'expires_in' in tokens:
        from time import time
        time_remaining = tokens['expires_in'] - (time() - tokens['_saved_at'])
        if time_remaining < refresh_if_expires_within:
            needs_refresh = True

    if needs_refresh and tokens.get('refresh_token'):
        try:
            new_tokens = make_oauth_request('/token', {
                'client_id': CLIENT_ID,
                'grant_type': 'refresh_token',
                'refresh_token': tokens['refresh_token'],
                'scope': ' '.join(SCOPES)
            })
            save_tokens(new_tokens)
            tokens = new_tokens
        except Exception:
            # Continue with existing token — it may still work, and if not
            # the caller will see the Graph error directly.
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

        # Special handling for authentication errors
        if e.code == 401:
            print(f"\nError: Authentication failed (401 Unauthorized)", file=sys.stderr)
            print(f"Your access token may have expired or is invalid.", file=sys.stderr)
            print(f"\nPlease re-authenticate with: o365 auth login\n", file=sys.stderr)
        else:
            print(f"Graph API Error: {e.code} - {error_body}", file=sys.stderr)

        return None


def global_parent_parser():
    """Return a fresh parent parser carrying flags every leaf command should expose.

    Subparsers don't propagate parents to their sub-subparsers, so each leaf
    `add_parser(...)` call needs `parents=[global_parent_parser()]` rather than
    relying on inheritance.

    Currently exposes:
      --json   Emit structured JSON instead of formatted text.
    """
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument(
        '--json', dest='json_mode', action='store_true',
        help='Emit structured JSON to stdout instead of formatted text',
    )
    return p


def is_json_mode(args):
    """True if --json was supplied at any parser level."""
    return bool(getattr(args, 'json_mode', False))


def emit_json(data):
    """Serialize data as JSON to stdout (UTF-8, no ASCII escaping, str() fallback)."""
    print(json.dumps(data, ensure_ascii=False, default=str, indent=2))


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
