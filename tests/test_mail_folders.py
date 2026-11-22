"""
Tests for mail folder resolution (well-known names, display names, nested
folders) and its use by the CLI (`mail read -f`) and the MCP server.
"""

import urllib.parse
from unittest.mock import MagicMock, patch

import pytest

from o365 import mail

# A fake mailbox folder tree:
#   Inbox (well-known)
#   Projects            -> Clients -> Acme
#   Receipts
#   Archive Stuff       -> Old
TREE = {
    None: [
        {"id": "id-inbox", "displayName": "Inbox", "childFolderCount": 0},
        {"id": "id-projects", "displayName": "Projects", "childFolderCount": 1},
        {"id": "id-receipts", "displayName": "Receipts", "childFolderCount": 0},
        {"id": "id-arch", "displayName": "Archive Stuff", "childFolderCount": 1},
    ],
    "id-projects": [
        {"id": "id-clients", "displayName": "Clients", "childFolderCount": 1},
    ],
    "id-arch": [
        {"id": "id-old", "displayName": "Old", "childFolderCount": 0},
    ],
    "id-clients": [
        {"id": "id-acme", "displayName": "Acme", "childFolderCount": 0},
    ],
}


class FakeGraph:
    """Routes folder-listing URLs to TREE and records every request."""

    def __init__(self, tree=TREE, fail=False):
        self.tree = tree
        self.fail = fail
        self.calls = []

    def __call__(self, url, access_token, *a, **kw):
        self.calls.append(url)
        if self.fail:
            return None
        path = urllib.parse.urlsplit(url).path
        if path.endswith("/me/mailFolders"):
            parent = None
        elif path.endswith("/childFolders"):
            parent = urllib.parse.unquote(path.split("/")[-2])
        else:
            raise AssertionError(f"unexpected URL {url}")
        return {"value": list(self.tree.get(parent, []))}


@pytest.fixture(autouse=True)
def clear_cache():
    mail._FOLDER_RESOLVE_CACHE.clear()
    yield
    mail._FOLDER_RESOLVE_CACHE.clear()


class TestResolveFolder:
    @pytest.mark.parametrize(
        "name,slug",
        [
            ("Sent Items", "sentitems"),
            ("sentitems", "sentitems"),
            ("Inbox", "inbox"),
            ("inbox", "inbox"),
            ("Deleted Items", "deleteditems"),
            ("Junk Email", "junkemail"),
            ("Drafts", "drafts"),
            ("archive", "archive"),
        ],
    )
    def test_well_known_names_need_no_request(self, name, slug):
        fake = FakeGraph()
        with patch("o365.mail.make_graph_request", fake):
            assert mail.resolve_folder(name, "tok") == slug
        assert fake.calls == []

    def test_top_level_custom_folder(self):
        fake = FakeGraph()
        with patch("o365.mail.make_graph_request", fake):
            assert mail.resolve_folder("Receipts", "tok") == "id-receipts"
        # Found at the top level: no child folders fetched
        assert not any("childFolders" in c for c in fake.calls)

    def test_display_name_is_case_insensitive(self):
        with patch("o365.mail.make_graph_request", FakeGraph()):
            assert mail.resolve_folder("receipts", "tok") == "id-receipts"

    def test_nested_folder(self):
        with patch("o365.mail.make_graph_request", FakeGraph()):
            assert mail.resolve_folder("Clients", "tok") == "id-clients"

    def test_deeply_nested_folder(self):
        with patch("o365.mail.make_graph_request", FakeGraph()):
            assert mail.resolve_folder("Acme", "tok") == "id-acme"

    def test_search_stops_at_first_match(self):
        """Finding 'Clients' (depth 1) must not descend into its children."""
        fake = FakeGraph()
        with patch("o365.mail.make_graph_request", fake):
            mail.resolve_folder("Clients", "tok")
        assert not any("id-clients" in c for c in fake.calls)

    def test_only_folders_with_children_are_expanded(self):
        fake = FakeGraph()
        with patch("o365.mail.make_graph_request", fake):
            mail.resolve_folder("Acme", "tok")
        assert not any("id-inbox" in c or "id-receipts" in c for c in fake.calls)

    def test_follows_pagination(self):
        page2 = "https://graph.microsoft.com/v1.0/me/mailFolders?page=2"
        responses = {
            "first": {
                "value": [{"id": "a", "displayName": "A", "childFolderCount": 0}],
                "@odata.nextLink": page2,
            },
            page2: {"value": [{"id": "b", "displayName": "B", "childFolderCount": 0}]},
        }

        def fake(url, token, *a, **kw):
            return responses.get(url, responses["first"])

        with patch("o365.mail.make_graph_request", fake):
            assert mail.resolve_folder("B", "tok") == "b"

    def test_not_found_raises_instead_of_exiting(self):
        with patch("o365.mail.make_graph_request", FakeGraph()):
            with pytest.raises(mail.MailFolderNotFoundError) as exc:
                mail.resolve_folder("No Such Folder", "tok")
        assert "No Such Folder" in str(exc.value)

    def test_api_failure_raises(self):
        with patch("o365.mail.make_graph_request", FakeGraph(fail=True)):
            with pytest.raises(mail.MailFolderError):
                mail.resolve_folder("Receipts", "tok")

    def test_graph_id_passes_through(self):
        folder_id = "AAMk" + "x" * 100
        fake = FakeGraph()
        with patch("o365.mail.make_graph_request", fake):
            assert mail.resolve_folder(folder_id, "tok") == folder_id
        assert fake.calls == []

    def test_result_is_cached(self):
        fake = FakeGraph()
        with patch("o365.mail.make_graph_request", fake):
            mail.resolve_folder("Acme", "tok")
            n = len(fake.calls)
            assert mail.resolve_folder("Acme", "tok") == "id-acme"
        assert len(fake.calls) == n


