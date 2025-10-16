# o365-cli Tests

Comprehensive test suite for the Office365 CLI tool.

## Running Tests

### Run all tests

```bash
pytest
```

### Run specific test file

```bash
pytest tests/test_config.py
pytest tests/test_auth.py
```

### Run specific test class

```bash
pytest tests/test_config.py::TestConfigSet
```

### Run specific test

```bash
pytest tests/test_config.py::TestConfigSet::test_set_new_value
```

### Run with verbose output

```bash
pytest -v
```

### Run with coverage

```bash
pytest --cov=o365 --cov-report=term-missing
```

### Run only fast tests (exclude slow/integration tests)

```bash
pytest -m "not slow"
```

## Test Structure

The test suite is organized by module:

- `test_auth.py` - Authentication commands (login, refresh, status)
- `test_config.py` - Configuration management commands
- `test_calendar.py` - Calendar commands (list, create, delete)
- `test_contacts.py` - Contacts commands (list, search)
- `test_chat.py` - Teams chat commands (list, read, send, search)
- `test_files.py` - OneDrive/SharePoint files commands
- `test_recordings.py` - Teams meeting recordings commands
- `test_mail.py` - Mail commands (sync, read, archive, mark-read)

## Fixtures

Common test fixtures are defined in `conftest.py`:

- `temp_config_dir` - Temporary config directory
- `temp_config_file` - Temporary config file with test credentials
- `temp_token_file` - Temporary token file with test OAuth tokens
- `mock_graph_api` - Mock Graph API responses
- `mock_access_token` - Mock OAuth access token
- `sample_email` - Sample email data
- `sample_calendar_event` - Sample calendar event data
- `sample_contact` - Sample contact data
- `sample_chat` - Sample chat data
- `sample_file` - Sample file/folder data
- `sample_recording` - Sample recording data

## Test Coverage

The test suite covers:

### Commands
- ✅ All command groups (auth, config, calendar, contacts, chat, files, recordings, mail)
- ✅ All subcommands within each group
- ✅ All command-line options and flags

### Functionality
- ✅ Successful operations
- ✅ Error handling (missing files, invalid inputs, API errors)
- ✅ Edge cases (empty results, pagination, filtering)
- ✅ Configuration management
- ✅ Token refresh and expiry
- ✅ Helper functions and utilities

### Test Types
- **Unit tests**: Fast, isolated tests with mocked dependencies
- **Integration tests**: Tests that verify component interaction (marked with `@pytest.mark.integration`)
- **Slow tests**: Long-running tests (marked with `@pytest.mark.slow`)

## Writing New Tests

When adding new tests:

1. Follow the existing test structure
2. Use descriptive test names (e.g., `test_list_with_user_filter`)
3. Use fixtures for common setup
4. Mock external dependencies (API calls, file I/O)
5. Test both success and error cases
6. Add docstrings to explain what is being tested

Example test:

```python
def test_search_by_name(self, mock_access_token, capsys):
    """Test searching contacts by name"""
    args = MagicMock()
    args.query = 'john'
    args.resolve = False

    with patch('o365.contacts.search_users') as mock_search:
        mock_search.return_value = [{
            'name': 'John Doe',
            'email': 'john.doe@example.com',
            'source': 'contact'
        }]

        contacts.cmd_search(args)

    captured = capsys.readouterr()
    assert "John Doe" in captured.out
```

## Dependencies

Test dependencies are specified in `pyproject.toml` under `optional-dependencies`:

- `pytest` - Test framework
- `pytest-mock` - Mocking support for pytest (cleaner mock syntax)
- `pytest-cov` - Coverage reporting

Install test dependencies only:

```bash
pip install -e ".[test]"
```

Install all development dependencies (testing + linting/formatting):

```bash
pip install -e ".[dev]"
```

## Continuous Integration

Tests should be run in CI/CD pipelines before merging changes. Example GitHub Actions workflow:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: pip install -e ".[dev]"
      - run: pytest -v
```
