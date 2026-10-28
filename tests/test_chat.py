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
        with patch('o365.chat.find_chats_by_user_or_name') as mock_find:
            mock_find.return_value = [sample_chat]
            args = MagicMock()
            args.with_user = "john"
            args.since = None
            args.count = None

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
                    'body': {'content': 'Hello', 'contentType': 'text'},
                    'createdDateTime': '2025-01-15T10:00:00Z'
                }
            ]
        }

        args = MagicMock()
        args.chat_id = "test-chat-id-123"
        args.with_user = None
        args.count = 50
        args.since = None

        chat.cmd_read(args)

        captured = capsys.readouterr()
        assert "Hello" in captured.out or "John Doe" in captured.out

    def test_read_chat_with_user(self, mock_access_token, mock_graph_api, sample_chat, capsys):
        """Test reading chat by user"""
        sample_chat_with_type = {**sample_chat, 'chatType': 'oneOnOne'}

        with patch('o365.chat.find_chats_by_user_or_name') as mock_find:
            mock_find.return_value = [sample_chat_with_type]
            mock_graph_api.return_value = {
                'value': [
                    {
                        'id': 'msg-1',
                        'from': {'user': {'displayName': 'John'}},
                        'body': {'content': 'Test', 'contentType': 'text'},
                        'createdDateTime': '2025-01-15T10:00:00Z'
                    }
                ]
            }

            args = MagicMock()
            args.chat_id = None
            args.with_user = "john"
            args.count = 50
            args.since = None

            chat.cmd_read(args)

        captured = capsys.readouterr()
        assert "Test" in captured.out or "john" in captured.out.lower()


class TestChatSend:
    """Tests for 'o365 chat send' command"""

    def test_send_to_user(self, mock_access_token, mock_graph_api, capsys):
        """Test sending message to user"""
        mock_graph_api.return_value = {'id': 'new-message-id'}

        sample_chat = {
            'id': 'chat-id-123',
            'chatType': 'oneOnOne',
            'topic': None,
            'members': [
                {'displayName': 'John Doe', 'email': 'john@example.com', 'userId': 'u1'}
            ]
        }

        with patch('o365.chat.find_chats_by_user_or_name') as mock_find:
            mock_find.return_value = [sample_chat]

            args = MagicMock()
            args.to = "john"
            args.chat_id = None
            args.message = "Hello there"
            args.files = []
            args.format = 'markdown'

            chat.cmd_send(args)

        captured = capsys.readouterr()
        assert "Message sent" in captured.out

    def test_send_to_chat_id(self, mock_access_token, mock_graph_api, capsys):
        """Test sending message to chat ID"""
        mock_graph_api.return_value = {'id': 'new-message-id'}

        args = MagicMock()
        args.to = None
        args.chat_id = "chat-id-123"
        args.message = "Hello everyone"
        args.files = []
        args.format = 'markdown'

        chat.cmd_send(args)

        captured = capsys.readouterr()
        assert "Message sent" in captured.out

    def _send(self, mock_graph_api, message, fmt='markdown'):
        """Run cmd_send against a chat ID and return the posted Graph body."""
        mock_graph_api.return_value = {'id': 'new-message-id'}
        args = MagicMock()
        args.to = None
        args.chat_id = "chat-id-123"
        args.message = message
        args.files = []
        args.format = fmt
        with patch('o365.chat.make_graph_request') as mock_req:
            mock_req.return_value = {'id': 'new-message-id'}
            chat.cmd_send(args)
        return mock_req.call_args.kwargs['data']['body']

    def test_send_markdown_is_default(self, mock_access_token, mock_graph_api):
        """Markdown renders to HTML: headings, bold, lists, code blocks"""
        body = self._send(mock_graph_api,
                          "## Title\n\n- **one**\n- two\n\n```\nA  1.2.3.4\n```")
        assert body['contentType'] == 'html'
        assert '<h2>Title</h2>' in body['content']
        assert '<li><strong>one</strong></li>' in body['content']
        assert '<pre><code>A  1.2.3.4</code></pre>' in body['content']

    def test_send_markdown_keeps_line_breaks(self, mock_access_token, mock_graph_api):
        """Single newlines in plain-looking text survive as <br>"""
        body = self._send(mock_graph_api, "line one\nline two")
        assert body['content'] == '<p>line one<br />line two</p>'

    def test_send_markdown_escapes_raw_html(self, mock_access_token, mock_graph_api):
        """Raw HTML in markdown is shown, not interpreted"""
        body = self._send(mock_graph_api, "<b>x</b> & y")
        assert '&lt;b&gt;x&lt;/b&gt; &amp; y' in body['content']

    def test_send_plain(self, mock_access_token, mock_graph_api):
        """--plain sends contentType text unchanged"""
        body = self._send(mock_graph_api, "**not bold**\n- dash", fmt='plain')
        assert body == {'contentType': 'text', 'content': "**not bold**\n- dash"}

    def test_send_html(self, mock_access_token, mock_graph_api):
        """--html passes the HTML through untouched"""
        body = self._send(mock_graph_api, "<p><b>hi</b></p>", fmt='html')
        assert body == {'contentType': 'html', 'content': "<p><b>hi</b></p>"}

    def test_send_message_from_stdin(self, mock_access_token, mock_graph_api,
                                     monkeypatch):
        """-m - reads the message from stdin"""
        import io
        monkeypatch.setattr('sys.stdin', io.StringIO("# From stdin\n"))
        body = self._send(mock_graph_api, '-')
        assert body['content'] == '<h1>From stdin</h1>'

    def test_send_parser_format_flags(self):
        """--plain/--html set format; default is markdown; they conflict"""
        import argparse
        parser = argparse.ArgumentParser()
        chat.setup_parser(parser.add_subparsers())
        base = ['send', '--chat', 'c', '-m', 'x']
        assert parser.parse_args(base).format == 'markdown'
        assert parser.parse_args(base + ['--plain']).format == 'plain'
        assert parser.parse_args(base + ['--html']).format == 'html'
        with pytest.raises(SystemExit):
            parser.parse_args(base + ['--plain', '--html'])


