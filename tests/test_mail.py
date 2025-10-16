"""
Tests for o365 mail commands
"""

import pytest
from unittest.mock import patch, MagicMock
from o365 import mail


class TestMailSync:
    """Tests for 'o365 mail sync' command"""

    def test_sync_default_folders(self, mock_access_token, mock_graph_api, sample_email, capsys):
        """Test syncing default folders"""
        mock_graph_api.return_value = {'value': [sample_email]}

        args = MagicMock()
        args.folders = None
        args.count = None
        args.since = None
        args.all = False
        args.focused_inbox = False
        args.list_folders = False

        with patch('o365.mail.MAIL_DIR') as mock_mail_dir:
            mock_mail_dir.mkdir = MagicMock()
            with patch('o365.mail.save_email_to_maildir'):
                mail.cmd_sync(args)

        captured = capsys.readouterr()
        assert "Syncing" in captured.out or "messages" in captured.out

    def test_sync_specific_folders(self, mock_access_token, mock_graph_api, sample_email, capsys):
        """Test syncing specific folders"""
        mock_graph_api.return_value = {'value': [sample_email]}

        args = MagicMock()
        args.folders = ["Inbox", "Sent"]
        args.count = None
        args.since = None
        args.all = False
        args.focused_inbox = False
        args.list_folders = False

        with patch('o365.mail.MAIL_DIR') as mock_mail_dir:
            mock_mail_dir.mkdir = MagicMock()
            with patch('o365.mail.save_email_to_maildir'):
                mail.cmd_sync(args)

        captured = capsys.readouterr()
        assert "Inbox" in captured.out or "Syncing" in captured.out

    def test_sync_list_folders(self, mock_access_token, mock_graph_api, capsys):
        """Test listing available folders"""
        mock_graph_api.return_value = {
            'value': [
                {'displayName': 'Inbox', 'id': 'inbox-id'},
                {'displayName': 'Sent Items', 'id': 'sent-id'}
            ]
        }

        args = MagicMock()
        args.list_folders = True

        mail.cmd_sync(args)

        captured = capsys.readouterr()
        assert "Inbox" in captured.out
        assert "Sent Items" in captured.out


class TestMailRead:
    """Tests for 'o365 mail read' command"""

    def test_read_recent_emails(self, capsys):
        """Test reading recent emails from local maildir"""
        args = MagicMock()
        args.email_ids = []
        args.count = 10
        args.folder = "INBOX"
        args.read_email = None
        args.search = None
        args.field = "subject"
        args.since = None
        args.unread = False
        args.read = False
        args.html = False

        with patch('o365.mail.MAIL_DIR') as mock_mail_dir:
            mock_mail_dir.__truediv__ = lambda self, x: MagicMock()
            with patch('o365.mail.get_emails_from_maildir') as mock_get:
                mock_get.return_value = []
                mail.cmd_read(args)

        captured = capsys.readouterr()
        assert "INBOX" in captured.out or "No" in captured.out

    def test_read_unread_only(self, capsys):
        """Test reading only unread emails"""
        args = MagicMock()
        args.email_ids = []
        args.count = 10
        args.folder = "INBOX"
        args.read_email = None
        args.search = None
        args.field = "subject"
        args.since = None
        args.unread = True
        args.read = False
        args.html = False

        with patch('o365.mail.MAIL_DIR'):
            with patch('o365.mail.get_emails_from_maildir') as mock_get:
                mock_get.return_value = []
                mail.cmd_read(args)

        captured = capsys.readouterr()
        assert "unread" in captured.out.lower() or "No" in captured.out

    def test_read_by_id(self, capsys):
        """Test reading specific email by ID"""
        args = MagicMock()
        args.email_ids = ["test-email-id"]
        args.count = 10
        args.folder = "INBOX"
        args.read_email = None
        args.search = None
        args.field = "subject"
        args.since = None
        args.unread = False
        args.read = False
        args.html = False

        with patch('o365.mail.MAIL_DIR'):
            with patch('o365.mail.find_email_by_id') as mock_find:
                mock_find.return_value = None
                mail.cmd_read(args)

        # Should handle email not found gracefully
        captured = capsys.readouterr()


class TestMailArchive:
    """Tests for 'o365 mail archive' command"""

    def test_archive_emails(self, mock_access_token, mock_graph_api, capsys):
        """Test archiving emails"""
        args = MagicMock()
        args.email_ids = ["email-1", "email-2"]
        args.dry_run = False

        with patch('o365.mail.MAIL_DIR'):
            with patch('o365.mail.find_email_by_id') as mock_find:
                mock_find.return_value = ("/path/to/email", {"message-id": "<test>"})
                with patch('o365.mail.move_email_to_archive'):
                    mail.cmd_archive(args)

        captured = capsys.readouterr()
        assert "Archived" in captured.out or "archive" in captured.out.lower()

    def test_archive_dry_run(self, mock_access_token, capsys):
        """Test archive in dry-run mode"""
        args = MagicMock()
        args.email_ids = ["email-1"]
        args.dry_run = True

        with patch('o365.mail.MAIL_DIR'):
            with patch('o365.mail.find_email_by_id') as mock_find:
                mock_find.return_value = ("/path/to/email", {"subject": "Test"})
                mail.cmd_archive(args)

        captured = capsys.readouterr()
        assert "Would archive" in captured.out or "DRY RUN" in captured.out


class TestMailMarkRead:
    """Tests for 'o365 mail mark-read' command"""

    def test_mark_read(self, mock_access_token, mock_graph_api, capsys):
        """Test marking emails as read"""
        args = MagicMock()
        args.email_ids = ["email-1", "email-2"]
        args.dry_run = False

        with patch('o365.mail.MAIL_DIR'):
            with patch('o365.mail.find_email_by_id') as mock_find:
                mock_find.return_value = ("/path/to/email", {"message-id": "<test>"})
                with patch('o365.mail.mark_email_read_locally'):
                    mail.cmd_mark_read(args)

        captured = capsys.readouterr()
        assert "Marked as read" in captured.out or "read" in captured.out.lower()

    def test_mark_read_dry_run(self, mock_access_token, capsys):
        """Test mark read in dry-run mode"""
        args = MagicMock()
        args.email_ids = ["email-1"]
        args.dry_run = True

        with patch('o365.mail.MAIL_DIR'):
            with patch('o365.mail.find_email_by_id') as mock_find:
                mock_find.return_value = ("/path/to/email", {"subject": "Test"})
                mail.cmd_mark_read(args)

        captured = capsys.readouterr()
        assert "Would mark" in captured.out or "DRY RUN" in captured.out
