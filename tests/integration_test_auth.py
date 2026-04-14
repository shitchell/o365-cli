"""
Integration tests for o365 auth commands

These tests make REAL OAuth calls to Microsoft Identity Platform.
They will only run if:
1. client_id and tenant are configured in ~/.config/o365/config
2. You have authenticated with `o365 auth login`

Run with:
    pytest tests/integration_test_auth.py -v
    pytest -m integration  # Run ALL integration tests

Note: Most auth tests are difficult to automate as they require
interactive device code flow. These tests verify status/token handling.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import json
import time
from o365 import auth


@pytest.mark.integration
class TestAuthIntegration:
    """Integration tests for auth commands"""

    def test_status_with_valid_token(self, real_access_token, capsys):
        """Test auth status with valid token"""
        args = MagicMock()

        auth.cmd_status(args)

        captured = capsys.readouterr()
        # Should show authenticated status
        assert "authenticated" in captured.out.lower() or "valid" in captured.out.lower()

    def test_token_file_exists(self, real_access_token):
        """Test that token file exists and is readable"""
        from o365.common import TOKEN_FILE

        assert TOKEN_FILE.exists()

        # Should be able to load tokens
        with open(TOKEN_FILE) as f:
            tokens = json.load(f)

        assert 'access_token' in tokens
        assert len(tokens['access_token']) > 0

    def test_load_tokens(self, real_access_token):
        """Test loading tokens from file"""
        from o365.common import load_tokens

        tokens = load_tokens()

        assert 'access_token' in tokens
        assert isinstance(tokens['access_token'], str)
        assert len(tokens['access_token']) > 0

    def test_get_access_token(self, real_access_token):
        """Test getting access token (with auto-refresh if needed)"""
        from o365.common import get_access_token

        token = get_access_token()

        assert isinstance(token, str)
        assert len(token) > 0


@pytest.mark.integration
@pytest.mark.slow
class TestAuthIntegrationSlow:
    """Slow integration tests for auth (token refresh)"""

    def test_token_expiry_check(self, real_access_token):
        """Test token expiry checking logic"""
        from o365.common import load_tokens

        tokens = load_tokens()

        # Check expiry fields exist
        if '_saved_at' in tokens and 'expires_in' in tokens:
            saved_at = tokens['_saved_at']
            expires_in = tokens['expires_in']
            time_elapsed = time.time() - saved_at
            time_remaining = expires_in - time_elapsed

            # Token should not be expired (or test would fail earlier)
            assert time_remaining > 0, "Token has expired"
        else:
            pytest.skip("Token doesn't have expiry metadata")

    def test_refresh_token_if_near_expiry(self, real_access_token):
        """Test automatic token refresh when near expiry"""
        from o365.common import load_tokens, TOKEN_FILE

        # Load current tokens
        original_tokens = load_tokens()

        # Check if refresh token exists
        if 'refresh_token' not in original_tokens:
            pytest.skip("No refresh token available")

        # Simulate near-expiry by modifying saved timestamp
        # (Make it look like token was saved a long time ago)
        test_tokens = original_tokens.copy()
        test_tokens['_saved_at'] = time.time() - (test_tokens['expires_in'] - 100)  # 100 seconds from expiry

        # Temporarily save modified tokens
        TOKEN_FILE.write_text(json.dumps(test_tokens, indent=2))

        try:
            # This should trigger auto-refresh
            from o365.common import get_access_token
            token = get_access_token()

            # Should still get a valid token
            assert isinstance(token, str)
            assert len(token) > 0

            # Load tokens again - should be refreshed
            new_tokens = load_tokens()

            # Saved timestamp should be updated
            assert new_tokens['_saved_at'] > test_tokens['_saved_at']

        finally:
            # Restore original tokens
            TOKEN_FILE.write_text(json.dumps(original_tokens, indent=2))


# Note: login and refresh tests are excluded as they require interactive auth
# Manual testing recommended for full authentication flow
