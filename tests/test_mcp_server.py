"""
Tests for MCP Server

Tests all 20 MCP tools to ensure they correctly call the underlying
structured data functions and handle errors appropriately.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


# Skip all tests if MCP SDK not installed
pytest.importorskip("mcp")

from o365 import mcp_server


class TestEmailTools:
    """Tests for email-related MCP tools"""

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_messages_structured')
    def test_read_emails_basic(self, mock_get_messages, mock_get_token):
        """Test read_emails with basic parameters"""
        mock_get_token.return_value = 'fake_token'
        mock_get_messages.return_value = [
            {'id': '1', 'subject': 'Test Email', 'from_email': 'test@example.com'}
        ]

        result = mcp_server.read_emails(folder='Inbox', limit=10)

        assert result['status'] == 'success'
        assert result['count'] == 1
        assert len(result['messages']) == 1
        mock_get_messages.assert_called_once()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_messages_structured')
    def test_read_emails_with_filters(self, mock_get_messages, mock_get_token):
        """Test read_emails with unread filter and since parameter"""
        mock_get_token.return_value = 'fake_token'
        mock_get_messages.return_value = []

        result = mcp_server.read_emails(
            folder='Inbox',
            unread=True,
            since='2 days ago',
            limit=5
        )

        assert result['status'] == 'success'
        assert result['count'] == 0
        mock_get_messages.assert_called_once()
        # Verify since was parsed to datetime
        call_args = mock_get_messages.call_args
        assert call_args[1]['since'] is not None
        assert isinstance(call_args[1]['since'], datetime)

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_messages_structured')
    def test_read_emails_invalid_since(self, mock_get_messages, mock_get_token):
        """Test read_emails with invalid since parameter"""
        mock_get_token.return_value = 'fake_token'

        result = mcp_server.read_emails(since='invalid date')

        assert result['status'] == 'error'
        assert 'Invalid since parameter' in result['error']
        mock_get_messages.assert_not_called()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_message_by_id_structured')
    def test_get_email_content(self, mock_get_message, mock_get_token):
        """Test get_email_content"""
        mock_get_token.return_value = 'fake_token'
        mock_get_message.return_value = {
            'id': 'msg123',
            'subject': 'Test',
            'body_content': 'Body text'
        }

        result = mcp_server.get_email_content(message_id='msg123')

        assert result['status'] == 'success'
        assert result['message']['id'] == 'msg123'
        mock_get_message.assert_called_once_with('fake_token', 'msg123')

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_message_by_id_structured')
    def test_get_email_content_not_found(self, mock_get_message, mock_get_token):
        """Test get_email_content when email not found"""
        mock_get_token.return_value = 'fake_token'
        mock_get_message.return_value = None

        result = mcp_server.get_email_content(message_id='invalid')

        assert result['status'] == 'error'
        assert 'not found' in result['error']

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.send_email_structured')
    def test_send_email(self, mock_send, mock_get_token):
        """Test send_email"""
        mock_get_token.return_value = 'fake_token'
        mock_send.return_value = {'status': 'success', 'message': 'Email sent'}

        result = mcp_server.send_email(
            to=['recipient@example.com'],
            subject='Test',
            body='Test body',
            cc=['cc@example.com']
        )

        assert result['status'] == 'success'
        mock_send.assert_called_once()


class TestCalendarTools:
    """Tests for calendar-related MCP tools"""

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_events_structured')
    def test_list_calendar_events_default(self, mock_get_events, mock_get_token):
        """Test list_calendar_events with default parameters"""
        mock_get_token.return_value = 'fake_token'
        mock_get_events.return_value = [
            {'id': 'evt1', 'subject': 'Meeting 1'},
            {'id': 'evt2', 'subject': 'Meeting 2'}
        ]

        result = mcp_server.list_calendar_events()

        assert result['status'] == 'success'
        assert result['count'] == 2
        mock_get_events.assert_called_once()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_events_structured')
    def test_list_calendar_events_with_dates(self, mock_get_events, mock_get_token):
        """Test list_calendar_events with start and end dates"""
        mock_get_token.return_value = 'fake_token'
        mock_get_events.return_value = []

        result = mcp_server.list_calendar_events(
            start_date='today',
            end_date='tomorrow'
        )

        assert result['status'] == 'success'
        mock_get_events.assert_called_once()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.create_event_structured')
    def test_create_calendar_event(self, mock_create, mock_get_token):
        """Test create_calendar_event"""
        mock_get_token.return_value = 'fake_token'
        mock_create.return_value = {
            'status': 'success',
            'event': {'id': 'new_evt', 'subject': 'New Meeting'}
        }

        result = mcp_server.create_calendar_event(
            title='New Meeting',
            start_time='tomorrow at 2pm',
            duration='1h',
            required_attendees=['attendee@example.com']
        )

        assert result['status'] == 'success'
        assert result['event']['subject'] == 'New Meeting'
        mock_create.assert_called_once()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.delete_event_structured')
    def test_delete_calendar_event(self, mock_delete, mock_get_token):
        """Test delete_calendar_event"""
        mock_get_token.return_value = 'fake_token'
        mock_delete.return_value = {
            'status': 'success',
            'message': 'Event deleted'
        }

        result = mcp_server.delete_calendar_event(event_id='evt123')

        assert result['status'] == 'success'
        mock_delete.assert_called_once_with('fake_token', 'evt123')


class TestFilesTools:
    """Tests for OneDrive/files-related MCP tools"""

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.list_files_structured')
    def test_list_onedrive_files(self, mock_list_files, mock_get_token):
        """Test list_onedrive_files"""
        mock_get_token.return_value = 'fake_token'
        mock_list_files.return_value = [
            {'id': 'file1', 'name': 'document.pdf', 'type': 'file'},
            {'id': 'folder1', 'name': 'Documents', 'type': 'folder'}
        ]

        result = mcp_server.list_onedrive_files(path='/Documents')

        assert result['status'] == 'success'
        assert result['count'] == 2
        mock_list_files.assert_called_once()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.search_files_structured')
    def test_search_onedrive(self, mock_search, mock_get_token):
        """Test search_onedrive"""
        mock_get_token.return_value = 'fake_token'
        mock_search.return_value = [
            {'id': 'file1', 'name': 'budget.xlsx'}
        ]

        result = mcp_server.search_onedrive(
            query='budget',
            file_type='xlsx',
            count=10
        )

        assert result['status'] == 'success'
        assert result['count'] == 1
        mock_search.assert_called_once()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.download_file_structured')
    def test_download_onedrive_file(self, mock_download, mock_get_token):
        """Test download_onedrive_file"""
        mock_get_token.return_value = 'fake_token'
        mock_download.return_value = {
            'status': 'success',
            'file_path': '/tmp/document.pdf'
        }

        result = mcp_server.download_onedrive_file(
            item_id='file123',
            dest_path='/tmp'
        )

        assert result['status'] == 'success'
        mock_download.assert_called_once()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.upload_file_structured')
    def test_upload_onedrive_file(self, mock_upload, mock_get_token):
        """Test upload_onedrive_file"""
        mock_get_token.return_value = 'fake_token'
        mock_upload.return_value = {
            'status': 'success',
            'item': {'id': 'new_file', 'name': 'uploaded.pdf'}
        }

        result = mcp_server.upload_onedrive_file(
            source_path='/tmp/local.pdf',
            dest_path='/Documents/uploaded.pdf'
        )

        assert result['status'] == 'success'
        mock_upload.assert_called_once()


class TestChatTools:
    """Tests for Teams chat-related MCP tools"""

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_chats_structured')
    def test_list_teams_chats(self, mock_get_chats, mock_get_token):
        """Test list_teams_chats"""
        mock_get_token.return_value = 'fake_token'
        mock_get_chats.return_value = [
            {'id': 'chat1', 'display_name': 'Chat with Alice'},
            {'id': 'chat2', 'display_name': 'Team Group'}
        ]

        result = mcp_server.list_teams_chats(count=50)

        assert result['status'] == 'success'
        assert result['count'] == 2
        mock_get_chats.assert_called_once_with('fake_token', count=50)

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_chat_messages_structured')
    def test_read_chat_messages(self, mock_get_messages, mock_get_token):
        """Test read_chat_messages"""
        mock_get_token.return_value = 'fake_token'
        mock_get_messages.return_value = [
            {'id': 'msg1', 'content': 'Hello', 'sender_name': 'Alice'}
        ]

        result = mcp_server.read_chat_messages(
            chat_id='chat123',
            count=10
        )

        assert result['status'] == 'success'
        assert result['count'] == 1
        mock_get_messages.assert_called_once()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.send_message_structured')
    def test_send_chat_message(self, mock_send, mock_get_token):
        """Test send_chat_message"""
        mock_get_token.return_value = 'fake_token'
        mock_send.return_value = {
            'status': 'success',
            'message_id': 'new_msg'
        }

        result = mcp_server.send_chat_message(
            chat_id='chat123',
            content='Hello there!'
        )

        assert result['status'] == 'success'
        mock_send.assert_called_once_with('fake_token', 'chat123', 'Hello there!')

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.search_messages_structured')
    def test_search_teams_messages(self, mock_search, mock_get_token):
        """Test search_teams_messages"""
        mock_get_token.return_value = 'fake_token'
        mock_search.return_value = [
            {'chat_id': 'chat1', 'content': 'project update'}
        ]

        result = mcp_server.search_teams_messages(
            query='project',
            count=20
        )

        assert result['status'] == 'success'
        assert result['count'] == 1
        mock_search.assert_called_once()


class TestContactsTools:
    """Tests for contacts-related MCP tools"""

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.search_users_structured')
    def test_search_contacts(self, mock_search, mock_get_token):
        """Test search_contacts"""
        mock_get_token.return_value = 'fake_token'
        mock_search.return_value = [
            {'name': 'John Doe', 'email': 'john@example.com'}
        ]

        result = mcp_server.search_contacts(query='john')

        assert result['status'] == 'success'
        assert result['count'] == 1
        mock_search.assert_called_once_with('fake_token', 'john')

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_contacts_structured')
    def test_list_contacts(self, mock_get_contacts, mock_get_token):
        """Test list_contacts"""
        mock_get_token.return_value = 'fake_token'
        mock_get_contacts.return_value = [
            {'name': 'Alice', 'email': 'alice@example.com'},
            {'name': 'Bob', 'email': 'bob@example.com'}
        ]

        result = mcp_server.list_contacts()

        assert result['status'] == 'success'
        assert result['count'] == 2
        mock_get_contacts.assert_called_once_with('fake_token')


class TestRecordingsTools:
    """Tests for recordings-related MCP tools"""

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.list_recordings_structured')
    def test_list_recordings(self, mock_list_recs, mock_get_token):
        """Test list_recordings"""
        mock_get_token.return_value = 'fake_token'
        mock_list_recs.return_value = [
            {'id': 'rec1', 'name': 'Meeting Recording.mp4'}
        ]

        result = mcp_server.list_recordings(count=10)

        assert result['status'] == 'success'
        assert result['count'] == 1
        mock_list_recs.assert_called_once()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.search_recordings_structured')
    def test_search_recordings(self, mock_search, mock_get_token):
        """Test search_recordings"""
        mock_get_token.return_value = 'fake_token'
        mock_search.return_value = []

        result = mcp_server.search_recordings(query='standup', count=5)

        assert result['status'] == 'success'
        assert result['count'] == 0
        mock_search.assert_called_once()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.download_recording_structured')
    def test_download_recording(self, mock_download, mock_get_token):
        """Test download_recording"""
        mock_get_token.return_value = 'fake_token'
        mock_download.return_value = {
            'status': 'success',
            'file_path': '/tmp/recording.mp4'
        }

        result = mcp_server.download_recording(
            recording_id='rec123',
            dest_path='/tmp'
        )

        assert result['status'] == 'success'
        mock_download.assert_called_once()

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_transcript_structured')
    def test_get_recording_transcript(self, mock_get_transcript, mock_get_token):
        """Test get_recording_transcript"""
        mock_get_token.return_value = 'fake_token'
        mock_get_transcript.return_value = {
            'status': 'success',
            'has_transcript': True,
            'entries': [{'timestamp': '00:00:10', 'text': 'Hello'}]
        }

        result = mcp_server.get_recording_transcript(recording_id='rec123')

        assert result['status'] == 'success'
        assert result['has_transcript'] is True
        mock_get_transcript.assert_called_once_with('fake_token', 'rec123')


class TestErrorHandling:
    """Tests for error handling across all tools"""

    @patch('o365.mcp_server.get_access_token')
    def test_email_tool_exception(self, mock_get_token):
        """Test that exceptions are caught and returned as error status"""
        mock_get_token.side_effect = Exception('Auth failed')

        result = mcp_server.read_emails()

        assert result['status'] == 'error'
        assert 'Auth failed' in result['error']

    @patch('o365.mcp_server.get_access_token')
    @patch('o365.mcp_server.get_events_structured')
    def test_calendar_tool_exception(self, mock_get_events, mock_get_token):
        """Test exception handling in calendar tools"""
        mock_get_token.return_value = 'fake_token'
        mock_get_events.side_effect = Exception('Graph API error')

        result = mcp_server.list_calendar_events()

        assert result['status'] == 'error'
        assert 'Graph API error' in result['error']


class TestMCPServerInit:
    """Tests for MCP server initialization"""

    def test_mcp_server_exists(self):
        """Test that MCP server object exists"""
        assert hasattr(mcp_server, 'mcp')
        assert mcp_server.mcp is not None

    def test_mcp_server_has_tools(self):
        """Test MCP server has decorated tool functions"""
        # Verify some key tools exist as functions
        assert callable(mcp_server.read_emails)
        assert callable(mcp_server.list_calendar_events)
        assert callable(mcp_server.list_onedrive_files)
        assert callable(mcp_server.list_teams_chats)
        assert callable(mcp_server.search_contacts)
