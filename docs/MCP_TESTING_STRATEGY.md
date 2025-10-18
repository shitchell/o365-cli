# MCP Testing Strategy - Preserving CLI Functionality

## Critical Goal: **ZERO REGRESSIONS**

The #1 priority during MCP implementation is to ensure that **no existing CLI functionality breaks**. This document outlines the testing strategy to guarantee this.

---

## Current Test Baseline (2025-10-18)

**Established Baseline:**
```
✅ 66 PASSING tests
❌ 39 FAILING tests (pre-existing failures, not regressions)
```

**Our commitment:**
- ✅ Keep all 66 passing tests passing
- 🎯 Don't introduce new failures
- 📈 Optionally fix some of the 39 existing failures
- ➕ Add new tests for MCP functionality

---

## Testing Phases

### Phase 0: Baseline Establishment ✅ COMPLETED

**Status:** ✅ Done (see results above)

**Commands run:**
```bash
pip install -e ".[dev]"
python -m pytest tests/ -v --tb=short
```

**Baseline recorded:**
- Total tests: 105
- Passing: 66
- Failing: 39 (pre-existing)

**Baseline file saved:** `docs/test-baseline-2025-10-18.txt`

---

### Phase 1: Pre-Refactoring Testing

**BEFORE making ANY code changes**, establish a detailed baseline.

#### 1.1 Run Full Test Suite
```bash
# Run all tests with verbose output
python -m pytest tests/ -v > test-results-baseline.txt

# Run with coverage
python -m pytest tests/ --cov=o365 --cov-report=html --cov-report=term

# Save coverage report
open htmlcov/index.html  # Review current coverage
```

#### 1.2 Identify Critical Passing Tests

**Calendar tests (17 passing):**
- ✅ All calendar list tests
- ✅ All calendar create tests
- ✅ All calendar delete tests
- ✅ All date parsing tests

**Config tests (18 passing):**
- ✅ All config list/get/set/unset tests
- ⚠️ 2 failing: `test_edit_*` (subprocess issue)

**Contacts tests (10 passing):**
- ✅ Most search tests
- ⚠️ 1 failing: `test_search_case_insensitive`

**Chat tests (4 passing):**
- ✅ Basic list/send tests
- ⚠️ 5 failing: user resolution issues

**Files tests (0 passing):**
- ⚠️ ALL FAILING (10 tests) - KeyError issues, missing functions

**Mail tests (0 passing):**
- ⚠️ ALL FAILING (9 tests) - MAIL_DIR attribute missing

**Recordings tests (10 passing):**
- ✅ All recordings tests passing

**Auth tests (0 passing):**
- ⚠️ ALL FAILING (7 tests) - Mocking issues

#### 1.3 Create Test Safety Net

**Create a "known good" test suite:**
```bash
# Run only passing tests
python -m pytest tests/test_calendar.py tests/test_config.py tests/test_contacts.py tests/test_recordings.py -v

# Save this as our "regression test suite"
```

**Mark critical tests:**
```python
# In tests, add markers for critical tests
@pytest.mark.critical  # Must not break
@pytest.mark.regression  # Run on every change
```

---

### Phase 2: During Refactoring - Continuous Testing

**CRITICAL RULE:** Run tests after **EVERY** module refactored.

#### 2.1 Mail Module Refactoring

**Before:**
```bash
# Run mail tests (even though they're failing)
python -m pytest tests/test_mail.py -v
```

**After refactoring:**
```bash
# 1. Run mail tests
python -m pytest tests/test_mail.py -v

# 2. Run FULL test suite (check for side effects)
python -m pytest tests/ -v

# 3. Verify 66 passing tests still pass
python -m pytest tests/test_calendar.py tests/test_config.py tests/test_contacts.py tests/test_recordings.py -v

# 4. Test actual CLI command
o365 mail read --unread --limit 5
o365 mail read --since "2 days ago"
```

**Acceptance criteria:**
- ✅ All 66 baseline passing tests still pass
- ✅ No new failures introduced
- ✅ CLI commands work as before
- ✅ New `get_messages_structured()` tests pass

#### 2.2 Calendar Module Refactoring

**Before:**
```bash
python -m pytest tests/test_calendar.py -v
# Should show 17 passing
```

