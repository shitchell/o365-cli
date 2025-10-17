"""
Pytest configuration and shared fixtures for o365-cli tests
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from configparser import ConfigParser
import os


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
    """Mock Graph API responses in all modules

    Returns a MagicMock that's shared across all modules.
    Tests can set mock_graph_api.return_value and it will apply to all modules.
    """
    class SynchronizedMockManager:
        """Wrapper that keeps all mocks synchronized"""
        def __init__(self, mocks):
            self.mocks = mocks
            self._return_value = {}
            self._side_effect = None

        @property
        def return_value(self):
            return self._return_value

        @return_value.setter
        def return_value(self, value):
            self._return_value = value
            for mock in self.mocks:
                mock.return_value = value
                mock.side_effect = None  # Clear side_effect when setting return_value

        @property
        def side_effect(self):
            return self._side_effect

        @side_effect.setter
        def side_effect(self, value):
            self._side_effect = value
            for mock in self.mocks:
                mock.side_effect = value

        def __getattr__(self, name):
            # Delegate other attributes to the first mock
            return getattr(self.mocks[0], name)

    with patch('o365.common.make_graph_request') as mock_common, \
         patch('o365.files.make_graph_request') as mock_files, \
         patch('o365.calendar.make_graph_request') as mock_calendar, \
         patch('o365.contacts.make_graph_request') as mock_contacts, \
         patch('o365.chat.make_graph_request') as mock_chat, \
         patch('o365.recordings.make_graph_request') as mock_recordings:

        all_mocks = [mock_common, mock_files, mock_calendar, mock_contacts, mock_chat, mock_recordings]

        # Set all to return empty dict by default
        for mock in all_mocks:
            mock.return_value = {}

        manager = SynchronizedMockManager(all_mocks)
        yield manager


@pytest.fixture
def mock_access_token():
    """Mock get_access_token to return a test token in all modules"""
    with patch('o365.common.get_access_token') as mock_common, \
         patch('o365.files.get_access_token') as mock_files, \
         patch('o365.calendar.get_access_token') as mock_calendar, \
         patch('o365.contacts.get_access_token') as mock_contacts, \
         patch('o365.chat.get_access_token') as mock_chat, \
         patch('o365.recordings.get_access_token') as mock_recordings:
        # Set all to return test token
        for mock in [mock_common, mock_files, mock_calendar, mock_contacts, mock_chat, mock_recordings]:
            mock.return_value = 'test-access-token'
        yield mock_common


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
    from datetime import datetime, timezone
    # Use current time so --since filters work correctly
    now = datetime.now(timezone.utc)
    now_str = now.strftime('%Y-%m-%dT%H:%M:%SZ')

    return {
        'id': 'test-recording-id-123',
        'name': 'Team Meeting-20250115_140000.mp4',
        'size': 157286400,  # ~150MB
        'createdDateTime': now_str,
        'lastModifiedDateTime': now_str,
        'file': {
            'mimeType': 'video/mp4'
        },
        'parentReference': {
            'path': '/drives/xxx/root:/Recordings'
        },
        'webUrl': 'https://example.sharepoint.com/recordings/meeting.mp4'
    }


# ============================================================================
# Integration Test Support
# ============================================================================

def _check_config_has_scope(scope_name):
    """Check if a specific scope is enabled in the real config"""
    from o365.common import CONFIG_FILE
    if not CONFIG_FILE.exists():
        return False

    parser = ConfigParser()
    parser.read(CONFIG_FILE)

    # Check if scope is enabled (default to true if not specified)
    return parser.getboolean('scopes', scope_name, fallback=True)


def _is_integration_configured():
    """Check if integration tests can run (client_id and tenant are set)"""
    from o365.common import CONFIG_FILE
    if not CONFIG_FILE.exists():
        return False

    parser = ConfigParser()
    parser.read(CONFIG_FILE)

    # Check if both client_id and tenant are configured
    has_client = parser.has_option('auth', 'client_id') and parser.get('auth', 'client_id')
    has_tenant = parser.has_option('auth', 'tenant') and parser.get('auth', 'tenant')

    return has_client and has_tenant


# Global test directory for cleanup
_TEST_DIR = None

# Pytest markers for conditional test execution
def pytest_configure(config):
    """Register custom markers and set up test isolation"""
    global _TEST_DIR

    # IMPORTANT: Set test environment variables BEFORE any o365 modules are imported
    # This prevents tests from using the user's real config/token files
    import tempfile
    import shutil
    _TEST_DIR = Path(tempfile.mkdtemp(prefix="o365-test-"))

    # Copy real config and tokens to test directory (for integration tests)
    real_config_dir = Path.home() / ".config" / "o365"
    real_config_file = real_config_dir / "config"
    real_token_file = real_config_dir / "tokens.json"

    test_config_file = _TEST_DIR / "config"
    test_token_file = _TEST_DIR / "test-tokens.json"

    if real_config_file.exists():
        shutil.copy2(real_config_file, test_config_file)
        print(f"\n✓ Copied real config to test directory: {test_config_file}")

    if real_token_file.exists():
        shutil.copy2(real_token_file, test_token_file)
        print(f"✓ Copied real tokens to test directory: {test_token_file}")

    # Override o365 paths to use test directory
    os.environ['O365_CONFIG_DIR'] = str(_TEST_DIR)
    os.environ['O365_TOKEN_FILE'] = str(test_token_file)
    os.environ['O365_MAIL_DIR'] = str(_TEST_DIR / 'mail')

    # Set dummy credentials for unit tests (integration tests will use copied config)
    if not os.environ.get('O365_CLIENT_ID'):
        os.environ['O365_CLIENT_ID'] = 'test-client-id-unit-tests'
    if not os.environ.get('O365_TENANT'):
        os.environ['O365_TENANT'] = 'test-tenant-unit-tests'

    config.addinivalue_line(
        "markers", "integration: Integration tests that make real API calls (run only if configured)"
    )
    config.addinivalue_line(
        "markers", "integration_mail: Integration tests for mail (requires mail scope)"
    )
    config.addinivalue_line(
        "markers", "integration_calendar: Integration tests for calendar (requires calendar scope)"
    )
    config.addinivalue_line(
        "markers", "integration_contacts: Integration tests for contacts (requires contacts scope)"
    )
    config.addinivalue_line(
        "markers", "integration_chat: Integration tests for chat (requires chat scope)"
    )
    config.addinivalue_line(
        "markers", "integration_files: Integration tests for files (requires files scope)"
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests if not configured"""
    skip_integration = pytest.mark.skip(reason="Integration tests require client_id and tenant in config")
    skip_mail = pytest.mark.skip(reason="Mail integration tests require mail scope enabled in config")
    skip_calendar = pytest.mark.skip(reason="Calendar integration tests require calendar scope enabled in config")
    skip_contacts = pytest.mark.skip(reason="Contacts integration tests require contacts scope enabled in config")
    skip_chat = pytest.mark.skip(reason="Chat integration tests require chat scope enabled in config")
    skip_files = pytest.mark.skip(reason="Files integration tests require files scope enabled in config")

    is_configured = _is_integration_configured()

    for item in items:
        # Check for integration marker
        if "integration" in item.keywords:
            if not is_configured:
                item.add_marker(skip_integration)
                continue

            # Check scope-specific markers
            if "integration_mail" in item.keywords and not _check_config_has_scope('mail'):
                item.add_marker(skip_mail)
            elif "integration_calendar" in item.keywords and not _check_config_has_scope('calendar'):
                item.add_marker(skip_calendar)
            elif "integration_contacts" in item.keywords and not _check_config_has_scope('contacts'):
                item.add_marker(skip_contacts)
            elif "integration_chat" in item.keywords and not _check_config_has_scope('chat'):
                item.add_marker(skip_chat)
            elif "integration_files" in item.keywords and not _check_config_has_scope('files'):
                item.add_marker(skip_files)


def pytest_unconfigure(config):
    """Clean up test directory after tests complete"""
    global _TEST_DIR

    if _TEST_DIR and _TEST_DIR.exists():
        import shutil
        try:
            shutil.rmtree(_TEST_DIR)
            print(f"\n✓ Cleaned up test directory: {_TEST_DIR}")
        except Exception as e:
            print(f"\n⚠ Warning: Could not clean up test directory {_TEST_DIR}: {e}")


@pytest.fixture
def real_access_token():
    """Get a real access token for integration tests"""
    from o365.common import get_access_token
    return get_access_token()


@pytest.fixture
def skip_if_no_integration():
    """Fixture to skip test if integration is not configured"""
    if not _is_integration_configured():
        pytest.skip("Integration tests require client_id and tenant in config")
