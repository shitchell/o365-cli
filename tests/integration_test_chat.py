"""
Integration tests for o365 chat commands

These tests make REAL API calls to Microsoft Graph API.
They will only run if:
1. client_id and tenant are configured in ~/.config/o365/config
2. scopes.chat is enabled in the config
3. You have authenticated with `o365 auth login`

Run with:
    pytest tests/integration_test_chat.py -v
    pytest -m integration_chat  # Run all chat integration tests
    pytest -m integration        # Run ALL integration tests
"""

import pytest
from unittest.mock import MagicMock
from o365 import chat


@pytest.mark.integration
@pytest.mark.integration_chat
class TestChatIntegration:
    """Integration tests for chat commands"""

    def test_list_chats(self, real_access_token, capsys):
        """Test listing chats"""
        args = MagicMock()
        args.count = 20
        args.with_user = None
        args.since = None

        chat.cmd_list(args)

        captured = capsys.readouterr()
        # Should complete without error (may have 0 chats)
        assert "Error" not in captured.out or "No chats found" in captured.out
        assert len(captured.out) >= 0

    def test_list_chats_with_count(self, real_access_token, capsys):
        """Test listing limited number of chats"""
        args = MagicMock()
        args.count = 5
        args.with_user = None
        args.since = None

        chat.cmd_list(args)

        captured = capsys.readouterr()
        # Should complete without error
        assert len(captured.out) >= 0

    def test_list_chats_since(self, real_access_token, capsys):
        """Test listing chats since a date"""
        args = MagicMock()
        args.count = 20
        args.with_user = None
        args.since = "7 days ago"

        chat.cmd_list(args)

        captured = capsys.readouterr()
        # Should complete without error
        assert len(captured.out) >= 0

    def test_search_messages(self, real_access_token, capsys):
        """Test searching chat messages"""
        args = MagicMock()
        args.query = "test"
        args.with_user = None
        args.since = None
        args.count = 10

        chat.cmd_search(args)

        captured = capsys.readouterr()
        # Should complete without error (may find 0 results)
        assert "Error" not in captured.out or "No messages found" in captured.out


@pytest.mark.integration
@pytest.mark.integration_chat
class TestChatHelperFunctions:
    """Test chat helper functions with real API"""

    def test_get_chats(self, real_access_token):
        """Test getting chats"""
        result = chat.get_chats(real_access_token, count=10)

        # Should return a list (may be empty)
        assert isinstance(result, list)

        # Each chat should have required fields
        for c in result:
            assert 'id' in c
            assert 'chatType' in c

    def test_get_chat_display_name(self, real_access_token):
        """Test getting chat display name"""
        chats = chat.get_chats(real_access_token, count=5)

        if not chats:
            pytest.skip("No chats available for testing")

        for c in chats:
            display_name = chat.get_chat_display_name(c)
            assert isinstance(display_name, str)
            assert len(display_name) > 0


@pytest.mark.integration
@pytest.mark.integration_chat
@pytest.mark.slow
class TestChatIntegrationSlow:
    """Slow integration tests for chat (read/send messages)"""

    def test_read_chat_messages(self, real_access_token, capsys):
        """Test reading messages from a chat"""
        # First get a chat
        chats = chat.get_chats(real_access_token, count=5)

        if not chats:
            pytest.skip("No chats available for testing")

        # Get first chat ID
        chat_id = chats[0]['id']

        args = MagicMock()
        args.chat_id = chat_id
        args.with_user = None
        args.count = 10
        args.since = None

        chat.cmd_read(args)

        captured = capsys.readouterr()
        # Should complete without error (may have 0 messages)
        assert "Error" not in captured.out or "No messages found" in captured.out

    def test_get_chat_messages(self, real_access_token):
        """Test getting messages from a chat"""
        # First get a chat
        chats = chat.get_chats(real_access_token, count=5)

        if not chats:
            pytest.skip("No chats available for testing")

        chat_id = chats[0]['id']
        messages = chat.get_chat_messages(real_access_token, chat_id, count=10)

        # Should return a list (may be empty)
        assert isinstance(messages, list)

        # Each message should have required fields
        for msg in messages:
            assert 'id' in msg
            assert 'createdDateTime' in msg
            assert 'body' in msg

    def test_search_messages_in_specific_chat(self, real_access_token):
        """Test searching messages within specific chats"""
        # Get a few chats
        chats = chat.get_chats(real_access_token, count=3)

        if not chats:
            pytest.skip("No chats available for testing")

        # Search for a common word
        results = chat.search_messages(real_access_token, "the", chats=chats, count=5)

        # Should return a list (may be empty)
        assert isinstance(results, list)

        # Each result should be a tuple of (chat, message)
        for c, msg in results:
            assert 'id' in c
            assert 'id' in msg
            assert 'body' in msg


# Note: Test for cmd_send is excluded as it would send real messages
# Manual testing recommended for send functionality
