# MCP Implementation Checklist

This is a step-by-step checklist for implementing the MCP server. Check off each item as you complete it.

## Phase 0: TESTING BASELINE ⚠️ CRITICAL

**MUST COMPLETE BEFORE ANY CODE CHANGES**

### 0.1 Establish Test Baseline
- [x] Install test dependencies: `pip install -e ".[dev]"`
- [x] Run full test suite: `pytest tests/ -v`
- [x] Record baseline: **66 PASSING, 39 FAILING (pre-existing)**
- [x] Save baseline to file: `docs/test-baseline-2025-10-18.txt`
- [ ] Review `docs/MCP_TESTING_STRATEGY.md`
- [ ] Understand which tests MUST NOT break (66 passing tests)

### 0.2 Generate Coverage Report
- [ ] Run with coverage: `pytest --cov=o365 --cov-report=html tests/`
- [ ] Open report: `open htmlcov/index.html`
- [ ] Document current coverage percentage: __%

### 0.3 Identify Critical Tests
- [ ] Calendar tests: 17 passing - MUST ALL REMAIN PASSING
- [ ] Config tests: 16 passing - MUST ALL REMAIN PASSING
- [ ] Contacts tests: 10 passing - MUST ALL REMAIN PASSING
- [ ] Recordings tests: 10 passing - MUST ALL REMAIN PASSING
- [ ] Chat tests: 4 passing - MUST ALL REMAIN PASSING

**⚠️ COMMITMENT: NO REGRESSIONS ALLOWED**
**If ANY of the 66 passing tests fail, STOP and fix before continuing.**

---

## Phase 1: Project Setup ⚙️

### 1.1 Update Python Version
- [ ] Update `pyproject.toml`: Change `requires-python = ">=3.10"`
- [ ] Test on Python 3.10: `python --version`
- [ ] Test on Python 3.11: `python --version`
- [ ] Test on Python 3.12: `python --version`
- [ ] **RUN TESTS AFTER CHANGE**: `pytest tests/ -v`
- [ ] **VERIFY**: Still 66 passing tests

### 1.2 Add MCP Dependencies
- [ ] Update `pyproject.toml`: Add `mcp>=1.2.0` to `[project.optional-dependencies]` under `mcp = [...]`
- [ ] Install dependencies: `pip install -e ".[mcp]"`
- [ ] Verify MCP installed: `python -c "import mcp; print(mcp.__version__)"`

### 1.3 Add Console Script Entry Point
- [ ] Update `pyproject.toml`: Add `o365-mcp = "o365.mcp_server:main"` to `[project.scripts]`
- [ ] Reinstall: `pip install -e ".[mcp]"`
- [ ] Test entry point exists: `which o365-mcp`

---

## Phase 2: Data Layer Refactoring 🔧

### 2.1 Refactor Mail Module

**BEFORE STARTING:**
- [ ] Run mail tests: `pytest tests/test_mail.py -v` (note: currently all failing)
- [ ] Test CLI manually: `o365 mail read --unread`
- [ ] Document current CLI output format

**IMPLEMENTATION:**
- [ ] Create `o365/mail.py::get_messages_structured()` function
  - Input: `access_token, folder, unread, since, search, limit`
  - Output: `list[dict]` with keys: `id, subject, from_email, from_name, received_datetime, is_read, has_attachments, body_preview, is_external`
- [ ] Create `o365/mail.py::get_message_by_id_structured()` function
- [ ] Create `o365/mail.py::send_email_structured()` function
- [ ] Update existing `cmd_read()` to use `get_messages_structured()` (format output, not data)
- [ ] Write unit tests for new functions in `tests/test_mail.py`

**AFTER CHANGES - CRITICAL TESTING:**
- [ ] Run mail tests: `pytest tests/test_mail.py -v`
- [ ] Run ALL tests: `pytest tests/ -v`
- [ ] **VERIFY: Still 66 passing tests** ⚠️
- [ ] Test CLI manually: `o365 mail read --unread`
- [ ] **VERIFY: CLI output unchanged** ⚠️
- [ ] Test CLI: `o365 mail read --since "2 days ago"`
- [ ] Test CLI: `o365 mail read --search "test"`
- [ ] **If ANY test fails that was passing before: STOP and fix** 🛑

### 2.2 Refactor Calendar Module

**BEFORE STARTING:**
- [ ] Run calendar tests: `pytest tests/test_calendar.py -v`
- [ ] **VERIFY: 17 tests passing** ⚠️ (this is our baseline)
- [ ] Test CLI manually: `o365 calendar list --today`

