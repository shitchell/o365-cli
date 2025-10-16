"""
Tests for o365 files commands
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from o365 import files


class TestFilesDrives:
    """Tests for 'o365 files drives' command"""

    def test_list_drives(self, mock_access_token, mock_graph_api, capsys):
        """Test listing available drives"""
        mock_graph_api.return_value = {
            'value': [
                {'id': 'drive-1', 'name': 'Personal', 'driveType': 'personal'},
                {'id': 'drive-2', 'name': 'Team Site', 'driveType': 'documentLibrary'}
            ]
        }

        args = MagicMock()
        args.verbose = False

        files.cmd_drives(args)

        captured = capsys.readouterr()
        assert "Personal" in captured.out
        assert "Team Site" in captured.out

    def test_list_drives_verbose(self, mock_access_token, mock_graph_api, capsys):
        """Test listing drives with verbose output"""
        mock_graph_api.return_value = {
            'value': [
                {'id': 'drive-1', 'name': 'Personal', 'driveType': 'personal'}
            ]
        }

        args = MagicMock()
        args.verbose = True

        files.cmd_drives(args)

        captured = capsys.readouterr()
        assert "drive-1" in captured.out


class TestFilesList:
    """Tests for 'o365 files list' command"""

    def test_list_root(self, mock_access_token, mock_graph_api, sample_file, capsys):
        """Test listing root directory"""
        mock_graph_api.return_value = {'value': [sample_file]}

        args = MagicMock()
        args.path = None
        args.long = False
        args.recursive = False
        args.since = None

        files.cmd_list(args)

        captured = capsys.readouterr()
        assert "document.pdf" in captured.out

    def test_list_with_path(self, mock_access_token, mock_graph_api, sample_file, capsys):
        """Test listing specific path"""
        mock_graph_api.return_value = {'value': [sample_file]}

        args = MagicMock()
        args.path = "/Documents"
        args.long = False
        args.recursive = False
        args.since = None

        files.cmd_list(args)

        captured = capsys.readouterr()
        assert "document.pdf" in captured.out

    def test_list_long_format(self, mock_access_token, mock_graph_api, sample_file, capsys):
        """Test listing with long format (size, date)"""
        mock_graph_api.return_value = {'value': [sample_file]}

        args = MagicMock()
        args.path = None
        args.long = True
        args.recursive = False
        args.since = None

        files.cmd_list(args)

        captured = capsys.readouterr()
        assert "1024" in captured.out or "1.0KB" in captured.out


class TestFilesSearch:
    """Tests for 'o365 files search' command"""

    def test_search_files(self, mock_access_token, mock_graph_api, sample_file, capsys):
        """Test searching for files"""
        mock_graph_api.return_value = {'value': [sample_file]}

        args = MagicMock()
        args.query = "document"
        args.type = None
        args.since = None
        args.count = 50

        files.cmd_search(args)

        captured = capsys.readouterr()
        assert "document.pdf" in captured.out

    def test_search_with_type_filter(self, mock_access_token, mock_graph_api, sample_file, capsys):
        """Test searching with file type filter"""
        mock_graph_api.return_value = {'value': [sample_file]}

        args = MagicMock()
        args.query = "report"
        args.type = "pdf"
        args.since = None
        args.count = 50

        files.cmd_search(args)

        captured = capsys.readouterr()
        assert "document.pdf" in captured.out


class TestFilesDownload:
    """Tests for 'o365 files download' command"""

    def test_download_file(self, mock_access_token, mock_graph_api, sample_file, tmp_path, capsys):
        """Test downloading a file"""
        mock_graph_api.return_value = sample_file

        args = MagicMock()
        args.source = "/document.pdf"
        args.dest = str(tmp_path)
        args.recursive = False
        args.overwrite = False

        with patch('o365.files.download_file_content') as mock_download:
            mock_download.return_value = b"fake pdf content"
            with patch('builtins.open', mock_open()) as mock_file:
                files.cmd_download(args)

        captured = capsys.readouterr()
        assert "Downloaded" in captured.out or "document.pdf" in captured.out


class TestFilesUpload:
    """Tests for 'o365 files upload' command"""

    def test_upload_file(self, mock_access_token, mock_graph_api, tmp_path, capsys):
        """Test uploading a file"""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        mock_graph_api.return_value = {'id': 'uploaded-file-id', 'name': 'test.txt'}

        args = MagicMock()
        args.source = str(test_file)
        args.dest = "/Documents"
        args.recursive = False
        args.overwrite = False

        files.cmd_upload(args)

        captured = capsys.readouterr()
        assert "Uploaded" in captured.out or "test.txt" in captured.out


class TestFormatFileSize:
    """Tests for format_file_size helper function"""

    def test_format_bytes(self):
        """Test formatting bytes"""
        result = files.format_file_size(500)
        assert "500B" in result or "500 B" in result

    def test_format_kilobytes(self):
        """Test formatting kilobytes"""
        result = files.format_file_size(2048)
        assert "2" in result and "KB" in result

    def test_format_megabytes(self):
        """Test formatting megabytes"""
        result = files.format_file_size(5242880)
        assert "5" in result and "MB" in result

    def test_format_gigabytes(self):
        """Test formatting gigabytes"""
        result = files.format_file_size(1073741824)
        assert "1" in result and "GB" in result
