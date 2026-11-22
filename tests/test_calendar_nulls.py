"""
Graph returns explicit nulls (not missing keys) for several event fields,
e.g. `onlineMeeting: null` on any non-Teams event. `.get(key, {})` does not
cover that case.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from o365 import calendar


def null_event():
    return {
        "id": "e1",
        "subject": "Lunch",
        "start": {"dateTime": "2026-11-21T12:00:00.0000000", "timeZone": "UTC"},
        "end": {"dateTime": "2026-11-21T13:00:00.0000000", "timeZone": "UTC"},
        "location": None,
        "organizer": {"emailAddress": None},
        "attendees": [{"emailAddress": None, "status": None, "type": "required"}],
        "isOnlineMeeting": False,
        "onlineMeeting": None,
        "body": None,
    }


def test_get_events_structured_null_fields():
    start = datetime(2026, 11, 21, tzinfo=timezone.utc)
    with patch("o365.calendar.list_events", return_value=[null_event()]):
        got = calendar.get_events_structured("tok", start, start)
    ev = got[0]
    assert ev["online_meeting_url"] == ""
    assert ev["location"] == ""
    assert ev["organizer_name"] == ""
    assert ev["body_content"] == ""
    assert ev["attendees"][0]["status"] == ""


def test_display_events_null_location(capsys):
    start = datetime(2026, 11, 21, tzinfo=timezone.utc)
    calendar.display_events([null_event()], start, start)
    assert "Lunch" in capsys.readouterr().out
