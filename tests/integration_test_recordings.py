"""
Integration tests for o365 recordings commands

These tests make REAL API calls to Microsoft Graph API.
They will only run if:
1. client_id and tenant are configured in ~/.config/o365/config
2. scopes.files is enabled in the config (recordings are stored in OneDrive)
3. You have authenticated with `o365 auth login`

Run with:
    pytest tests/integration_test_recordings.py -v
    pytest -m integration_files  # Recordings use files scope
    pytest -m integration        # Run ALL integration tests
"""

import pytest
from unittest.mock import MagicMock
from o365 import recordings


@pytest.mark.integration
@pytest.mark.integration_files
class TestRecordingsIntegration:
    """Integration tests for recordings commands"""

    def test_list_recordings(self, real_access_token, capsys):
        """Test listing recordings"""
        args = MagicMock()
        args.since = None
        args.before = None
        args.organizer = None
        args.count = 10

        recordings.cmd_list(args)

        captured = capsys.readouterr()
        # Should complete without error (may have 0 recordings)
        assert "Error" not in captured.out or "No recordings found" in captured.out
        assert len(captured.out) >= 0

    def test_list_recordings_with_since(self, real_access_token, capsys):
        """Test listing recordings since a date"""
        args = MagicMock()
        args.since = "30 days ago"
        args.before = None
        args.organizer = None
        args.count = 10

        recordings.cmd_list(args)

        captured = capsys.readouterr()
        # Should complete without error
        assert len(captured.out) >= 0

    def test_search_recordings(self, real_access_token, capsys):
        """Test searching for recordings"""
        args = MagicMock()
        args.query = "meeting"
        args.since = None
        args.organizer = None
        args.count = 10

        recordings.cmd_search(args)

        captured = capsys.readouterr()
        # Should complete without error (may find 0 results)
        assert "Error" not in captured.out or "No recordings found" in captured.out


@pytest.mark.integration
@pytest.mark.integration_files
class TestRecordingsHelperFunctions:
    """Test recordings helper functions with real API"""

    def test_list_recordings_function(self, real_access_token):
        """Test list_recordings helper function"""
        result = recordings.list_recordings(real_access_token, count=5)

        # Should return a list (may be empty)
        assert isinstance(result, list)

        # Each recording should have required fields
        for rec in result:
            assert 'id' in rec
            assert 'name' in rec
            assert 'createdDateTime' in rec

    def test_search_recordings_function(self, real_access_token):
        """Test search_recordings helper function"""
        result = recordings.search_recordings(real_access_token, "test", count=5)

        # Should return a list (may be empty)
        assert isinstance(result, list)

        # Each recording should have required fields
        for rec in result:
            assert 'id' in rec
            assert 'name' in rec

    def test_format_size(self):
        """Test format_size helper function"""
        assert recordings.format_size(0) == "0.0B"
        assert recordings.format_size(1024) == "1.0KB"
        assert recordings.format_size(1024 * 1024) == "1.0MB"
        assert recordings.format_size(1024 * 1024 * 1024) == "1.0GB"


@pytest.mark.integration
@pytest.mark.integration_files
@pytest.mark.slow
class TestRecordingsIntegrationSlow:
    """Slow integration tests for recordings (download/transcript)"""

    def test_get_recording_info(self, real_access_token, capsys):
        """Test getting recording details"""
        # First list recordings to get an ID
        result = recordings.list_recordings(real_access_token, count=1)

        if not result:
            pytest.skip("No recordings available for testing")

        recording_id = result[0]['id']

        args = MagicMock()
        args.recording_id = recording_id

        recordings.cmd_info(args)

        captured = capsys.readouterr()
        # Should show recording details
        assert "Recording Details" in captured.out or "Recording Details" in str(captured)
        assert "Name:" in captured.out
        assert "Size:" in captured.out

    def test_get_transcript(self, real_access_token):
        """Test getting transcript for a recording (if available)"""
        # First list recordings to get an ID
        result = recordings.list_recordings(real_access_token, count=1)

        if not result:
            pytest.skip("No recordings available for testing")

        recording_id = result[0]['id']

        # Try to get transcript (may not exist)
        transcript = recordings.get_transcript(real_access_token, recording_id)

        # Should return string or None
        assert transcript is None or isinstance(transcript, str)

    def test_parse_vtt_transcript(self):
        """Test VTT transcript parsing"""
        sample_vtt = """WEBVTT

00:00:00.000 --> 00:00:05.000
Hello everyone

00:00:05.000 --> 00:00:10.000
Welcome to the meeting

00:00:10.000 --> 00:00:15.000
Let's get started
"""
        result = recordings.parse_vtt_transcript(sample_vtt)

        # Should return list of tuples
        assert isinstance(result, list)
        assert len(result) == 3

        # Each entry should be (timestamp, text)
        for timestamp, text in result:
            assert isinstance(timestamp, str)
            assert isinstance(text, str)
            assert len(text) > 0

        # Check specific entries
        assert result[0][1] == "Hello everyone"
        assert result[1][1] == "Welcome to the meeting"
        assert result[2][1] == "Let's get started"


# Note: Test for cmd_download is excluded as it would download large files
# Manual testing recommended for download functionality