**IMPLEMENTATION:**
- [ ] Create `o365/calendar.py::get_events_structured()` function
  - Output: `list[dict]` with keys: `id, subject, start, end, location, is_all_day, is_online_meeting, online_meeting_url, organizer_email, organizer_name, attendees, body_preview`
- [ ] Create `o365/calendar.py::create_event_structured()` function
- [ ] Create `o365/calendar.py::delete_event_structured()` function
- [ ] Update existing CLI commands to use structured functions (ONLY format, don't change data)
- [ ] Write unit tests in `tests/test_calendar.py` for new functions

**AFTER CHANGES - CRITICAL TESTING:**
- [ ] Run calendar tests: `pytest tests/test_calendar.py -v`
- [ ] **VERIFY: ALL 17 tests STILL passing** ⚠️🛑 (CRITICAL!)
- [ ] Run ALL tests: `pytest tests/ -v`
- [ ] **VERIFY: Still 66 passing tests total** ⚠️
- [ ] Test CLI: `o365 calendar list --today`
- [ ] Test CLI: `o365 calendar list --week`
- [ ] Test CLI: `o365 calendar create "Test" "2025-10-20 14:00" "1h"`
- [ ] **VERIFY: CLI output format unchanged** ⚠️
- [ ] **If ANY calendar test fails: STOP IMMEDIATELY and fix** 🛑

### 2.3 Refactor Files Module
- [ ] Create `o365/files.py::list_files_structured()` function
  - Output: `list[dict]` with keys: `id, name, path, type, size, modified, created, web_url, download_url`
- [ ] Create `o365/files.py::search_files_structured()` function
- [ ] Create `o365/files.py::download_file_structured()` function
- [ ] Create `o365/files.py::upload_file_structured()` function
- [ ] Update CLI commands
- [ ] Test CLI: `o365 files list`
- [ ] Write unit tests in `tests/test_files.py`
- [ ] Run tests: `pytest tests/test_files.py -v`

### 2.4 Refactor Chat Module
- [ ] Create `o365/chat.py::get_chats_structured()` function
- [ ] Create `o365/chat.py::get_chat_messages_structured()` function
- [ ] Create `o365/chat.py::search_messages_structured()` function
- [ ] Create `o365/chat.py::send_message_structured()` function
- [ ] Update CLI commands
- [ ] Test CLI: `o365 chat list`
- [ ] Write unit tests in `tests/test_chat.py`
- [ ] Run tests: `pytest tests/test_chat.py -v`

### 2.5 Refactor Contacts & Recordings
- [ ] Create `o365/contacts.py::search_contacts_structured()` function
- [ ] Create `o365/recordings.py::get_recordings_structured()` function
- [ ] Create `o365/recordings.py::get_transcript_structured()` function
- [ ] Update CLI commands
- [ ] Test CLI commands
- [ ] Write unit tests
- [ ] Run tests: `pytest tests/ -v`

---

## Phase 3: MCP Server Implementation 🚀

### 3.1 Create MCP Server Module
- [ ] Create file: `o365/mcp_server.py`
- [ ] Add imports: `from mcp import FastMCP, Context`
- [ ] Initialize server: `mcp = FastMCP("Office365", version="1.0.0")`
- [ ] Create `get_authenticated_token()` helper function
- [ ] Test basic server runs: `python -m o365.mcp_server`

### 3.2 Implement Mail Tools
- [ ] Implement `@mcp.tool() async def read_emails(...)`
- [ ] Implement `@mcp.tool() async def get_email_content(...)`
- [ ] Implement `@mcp.tool() async def send_email(...)`
- [ ] Implement `@mcp.tool() async def archive_emails(...)`
- [ ] Test each tool manually with MCP client

### 3.3 Implement Calendar Tools
- [ ] Implement `@mcp.tool() async def list_calendar_events(...)`
- [ ] Implement `@mcp.tool() async def create_calendar_event(...)`
- [ ] Implement `@mcp.tool() async def delete_calendar_event(...)`
- [ ] Test each tool

### 3.4 Implement Files Tools
- [ ] Implement `@mcp.tool() async def list_onedrive_files(...)`
- [ ] Implement `@mcp.tool() async def search_onedrive(...)`
- [ ] Implement `@mcp.tool() async def download_file(...)`
- [ ] Implement `@mcp.tool() async def upload_file(...)`
- [ ] Test each tool

### 3.5 Implement Chat Tools
- [ ] Implement `@mcp.tool() async def list_teams_chats(...)`
- [ ] Implement `@mcp.tool() async def read_chat_messages(...)`
- [ ] Implement `@mcp.tool() async def send_chat_message(...)`
- [ ] Implement `@mcp.tool() async def search_teams_messages(...)`
- [ ] Test each tool

### 3.6 Implement Contact & Recording Tools
- [ ] Implement `@mcp.tool() async def search_contacts(...)`
- [ ] Implement `@mcp.tool() async def list_recordings(...)`
- [ ] Implement `@mcp.tool() async def download_recording(...)`
- [ ] Test each tool

### 3.7 Implement Resources
- [ ] Implement `@mcp.resource("o365://mail/unread")`
- [ ] Implement `@mcp.resource("o365://calendar/today")`
- [ ] Implement `@mcp.resource("o365://files/recent")`
- [ ] Test resource access

### 3.8 Implement Prompts
- [ ] Implement `@mcp.prompt() async def review_unread_emails()`
- [ ] Implement `@mcp.prompt() async def summarize_todays_meetings()`
- [ ] Implement `@mcp.prompt() async def find_recent_files()`
- [ ] Test prompts

### 3.9 Add Main Entry Point
- [ ] Add `def main()` function to `o365/mcp_server.py`
- [ ] Call `mcp.run()` in main
- [ ] Test: `o365-mcp` command works

### 3.10 Add CLI Command
- [ ] Update `o365/__main__.py`: Add `mcp` subcommand
- [ ] Add `cmd_mcp(args)` function
- [ ] Add `--transport` argument (stdio/sse)
- [ ] Add `--log-level` argument
- [ ] Test: `o365 mcp --help` shows help
- [ ] Test: `o365 mcp` starts server

---

## Phase 4: Testing 🧪

### 4.1 Unit Tests for MCP Tools
- [ ] Create `tests/test_mcp_server.py`
- [ ] Test `read_emails()` with mocked data
- [ ] Test `list_calendar_events()` with mocked data
- [ ] Test `search_onedrive()` with mocked data
- [ ] Test `list_teams_chats()` with mocked data
- [ ] Test `search_contacts()` with mocked data
- [ ] Test error handling (token expired, API errors)
- [ ] Run tests: `pytest tests/test_mcp_server.py -v`
- [ ] Check coverage: `pytest --cov=o365.mcp_server tests/test_mcp_server.py`
- [ ] Ensure coverage >80%

### 4.2 Integration Tests
- [ ] Create `tests/test_e2e_mcp.py`
- [ ] Test server startup and shutdown
- [ ] Test tool discovery (tools/list)
- [ ] Test tool execution (tools/call)
- [ ] Test resource access (resources/read)
- [ ] Test prompt templates (prompts/list)
- [ ] Run tests: `pytest tests/test_e2e_mcp.py -v`

### 4.3 Manual Testing with Claude Desktop
- [ ] Install package: `pip install -e ".[mcp]"`
- [ ] Configure Claude Desktop:
  - [ ] Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
  - [ ] Add office365 MCP server config
- [ ] Restart Claude Desktop
- [ ] Test query: "Show my unread emails from the last 2 days"
- [ ] Test query: "What meetings do I have today?"
- [ ] Test query: "Search OneDrive for files containing 'budget'"
- [ ] Test query: "List my recent Teams chats"
- [ ] Test query: "Create a meeting tomorrow at 2pm for 1 hour"
- [ ] Test error handling: "Show email with ID 'invalid-id'"
- [ ] Verify all tools work as expected

---

## Phase 5: Documentation 📚

### 5.1 User Documentation
- [ ] Create `docs/MCP_USER_GUIDE.md`
  - [ ] What is MCP section
  - [ ] Installation instructions
  - [ ] Claude Desktop configuration
  - [ ] Example queries
  - [ ] Troubleshooting section
- [ ] Add screenshots (optional)

### 5.2 Developer Documentation
- [ ] Create `docs/MCP_DEVELOPER_GUIDE.md`
  - [ ] Architecture overview
  - [ ] How to add new tools
  - [ ] How to add new resources
  - [ ] Testing guidelines
  - [ ] Contributing section

### 5.3 Update README
- [ ] Add "MCP Server" section to `README.md`
- [ ] Add installation instructions with `[mcp]` extra
- [ ] Add Claude Desktop configuration example
- [ ] Add example queries
- [ ] Link to `docs/MCP_USER_GUIDE.md`

### 5.4 API Reference
- [ ] Create script: `scripts/generate_mcp_docs.py`
- [ ] Generate tool reference from docstrings
- [ ] Create `docs/MCP_API_REFERENCE.md`
- [ ] Document all 15+ tools
- [ ] Document all resources
- [ ] Document all prompts

### 5.5 Changelog
- [ ] Update `CHANGELOG.md` (or create if missing)
- [ ] Add entry for MCP server feature
- [ ] List all new tools
- [ ] Note Python version requirement change

---

## Phase 6: Optimization & Polish ✨

### 6.1 Performance Optimization
- [ ] Profile slow tools: `python -m cProfile -m o365.mcp_server`
- [ ] Add connection pooling for Graph API requests
- [ ] Implement resource caching (60s TTL)
- [ ] Optimize pagination (use `$top` and `$skip`)
- [ ] Benchmark response times (target <3s)

### 6.2 Error Handling
- [ ] Review all error messages for clarity
- [ ] Add retry logic for transient errors (with exponential backoff)
- [ ] Handle rate limiting (429 responses)
- [ ] Test error scenarios:
  - [ ] Invalid token
  - [ ] Expired token
  - [ ] Permission denied
  - [ ] Resource not found
  - [ ] Network timeout
- [ ] Ensure all errors return user-friendly messages

### 6.3 Logging
- [ ] Configure structured logging
- [ ] Log all tool calls (INFO level)
- [ ] Log all Graph API requests (DEBUG level)
- [ ] Log authentication events (INFO level)
- [ ] Log errors with stack traces (ERROR level)
- [ ] Add performance metrics logging
- [ ] Test log output at different levels

### 6.4 Security Review
- [ ] Verify tokens never logged
- [ ] Verify token file permissions (0o600)
- [ ] Review input validation for all tools
- [ ] Test for path traversal attacks
- [ ] Review OAuth scope minimums
- [ ] Test with restricted permissions

---

## Phase 7: Release Preparation 🎉

### 7.1 Version Bump
- [ ] Update version in `o365/__init__.py`
- [ ] Update version in `pyproject.toml`
- [ ] Update version in `o365/mcp_server.py`

### 7.2 Final Testing
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Run with coverage: `pytest --cov=o365 tests/`
- [ ] Test installation: `pip install -e ".[mcp]"`
- [ ] Test CLI: `o365 --help`
- [ ] Test MCP: `o365 mcp`
- [ ] Test with Claude Desktop (full workflow)

### 7.3 Code Quality
- [ ] Run Black formatter: `black o365/`
- [ ] Run Flake8 linter: `flake8 o365/`
- [ ] Fix all linting errors
- [ ] Review code for TODOs/FIXMEs
- [ ] Clean up debug code

### 7.4 Documentation Review
- [ ] Proofread all documentation
- [ ] Test all code examples in docs
- [ ] Verify all links work
- [ ] Check for typos

### 7.5 Create Release
- [ ] Create feature branch: `git checkout -b feature/mcp-server`
- [ ] Commit all changes
- [ ] Push to GitHub: `git push origin feature/mcp-server`
- [ ] Create pull request
- [ ] Get code review
- [ ] Merge to main
- [ ] Tag release: `git tag v1.1.0`
- [ ] Push tag: `git push origin v1.1.0`

---

## Success Criteria ✅

### Functional
- [ ] All 15+ tools implemented and tested
- [ ] 3+ resources implemented
- [ ] 3+ prompts implemented
- [ ] Works with Claude Desktop
- [ ] Authentication seamless
- [ ] Error handling robust

### Quality
- [ ] Test coverage >80%
- [ ] All tests passing
- [ ] No linting errors
- [ ] Documentation complete

### Performance
- [ ] Average response time <3s
- [ ] Token refresh works automatically
- [ ] No memory leaks

### User Experience
- [ ] Installation straightforward
- [ ] Configuration simple
- [ ] Natural language queries work
- [ ] Error messages helpful

---

## Quick Start Commands

```bash
# Phase 1: Setup
pip install -e ".[mcp]"

# Phase 2: Test refactoring
pytest tests/ -v

# Phase 3: Test MCP server
python -m o365.mcp_server
o365 mcp

# Phase 4: Run tests
pytest tests/test_mcp_server.py -v --cov=o365.mcp_server

# Phase 5: Generate docs
python scripts/generate_mcp_docs.py > docs/MCP_API_REFERENCE.md

# Phase 6: Code quality
black o365/
flake8 o365/

# Phase 7: Release
git checkout -b feature/mcp-server
git add .
git commit -m "Add MCP server implementation"
git push origin feature/mcp-server
```

---

## Notes

- Check off items as you complete them
- Skip optional items if not needed
- Adjust timeline based on your schedule
- Ask for help when stuck
- Test frequently!

**Estimated Total Time:** 6-10 days

**Last Updated:** 2025-10-18
