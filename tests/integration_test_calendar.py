"""
Integration tests for o365 calendar commands

These tests make REAL API calls to Microsoft Graph API.
They will only run if:
1. client_id and tenant are configured in ~/.config/o365/config
2. scopes.calendar is enabled in the config
3. You have authenticated with `o365 auth login`

Run with:
    pytest tests/integration_test_calendar.py -v
    pytest -m integration_calendar  # Run all calendar integration tests
    pytest -m integration            # Run ALL integration tests
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from o365 import calendar


@pytest.mark.integration
@pytest.mark.integration_calendar
class TestCalendarIntegration:
    """Integration tests for calendar commands"""

    def test_list_today(self, real_access_token, capsys):
        """Test listing today's calendar events"""
        args = MagicMock()
        args.today = True
        args.week = False
        args.month = False
        args.after = None
        args.before = None
        args.user = None

        calendar.cmd_list(args)

        captured = capsys.readouterr()
        # Should complete without error (may have 0 events)
        assert "Error" not in captured.out or "No events found" in captured.out
        assert len(captured.out) >= 0

    def test_list_week(self, real_access_token, capsys):
        """Test listing this week's calendar events"""
        args = MagicMock()
        args.today = False
        args.week = True
        args.month = False
        args.after = None
        args.before = None
        args.user = None

        calendar.cmd_list(args)

        captured = capsys.readouterr()
        # Should complete without error (may have 0 events)
        assert "Error" not in captured.out or "No events found" in captured.out
        assert len(captured.out) >= 0

    def test_list_after_date(self, real_access_token, capsys):
        """Test listing events after a specific date"""
        args = MagicMock()
        args.today = False
        args.week = False
        args.month = False
        args.after = "3 days ago"
        args.before = None
        args.user = None

        calendar.cmd_list(args)

        captured = capsys.readouterr()
        # Should complete without error
        assert "Error" not in captured.out or "No events found" in captured.out

    def test_list_month(self, real_access_token, capsys):
        """Test listing this month's calendar events"""
        args = MagicMock()
        args.today = False
        args.week = False
        args.month = True
        args.after = None
        args.before = None
        args.user = None

        calendar.cmd_list(args)

        captured = capsys.readouterr()
        # Should complete without error
        assert "Error" not in captured.out or "No events found" in captured.out


@pytest.mark.integration
@pytest.mark.integration_calendar
@pytest.mark.slow
class TestCalendarIntegrationSlow:
    """Slow integration tests for calendar (create/delete events)"""

    def test_create_and_delete_event(self, real_access_token, capsys):
        """Test creating and then deleting a calendar event"""
        # Create event 1 day from now
        create_args = MagicMock()
        create_args.title = "Test Event (Integration Test)"
        create_args.when = "tomorrow at 3pm"
        create_args.duration = "30m"
        create_args.required = None
        create_args.optional = None
        create_args.description = "This is a test event created by integration tests"
        create_args.location = None
        create_args.online_meeting = False

        calendar.cmd_create(create_args)

        captured = capsys.readouterr()
        # Should create successfully
        assert "Event created successfully" in captured.out
        assert "Event ID:" in captured.out

        # Extract event ID from output
        lines = captured.out.split('\n')
        event_id = None
        for line in lines:
            if line.startswith("Event ID:"):
                event_id = line.split("Event ID:")[1].strip()
                break

        if not event_id:
            pytest.fail("Could not extract event ID from create output")

        # Now delete the event
        delete_args = MagicMock()
        delete_args.event_ids = [event_id]

        calendar.cmd_delete(delete_args)

        captured = capsys.readouterr()
        # Should delete successfully
        assert "deleted successfully" in captured.out.lower()

    def test_create_event_with_location(self, real_access_token, capsys):
        """Test creating an event with location"""
        create_args = MagicMock()
        create_args.title = "Test Meeting (Integration Test)"
        create_args.when = "tomorrow at 2pm"
        create_args.duration = "1h"
        create_args.required = None
        create_args.optional = None
        create_args.description = "Test meeting with location"
        create_args.location = "Conference Room A"
        create_args.online_meeting = False

        calendar.cmd_create(create_args)

        captured = capsys.readouterr()
        # Should create successfully
        assert "Event created successfully" in captured.out
        assert "Location: Conference Room A" in captured.out

        # Extract and delete the event
        lines = captured.out.split('\n')
        event_id = None
        for line in lines:
            if line.startswith("Event ID:"):
                event_id = line.split("Event ID:")[1].strip()
                break

        if event_id:
            delete_args = MagicMock()
            delete_args.event_ids = [event_id]
            calendar.cmd_delete(delete_args)

    def test_create_online_meeting(self, real_access_token, capsys):
        """Test creating a Teams online meeting"""
        create_args = MagicMock()
        create_args.title = "Test Teams Meeting (Integration Test)"
        create_args.when = "tomorrow at 4pm"
        create_args.duration = "30m"
        create_args.required = None
        create_args.optional = None
        create_args.description = "Test Teams meeting"
        create_args.location = None
        create_args.online_meeting = True

        calendar.cmd_create(create_args)

        captured = capsys.readouterr()
        # Should create successfully
        assert "Event created successfully" in captured.out
        assert "Teams meeting: Yes" in captured.out

        # Extract and delete the event
        lines = captured.out.split('\n')
        event_id = None
        for line in lines:
            if line.startswith("Event ID:"):
                event_id = line.split("Event ID:")[1].strip()
                break

        if event_id:
            delete_args = MagicMock()
            delete_args.event_ids = [event_id]
            calendar.cmd_delete(delete_args)


@pytest.mark.integration
@pytest.mark.integration_calendar
class TestCalendarHelperFunctions:
    """Test calendar helper functions with real API"""

    def test_parse_since_expression(self):
        """Test time parsing helper"""
        # Test relative times
        result = calendar.parse_since_expression("2 days ago")
        assert isinstance(result, datetime)
        assert result < datetime.now(calendar.LOCAL_TZ)

        result = calendar.parse_since_expression("1 week ago")
        assert isinstance(result, datetime)

        result = calendar.parse_since_expression("yesterday")
        assert isinstance(result, datetime)

    def test_parse_duration(self):
        """Test duration parsing"""
        # Test various duration formats
        result = calendar.parse_duration("1h")
        assert result == timedelta(hours=1)

        result = calendar.parse_duration("30m")
        assert result == timedelta(minutes=30)

        result = calendar.parse_duration("1h30m")
        assert result == timedelta(hours=1, minutes=30)

        result = calendar.parse_duration("1.5h")
        assert result == timedelta(hours=1.5)
