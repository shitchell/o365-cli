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
            args.mentions = []
            args.dry_run = False

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
        args.mentions = []
        args.dry_run = False

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
        args.mentions = []
        args.dry_run = False
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


MEMBERS_RESPONSE = {'value': [
    {'userId': 'u-luke', 'displayName': 'Luke Hands', 'email': 'luke.hands@example.com'},
    {'userId': 'u-shaun', 'displayName': 'Shaun Mitchell', 'email': 'shaun.mitchell@example.com'},
    {'userId': 'u-lucy', 'displayName': 'Lucy Hart', 'email': 'lucy.hart@example.com'},
    {'userId': None, 'displayName': 'Some Bot'},
]}
MEMBERS = [
    {'userId': 'u-luke', 'displayName': 'Luke Hands', 'email': 'luke.hands@example.com'},
    {'userId': 'u-shaun', 'displayName': 'Shaun Mitchell', 'email': 'shaun.mitchell@example.com'},
    {'userId': 'u-lucy', 'displayName': 'Lucy Hart', 'email': 'lucy.hart@example.com'},
]


class TestResolveMention:
    """resolve_mention() name matching tiers"""

    @pytest.mark.parametrize('name,uid', [
        ('Luke Hands', 'u-luke'),
        ('luke hands', 'u-luke'),
        ('  Luke   Hands ', 'u-luke'),
        ('luke.hands@example.com', 'u-luke'),
        ('shaun.mitchell', 'u-shaun'),
        ('Luke', 'u-luke'),
        ('sha', 'u-shaun'),
        ('Mitchell', 'u-shaun'),
        ('hart', 'u-lucy'),
    ])
    def test_resolves(self, name, uid):
        assert chat.resolve_mention(name, MEMBERS)['userId'] == uid

    def test_ambiguous_lists_candidates(self):
        with pytest.raises(chat.MentionError) as e:
            chat.resolve_mention('Lu', MEMBERS)
        assert 'ambiguous' in str(e.value)
        assert 'Lucy Hart' in str(e.value) and 'Luke Hands' in str(e.value)

    def test_no_match_lists_members(self):
        with pytest.raises(chat.MentionError) as e:
            chat.resolve_mention('Roman', MEMBERS)
        assert 'no member' in str(e.value)
        assert 'Luke Hands' in str(e.value)

    def test_exact_beats_prefix(self):
        members = MEMBERS + [{'userId': 'u-l2', 'displayName': 'Luke Handsome', 'email': ''}]
        assert chat.resolve_mention('Luke Hands', members)['userId'] == 'u-luke'

    def test_get_chat_members_skips_userless_and_pages(self):
        pages = [
            {'value': MEMBERS_RESPONSE['value'][:2], '@odata.nextLink': 'https://next'},
            {'value': MEMBERS_RESPONSE['value'][2:]},
        ]
        with patch('o365.chat.make_graph_request', side_effect=pages) as req:
            members = chat.get_chat_members('tok', 'c1')
        assert [m['userId'] for m in members] == ['u-luke', 'u-shaun', 'u-lucy']
        assert req.call_args_list[0].args[0].endswith('/chats/c1/members')
        assert req.call_args_list[1].args[0] == 'https://next'


