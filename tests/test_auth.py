"""
Tests for o365 auth commands
"""

import pytest
import json
from unittest.mock import patch, MagicMock, call
from o365 import auth


class TestAuthLogin:
    """Tests for 'o365 auth login' command"""

    def test_login_success(self, temp_config_file, temp_token_file, capsys):
        """Test successful authentication flow"""
        mock_device_code_response = {
            'device_code': 'test-device-code',
            'user_code': 'TEST123',
            'verification_uri': 'https://microsoft.com/devicelogin',
            'expires_in': 900,
            'interval': 5
        }

        mock_token_response = {
            'access_token': 'new-access-token',
            'refresh_token': 'new-refresh-token',
            'expires_in': 3600
        }

        args = MagicMock()

        with patch('o365.auth.CONFIG_FILE', temp_config_file), \
             patch('o365.auth.TOKEN_FILE', temp_token_file), \
             patch('o365.auth.make_oauth_request') as mock_oauth:

            # First call returns device code, second returns token
            mock_oauth.side_effect = [
                mock_device_code_response,
                mock_token_response
            ]

            with patch('time.sleep'):  # Skip sleep
                auth.cmd_login(args)

        captured = capsys.readouterr()
        assert "TEST123" in captured.out
        assert "https://microsoft.com/devicelogin" in captured.out

        # Verify token was saved
        with open(temp_token_file) as f:
            saved_tokens = json.load(f)
        assert saved_tokens['access_token'] == 'new-access-token'

    def test_login_timeout(self, temp_config_file, temp_token_file):
        """Test authentication timeout"""
        mock_device_code_response = {
            'device_code': 'test-device-code',
            'user_code': 'TEST123',
            'verification_uri': 'https://microsoft.com/devicelogin',
            'expires_in': 900,
            'interval': 5
        }

        args = MagicMock()

        with patch('o365.auth.CONFIG_FILE', temp_config_file), \
             patch('o365.auth.TOKEN_FILE', temp_token_file), \
             patch('o365.auth.make_oauth_request') as mock_oauth:

            # First call returns device code, subsequent calls return pending/error
            def oauth_side_effect(endpoint, data):
                if endpoint == '/devicecode':
                    return mock_device_code_response
                else:
                    # Simulate authorization_pending error
                    from urllib.error import HTTPError
                    raise HTTPError(None, 400, 'Bad Request', {}, None)

            mock_oauth.side_effect = oauth_side_effect

            with patch('time.sleep'), \
                 patch('time.time', side_effect=[0, 1000]):  # Simulate timeout
                with pytest.raises(SystemExit):
                    auth.cmd_login(args)


class TestAuthRefresh:
    """Tests for 'o365 auth refresh' command"""

    def test_refresh_success(self, temp_config_file, temp_token_file, capsys):
        """Test successful token refresh"""
        mock_token_response = {
            'access_token': 'refreshed-access-token',
            'refresh_token': 'refreshed-refresh-token',
            'expires_in': 3600
        }

        args = MagicMock()

        with patch('o365.auth.CONFIG_FILE', temp_config_file), \
             patch('o365.auth.TOKEN_FILE', temp_token_file), \
             patch('o365.auth.make_oauth_request') as mock_oauth:

            mock_oauth.return_value = mock_token_response
            auth.cmd_refresh(args)

        captured = capsys.readouterr()
        assert "refreshed successfully" in captured.out

        # Verify new token was saved
        with open(temp_token_file) as f:
            saved_tokens = json.load(f)
        assert saved_tokens['access_token'] == 'refreshed-access-token'

    def test_refresh_no_refresh_token(self, temp_config_file, temp_token_file):
        """Test refresh when no refresh token exists"""
        # Remove refresh token
        with open(temp_token_file) as f:
            tokens = json.load(f)
        del tokens['refresh_token']
        with open(temp_token_file, 'w') as f:
            json.dump(tokens, f)

        args = MagicMock()

        with patch('o365.auth.CONFIG_FILE', temp_config_file), \
             patch('o365.auth.TOKEN_FILE', temp_token_file):
            with pytest.raises(SystemExit):
                auth.cmd_refresh(args)


class TestAuthStatus:
    """Tests for 'o365 auth status' command"""

    def test_status_valid_token(self, temp_config_file, temp_token_file, capsys):
        """Test status with valid, non-expired token"""
        import time

        # Create token that's not expired
        tokens = {
            'access_token': 'valid-token',
            'refresh_token': 'refresh-token',
            'expires_in': 3600,
            '_saved_at': time.time() - 1000  # Saved 1000 seconds ago
        }
        with open(temp_token_file, 'w') as f:
            json.dump(tokens, f)

        args = MagicMock()

        with patch('o365.auth.CONFIG_FILE', temp_config_file), \
             patch('o365.auth.TOKEN_FILE', temp_token_file):
            auth.cmd_status(args)

        captured = capsys.readouterr()
        assert "authenticated" in captured.out.lower()
        assert "expires" in captured.out.lower()

    def test_status_expired_token(self, temp_config_file, temp_token_file, capsys):
        """Test status with expired token"""
        import time

        # Create expired token
        tokens = {
            'access_token': 'expired-token',
            'refresh_token': 'refresh-token',
            'expires_in': 3600,
            '_saved_at': time.time() - 4000  # Saved 4000 seconds ago (expired)
        }
        with open(temp_token_file, 'w') as f:
            json.dump(tokens, f)

        args = MagicMock()

        with patch('o365.auth.CONFIG_FILE', temp_config_file), \
             patch('o365.auth.TOKEN_FILE', temp_token_file):
            auth.cmd_status(args)

        captured = capsys.readouterr()
        assert "expired" in captured.out.lower()

    def test_status_no_token_file(self, temp_config_file, temp_config_dir):
        """Test status when no token file exists"""
        nonexistent_token = temp_config_dir / "nonexistent_tokens.json"

        args = MagicMock()

        with patch('o365.auth.CONFIG_FILE', temp_config_file), \
             patch('o365.auth.TOKEN_FILE', nonexistent_token):
            with pytest.raises(SystemExit):
                auth.cmd_status(args)