**After refactoring:**
```bash
# 1. Calendar tests must ALL still pass
python -m pytest tests/test_calendar.py -v
# MUST show 17 passing, 0 new failures

# 2. Full suite
python -m pytest tests/ -v

# 3. Manual CLI testing
o365 calendar list --today
o365 calendar list --week
o365 calendar create "Test Meeting" "2025-10-20 14:00" "1h"
```

**Acceptance criteria:**
- ✅ All 17 calendar tests still pass (CRITICAL)
- ✅ CLI output unchanged
- ✅ New `get_events_structured()` tests pass

#### 2.3 Files Module Refactoring

**Before:**
```bash
python -m pytest tests/test_files.py -v
# Currently all failing
```

**After refactoring:**
```bash
# 1. Files tests
python -m pytest tests/test_files.py -v

# 2. Try to fix some existing failures
# (optional, but good opportunity)

# 3. CLI testing
o365 files list
o365 files search "test"
```

**Acceptance criteria:**
- ✅ No new failures introduced
- ✅ CLI commands still work
- ⭐ Bonus: Fix some existing test failures

#### 2.4 Chat Module Refactoring

```bash
# Before
python -m pytest tests/test_chat.py -v
# 4 passing, 5 failing

# After
python -m pytest tests/test_chat.py -v
# MUST: Still 4 passing minimum

# CLI testing
o365 chat list
o365 chat read <chat-id>
```

#### 2.5 Other Modules

Repeat the pattern for:
- `contacts.py` (10 passing - keep all)
- `recordings.py` (10 passing - keep all)

---

### Phase 3: MCP Server Testing

#### 3.1 Unit Tests for New Code

**Create tests for new `*_structured()` functions:**

```python
# tests/test_mail.py
class TestMailStructured:
    """Tests for new structured data functions"""

    def test_get_messages_structured_returns_dict(self, mock_access_token):
        """Ensure structured function returns proper schema"""
        result = mail.get_messages_structured(
            access_token=mock_access_token,
            unread=True,
            limit=10
        )

        assert isinstance(result, list)
        assert len(result) > 0

        # Verify schema
        msg = result[0]
        assert "id" in msg
        assert "subject" in msg
        assert "from_email" in msg
        assert "received_datetime" in msg
        assert "is_read" in msg

    def test_get_messages_structured_same_data_as_cli(self, mock_access_token):
        """Ensure structured function returns same data as CLI function"""
        # Both should hit same Graph API endpoint
        # Just different formatting
        pass
```

**Coverage target:** >80% for new code

#### 3.2 Integration Tests

```python
# tests/test_mcp_server.py
import pytest
from unittest.mock import Mock, patch
from o365.mcp_server import read_emails, list_calendar_events

@pytest.mark.asyncio
class TestMCPTools:
    """Integration tests for MCP tools"""

    async def test_read_emails_tool(self):
        """Test read_emails MCP tool"""
        with patch('o365.mcp_server.get_authenticated_token') as mock_token, \
             patch('o365.mail.get_messages_structured') as mock_get:

            mock_token.return_value = "test_token"
            mock_get.return_value = [
                {"id": "1", "subject": "Test"}
            ]

            result = await read_emails(unread=True, limit=10)

            assert len(result) == 1
            assert result[0]["subject"] == "Test"
```

#### 3.3 Regression Testing

**Create regression test suite:**

```python
# tests/test_regression.py
"""
Regression tests to ensure CLI functionality unchanged after MCP addition
"""

@pytest.mark.regression
class TestCLIRegression:
    """Ensure CLI commands still work exactly as before"""

    def test_mail_read_output_format_unchanged(self):
        """Mail read output should be identical to pre-MCP version"""
        # Compare output format
        pass

    def test_calendar_list_output_unchanged(self):
        """Calendar list output format unchanged"""
        pass
```

Run regression tests:
```bash
python -m pytest -m regression -v
```

---

### Phase 4: Manual CLI Testing Checklist

**Test each CLI command manually to ensure it works:**

