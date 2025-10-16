"""
Pytest configuration and shared fixtures for o365-cli tests
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from configparser import ConfigParser


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory for testing"""
    config_dir = tmp_path / ".config" / "o365"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def temp_config_file(temp_config_dir):
    """Create a temporary config file with test credentials"""
    config_file = temp_config_dir / "config"
    parser = ConfigParser()

    parser.add_section('auth')
    parser.set('auth', 'client_id', 'test-client-id')
    parser.set('auth', 'tenant', 'test-tenant')

    parser.add_section('scopes')
    parser.set('scopes', 'mail', 'true')
    parser.set('scopes', 'calendar', 'true')
    parser.set('scopes', 'contacts', 'true')
    parser.set('scopes', 'chat', 'true')
    parser.set('scopes', 'files', 'true')
    parser.set('scopes', 'files.all', 'false')
    parser.set('scopes', 'sites.all', 'false')

    with open(config_file, 'w') as f:
        parser.write(f)

    return config_file


@pytest.fixture
def temp_token_file(temp_config_dir):
    """Create a temporary token file with test tokens"""
    token_file = temp_config_dir / "tokens.json"
    tokens = {
        'access_token': 'test-access-token',
        'refresh_token': 'test-refresh-token',
        'expires_in': 3600,
        '_saved_at': 1000000000
    }
    token_file.write_text(json.dumps(tokens, indent=2))
    return token_file


@pytest.fixture
def mock_config(temp_config_file, temp_token_file):
    """Mock the o365.common module config to use temp files"""
    with patch('o365.common.CONFIG_FILE', temp_config_file), \
         patch('o365.common.CONFIG_DIR', temp_config_file.parent), \
         patch('o365.common.TOKEN_FILE', temp_token_file):
        yield


@pytest.fixture
def mock_graph_api():
    """Mock Graph API responses"""
    def _make_response(data=None, status_code=200):
        """Helper to create mock response"""
        if data is None:
            data = {}
        return data

    with patch('o365.common.make_graph_request') as mock:
        mock.side_effect = lambda url, token, **kwargs: _make_response()
        yield mock


@pytest.fixture
def mock_access_token():
    """Mock get_access_token to return a test token"""
    with patch('o365.common.get_access_token') as mock:
        mock.return_value = 'test-access-token'
        yield mock


@pytest.fixture
def sample_email():
    """Sample email data from Graph API"""
    return {
        'id': 'test-email-id-123',
        'subject': 'Test Email Subject',
        'from': {
            'emailAddress': {
                'name': 'John Doe',
                'address': 'john.doe@example.com'
            }
        },
        'receivedDateTime': '2025-01-15T10:30:00Z',
        'bodyPreview': 'This is a test email body preview',
        'isRead': False,
        'hasAttachments': False
    }


@pytest.fixture
def sample_calendar_event():
    """Sample calendar event data from Graph API"""
    return {
        'id': 'test-event-id-123',
        'subject': 'Team Meeting',
        'start': {
            'dateTime': '2025-01-15T14:00:00.0000000',
            'timeZone': 'UTC'
        },
        'end': {
            'dateTime': '2025-01-15T15:00:00.0000000',
            'timeZone': 'UTC'
        },
        'location': {
            'displayName': 'Conference Room A'
        },
        'attendees': []
    }


@pytest.fixture
def sample_contact():
    """Sample contact data from Graph API"""
    return {
        'id': 'test-contact-id-123',
        'displayName': 'John Doe',
        'emailAddresses': [
            {
                'address': 'john.doe@example.com',
                'name': 'John Doe'
            }
        ]
    }


@pytest.fixture
def sample_chat():
    """Sample chat data from Graph API"""
    return {
        'id': 'test-chat-id-123',
        'topic': 'Project Discussion',
        'chatType': 'oneOnOne',
        'lastMessagePreview': {
            'createdDateTime': '2025-01-15T10:30:00Z',
            'body': {
                'content': 'Last message preview'
            },
            'from': {
                'user': {
                    'displayName': 'John Doe'
                }
            }
        },
        'members': [
            {
                'displayName': 'John Doe',
                'email': 'john.doe@example.com'
            }
        ]
    }


@pytest.fixture
def sample_file():
    """Sample file/folder data from Graph API"""
    return {
        'id': 'test-file-id-123',
        'name': 'document.pdf',
        'size': 1024,
        'createdDateTime': '2025-01-15T10:00:00Z',
        'lastModifiedDateTime': '2025-01-15T10:30:00Z',
        'file': {},  # Indicates this is a file (not a folder)
        'webUrl': 'https://example.sharepoint.com/document.pdf'
    }


@pytest.fixture
def sample_recording():
    """Sample recording file data from Graph API"""
    return {
        'id': 'test-recording-id-123',
        'name': 'Team Meeting-20250115_140000.mp4',
        'size': 157286400,  # ~150MB
        'createdDateTime': '2025-01-15T14:30:00Z',
        'lastModifiedDateTime': '2025-01-15T14:35:00Z',
        'file': {
            'mimeType': 'video/mp4'
        },
        'webUrl': 'https://example.sharepoint.com/recordings/meeting.mp4'
    }
