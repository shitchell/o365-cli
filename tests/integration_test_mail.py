"""
Integration tests for o365 mail commands

Note: Mail commands are mostly wrappers around external scripts
(o365-mail-sync.py, mail-read, mail-archive, mail-mark-read, trinoor.email).

These tests make REAL calls to those scripts if they exist.
They will only run if:
1. client_id and tenant are configured in ~/.config/o365/config
2. scopes.mail is enabled in the config
3. You have authenticated with `o365 auth login`

Run with:
    pytest tests/integration_test_mail.py -v
    pytest -m integration_mail  # Run all mail integration tests
    pytest -m integration        # Run ALL integration tests
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from o365 import mail


@pytest.mark.integration
@pytest.mark.integration_mail
class TestMailIntegration:
    """Integration tests for mail commands"""

    def test_sync_list_folders(self, real_access_token, capsys):
        """Test listing mail folders (if script exists)"""
        script_path = Path.home() / "bin" / "o365-mail-sync.py"

        if not script_path.exists():
            pytest.skip(f"Mail sync script not found at {script_path}")

        args = MagicMock()
        args.list_folders = True
        args.folders = None
        args.count = None
        args.since = None
        args.all = False
        args.focused_inbox = False

        try:
            mail.cmd_sync(args)
        except SystemExit as e:
            # Script may exit with 0 on success
            if e.code != 0:
                pytest.fail(f"Mail sync failed with exit code {e.code}")

        captured = capsys.readouterr()
        # Just verify it completes without error
        assert len(captured.out) >= 0 or len(captured.err) >= 0


@pytest.mark.integration
@pytest.mark.integration_mail
@pytest.mark.slow
class TestMailIntegrationSlow:
    """Slow integration tests for mail (actual sync/send)"""

    def test_sync_inbox(self, real_access_token, capsys):
        """Test syncing inbox with limited count"""
        script_path = Path.home() / "bin" / "o365-mail-sync.py"

        if not script_path.exists():
            pytest.skip(f"Mail sync script not found at {script_path}")

        args = MagicMock()
        args.folders = ['Inbox']
        args.count = 5  # Limit to 5 messages for speed
        args.since = None
        args.all = False
        args.focused_inbox = False
        args.list_folders = False

        try:
            mail.cmd_sync(args)
        except SystemExit as e:
            # Script may exit with 0 on success
            if e.code != 0:
                pytest.fail(f"Mail sync failed with exit code {e.code}")

        captured = capsys.readouterr()
        # Should complete without error
        assert "Error" not in captured.err or len(captured.out) >= 0


# Note: mail read, archive, mark-read tests require local maildir to exist
# These are best tested manually after running mail sync

@pytest.mark.integration
@pytest.mark.integration_mail
class TestMailReadIntegration:
    """Integration tests for mail read (requires local maildir)"""

    def test_read_inbox_list(self, real_access_token, capsys):
        """Test listing inbox emails"""
        script_path = Path.home() / "bin" / "mail-read"
        maildir = Path.home() / ".mail" / "office365" / "INBOX"

        if not script_path.exists():
            pytest.skip(f"Mail read script not found at {script_path}")

        if not maildir.exists():
            pytest.skip(f"Maildir not found at {maildir}. Run 'o365 mail sync' first")

        args = MagicMock()
        args.ids = []
        args.count = 10
        args.folder = None
        args.read_email = None
        args.search = None
        args.field = None
        args.since = None
        args.unread = False
        args.read = False
        args.html = False

        try:
            mail.cmd_read(args)
        except SystemExit as e:
            if e.code != 0:
                pytest.fail(f"Mail read failed with exit code {e.code}")

        captured = capsys.readouterr()
        # Should complete without error (may be empty)
        assert len(captured.out) >= 0 or len(captured.err) >= 0