#### Mail Commands
```bash
# Read
- [ ] o365 mail read
- [ ] o365 mail read --unread
- [ ] o365 mail read --since "2 days ago"
- [ ] o365 mail read --search "test"
- [ ] o365 mail read <message-id>

# Send
- [ ] o365 mail send

# Archive
- [ ] o365 mail archive --unread

# Mark read
- [ ] o365 mail mark-read --unread

# Download attachment
- [ ] o365 mail download-attachment <msg-id> <attachment-id>
```

#### Calendar Commands
```bash
- [ ] o365 calendar list
- [ ] o365 calendar list --today
- [ ] o365 calendar list --week
- [ ] o365 calendar list --after "tomorrow"
- [ ] o365 calendar create "Meeting" "2025-10-20 14:00" "1h"
- [ ] o365 calendar delete <event-id>
```

#### Files Commands
```bash
- [ ] o365 files drives
- [ ] o365 files list
- [ ] o365 files list --path "Documents"
- [ ] o365 files search "test"
- [ ] o365 files download <file-path>
- [ ] o365 files upload <local-file>
```

#### Chat Commands
```bash
- [ ] o365 chat list
- [ ] o365 chat read <chat-id>
- [ ] o365 chat send <user-email> "message"
- [ ] o365 chat search "keyword"
```

#### Other Commands
```bash
- [ ] o365 contacts list
- [ ] o365 contacts search "john"
- [ ] o365 recordings list
- [ ] o365 auth status
- [ ] o365 config list
```

**Document any behavioral changes in CHANGELOG.md**

---

### Phase 5: CI/CD Integration

**Set up automated testing:**

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest tests/ -v --tb=short

      - name: Check coverage
        run: |
          pytest --cov=o365 --cov-report=term --cov-fail-under=70

      - name: Run regression tests
        run: |
          pytest -m regression -v
```

---

## Test-Driven Development Workflow

**For each new feature/refactoring:**

### 1. Write Tests First (TDD)
```bash
# 1. Write test for new structured function
# tests/test_mail.py
def test_get_messages_structured():
    # Test not implemented yet, will fail
    pass

# 2. Run test - should fail
pytest tests/test_mail.py::test_get_messages_structured -v

# 3. Implement function
# o365/mail.py
def get_messages_structured(...):
    # Implementation
    pass

# 4. Run test - should pass
pytest tests/test_mail.py::test_get_messages_structured -v

# 5. Run ALL tests - ensure no regressions
pytest tests/ -v
```

### 2. Refactor Existing Code
```bash
# 1. Baseline - run tests before refactoring
pytest tests/test_calendar.py -v
# Note: 17 passing

# 2. Refactor code
# Make changes to calendar.py

# 3. Run tests immediately
pytest tests/test_calendar.py -v
# Must still show: 17 passing

# 4. If ANY test fails - STOP and fix before continuing
# Do NOT proceed with broken tests
```

### 3. Add MCP Code
```bash
# 1. Tests for MCP tools
# tests/test_mcp_server.py
@pytest.mark.asyncio
async def test_list_calendar_events_tool():
    # Test MCP tool
    pass

# 2. Implement MCP tool
# o365/mcp_server.py
@mcp.tool()
async def list_calendar_events(...):
    # Implementation
    pass

# 3. Run MCP tests
pytest tests/test_mcp_server.py -v

# 4. Run ALL tests (regression check)
pytest tests/ -v
```

---

## Regression Prevention Checklist

Before committing ANY code:

- [ ] All baseline tests (66) still pass
- [ ] No new test failures introduced
- [ ] Coverage hasn't decreased
- [ ] Manual CLI testing completed
- [ ] Code formatted: `black o365/`
- [ ] Linting clean: `flake8 o365/`
- [ ] Tests pass on Python 3.10, 3.11, 3.12

**If ANY checkbox fails → DO NOT COMMIT**

---

## Test Commands Reference

### Quick Commands
```bash
# Run all tests
pytest tests/ -v

# Run specific module
pytest tests/test_calendar.py -v

# Run only passing baseline tests (critical)
pytest tests/test_calendar.py tests/test_config.py tests/test_contacts.py tests/test_recordings.py -v

# Run with coverage
pytest --cov=o365 --cov-report=html tests/

# Run regression tests only
pytest -m regression -v

# Run fast tests only
pytest -m "not slow" -v

