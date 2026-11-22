"""
Tests for chat fetch/paging/normalize robustness.

Covers the shared Graph paging helper, chat list/read paging past Graph's
50-item page cap, `--since` filtering for both list and read, and Teams
system/bot messages whose `from` is null.
"""

import argparse
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from o365 import chat
from o365.common import iter_graph_pages, GraphRequestError

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def user_msg(i, when, name="Alice"):
    return {
        "id": f"m{i}",
        "messageType": "message",
        "createdDateTime": iso(when),
        "from": {"user": {"displayName": name, "id": f"u-{name}"}},
        "body": {"contentType": "html", "content": f"<p>hello {i}</p>"},
    }


def system_msg(i, when, detail_type="membersAddedEventMessageDetail", **detail):
    return {
        "id": f"s{i}",
        # Graph reports system messages as unknownFutureValue unless the
        # request opts in with `Prefer: include-unknown-enum-members`.
        "messageType": "unknownFutureValue",
        "createdDateTime": iso(when),
        "from": None,
        "body": {"contentType": "html", "content": "<systemEventMessage/>"},
        "eventDetail": {"@odata.type": f"#microsoft.graph.{detail_type}", **detail},
    }


def paged(items, sizes, base="https://graph/next"):
    """Split items into Graph-style pages of the given sizes, chained by nextLink."""
    pages, start = [], 0
    for n, size in enumerate(sizes):
        page = {"value": items[start : start + size]}
        start += size
        if start < len(items):
            page["@odata.nextLink"] = f"{base}/{n + 1}"
        pages.append(page)
    return pages


def chat_obj(i, last_when):
    return {
        "id": f"c{i}",
        "chatType": "group",
        "topic": f"Chat {i}",
        "members": [],
        "lastMessagePreview": (
            {
                "createdDateTime": iso(last_when),
                "body": {"contentType": "text", "content": "x"},
                "from": None,
            }
            if last_when
            else None
        ),
    }


# ---------------------------------------------------------------------------
# common.iter_graph_pages
# ---------------------------------------------------------------------------


class TestIterGraphPages:
    def test_follows_next_link(self):
        pages = [{"value": [1], "@odata.nextLink": "https://n/2"}, {"value": [2]}]
        calls = []

        def req(url, token):
            calls.append(url)
            return pages[len(calls) - 1]

        got = list(iter_graph_pages("/me/chats", "tok", request=req))
        assert got == pages
        assert calls == ["/me/chats", "https://n/2"]

    def test_stops_on_error_by_default(self):
        got = list(iter_graph_pages("/x", "tok", request=lambda u, t: None))
        assert got == []

    def test_strict_raises(self):
        with pytest.raises(GraphRequestError):
            list(iter_graph_pages("/x", "tok", request=lambda u, t: None, strict=True))


# ---------------------------------------------------------------------------
# chat list
# ---------------------------------------------------------------------------


class TestGetChats:
    def test_pages_past_50(self):
        chats = [chat_obj(i, NOW - timedelta(hours=i)) for i in range(120)]
        pages = paged(chats, [40, 50, 50])  # Graph returns short pages too
        with patch("o365.chat.make_graph_request", side_effect=pages) as req:
            got = chat.get_chats("tok", count=80)
        assert [c["id"] for c in got] == [f"c{i}" for i in range(80)]
        assert req.call_count == 2
        first_url = req.call_args_list[0].args[0]
        assert "%24top=50" in first_url  # never above Graph's cap
        assert req.call_args_list[1].args[0] == "https://graph/next/1"

    def test_expands_last_message_preview(self):
        # Without $expand=lastMessagePreview Graph omits the field, which is
        # why `chat list --since` used to return 0 chats.
        with patch("o365.chat.make_graph_request", return_value={"value": []}) as req:
            chat.get_chats("tok", count=10)
        url = req.call_args.args[0]
        assert "lastMessagePreview" in url.split("%24expand=")[1].split("&")[0]

    def test_since_filters_and_stops_paging(self):
        since = NOW - timedelta(days=3)
        recent = [
            chat_obj(i, NOW - timedelta(days=i * 0.5)) for i in range(5)
        ]  # 0..2 days old
        no_preview = [chat_obj(99, None)]
        old = [chat_obj(10 + i, NOW - timedelta(days=10 + i)) for i in range(60)]
        pages = paged(recent + no_preview + old, [3, 50, 50])
        with patch("o365.chat.make_graph_request", side_effect=pages) as req:
            got = chat.get_chats("tok", count=50, since=since)
        assert [c["id"] for c in got] == [f"c{i}" for i in range(5)]
        # Ordered by last message desc, so the first older chat ends the scan
        assert req.call_count == 2

    def test_cmd_list_since(self, capsys):
        since_expr = "3 days ago"
        chats = [
            chat_obj(1, datetime.now(timezone.utc) - timedelta(hours=2)),
            chat_obj(2, datetime.now(timezone.utc) - timedelta(days=30)),
        ]
        args = argparse.Namespace(
            with_user=None, since=since_expr, count=None, json_mode=False
        )
        with (
            patch("o365.chat.get_access_token", return_value="tok"),
            patch("o365.chat.make_graph_request", return_value={"value": chats}),
        ):
            chat.cmd_list(args)
        out = capsys.readouterr().out
        assert "(1 shown)" in out
        assert "Chat 1" in out and "Chat 2" not in out

    def test_structured_handles_null_preview(self):
        chats = [chat_obj(1, None), chat_obj(2, NOW)]
        with patch("o365.chat.make_graph_request", return_value={"value": chats}):
            got = chat.get_chats_structured("tok", count=10)
        assert got[0]["last_message_datetime"] == ""
        assert got[1]["last_message_datetime"] == iso(NOW)
        assert got[1]["last_message_preview"] == "x"


