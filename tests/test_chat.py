"""
Tests for o365 chat commands
"""

import pytest
from unittest.mock import patch, MagicMock
from o365 import chat


class TestChatList:
    """Tests for 'o365 chat list' command"""

    def test_list_chats(self, mock_access_token, mock_graph_api, sample_chat, capsys):
        """Test listing chats"""
        mock_graph_api.return_value = {'value': [sample_chat]}

        args = MagicMock()
        args.with_user = None
        args.since = None
        args.count = None

        chat.cmd_list(args)

        captured = capsys.readouterr()
        assert "Project Discussion" in captured.out or "John Doe" in captured.out

    def test_list_with_user_filter(self, mock_access_token, mock_graph_api, sample_chat, capsys):
        """Test listing chats filtered by user"""
        mock_graph_api.return_value = {'value': [sample_chat]}

        args = MagicMock()
        args.with_user = "john"
        args.since = None
        args.count = None

        with patch('o365.chat.resolve_user') as mock_resolve:
            mock_resolve.return_value = "john.doe@example.com"
            chat.cmd_list(args)

        captured = capsys.readouterr()
        assert "john" in captured.out.lower() or "Project Discussion" in captured.out

    def test_list_no_chats(self, mock_access_token, mock_graph_api, capsys):
        """Test listing when no chats exist"""
        mock_graph_api.return_value = {'value': []}

        args = MagicMock()
        args.with_user = None
        args.since = None
        args.count = None

        chat.cmd_list(args)

        captured = capsys.readouterr()
        assert "No chats found" in captured.out or "0 chats" in captured.out


class TestChatRead:
    """Tests for 'o365 chat read' command"""

    def test_read_chat_by_id(self, mock_access_token, mock_graph_api, sample_chat, capsys):
        """Test reading chat by ID"""
        mock_graph_api.return_value = {
            'value': [
                {
                    'id': 'msg-1',
                    'from': {'user': {'displayName': 'John Doe'}},
                    'body': {'content': 'Hello'},
                    'createdDateTime': '2025-01-15T10:00:00Z'
                }
            ]
        }

        args = MagicMock()
        args.chat_id = "test-chat-id-123"
        args.with_user = None
        args.count = 50

        chat.cmd_read(args)

        captured = capsys.readouterr()
        assert "Hello" in captured.out or "John Doe" in captured.out

    def test_read_chat_with_user(self, mock_access_token, mock_graph_api, sample_chat, capsys):
        """Test reading chat by user"""
        mock_graph_api.return_value = {'value': [sample_chat]}

        args = MagicMock()
        args.chat_id = None
        args.with_user = "john"
        args.count = 50

        with patch('o365.chat.resolve_user') as mock_resolve:
            mock_resolve.return_value = "john.doe@example.com"
            with patch('o365.chat.get_messages') as mock_messages:
                mock_messages.return_value = [
                    {
                        'id': 'msg-1',
                        'from': {'user': {'displayName': 'John'}},
                        'body': {'content': 'Test'},
                        'createdDateTime': '2025-01-15T10:00:00Z'
                    }
                ]
                chat.cmd_read(args)

        captured = capsys.readouterr()
        assert "Test" in captured.out or "john" in captured.out.lower()


class TestChatSend:
    """Tests for 'o365 chat send' command"""

    def test_send_to_user(self, mock_access_token, mock_graph_api, capsys):
        """Test sending message to user"""
        mock_graph_api.return_value = {'id': 'new-message-id'}

        args = MagicMock()
        args.to = "john"
        args.chat = None
        args.message = "Hello there"

        with patch('o365.chat.resolve_user') as mock_resolve:
            mock_resolve.return_value = "john.doe@example.com"
            with patch('o365.chat.find_chat_with_user') as mock_find:
                mock_find.return_value = "chat-id-123"
                chat.cmd_send(args)

        captured = capsys.readouterr()
        assert "Message sent" in captured.out

    def test_send_to_chat_id(self, mock_access_token, mock_graph_api, capsys):
        """Test sending message to chat ID"""
        mock_graph_api.return_value = {'id': 'new-message-id'}

        args = MagicMock()
        args.to = None
        args.chat = "chat-id-123"
        args.message = "Hello everyone"

        chat.cmd_send(args)

        captured = capsys.readouterr()
        assert "Message sent" in captured.out


class TestChatSearch:
    """Tests for 'o365 chat search' command"""

    def test_search_messages(self, mock_access_token, mock_graph_api, capsys):
        """Test searching messages"""
        mock_graph_api.return_value = {
            'value': [
                {
                    'id': 'msg-1',
                    'chatId': 'chat-1',
                    'from': {'user': {'displayName': 'John'}},
                    'body': {'content': 'deployment complete'},
                    'createdDateTime': '2025-01-15T10:00:00Z'
                }
            ]
        }

        args = MagicMock()
        args.query = "deployment"
        args.with_user = None
        args.since = None
        args.count = 50

        chat.cmd_search(args)

        captured = capsys.readouterr()
        assert "deployment" in captured.out.lower()

    def test_search_no_results(self, mock_access_token, mock_graph_api, capsys):
        """Test searching when no matches found"""
        mock_graph_api.return_value = {'value': []}

        args = MagicMock()
        args.query = "nonexistent"
        args.with_user = None
        args.since = None
        args.count = 50

        chat.cmd_search(args)

        captured = capsys.readouterr()
        assert "No messages found" in captured.out or "0 messages" in captured.out
