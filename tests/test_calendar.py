"""
Tests for o365 calendar commands
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from o365 import calendar as calendar_mod


class TestCalendarList:
    """Tests for 'o365 calendar list' command"""

    def test_list_today(self, mock_access_token, mock_graph_api, sample_calendar_event, capsys):
        """Test listing today's events"""
        mock_graph_api.return_value = {'value': [sample_calendar_event]}

        args = MagicMock()
        args.today = True
        args.week = False
        args.month = False
        args.after = None
        args.before = None
        args.user = None

        calendar_mod.cmd_list(args)

        captured = capsys.readouterr()
        assert "Team Meeting" in captured.out

    def test_list_week(self, mock_access_token, mock_graph_api, sample_calendar_event, capsys):
        """Test listing this week's events"""
        mock_graph_api.return_value = {'value': [sample_calendar_event]}

        args = MagicMock()
        args.today = False
        args.week = True
        args.month = False
        args.after = None
        args.before = None
        args.user = None

        calendar_mod.cmd_list(args)

        captured = capsys.readouterr()
        assert "Team Meeting" in captured.out

    def test_list_month(self, mock_access_token, mock_graph_api, sample_calendar_event, capsys):
        """Test listing this month's events"""
        mock_graph_api.return_value = {'value': [sample_calendar_event]}

        args = MagicMock()
        args.today = False
        args.week = False
        args.month = True
        args.after = None
        args.before = None
        args.user = None

        calendar_mod.cmd_list(args)

        captured = capsys.readouterr()
        assert "Team Meeting" in captured.out

    def test_list_with_date_range(self, mock_access_token, mock_graph_api, sample_calendar_event, capsys):
        """Test listing with custom date range"""
        mock_graph_api.return_value = {'value': [sample_calendar_event]}

        args = MagicMock()
        args.today = False
        args.week = False
        args.month = False
        args.after = "2025-01-01"
        args.before = "2025-01-31"
        args.user = None

        calendar_mod.cmd_list(args)

        captured = capsys.readouterr()
        assert "Team Meeting" in captured.out

    def test_list_other_user_calendar(self, mock_access_token, mock_graph_api, sample_calendar_event, capsys):
        """Test viewing another user's calendar"""
        mock_graph_api.return_value = {'value': [sample_calendar_event]}

        args = MagicMock()
        args.today = True
        args.week = False
        args.month = False
        args.after = None
        args.before = None
        args.user = "john"

        with patch('o365.calendar.resolve_user') as mock_resolve:
            mock_resolve.return_value = "john.doe@example.com"
            with patch('o365.calendar.get_calendar_id_for_user') as mock_cal_id:
                mock_cal_id.return_value = "test-calendar-id"
                calendar_mod.cmd_list(args)

        captured = capsys.readouterr()
        assert "john.doe@example.com" in captured.out

    def test_list_no_events(self, mock_access_token, mock_graph_api, capsys):
        """Test listing when no events exist"""
        mock_graph_api.return_value = {'value': []}

        args = MagicMock()
        args.today = True
        args.week = False
        args.month = False
        args.after = None
        args.before = None
        args.user = None

        calendar_mod.cmd_list(args)

        captured = capsys.readouterr()
        assert "No events found" in captured.out


