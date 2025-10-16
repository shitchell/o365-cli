"""
OAuth2 authentication commands for Office365

Handles device code flow authentication, token refresh, and status checking.
"""

import json
import time
import sys
import urllib.error
from datetime import datetime, timedelta

from .common import (
    CLIENT_ID, TENANT, SCOPES, TOKEN_FILE,
    make_oauth_request, save_tokens, load_tokens
)


def device_code_flow():
    """Initiate device code flow and get tokens"""

    # Step 1: Request device code
    device_code_data = make_oauth_request('/devicecode', {
        'client_id': CLIENT_ID,
        'scope': ' '.join(SCOPES)
    })

    print("\n" + "="*70)
    print("OFFICE365 OAUTH2 AUTHENTICATION")
    print("="*70)
    print(f"\n1. Open this URL in your browser:\n   {device_code_data['verification_uri']}")
    print(f"\n2. Enter this code: {device_code_data['user_code']}")
    print("\n3. Sign in with your Office365 account")
    print(f"\nWaiting for authentication (expires in {device_code_data['expires_in']} seconds)...")
    print("="*70 + "\n")

    # Step 2: Poll for token
    interval = device_code_data['interval']
    device_code = device_code_data['device_code']
    expires_in = device_code_data['expires_in']
    start_time = time.time()

    while True:
        if time.time() - start_time > expires_in:
            print("ERROR: Authentication timed out")
            sys.exit(1)

        time.sleep(interval)

        try:
            tokens = make_oauth_request('/token', {
                'client_id': CLIENT_ID,
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                'device_code': device_code
            })

            # Save tokens
            save_tokens(tokens)

            print("\n✓ Authentication successful!")
            print(f"✓ Tokens saved to {TOKEN_FILE}")
            print(f"✓ Access token expires in {tokens.get('expires_in', 3600)} seconds\n")
            return tokens

        except urllib.error.HTTPError as e:
            error_data = json.loads(e.read())
            error_code = error_data.get('error')

            if error_code == 'authorization_pending':
                print(".", end="", flush=True)
                continue
            elif error_code == 'authorization_declined':
                print("\n\nERROR: Authentication was declined")
                sys.exit(1)
            elif error_code == 'expired_token':
                print("\n\nERROR: Device code expired")
                sys.exit(1)
            else:
                print(f"\n\nERROR: {error_code}")
                sys.exit(1)


def refresh_token():
    """Refresh existing token"""
    if not TOKEN_FILE.exists():
        print("No existing token found. Running initial authentication...")
        return device_code_flow()

    tokens = load_tokens()

    if 'refresh_token' not in tokens:
        print("No refresh token found. Running initial authentication...")
        return device_code_flow()

    try:
        new_tokens = make_oauth_request('/token', {
            'client_id': CLIENT_ID,
            'grant_type': 'refresh_token',
            'refresh_token': tokens['refresh_token'],
            'scope': ' '.join(SCOPES)
        })

        save_tokens(new_tokens)
        print(f"✓ Token refreshed successfully")
        return new_tokens

    except urllib.error.HTTPError:
        print(f"Token refresh failed. Running initial authentication...")
        return device_code_flow()


def check_status():
    """Check authentication status and token info"""
    if not TOKEN_FILE.exists():
        print("Not authenticated. Run: o365 auth login")
        sys.exit(1)

    tokens = load_tokens()

    print("\n" + "="*70)
    print("AUTHENTICATION STATUS")
    print("="*70)

    print(f"\n✓ Authenticated")
    print(f"Token file: {TOKEN_FILE}")

    # Check if we have required tokens
    has_access = 'access_token' in tokens
    has_refresh = 'refresh_token' in tokens

    print(f"Access token: {'✓' if has_access else '✗'}")
    print(f"Refresh token: {'✓' if has_refresh else '✗'}")

    # Show expiry if available (tokens usually expire in 1 hour)
    if 'expires_in' in tokens:
        # Note: This is from when token was saved, not current time
        # In production, you'd store a timestamp with the token
        print(f"\nNote: Access tokens typically expire after 1 hour")
        print(f"Run 'o365 auth refresh' to get a new access token")

    print("\n" + "="*70 + "\n")


# Command handlers

def cmd_login(args):
    """Handle 'o365 auth login' command"""
    device_code_flow()


def cmd_refresh(args):
    """Handle 'o365 auth refresh' command"""
    refresh_token()


def cmd_status(args):
    """Handle 'o365 auth status' command"""
    check_status()


# Setup and routing

def setup_parser(subparsers):
    """Setup argparse subcommands for auth"""

    # o365 auth login
    login_parser = subparsers.add_parser(
        'login',
        help='Authenticate with Office365 (device code flow)',
        description='Authenticate with Office365 using device code flow. '
                    'The token will be stored locally for future use.'
    )
    login_parser.set_defaults(func=cmd_login)

    # o365 auth refresh
    refresh_parser = subparsers.add_parser(
        'refresh',
        help='Refresh OAuth2 access token',
        description='Refresh OAuth2 access token using stored refresh token. '
                    'Useful for non-interactive scenarios (e.g., cron jobs).'
    )
    refresh_parser.set_defaults(func=cmd_refresh)

    # o365 auth status
    status_parser = subparsers.add_parser(
        'status',
        help='Show authentication status',
        description='Show authentication status and token information.'
    )
    status_parser.set_defaults(func=cmd_status)


def handle_command(args):
    """Route to appropriate auth subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No auth subcommand specified", file=sys.stderr)
        sys.exit(1)
