"""
Tests for o365 recordings commands
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from o365 import recordings


class TestRecordingsList:
    """Tests for 'o365 recordings list' command"""

    def test_list_recordings(self, mock_access_token, mock_graph_api, sample_recording, capsys):
        """Test listing recordings"""
        # Mock returns recordings directly (list_recordings makes one API call to /Recordings:/children)
        mock_graph_api.return_value = {'value': [sample_recording]}

        args = MagicMock()
        args.since = None
        args.before = None
        args.organizer = None
        args.count = 50

        recordings.cmd_list(args)

        captured = capsys.readouterr()
        assert "Team Meeting" in captured.out or ".mp4" in captured.out

    def test_list_with_since_filter(self, mock_access_token, mock_graph_api, sample_recording, capsys):
        """Test listing recordings with since filter"""
        # Mock returns recordings directly (list_recordings makes one API call to /Recordings:/children)
        mock_graph_api.return_value = {'value': [sample_recording]}

        args = MagicMock()
        args.since = "1 week ago"
        args.before = None
        args.organizer = None
        args.count = 50

        recordings.cmd_list(args)

        captured = capsys.readouterr()
        assert ".mp4" in captured.out

    def test_list_no_recordings(self, mock_access_token, mock_graph_api, capsys):
        """Test listing when no recordings exist"""
        mock_graph_api.return_value = {'value': []}

        args = MagicMock()
        args.since = None
        args.before = None
        args.organizer = None
        args.count = 50

        recordings.cmd_list(args)

        captured = capsys.readouterr()
        assert "No recordings found" in captured.out or "0 found" in captured.out


class TestRecordingsSearch:
    """Tests for 'o365 recordings search' command"""

    def test_search_recordings(self, mock_access_token, mock_graph_api, sample_recording, capsys):
        """Test searching for recordings"""
        # Mock returns search results directly (search makes one API call to search)
        mock_graph_api.return_value = {'value': [sample_recording]}

        args = MagicMock()
        args.query = "meeting"
        args.since = None
        args.organizer = None
        args.count = 50

        recordings.cmd_search(args)

        captured = capsys.readouterr()
        assert ".mp4" in captured.out

    def test_search_no_results(self, mock_access_token, mock_graph_api, capsys):
        """Test searching when no matches found"""
        mock_graph_api.return_value = {'value': []}

        args = MagicMock()
        args.query = "nonexistent"
        args.since = None
        args.organizer = None
        args.count = 50

        recordings.cmd_search(args)

        captured = capsys.readouterr()
        assert "No recordings found" in captured.out or "0 found" in captured.out


class TestRecordingsDownload:
    """Tests for 'o365 recordings download' command"""

    def test_download_recording(self, mock_access_token, mock_graph_api, sample_recording, tmp_path, capsys):
        """Test downloading a recording"""
        # Mock get recording metadata
        mock_graph_api.return_value = sample_recording

        args = MagicMock()
        args.recording_id = "test-recording-id-123"
        args.dest = str(tmp_path)
        args.filename = None

        # Mock urlopen to return fake file data
        mock_response = MagicMock()
        # Use side_effect to return data once, then empty bytes to stop the loop
        mock_response.read.side_effect = [b"fake video data", b""]
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.headers.get.return_value = '1000'  # Content-Length

        with patch('urllib.request.urlopen', return_value=mock_response):
            recordings.cmd_download(args)

        captured = capsys.readouterr()
        assert "Downloaded" in captured.out or "recording" in captured.out.lower() or "complete" in captured.out.lower()

    def test_download_with_custom_filename(self, mock_access_token, mock_graph_api, sample_recording, tmp_path, capsys):
        """Test downloading with custom filename"""
        # Mock get recording metadata
        mock_graph_api.return_value = sample_recording

        args = MagicMock()
        args.recording_id = "test-recording-id-123"
        args.dest = str(tmp_path)
        args.filename = "custom_name.mp4"

        # Mock urlopen to return fake file data
        mock_response = MagicMock()
        # Use side_effect to return data once, then empty bytes to stop the loop
        mock_response.read.side_effect = [b"fake video data", b""]
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.headers.get.return_value = '1000'  # Content-Length

        with patch('urllib.request.urlopen', return_value=mock_response):
            recordings.cmd_download(args)

        captured = capsys.readouterr()
        assert "custom_name.mp4" in captured.out or "Downloaded" in captured.out or "complete" in captured.out.lower()


class TestRecordingsTranscript:
    """Tests for 'o365 recordings transcript' command"""

    def test_get_transcript_text(self, mock_access_token, mock_graph_api, sample_recording, capsys):
        """Test getting transcript in text format"""
        args = MagicMock()
        args.recording_id = "test-recording-id-123"
        args.format = "txt"
        args.output = None
        args.timestamps = False
        args.speakers = False

        vtt_content = """WEBVTT

00:00:10.000 --> 00:00:15.000
<v John Doe>Hello everyone

00:00:20.000 --> 00:00:25.000
<v Jane Smith>Hi there"""

        with patch('o365.recordings.get_transcript') as mock_transcript:
            mock_transcript.return_value = vtt_content
            recordings.cmd_transcript(args)

        captured = capsys.readouterr()
        assert "Hello everyone" in captured.out or "transcript" in captured.out.lower()

    def test_get_transcript_vtt(self, mock_access_token, mock_graph_api, sample_recording, capsys):
        """Test getting transcript in VTT format"""
        args = MagicMock()
        args.recording_id = "test-recording-id-123"
        args.format = "vtt"
        args.output = None
        args.timestamps = False
        args.speakers = False

        vtt_content = "WEBVTT\n\n00:00:10.000 --> 00:00:15.000\n<v John Doe>Hello"

        with patch('o365.recordings.get_transcript') as mock_transcript:
            mock_transcript.return_value = vtt_content
            recordings.cmd_transcript(args)

        captured = capsys.readouterr()
        assert "WEBVTT" in captured.out

    def test_transcript_not_found(self, mock_access_token, mock_graph_api):
        """Test when transcript is not available"""
        args = MagicMock()
        args.recording_id = "test-recording-id-123"
        args.format = "txt"
        args.output = None
        args.timestamps = False
        args.speakers = False

        with patch('o365.recordings.get_transcript') as mock_transcript:
            mock_transcript.return_value = None
            with pytest.raises(SystemExit):
                recordings.cmd_transcript(args)


class TestRecordingsInfo:
    """Tests for 'o365 recordings info' command"""

    def test_show_recording_info(self, mock_access_token, mock_graph_api, sample_recording, capsys):
        """Test showing recording information"""
        mock_graph_api.return_value = sample_recording

        args = MagicMock()
        args.recording_id = "test-recording-id-123"

        recordings.cmd_info(args)

        captured = capsys.readouterr()
        assert "Team Meeting" in captured.out or "mp4" in captured.out


class TestParseVttTranscript:
    """Tests for parse_vtt_transcript helper function"""

    def test_parse_vtt(self):
        """Test parsing VTT transcript"""
        vtt_content = """WEBVTT

00:00:10.000 --> 00:00:15.000
<v John Doe>Hello everyone

00:00:20.000 --> 00:00:25.000
<v Jane Smith>How are you?"""

        result = recordings.parse_vtt_transcript(vtt_content)

        assert len(result) >= 2
        assert any("Hello" in text for _, text in result)

    def test_parse_vtt_with_speaker(self):
        """Test parsing VTT with speaker names"""
        vtt_content = """WEBVTT

00:00:10.000 --> 00:00:15.000
<v John Doe>Test message"""

        result = recordings.parse_vtt_transcript(vtt_content)

        assert len(result) > 0