class TestCalendarCreate:
    """Tests for 'o365 calendar create' command"""

    def test_create_simple_event(self, mock_access_token, mock_graph_api, sample_calendar_event, capsys):
        """Test creating a simple event"""
        mock_graph_api.return_value = sample_calendar_event

        args = MagicMock()
        args.title = "Test Meeting"
        args.when = "tomorrow at 2pm"
        args.duration = "1h"
        args.required = None
        args.optional = None
        args.description = None
        args.location = None
        args.online_meeting = True

        calendar_mod.cmd_create(args)

        captured = capsys.readouterr()
        assert "Event created successfully" in captured.out
        assert "Test Meeting" in captured.out

    def test_create_with_attendees(self, mock_access_token, mock_graph_api, sample_calendar_event, capsys):
        """Test creating event with attendees"""
        mock_graph_api.return_value = sample_calendar_event

        args = MagicMock()
        args.title = "Team Meeting"
        args.when = "tomorrow at 10am"
        args.duration = "2h"
        args.required = ["john", "jane"]
        args.optional = ["bob"]
        args.description = "Sprint planning meeting"
        args.location = "Conference Room A"
        args.online_meeting = True

        with patch('o365.calendar.resolve_user') as mock_resolve:
            mock_resolve.side_effect = lambda q, t: f"{q}@example.com"
            calendar_mod.cmd_create(args)

        captured = capsys.readouterr()
        assert "Event created successfully" in captured.out

    def test_create_with_custom_duration(self, mock_access_token, mock_graph_api, sample_calendar_event, capsys):
        """Test creating event with custom duration format"""
        mock_graph_api.return_value = sample_calendar_event

        args = MagicMock()
        args.title = "Quick Sync"
        args.when = "today at 3pm"
        args.duration = "30m"
        args.required = None
        args.optional = None
        args.description = None
        args.location = None
        args.online_meeting = True

        calendar_mod.cmd_create(args)

        captured = capsys.readouterr()
        assert "30m" in captured.out


class TestCalendarDelete:
    """Tests for 'o365 calendar delete' command"""

    def test_delete_single_event(self, mock_access_token, mock_graph_api, capsys):
        """Test deleting a single event"""
        mock_graph_api.return_value = {}

        args = MagicMock()
        args.event_ids = ["event-id-123"]

        calendar_mod.cmd_delete(args)

        captured = capsys.readouterr()
        assert "Event deleted successfully" in captured.out

    def test_delete_multiple_events(self, mock_access_token, mock_graph_api, capsys):
        """Test deleting multiple events"""
        mock_graph_api.return_value = {}

        args = MagicMock()
        args.event_ids = ["event-id-1", "event-id-2", "event-id-3"]

        calendar_mod.cmd_delete(args)

        captured = capsys.readouterr()
        assert captured.out.count("Event deleted successfully") == 3


class TestParseDuration:
    """Tests for parse_duration helper function"""

    def test_parse_hours(self):
        """Test parsing hours"""
        result = calendar_mod.parse_duration("2h")
        assert result.total_seconds() == 7200

    def test_parse_minutes(self):
        """Test parsing minutes"""
        result = calendar_mod.parse_duration("30m")
        assert result.total_seconds() == 1800

    def test_parse_combined(self):
        """Test parsing combined hours and minutes"""
        result = calendar_mod.parse_duration("1h30m")
        assert result.total_seconds() == 5400

    def test_parse_decimal_hours(self):
        """Test parsing decimal hours"""
        result = calendar_mod.parse_duration("1.5h")
        assert result.total_seconds() == 5400

    def test_parse_invalid_format(self):
        """Test parsing invalid duration format"""
        with pytest.raises(ValueError):
            calendar_mod.parse_duration("invalid")


class TestParseSinceExpression:
    """Tests for parse_since_expression helper function"""

    def test_parse_relative_days(self):
        """Test parsing relative days"""
        result = calendar_mod.parse_since_expression("2 days ago")
        assert result is not None

    def test_parse_relative_weeks(self):
        """Test parsing relative weeks"""
        result = calendar_mod.parse_since_expression("1 week ago")
        assert result is not None

    def test_parse_yesterday(self):
        """Test parsing 'yesterday' keyword"""
        result = calendar_mod.parse_since_expression("yesterday")
        assert result is not None

    def test_parse_today(self):
        """Test parsing 'today' keyword"""
        result = calendar_mod.parse_since_expression("today")
        assert result is not None

    def test_parse_absolute_date(self):
        """Test parsing absolute date"""
        result = calendar_mod.parse_since_expression("2025-01-15")
        assert result is not None

    def test_parse_invalid_expression(self):
        """Test parsing invalid expression"""
        with pytest.raises(ValueError):
            calendar_mod.parse_since_expression("not a valid date")