class TestMessagesStreamUsesResolvedFolder:
    def _stream_url(self, folder):
        urls = []

        def fake(url, token, *a, **kw):
            urls.append(url)
            if "/messages" in url:
                return {"value": []}
            return FakeGraph()(url, token)

        with patch("o365.mail.make_graph_request", fake):
            list(mail.get_messages_stream("tok", folder=folder, max_count=3))
        return [u for u in urls if "/messages" in u][0]

    def test_display_name_resolved_to_slug(self):
        assert "/me/mailFolders/sentitems/messages" in self._stream_url("Sent Items")

    def test_nested_name_resolved_to_id(self):
        assert "/me/mailFolders/id-acme/messages" in self._stream_url("Acme")

    def test_unknown_folder_raises(self):
        with patch("o365.mail.make_graph_request", FakeGraph()):
            with pytest.raises(mail.MailFolderNotFoundError):
                list(mail.get_messages_stream("tok", folder="Nope"))


class TestResolveFolderIdempotent:
    @pytest.mark.parametrize(
        "folder_id",
        [
            "AAMkAD" + "Zm9vYmFyLWJhei1xdXV4" * 4 + "AAuAAAAAAC=",
            # Older-format IDs start with AQMk, not AAMk
            "AQMkAD" + "Zm9vYmFyLWJhei1xdXV4" * 5 + "_-4AAAKigQAAAA==",
        ],
    )
    def test_graph_ids_pass_through_without_requests(self, folder_id):
        fake = FakeGraph()
        with patch("o365.mail.make_graph_request", fake):
            assert mail.resolve_folder(folder_id, "tok") == folder_id
        assert fake.calls == []

    def test_resolving_a_resolved_id_is_a_no_op(self):
        fake = FakeGraph()
        with patch("o365.mail.make_graph_request", fake):
            once = mail.resolve_folder("Acme", "tok")
            n = len(fake.calls)
            assert mail.resolve_folder(once, "tok") == once
        assert len(fake.calls) == n


class TestCmdReadSharesStreamResolution:
    """cmd_read must not resolve on its own; get_messages_stream does it."""

    def _args(self, folder):
        args = MagicMock()
        args.ids = []
        args.folder = folder
        args.count = 3
        args.since = None
        args.unread = False
        args.read = False
        args.search = None
        return args

    def test_cmd_read_passes_raw_folder_to_stream(self):
        seen = {}

        def fake_stream(token, folder=None, **kw):
            seen["folder"] = folder
            return iter([])

        with (
            patch("o365.mail.get_access_token", return_value="tok"),
            patch("o365.mail.get_user_domain", return_value="x.com"),
            patch("o365.mail.is_json_mode", return_value=False),
            patch("o365.mail.get_messages_stream", fake_stream),
            patch(
                "o365.mail.resolve_folder", side_effect=AssertionError("resolved twice")
            ),
        ):
            mail.cmd_read(self._args("Sent Items"))
        assert seen["folder"] == "Sent Items"

    @pytest.mark.parametrize("json_mode", [False, True])
    def test_unknown_folder_friendly_exit_in_both_modes(self, json_mode, capsys):
        with (
            patch("o365.mail.get_access_token", return_value="tok"),
            patch("o365.mail.get_user_domain", return_value="x.com"),
            patch("o365.mail.is_json_mode", return_value=json_mode),
            patch("o365.mail.make_graph_request", FakeGraph()),
        ):
            with pytest.raises(SystemExit) as exc:
                mail.cmd_read(self._args("Nope"))
        assert exc.value.code == 1
        assert "'Nope' not found" in capsys.readouterr().err


class TestGetMessageShared:
    """CLI `mail read <ID>` and MCP get_message_by_id_structured share get_message."""

    MSG = {
        "id": "m/1+x=",
        "subject": "s",
        "from": {"emailAddress": {"address": "a@x.com", "name": "A"}},
        "receivedDateTime": "2026-01-01T00:00:00Z",
        "body": {"contentType": "text", "content": "hi"},
        "attachments": [],
    }

    def test_get_message_encodes_id(self):
        urls = []

        def fake(url, token, *a, **kw):
            urls.append(url)
            return dict(self.MSG)

        with patch("o365.mail.make_graph_request", fake):
            assert mail.get_message("tok", "m/1+x=")["id"] == "m/1+x="
        assert "/me/messages/m%2F1%2Bx%3D?" in urls[0]
        assert "$expand=attachments" in urls[0]

    def test_get_message_missing_returns_none(self):
        with patch("o365.mail.make_graph_request", return_value=None):
            assert mail.get_message("tok", "x") is None

    def test_structured_uses_get_message(self):
        with (
            patch("o365.mail.get_message", return_value=dict(self.MSG)) as gm,
            patch("o365.mail.get_user_domain", return_value="x.com"),
        ):
            out = mail.get_message_by_id_structured("tok", "m/1+x=")
        gm.assert_called_once_with("tok", "m/1+x=")
        assert out["from_email"] == "a@x.com"

    def test_cmd_read_ids_uses_get_message(self):
        args = MagicMock()
        args.ids = ["m/1+x="]
        with (
            patch("o365.mail.get_access_token", return_value="tok"),
            patch("o365.mail.get_message", return_value=dict(self.MSG)) as gm,
            patch("o365.mail.is_json_mode", return_value=True),
            patch("o365.mail.emit_json"),
        ):
            mail.cmd_read(args)
        gm.assert_called_once_with("tok", "m/1+x=")