# ---------------------------------------------------------------------------
# chat read
# ---------------------------------------------------------------------------


class TestGetChatMessages:
    def test_pages_until_count(self):
        msgs = [user_msg(i, NOW - timedelta(minutes=i)) for i in range(200)]
        pages = paged(msgs, [28, 50, 50, 50, 22])
        with patch("o365.chat.make_graph_request", side_effect=pages) as req:
            got = chat.get_chat_messages("tok", "c1", count=120)
        assert len(got) == 120
        assert req.call_count == 3
        # Oldest first, and exactly the newest 120
        assert got[0]["id"] == "m119" and got[-1]["id"] == "m0"

    def test_since_spans_pages_and_stops_at_first_older(self):
        since = NOW - timedelta(days=10)
        inside = [
            user_msg(i, NOW - timedelta(days=i * 0.25)) for i in range(33)
        ]  # up to 8 days
        outside = [user_msg(100 + i, NOW - timedelta(days=20 + i)) for i in range(150)]
        pages = paged(inside + outside, [28, 50, 50, 50])
        with patch("o365.chat.make_graph_request", side_effect=pages) as req:
            got = chat.get_chat_messages("tok", "c1", count=200, since=since)
        assert len(got) == 33
        # Page 2 contains the first older message; page 3+ must not be fetched
        assert req.call_count == 2

    def test_since_with_default_count_does_not_scan_history(self):
        since = NOW - timedelta(days=3)
        msgs = [user_msg(0, NOW - timedelta(days=1))] + [
            user_msg(i, NOW - timedelta(days=30 + i)) for i in range(1, 300)
        ]
        pages = paged(msgs, [50] * 6)
        with patch("o365.chat.make_graph_request", side_effect=pages) as req:
            got = chat.get_chat_messages("tok", "c1", count=50, since=since)
        assert [m["id"] for m in got] == ["m0"]
        assert req.call_count == 1


class TestNormalizeChatMessage:
    def test_null_from_system_event(self):
        n = chat.normalize_chat_message(
            system_msg(1, NOW, members=[{"id": "a"}, {"id": "b"}])
        )
        assert n["sender_name"] == "System"
        assert n["is_system"] is True
        assert n["event_type"] == "membersAdded"
        assert n["text"] == "[members added: 2]"

    def test_chat_renamed_event(self):
        n = chat.normalize_chat_message(
            system_msg(
                1, NOW, "chatRenamedEventMessageDetail", chatDisplayName="New name"
            )
        )
        assert n["text"] == "[chat renamed: New name]"

    def test_application_sender(self):
        msg = user_msg(1, NOW)
        msg["from"] = {"user": None, "application": {"displayName": "Workflows"}}
        n = chat.normalize_chat_message(msg)
        assert n["sender_name"] == "Workflows"
        assert n["is_system"] is False

    def test_null_nested_fields(self):
        msg = {
            "id": "x",
            "createdDateTime": iso(NOW),
            "from": {"user": {"displayName": None, "userPrincipalName": None}},
            "body": None,
        }
        n = chat.normalize_chat_message(msg)
        assert n["sender_name"] == "Unknown"
        assert n["sender_email"] == ""
        assert n["text"] == ""

    def test_html_body_stripped(self):
        assert chat.normalize_chat_message(user_msg(1, NOW))["text"] == "hello 1"


