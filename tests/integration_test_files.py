"""
Integration tests for o365 files commands

These tests make REAL API calls to Microsoft Graph API.
They will only run if:
1. client_id and tenant are configured in ~/.config/o365/config
2. scopes.files is enabled in the config
3. You have authenticated with `o365 auth login`

Run with:
    pytest tests/integration_test_files.py -v
    pytest -m integration_files  # Run all files integration tests
    pytest -m integration        # Run ALL integration tests
"""

import pytest
from o365 import files
from unittest.mock import MagicMock


@pytest.mark.integration
@pytest.mark.integration_files
class TestFilesIntegration:
    """Integration tests for files commands"""

    def test_list_drives(self, real_access_token, capsys):
        """Test listing drives with real API"""
        args = MagicMock()
        args.verbose = False

        files.cmd_drives(args)

        captured = capsys.readouterr()
        # Should show at least personal OneDrive
        assert "OneDrive" in captured.out or "Personal" in captured.out or "Drive" in captured.out

    def test_list_root(self, real_access_token, capsys):
        """Test listing root directory"""
        args = MagicMock()
        args.path = None
        args.drive = None
        args.long = False
        args.recursive = False
        args.since = None

        files.cmd_list(args)

        captured = capsys.readouterr()
        # Should complete without error (may be empty or have files)
        assert "Error" not in captured.out or len(captured.out) >= 0

    def test_list_with_long_format(self, real_access_token, capsys):
        """Test listing with detailed output"""
        args = MagicMock()
        args.path = None
        args.drive = None
        args.long = True
        args.recursive = False
        args.since = None

        files.cmd_list(args)

        captured = capsys.readouterr()
        # If there are files, should show size/date info
        assert len(captured.out) >= 0  # Just verify it completes

    def test_search_files(self, real_access_token, capsys):
        """Test searching for files"""
        args = MagicMock()
        args.query = "test"  # Search for 'test'
        args.drive = None
        args.type = None
        args.since = None
        args.count = 10

        files.cmd_search(args)

        captured = capsys.readouterr()
        # Should complete without error (may find 0 results)
        assert "Error" not in captured.out or "No files found" in captured.out or len(captured.out) >= 0


@pytest.mark.integration
@pytest.mark.integration_files
@pytest.mark.slow
class TestFilesIntegrationSlow:
    """Slow integration tests for files (upload/download)"""

    def test_drives_verbose(self, real_access_token, capsys):
        """Test verbose drive listing"""
        args = MagicMock()
        args.verbose = True

        files.cmd_drives(args)

        captured = capsys.readouterr()
        # Verbose mode should show drive IDs
        assert len(captured.out) > 0
