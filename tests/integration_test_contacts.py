"""
Integration tests for o365 contacts commands

These tests make REAL API calls to Microsoft Graph API.
They will only run if:
1. client_id and tenant are configured in ~/.config/o365/config
2. scopes.contacts is enabled in the config
3. You have authenticated with `o365 auth login`

Run with:
    pytest tests/integration_test_contacts.py -v
    pytest -m integration_contacts  # Run all contacts integration tests
    pytest -m integration             # Run ALL integration tests
"""

import pytest
from unittest.mock import MagicMock
from o365 import contacts


@pytest.mark.integration
@pytest.mark.integration_contacts
class TestContactsIntegration:
    """Integration tests for contacts commands"""

    def test_list_contacts(self, real_access_token, capsys):
        """Test listing all contacts and calendar owners"""
        args = MagicMock()

        contacts.cmd_list(args)

        captured = capsys.readouterr()
        # Should complete without error (may have 0 contacts)
        assert "Total:" in captured.out
        assert len(captured.out) > 0

    def test_search_contacts_no_results(self, real_access_token, capsys):
        """Test searching for non-existent contact"""
        args = MagicMock()
        args.query = "zzz_nonexistent_user_xyz_12345"
        args.resolve = False

        # Should exit with code 1 for no results
        with pytest.raises(SystemExit) as exc_info:
            contacts.cmd_search(args)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "No users found" in captured.err


@pytest.mark.integration
@pytest.mark.integration_contacts
class TestContactsHelperFunctions:
    """Test contacts helper functions with real API"""

    def test_get_contacts(self, real_access_token):
        """Test getting all personal contacts"""
        result = contacts.get_contacts(real_access_token)

        # Should return a list (may be empty)
        assert isinstance(result, list)

        # Each contact should have required fields
        for contact in result:
            assert 'name' in contact
            assert 'email' in contact
            assert 'source' in contact
            assert contact['source'] == 'contact'

    def test_get_calendar_owners(self, real_access_token):
        """Test getting calendar owners"""
        result = contacts.get_calendar_owners(real_access_token)

        # Should return a list (may be empty)
        assert isinstance(result, list)

        # Each owner should have required fields
        for owner in result:
            assert 'name' in owner
            assert 'email' in owner
            assert 'source' in owner
            assert owner['source'] == 'calendar'

    def test_get_unique_users(self, real_access_token):
        """Test getting all unique users (contacts + calendar owners)"""
        result = contacts.get_unique_users(real_access_token)

        # Should return a list (may be empty)
        assert isinstance(result, list)

        # Should be unique by email
        emails = [u['email'] for u in result]
        assert len(emails) == len(set(emails))

    def test_search_users_by_email(self, real_access_token):
        """Test searching by exact email (if we have any contacts)"""
        all_users = contacts.get_unique_users(real_access_token)

        if not all_users:
            pytest.skip("No contacts available for testing")

        # Use first user's email for search
        test_email = all_users[0]['email']
        result = contacts.search_users(test_email, real_access_token)

        # Should find exactly one match
        assert len(result) == 1
        assert result[0]['email'] == test_email

    def test_search_users_by_name(self, real_access_token):
        """Test searching by partial name"""
        all_users = contacts.get_unique_users(real_access_token)

        if not all_users:
            pytest.skip("No contacts available for testing")

        # Use part of first user's name for search
        test_name = all_users[0]['name']
        if not test_name:
            pytest.skip("First contact has no name")

        # Search for first part of name
        search_term = test_name.split()[0] if ' ' in test_name else test_name[:3]
        result = contacts.search_users(search_term, real_access_token)

        # Should find at least one match
        assert len(result) >= 1

        # At least one result should match our search term
        found = False
        for user in result:
            if search_term.lower() in user['name'].lower():
                found = True
                break
        assert found


@pytest.mark.integration
@pytest.mark.integration_contacts
@pytest.mark.slow
class TestContactsIntegrationSlow:
    """Slow integration tests for contacts"""

    def test_search_all_contacts_performance(self, real_access_token):
        """Test performance of searching all contacts"""
        import time

        start = time.time()
        all_users = contacts.get_unique_users(real_access_token)
        elapsed = time.time() - start

        # Should complete in reasonable time (< 10 seconds)
        assert elapsed < 10.0

        # Should return results
        assert isinstance(all_users, list)