class TestChatSendMentions:
    """@[Name] mentions through cmd_send, with the members GET and POST mocked"""

    def _run(self, message, fmt='markdown', mentions=None, files=None,
             dry_run=False):
        """Run cmd_send; return (posted message dict or None, request mock)."""
        args = MagicMock()
        args.to = None
        args.chat_id = 'chat-1'
        args.message = message
        args.files = files or []
        args.format = fmt
        args.mentions = mentions or []
        args.dry_run = dry_run

        def fake_request(url, token, method='GET', data=None):
            if url.endswith('/members'):
                return MEMBERS_RESPONSE
            if url.endswith('/messages') and method == 'POST':
                return {'id': 'new-message-id'}
            raise AssertionError(f'unexpected request {method} {url}')

        with patch('o365.chat.get_access_token', return_value='tok'), \
             patch('o365.chat.make_graph_request', side_effect=fake_request) as req:
            chat.cmd_send(args)
        posts = [c for c in req.call_args_list if c.kwargs.get('method') == 'POST']
        return (posts[-1].kwargs['data'] if posts else None), req

    def test_markdown_mention(self):
        data, _ = self._run('hey @[Luke], **look**')
        assert data['body'] == {
            'contentType': 'html',
            'content': '<p>hey <at id="0">Luke Hands</at>, <strong>look</strong></p>',
        }
        assert data['mentions'] == [{
            'id': 0,
            'mentionText': 'Luke Hands',
            'mentioned': {'user': {
                'id': 'u-luke',
                'displayName': 'Luke Hands',
                'userIdentityType': 'aadUser',
            }},
        }]

    def test_multiple_and_repeated_mentions_get_own_ids(self):
        data, _ = self._run('@[Luke] and @[shaun] and @[Luke Hands] again')
        assert data['body']['content'] == (
            '<p><at id="0">Luke Hands</at> and <at id="1">Shaun Mitchell</at>'
            ' and <at id="2">Luke Hands</at> again</p>')
        assert [m['id'] for m in data['mentions']] == [0, 1, 2]
        assert [m['mentioned']['user']['id'] for m in data['mentions']] == [
            'u-luke', 'u-shaun', 'u-luke']

    def test_name_with_markdown_chars_not_mangled(self):
        """The name is not parsed as markdown (no emphasis from _ or *)"""
        members = {'value': [{'userId': 'u-x', 'displayName': 'a_b *c*', 'email': ''}]}
        with patch('o365.chat.make_graph_request', return_value=members):
            ctype, content, mentions = chat.render_message_with_mentions(
                'hi @[a_b *c*]', 'markdown',
                lambda: chat.get_chat_members('tok', 'c'))
        assert content == '<p>hi <at id="0">a_b *c*</at></p>'

    def test_bare_at_and_no_mentions_skip_member_lookup(self):
        data, req = self._run('mail me@example.com or @luke')
        assert 'mentions' not in data
        assert not any(c.args[0].endswith('/members') for c in req.call_args_list)
        assert data['body']['content'] == '<p>mail me@example.com or @luke</p>'

    def test_mention_in_code_is_literal(self):
        data, req = self._run('use `@[Nobody]` syntax\n\n```\n@[Nobody]\n```')
        assert 'mentions' not in data
        assert '<code>@[Nobody]</code>' in data['body']['content']
        assert '<pre><code>@[Nobody]</code></pre>' in data['body']['content']
        assert not any(c.args[0].endswith('/members') for c in req.call_args_list)

    def test_html_mode_mentions(self):
        data, _ = self._run('<p>hi @[Lucy] &amp; co</p>', fmt='html')
        assert data['body']['content'] == '<p>hi <at id="0">Lucy Hart</at> &amp; co</p>'
        assert data['mentions'][0]['mentioned']['user']['id'] == 'u-lucy'

    def test_mention_flag_prepends(self):
        data, _ = self._run('deployed', mentions=['Luke', 'Shaun'])
        assert data['body']['content'] == (
            '<p><at id="0">Luke Hands</at> <at id="1">Shaun Mitchell</at> deployed</p>')

    def test_mention_flag_without_message(self):
        data, _ = self._run(None, mentions=['Luke'])
        assert data['body']['content'] == '<p><at id="0">Luke Hands</at></p>'

    def test_plain_warns_and_sends_literal(self, capsys):
        data, req = self._run('@[Luke] hi', fmt='plain')
        assert data['body'] == {'contentType': 'text', 'content': '@[Luke] hi'}
        assert 'mentions' not in data
        assert 'Warning' in capsys.readouterr().err

    def test_plain_with_mention_flag_errors(self):
        with pytest.raises(SystemExit):
            self._run('hi', fmt='plain', mentions=['Luke'])

    def test_unknown_mention_errors_without_sending(self, capsys):
        with pytest.raises(SystemExit):
            self._run('@[Roman] hi')
        err = capsys.readouterr().err
        assert '@[Roman] matches no member' in err

    def test_ambiguous_mention_errors(self, capsys):
        with pytest.raises(SystemExit):
            self._run('@[lu] hi')
        assert 'ambiguous' in capsys.readouterr().err

    def test_dry_run_prints_payload_and_does_not_post(self, capsys):
        import json
        data, _ = self._run('@[Luke] hi', dry_run=True)
        assert data is None
        out = json.loads(capsys.readouterr().out)
        assert out['method'] == 'POST'
        assert out['url'].endswith('/chats/chat-1/messages')
        assert out['body']['mentions'][0]['mentionText'] == 'Luke Hands'

    def test_dry_run_with_file_skips_upload(self, tmp_path, capsys):
        import json
        f = tmp_path / 'r.pdf'
        f.write_text('x')
        with patch('o365.files.upload_file') as up:
            data, _ = self._run('@[Luke] see file', files=[str(f)], dry_run=True)
        up.assert_not_called()
        out = json.loads(capsys.readouterr().out)
        body = out['body']
        assert body['body']['content'].startswith(
            '<p><at id="0">Luke Hands</at> see file</p><attachment id="')
        assert body['attachments'][0]['name'] == 'r.pdf'
        assert body['mentions'][0]['id'] == 0

    def test_mentions_with_attachments_in_send_message(self):
        att = [{'id': 'g1', 'name': 'a.pdf', 'web_url': 'https://share/a'}]
        m = [{'id': 0, 'mentionText': 'X', 'mentioned': {'user': {'id': 'u'}}}]
        with patch('o365.chat.make_graph_request') as req:
            chat.send_message('tok', 'c', '<p><at id="0">X</at></p>',
                              attachments=att, content_type='html', mentions=m)
        data = req.call_args.kwargs['data']
        assert data['mentions'] == m
        assert data['body']['content'] == (
            '<p><at id="0">X</at></p><attachment id="g1"></attachment>')

    def test_parser_mention_and_dry_run(self):
        import argparse
        parser = argparse.ArgumentParser()
        chat.setup_parser(parser.add_subparsers())
        a = parser.parse_args(['send', '--chat', 'c', '--mention', 'Luke',
                               '--mention', 'Shaun', '--dry-run'])
        assert a.mentions == ['Luke', 'Shaun'] and a.dry_run is True
        b = parser.parse_args(['send', '--chat', 'c', '-m', 'x'])
        assert b.mentions == [] and b.dry_run is False


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
