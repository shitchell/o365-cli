"""
Tests for o365 contacts commands
"""

import pytest
from unittest.mock import patch, MagicMock
from o365 import contacts


class TestContactsList:
    """Tests for 'o365 contacts list' command"""

    def test_list_contacts(self, mock_access_token, mock_graph_api, sample_contact, capsys):
        """Test listing all contacts"""
        mock_graph_api.return_value = {'value': [sample_contact]}

        args = MagicMock()

        with patch('o365.contacts.get_contacts') as mock_get:
            mock_get.return_value = [{
                'name': 'John Doe',
                'email': 'john.doe@example.com',
                'source': 'contact'
            }]

            with patch('o365.contacts.get_calendar_owners') as mock_owners:
                mock_owners.return_value = []
                contacts.cmd_list(args)

        captured = capsys.readouterr()
        assert "John Doe" in captured.out
        assert "john.doe@example.com" in captured.out

    def test_list_empty_contacts(self, mock_access_token, capsys):
        """Test listing when no contacts exist"""
        args = MagicMock()

        with patch('o365.contacts.get_unique_users') as mock_get:
            mock_get.return_value = []
            contacts.cmd_list(args)

        captured = capsys.readouterr()
        assert "Total: 0 users" in captured.out


class TestContactsSearch:
    """Tests for 'o365 contacts search' command"""

    def test_search_by_name(self, mock_access_token, capsys):
        """Test searching contacts by name"""
        args = MagicMock()
        args.query = 'john'
        args.resolve = False

        with patch('o365.contacts.search_users') as mock_search:
            mock_search.return_value = [{
                'name': 'John Doe',
                'email': 'john.doe@example.com',
                'source': 'contact'
            }]

            contacts.cmd_search(args)

        captured = capsys.readouterr()
        assert "John Doe" in captured.out
        assert "john.doe@example.com" in captured.out

    def test_search_by_email(self, mock_access_token, capsys):
        """Test searching contacts by email address"""
        args = MagicMock()
        args.query = 'john.doe@example.com'
        args.resolve = False

        with patch('o365.contacts.search_users') as mock_search:
            mock_search.return_value = [{
                'name': 'John Doe',
                'email': 'john.doe@example.com',
                'source': 'contact'
            }]

            contacts.cmd_search(args)

        captured = capsys.readouterr()
        assert "John Doe" in captured.out

    def test_search_no_results(self, mock_access_token):
        """Test searching when no matches found"""
        args = MagicMock()
        args.query = 'nonexistent'
        args.resolve = False

        with patch('o365.contacts.search_users') as mock_search:
            mock_search.return_value = []

            with pytest.raises(SystemExit):
                contacts.cmd_search(args)

    def test_search_resolve_single_match(self, mock_access_token, capsys):
        """Test search with --resolve flag (single match)"""
        args = MagicMock()
        args.query = 'john'
        args.resolve = True

        with patch('o365.contacts.search_users') as mock_search:
            mock_search.return_value = [{
                'name': 'John Doe',
                'email': 'john.doe@example.com',
                'source': 'contact'
            }]

            contacts.cmd_search(args)

        captured = capsys.readouterr()
        # In resolve mode, only email is printed
        assert captured.out.strip() == 'john.doe@example.com'

    def test_search_resolve_multiple_matches(self, mock_access_token):
        """Test search with --resolve flag (ambiguous, multiple matches)"""
        args = MagicMock()
        args.query = 'john'
        args.resolve = True

        with patch('o365.contacts.search_users') as mock_search:
            mock_search.return_value = [
                {'name': 'John Doe', 'email': 'john.doe@example.com', 'source': 'contact'},
                {'name': 'John Smith', 'email': 'john.smith@example.com', 'source': 'contact'}
            ]

            with pytest.raises(SystemExit):
                contacts.cmd_search(args)

    def test_search_multiple_results_no_resolve(self, mock_access_token, capsys):
        """Test search showing multiple results without resolve"""
        args = MagicMock()
        args.query = 'john'
        args.resolve = False

        with patch('o365.contacts.search_users') as mock_search:
            mock_search.return_value = [
                {'name': 'John Doe', 'email': 'john.doe@example.com', 'source': 'contact'},
                {'name': 'John Smith', 'email': 'john.smith@example.com', 'source': 'contact'}
            ]

            contacts.cmd_search(args)

        captured = capsys.readouterr()
        assert "Found 2 users" in captured.out
        assert "John Doe" in captured.out
        assert "John Smith" in captured.out