# Run specific test
pytest tests/test_calendar.py::TestCalendarList::test_list_today -v
```

### Coverage Commands
```bash
# Generate coverage report
pytest --cov=o365 --cov-report=html --cov-report=term-missing tests/

# Open coverage report
open htmlcov/index.html

# Check coverage threshold
pytest --cov=o365 --cov-fail-under=70 tests/
```

### Debugging Commands
```bash
# Run with print statements visible
pytest tests/test_mail.py -v -s

# Drop into debugger on failure
pytest tests/test_mail.py -v --pdb

# Show full traceback
pytest tests/test_mail.py -v --tb=long

# Run last failed tests only
pytest --lf -v
```

---

## Test Documentation Standards

### For New Tests
```python
def test_get_messages_structured_with_filters():
    """
    Test get_messages_structured with multiple filters.

    This test ensures that:
    1. Unread filter is applied correctly
    2. Date range filter works
    3. Search query filters results
    4. Return format matches schema

    Related to: MCP implementation, mail.py refactoring
    """
    # Arrange
    # ...

    # Act
    # ...

    # Assert
    # ...
```

### For Modified Tests
```python
def test_existing_function():
    """
    Original test description.

    MODIFIED (2025-10-18): Updated to work with refactored data layer.
    Changes: Updated mock to match new internal function signature.
    CLI behavior: UNCHANGED
    """
    # ...
```

---

## Troubleshooting Test Failures

### Common Issues

#### 1. Import Errors
```python
# Error: ModuleNotFoundError: No module named 'o365.mcp_server'
# Solution: MCP dependencies not installed
pip install -e ".[mcp]"
```

#### 2. Mock Issues
```python
# Error: AttributeError: module 'o365.mail' has no attribute 'get_messages_structured'
# Solution: Function not implemented yet, or wrong mock path
with patch('o365.mail.get_messages_structured') as mock:
    # Make sure function exists first
```

#### 3. Async Test Issues
```python
# Error: RuntimeError: no running event loop
# Solution: Use @pytest.mark.asyncio decorator
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
```

---

## Success Metrics

### Per-Phase Metrics

**Phase 1 (Setup):**
- ✅ Baseline established: 66 passing tests documented
- ✅ Coverage report generated

**Phase 2 (Refactoring):**
- ✅ All 66 baseline tests still pass
- ✅ 0 new failures introduced
- ✅ Coverage maintained or increased
- ✅ All CLI commands manually tested

**Phase 3 (MCP Implementation):**
- ✅ All 66 baseline tests still pass
- ✅ New MCP tests: >20 tests added
- ✅ MCP test coverage: >80%
- ✅ Total passing tests: >86 (66 + 20)

**Phase 4 (Release):**
- ✅ All tests passing: 100+
- ✅ Coverage: >75% overall
- ✅ Zero regressions confirmed
- ✅ Manual testing: All commands work

---

## Rollback Plan

**If tests start failing:**

1. **Immediate:** Stop development
2. **Identify:** Which module caused failure?
3. **Options:**
   - Fix the issue immediately
   - Rollback the last change: `git checkout HEAD~1 o365/mail.py`
   - Create new branch to debug: `git checkout -b fix/test-failures`
4. **Verify:** Tests pass before continuing
5. **Document:** What broke and why in commit message

**Never commit broken tests to main branch**

---

## Documentation

**Track test changes:**
- Update `tests/README.md` with new test descriptions
- Document any test modifications in commit messages
- Note test coverage changes in PR descriptions
- Keep `docs/test-baseline-*.txt` files for each major change

---

## Summary

**Key Principles:**

1. ✅ **Test BEFORE refactoring** - Establish baseline
2. ✅ **Test AFTER each change** - Continuous validation
3. ✅ **Never commit broken tests** - All tests must pass
4. ✅ **Manual CLI testing** - Automated tests aren't enough
5. ✅ **Document everything** - Track baselines and changes

**Remember:** The goal is to ADD MCP functionality, not BREAK existing CLI functionality!

---

**Document Version:** 1.0
**Last Updated:** 2025-10-18
**Baseline Date:** 2025-10-18
**Baseline Results:** 66 passing, 39 failing (pre-existing)