class TestSendMessageAttachments:
    """send_message() body building when files are attached"""

    ATT = [{'id': 'g1', 'name': 'a.pdf', 'web_url': 'https://share/a'}]

    def test_html_content_with_attachment(self):
        with patch('o365.chat.make_graph_request') as mock_req:
            chat.send_message('tok', 'c', '<p><strong>hi</strong></p>',
                              attachments=self.ATT, content_type='html')
        body = mock_req.call_args.kwargs['data']['body']
        assert body['contentType'] == 'html'
        assert body['content'] == ('<p><strong>hi</strong></p>'
                                   '<attachment id="g1"></attachment>')

    def test_plain_content_with_attachment_escaped(self):
        with patch('o365.chat.make_graph_request') as mock_req:
            chat.send_message('tok', 'c', 'a<b\nc', attachments=self.ATT)
        body = mock_req.call_args.kwargs['data']['body']
        assert body['content'] == 'a&lt;b<br>c<attachment id="g1"></attachment>'


class TestChatSearch:
    """Tests for 'o365 chat search' command"""

    def test_search_messages(self, mock_access_token, mock_graph_api, sample_chat, capsys):
        """Test searching messages"""
        # First call: search API returns results
        mock_graph_api.return_value = {
            'value': [{
                'hitsContainers': [{
                    'hits': [{
                        'resource': {
                            'chatId': 'chat-1',
                            'from': {'user': {'displayName': 'John'}},
                            'body': {'content': 'deployment complete'},
                            'createdDateTime': '2025-01-15T10:00:00Z',
                            'summary': 'deployment complete'
                        }
                    }],
                    'total': 1,
                    'moreResultsAvailable': False
                }]
            }]
        }

        args = MagicMock()
        args.query = "deployment"
        args.chat_id = None
        args.with_user = None
        args.from_user = None
        args.since = None
        args.count = 50

        chat.cmd_search(args)

        captured = capsys.readouterr()
        assert "deployment" in captured.out.lower()

    def test_search_no_results(self, mock_access_token, mock_graph_api, capsys):
        """Test searching when no matches found"""
        # Search API returns empty results
        mock_graph_api.return_value = {
            'value': [{
                'hitsContainers': [{
                    'hits': [],
                    'total': 0,
                    'moreResultsAvailable': False
                }]
            }]
        }

        args = MagicMock()
        args.query = "nonexistent"
        args.chat_id = None
        args.with_user = None
        args.from_user = None
        args.since = None
        args.count = 50

        chat.cmd_search(args)

        captured = capsys.readouterr()
        assert "No messages found" in captured.out or "0 results" in captured.out