class TestGetContacts:
    """Tests for get_contacts helper function"""

    def test_get_contacts_pagination(self, mock_access_token):
        """Test that get_contacts handles pagination"""
        page1 = {
            'value': [
                {'displayName': 'Contact 1', 'emailAddresses': [{'address': 'c1@example.com'}], 'id': '1'}
            ],
            '@odata.nextLink': 'https://graph.microsoft.com/v1.0/me/contacts?$skip=1'
        }
        page2 = {
            'value': [
                {'displayName': 'Contact 2', 'emailAddresses': [{'address': 'c2@example.com'}], 'id': '2'}
            ]
        }

        with patch('o365.contacts.make_graph_request') as mock_request:
            mock_request.side_effect = [page1, page2]

            result = contacts.get_contacts('test-token')

        assert len(result) == 2
        assert result[0]['email'] == 'c1@example.com'
        assert result[1]['email'] == 'c2@example.com'

    def test_get_contacts_filters_no_email(self, mock_access_token):
        """Test that contacts without email are filtered out"""
        with patch('o365.contacts.make_graph_request') as mock_request:
            mock_request.return_value = {
                'value': [
                    {'displayName': 'No Email Contact', 'emailAddresses': [], 'id': '1'},
                    {'displayName': 'With Email', 'emailAddresses': [{'address': 'has@example.com'}], 'id': '2'}
                ]
            }

            result = contacts.get_contacts('test-token')

        assert len(result) == 1
        assert result[0]['email'] == 'has@example.com'


class TestSearchUsers:
    """Tests for search_users helper function"""

    def test_search_by_email_exact_match(self, mock_access_token):
        """Test searching by exact email match"""
        with patch('o365.contacts.get_unique_users') as mock_get:
            mock_get.return_value = [
                {'name': 'John Doe', 'email': 'john.doe@example.com', 'source': 'contact'},
                {'name': 'Jane Smith', 'email': 'jane.smith@example.com', 'source': 'contact'}
            ]

            result = contacts.search_users('john.doe@example.com', 'test-token')

        assert len(result) == 1
        assert result[0]['email'] == 'john.doe@example.com'

    def test_search_by_name_partial_match(self, mock_access_token):
        """Test searching by partial name match"""
        with patch('o365.contacts.get_unique_users') as mock_get:
            mock_get.return_value = [
                {'name': 'John Doe', 'email': 'john.doe@example.com', 'source': 'contact'},
                {'name': 'Jane Doe', 'email': 'jane.doe@example.com', 'source': 'contact'},
                {'name': 'Bob Smith', 'email': 'bob.smith@example.com', 'source': 'contact'}
            ]

            result = contacts.search_users('doe', 'test-token')

        assert len(result) == 2
        assert all('doe' in u['name'].lower() for u in result)

    def test_search_case_insensitive(self, mock_access_token):
        """Test that search is case insensitive"""
        with patch('o365.contacts.get_unique_users') as mock_get:
            mock_get.return_value = [
                {'name': 'John Doe', 'email': 'JOHN.DOE@EXAMPLE.COM', 'source': 'contact'}
            ]

            result = contacts.search_users('JOHN.DOE@EXAMPLE.COM', 'test-token')

        assert len(result) == 1
        assert result[0]['email'] == 'john.doe@example.com'