class TestReadWithSystemMessages:
    def _pages(self):
        return {
            "value": [
                user_msg(1, NOW),
                system_msg(2, NOW - timedelta(minutes=1)),
                system_msg(
                    3,
                    NOW - timedelta(minutes=2),
                    "chatRenamedEventMessageDetail",
                    chatDisplayName="T",
                ),
            ]
        }

    def test_cmd_read_does_not_crash(self, capsys):
        args = argparse.Namespace(
            chat_id="c1",
            chat_id_flag=None,
            with_user=None,
            count=None,
            since=None,
            json_mode=False,
        )
        with (
            patch("o365.chat.get_access_token", return_value="tok"),
            patch("o365.chat.make_graph_request", return_value=self._pages()),
        ):
            chat.cmd_read(args)
        out = capsys.readouterr().out
        assert "(3 shown)" in out
        assert "System" in out
        assert "[members added]" in out
        assert "[chat renamed: T]" in out

    def test_cmd_read_json(self, capsys):
        import json

        args = argparse.Namespace(
            chat_id="c1",
            chat_id_flag=None,
            with_user=None,
            count=None,
            since=None,
            json_mode=True,
        )
        with (
            patch("o365.chat.get_access_token", return_value="tok"),
            patch("o365.chat.make_graph_request", return_value=self._pages()),
        ):
            chat.cmd_read(args)
        data = json.loads(capsys.readouterr().out)
        assert data["count"] == 3
        events = [m["event_type"] for m in data["messages"]]
        assert events == ["chatRenamed", "membersAdded", None]

    def test_structured_messages(self):
        with patch("o365.chat.make_graph_request", return_value=self._pages()):
            got = chat.get_chat_messages_structured("tok", "c1", count=10)
        assert [m["sender_name"] for m in got] == ["System", "System", "Alice"]
        assert got[0]["event_type"] == "chatRenamed"
        assert got[2]["content"] == "hello 1"


class TestPrecedingMessages:
    def test_context_pages_back_and_respects_top_cap(self):
        hit_time = NOW - timedelta(days=5)
        msgs = [user_msg(i, NOW - timedelta(hours=i * 6)) for i in range(100)]  # 4/day
        pages = paged(msgs, [50, 50])
        with patch("o365.chat.make_graph_request", side_effect=pages) as req:
            got = chat._fetch_preceding_messages("tok", "c1", iso(hit_time), 25)
        assert len(got) == 25
        # hit is m20; the 25 before it are m21..m45, returned oldest first
        assert got[0]["id"] == "m45" and got[-1]["id"] == "m21"
        assert (
            "%24top=50" in req.call_args_list[0].args[0]
            or "$top=50" in req.call_args_list[0].args[0]
        )


# ---------------------------------------------------------------------------
# MCP goes through the same chat.py path
# ---------------------------------------------------------------------------


class TestMcpChat:
    @pytest.fixture(autouse=True)
    def _needs_mcp(self):
        pytest.importorskip("mcp")

    def test_list_teams_chats_since(self):
        from o365 import mcp_server

        chats = [
            chat_obj(1, datetime.now(timezone.utc) - timedelta(hours=1)),
            chat_obj(2, datetime.now(timezone.utc) - timedelta(days=30)),
        ]
        with (
            patch("o365.mcp_server.get_access_token", return_value="tok"),
            patch("o365.chat.make_graph_request", return_value={"value": chats}),
        ):
            result = mcp_server.list_teams_chats(count=10, since="3 days ago")
        assert result["status"] == "success"
        assert [c["id"] for c in result["chats"]] == ["c1"]

    def test_read_chat_messages_system_events(self):
        from o365 import mcp_server

        page = {"value": [user_msg(1, NOW), system_msg(2, NOW - timedelta(minutes=1))]}
        with (
            patch("o365.mcp_server.get_access_token", return_value="tok"),
            patch("o365.chat.make_graph_request", return_value=page),
        ):
            result = mcp_server.read_chat_messages(chat_id="c1", count=10)
        assert result["status"] == "success"
        assert [m["sender_name"] for m in result["messages"]] == ["System", "Alice"]
