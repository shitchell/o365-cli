# MCP Server Implementation Plan for o365-cli

## Overview

This document outlines a step-by-step plan to add Model Context Protocol (MCP) server capabilities to o365-cli, enabling LLM clients like Claude Desktop to interact with Office 365 resources through natural language.

## Project Goals

1. Expose o365-cli functionality as MCP tools, resources, and prompts
2. Maintain backward compatibility with existing CLI
3. Enable natural language interaction with Office 365 via Claude and other MCP clients
4. Provide structured data output suitable for LLM consumption

## Prerequisites

- Python >=3.10 (MCP SDK requirement)
- Existing o365-cli codebase (current version: 1.0.0)
- Understanding of MCP concepts: tools, resources, prompts
- Existing Office 365 authentication setup

---

## Phase 1: Project Setup and Dependencies

### Task 1.1: Update Python Version Requirement

**Files to modify:**
- `pyproject.toml`

**Changes:**
```toml
[project]
requires-python = ">=3.10"  # Changed from >=3.7
```

**Rationale:** MCP SDK requires Python 3.10+

**Validation:**
- Check that existing dependencies are compatible with Python 3.10+
- Run tests on Python 3.10, 3.11, 3.12, 3.13

### Task 1.2: Add MCP Dependencies

**Files to modify:**
- `pyproject.toml`

**Changes:**
```toml
[project]
dependencies = [
    "python-dateutil>=2.8.0",
    "html2text>=2020.1.16",
]

[project.optional-dependencies]
mcp = [
    "mcp>=1.2.0",
]
dev = [
    "pytest>=7.0.0",
    "pytest-mock>=3.10.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "flake8>=6.0.0",
]
```

**Installation:**
```bash
pip install -e ".[mcp]"
```

**Validation:**
- `pip install -e ".[mcp]"` succeeds
- `python -c "import mcp; print(mcp.__version__)"` works

### Task 1.3: Update Console Scripts

**Files to modify:**
- `pyproject.toml`

**Changes:**
```toml
[project.scripts]
o365 = "o365.__main__:main"
o365-mcp = "o365.mcp_server:main"  # NEW
```

**Validation:**
- After install, `which o365-mcp` shows the installed script
- `o365-mcp --help` displays help (even if not implemented yet)

---

## Phase 2: Data Layer Refactoring

### Context

The current CLI code returns formatted strings for terminal display. MCP tools need structured data (dicts/lists). We need to separate data retrieval from presentation.

### Task 2.1: Refactor Mail Module

**Files to modify:**
- `o365/mail.py`

**Approach:**
Create new functions that return structured data:

```python
def get_messages_structured(
    access_token: str,
    folder: str = "inbox",
    unread: bool = False,
    since: str = None,
    search: str = None,
    limit: int = 50
) -> list[dict]:
    """
    Get messages as structured data (not formatted strings).

    Returns:
        list[dict]: List of message dictionaries with keys:
            - id: str
            - subject: str
            - from_email: str
            - from_name: str
            - received_datetime: str (ISO 8601)
            - is_read: bool
            - has_attachments: bool
            - body_preview: str
            - is_external: bool
            - attachments: list[dict] (if present)
    """
    # Use existing get_messages_stream() but return raw data
    # instead of formatted output
    pass
```

**Pattern:**
- Keep existing `cmd_*()` functions for CLI (they format output)
- Add new `get_*_structured()` functions for MCP (return dicts/lists)
- Share common Graph API logic

**Validation:**
- `get_messages_structured()` returns list of dicts
- All expected fields are present
- Existing CLI commands still work

### Task 2.2: Refactor Calendar Module

**Files to modify:**
- `o365/calendar.py`

**New function:**
```python
def get_events_structured(
    access_token: str,
    calendar_id: str = None,
    user_email: str = None,
    since: str = None,
    until: str = None,
    limit: int = 100
) -> list[dict]:
    """
    Get calendar events as structured data.

    Returns:
        list[dict]: List of event dictionaries with keys:
            - id: str
            - subject: str
            - start: str (ISO 8601)
            - end: str (ISO 8601)
            - location: str | None
            - is_all_day: bool
            - is_online_meeting: bool
            - online_meeting_url: str | None
            - organizer_email: str
            - organizer_name: str
            - attendees: list[dict]
            - body_preview: str
    """
    pass
```

**Validation:**
- Returns structured event data
- Date/time in ISO 8601 format
- CLI commands unaffected

### Task 2.3: Refactor Files Module

**Files to modify:**
- `o365/files.py`

**New functions:**
```python
def list_files_structured(
    access_token: str,
    drive_id: str = None,
    path: str = "/",
    recursive: bool = False
) -> list[dict]:
    """
    List files as structured data.

    Returns:
        list[dict]: Files/folders with keys:
            - id: str
            - name: str
            - path: str
            - type: "file" | "folder"
            - size: int | None (bytes)
            - modified: str (ISO 8601)
            - created: str (ISO 8601)
            - web_url: str
            - download_url: str | None
    """
    pass

def search_files_structured(
    access_token: str,
    query: str,
    drive_id: str = None,
    file_type: str = None
) -> list[dict]:
    """Search files, return structured data"""
    pass
```

**Validation:**
- Structured output matches schema
- File sizes are in bytes
- Timestamps in ISO 8601

### Task 2.4: Refactor Chat Module

**Files to modify:**
- `o365/chat.py`

**New functions:**
```python
def get_chats_structured(
    access_token: str,
    user_filter: str = None,
    name_filter: str = None
) -> list[dict]:
    """Get Teams chats as structured data"""
    pass

def get_chat_messages_structured(
    access_token: str,
    chat_id: str,
    limit: int = 50
) -> list[dict]:
    """Get chat messages as structured data"""
    pass

def search_messages_structured(
    access_token: str,
    query: str,
    since: str = None,
    until: str = None
) -> list[dict]:
    """Search chat messages as structured data"""
    pass
```

**Validation:**
- Returns structured chat data
- Message ordering preserved
- Timestamps in ISO 8601

### Task 2.5: Refactor Other Modules

Repeat the pattern for:
- `o365/contacts.py` → `search_contacts_structured()`
- `o365/recordings.py` → `get_recordings_structured()`, `get_transcript_structured()`

---

## Phase 3: MCP Server Implementation

### Task 3.1: Create MCP Server Module

**New file:** `o365/mcp_server.py`

**Initial structure:**
```python
"""
MCP Server for Office 365 CLI

Exposes Office 365 functionality via Model Context Protocol.
"""

from mcp import FastMCP, Context
from typing import Optional, List, Dict, Any
import logging

from .common import load_config, get_access_token
from . import mail, calendar, files, chat, contacts, recordings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP(
    name="Office365",
    version="1.0.0",
    description="Access Microsoft Office 365 resources via MCP"
)

# ==========================================
# AUTHENTICATION HELPERS
# ==========================================

def get_authenticated_token() -> str:
    """Get valid access token, refreshing if needed"""
    config = load_config()
    return get_access_token(config)

# ==========================================
# TOOLS - MAIL
# ==========================================

@mcp.tool()
async def read_emails(
    unread: bool = False,
    since: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Read Office 365 emails with optional filters.

    Args:
        unread: Only show unread messages
        since: Date/time expression (e.g., "2 days ago", "yesterday", "2025-01-01")
        search: Search query string (searches subject, body, from)
        limit: Maximum number of messages to return (default: 50, max: 200)

    Returns:
        List of email message dictionaries containing id, subject, from,
        received time, read status, preview, and attachment info.

    Examples:
        - Read unread emails: read_emails(unread=True)
        - Search emails: read_emails(search="project alpha")
        - Recent emails: read_emails(since="48 hours ago", limit=10)
    """
    try:
        token = get_authenticated_token()
        messages = mail.get_messages_structured(
            access_token=token,
            unread=unread,
            since=since,
            search=search,
            limit=min(limit, 200)  # Cap at 200
        )
        logger.info(f"Retrieved {len(messages)} emails")
        return messages
    except Exception as e:
        logger.error(f"Error reading emails: {e}")
        raise

@mcp.tool()
async def get_email_content(email_id: str) -> Dict[str, Any]:
    """
    Get full content of a specific email by ID.

    Args:
        email_id: The Graph API message ID

    Returns:
        Email with full body content, attachments, and metadata
    """
    try:
        token = get_authenticated_token()
        # Implementation needed in mail.py
        message = mail.get_message_by_id_structured(token, email_id)
        return message
    except Exception as e:
        logger.error(f"Error getting email {email_id}: {e}")
        raise

@mcp.tool()
async def send_email(
    to: List[str],
    subject: str,
    body: str,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    is_html: bool = True
) -> Dict[str, str]:
    """
    Send an email via Office 365.

    Args:
        to: List of recipient email addresses
        subject: Email subject line
        body: Email body content
        cc: Optional CC recipients
        bcc: Optional BCC recipients
        is_html: Whether body is HTML (default: True)

    Returns:
        Status dictionary with message_id and status
    """
    try:
        token = get_authenticated_token()
        result = mail.send_email_structured(
            access_token=token,
            to_addresses=to,
            subject=subject,
            body=body,
            cc_addresses=cc or [],
            bcc_addresses=bcc or [],
            is_html=is_html
        )
        logger.info(f"Email sent to {', '.join(to)}")
        return result
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise

# ==========================================
# TOOLS - CALENDAR
# ==========================================

@mcp.tool()
async def list_calendar_events(
    today: bool = False,
    week: bool = False,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    List calendar events with date filters.

    Args:
        today: Show only today's events
        week: Show this week's events
        since: Start date/time (e.g., "tomorrow", "2025-01-15")
        until: End date/time (e.g., "next Friday", "2025-01-20")
        limit: Maximum number of events to return

    Returns:
        List of calendar event dictionaries

    Examples:
        - Today's events: list_calendar_events(today=True)
        - This week: list_calendar_events(week=True)
        - Date range: list_calendar_events(since="2025-01-15", until="2025-01-20")
    """
    try:
        token = get_authenticated_token()

        # Handle convenience flags
        if today:
            from datetime import date
            today_str = date.today().isoformat()
            since = today_str
            until = today_str
        elif week:
            # Implementation for week range
            pass

        events = calendar.get_events_structured(
            access_token=token,
            since=since,
            until=until,
            limit=limit
        )
        logger.info(f"Retrieved {len(events)} calendar events")
        return events
    except Exception as e:
        logger.error(f"Error listing calendar events: {e}")
        raise

@mcp.tool()
async def create_calendar_event(
    subject: str,
    start: str,
    end: str,
    location: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    body: Optional[str] = None,
    is_online_meeting: bool = False
) -> Dict[str, Any]:
    """
    Create a new calendar event.

    Args:
        subject: Event title/subject
        start: Start time (ISO 8601 or natural language)
        end: End time (ISO 8601 or natural language)
        location: Event location
        attendees: List of attendee email addresses
        body: Event description
        is_online_meeting: Create as Teams meeting

    Returns:
        Created event details including ID and online meeting link
    """
    try:
        token = get_authenticated_token()
        event = calendar.create_event_structured(
            access_token=token,
            subject=subject,
            start=start,
            end=end,
            location=location,
            attendees=attendees or [],
            body=body,
            is_online_meeting=is_online_meeting
        )
        logger.info(f"Created calendar event: {subject}")
        return event
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        raise

# ==========================================
# TOOLS - FILES
# ==========================================

@mcp.tool()
async def list_onedrive_files(
    path: str = "/",
    recursive: bool = False,
    drive: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List files and folders in OneDrive/SharePoint.

    Args:
        path: Path to list (default: root "/")
        recursive: Include subdirectories
        drive: Drive name or ID (default: personal OneDrive)

    Returns:
        List of files and folders with metadata
    """
    try:
        token = get_authenticated_token()
        items = files.list_files_structured(
            access_token=token,
            drive_id=drive,
            path=path,
            recursive=recursive
        )
        logger.info(f"Listed {len(items)} items at {path}")
        return items
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise

@mcp.tool()
async def search_onedrive(
    query: str,
    drive: Optional[str] = None,
    file_type: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Search for files in OneDrive/SharePoint.

    Args:
        query: Search query
        drive: Drive name or ID to search in
        file_type: Filter by extension (e.g., "xlsx", "pdf")
        limit: Maximum results to return

    Returns:
        List of matching files with metadata
    """
    try:
        token = get_authenticated_token()
        results = files.search_files_structured(
            access_token=token,
            query=query,
            drive_id=drive,
            file_type=file_type,
            limit=limit
        )
        logger.info(f"Found {len(results)} files matching '{query}'")
        return results
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        raise

@mcp.tool()
async def download_file(
    file_path: str,
    destination: str,
    drive: Optional[str] = None
) -> Dict[str, str]:
    """
    Download a file from OneDrive.

    Args:
        file_path: Path to file in OneDrive
        destination: Local path to save file
        drive: Drive name or ID

    Returns:
        Status with local file path and size
    """
    try:
        token = get_authenticated_token()
        result = files.download_file_structured(
            access_token=token,
            file_path=file_path,
            destination=destination,
            drive_id=drive
        )
        logger.info(f"Downloaded {file_path} to {destination}")
        return result
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise

# ==========================================
# TOOLS - TEAMS CHAT
# ==========================================

@mcp.tool()
async def list_teams_chats(
    user_filter: Optional[str] = None,
    name_filter: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    List Teams chats.

    Args:
        user_filter: Filter by participant email/name
        name_filter: Filter by chat name
        limit: Maximum chats to return

    Returns:
        List of chat conversations
    """
    try:
        token = get_authenticated_token()
        chats = chat.get_chats_structured(
            access_token=token,
            user_filter=user_filter,
            name_filter=name_filter,
            limit=limit
        )
        logger.info(f"Retrieved {len(chats)} chats")
        return chats
    except Exception as e:
        logger.error(f"Error listing chats: {e}")
        raise

@mcp.tool()
async def read_chat_messages(
    chat_id: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Read messages from a Teams chat.

    Args:
        chat_id: The chat ID
        limit: Maximum messages to return

    Returns:
        List of messages in chronological order
    """
    try:
        token = get_authenticated_token()
        messages = chat.get_chat_messages_structured(
            access_token=token,
            chat_id=chat_id,
            limit=limit
        )
        logger.info(f"Retrieved {len(messages)} messages from chat {chat_id}")
        return messages
    except Exception as e:
        logger.error(f"Error reading chat messages: {e}")
        raise

@mcp.tool()
async def search_teams_messages(
    query: str,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Search Teams chat messages.

    Args:
        query: Search query
        since: Start date
        until: End date
        limit: Maximum results

    Returns:
        List of matching messages with context
    """
    try:
        token = get_authenticated_token()
        results = chat.search_messages_structured(
            access_token=token,
            query=query,
            since=since,
            until=until,
            limit=limit
        )
        logger.info(f"Found {len(results)} messages matching '{query}'")
        return results
    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        raise

# ==========================================
# TOOLS - CONTACTS
# ==========================================

@mcp.tool()
async def search_contacts(
    query: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Search for contacts by name or email.

    Args:
        query: Name or email to search for
        limit: Maximum results

    Returns:
        List of matching contacts
    """
    try:
        token = get_authenticated_token()
        results = contacts.search_contacts_structured(
            access_token=token,
            query=query,
            limit=limit
        )
        logger.info(f"Found {len(results)} contacts matching '{query}'")
        return results
    except Exception as e:
        logger.error(f"Error searching contacts: {e}")
        raise

# ==========================================
# RESOURCES
# ==========================================

@mcp.resource("o365://mail/unread")
async def unread_emails_resource() -> str:
    """Resource: Current unread email count and recent unread messages"""
    try:
        token = get_authenticated_token()
        messages = mail.get_messages_structured(
            access_token=token,
            unread=True,
            limit=100
        )
        return {
            "uri": "o365://mail/unread",
            "mimeType": "application/json",
            "count": len(messages),
            "messages": messages[:10]  # First 10 for preview
        }
    except Exception as e:
        logger.error(f"Error fetching unread emails resource: {e}")
        raise

@mcp.resource("o365://calendar/today")
async def today_calendar_resource() -> str:
    """Resource: Today's calendar events"""
    try:
        from datetime import date
        token = get_authenticated_token()
        today = date.today().isoformat()
        events = calendar.get_events_structured(
            access_token=token,
            since=today,
            until=today
        )
        return {
            "uri": "o365://calendar/today",
            "mimeType": "application/json",
            "date": today,
            "count": len(events),
            "events": events
        }
    except Exception as e:
        logger.error(f"Error fetching today's calendar resource: {e}")
        raise

@mcp.resource("o365://files/recent")
async def recent_files_resource() -> str:
    """Resource: Recently modified OneDrive files"""
    try:
        token = get_authenticated_token()
        # Get recent files (last 7 days)
        files_list = files.list_files_structured(
            access_token=token,
            path="/",
            recursive=True
        )
        # Sort by modified date, take top 20
        files_list.sort(key=lambda x: x.get("modified", ""), reverse=True)
        return {
            "uri": "o365://files/recent",
            "mimeType": "application/json",
            "count": len(files_list[:20]),
            "files": files_list[:20]
        }
    except Exception as e:
        logger.error(f"Error fetching recent files resource: {e}")
        raise

# ==========================================
# PROMPTS
# ==========================================

@mcp.prompt()
async def review_unread_emails() -> str:
    """Prompt: Review and summarize unread emails"""
    return {
        "name": "review_unread_emails",
        "description": "Review all unread emails and provide a summary",
        "messages": [
            {
                "role": "user",
                "content": "Please review my unread emails and provide a summary organized by priority and topic. Flag any urgent items or action items."
            }
        ]
    }

@mcp.prompt()
async def summarize_todays_meetings() -> str:
    """Prompt: Summarize today's calendar"""
    return {
        "name": "summarize_todays_meetings",
        "description": "Summarize all meetings scheduled for today",
        "messages": [
            {
                "role": "user",
                "content": "Please show me all my meetings scheduled for today, with times, attendees, and locations. Highlight any conflicts or back-to-back meetings."
            }
        ]
    }

@mcp.prompt()
async def find_recent_files() -> str:
    """Prompt: Find recently modified files"""
    return {
        "name": "find_recent_files",
        "description": "Show recently modified OneDrive files",
        "messages": [
            {
                "role": "user",
                "content": "Show me the files I've modified in OneDrive in the last 7 days, organized by type."
            }
        ]
    }

# ==========================================
# SERVER STARTUP
# ==========================================

def main():
    """Run the MCP server"""
    logger.info("Starting Office 365 MCP Server")
    mcp.run()

if __name__ == "__main__":
    main()
```

**Validation:**
- `python -m o365.mcp_server` starts without errors
- `o365-mcp` command works after installation

### Task 3.2: Add CLI Command for MCP Server

**Files to modify:**
- `o365/__main__.py`

**Changes:**
```python
def main():
    parser = argparse.ArgumentParser(
        description="Office365 CLI - Command-line interface for Office 365"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ... existing commands ...

    # MCP server command
    mcp_parser = subparsers.add_parser(
        'mcp',
        help='Start MCP server for LLM integration'
    )
    mcp_parser.add_argument(
        '--transport',
        choices=['stdio', 'sse'],
        default='stdio',
        help='Transport mechanism (default: stdio)'
    )
    mcp_parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    mcp_parser.set_defaults(func=cmd_mcp)

    # ... rest of main() ...

def cmd_mcp(args):
    """Start the MCP server"""
    import logging
    logging.basicConfig(level=getattr(logging, args.log_level))

    from .mcp_server import mcp
    logger.info(f"Starting MCP server with {args.transport} transport")
    mcp.run(transport=args.transport)
```

**Validation:**
- `o365 mcp --help` shows help
- `o365 mcp` starts the server

---

## Phase 4: Testing and Validation

### Task 4.1: Unit Tests for MCP Tools

**New file:** `tests/test_mcp_server.py`

**Test structure:**
```python
import pytest
from unittest.mock import Mock, patch
from o365.mcp_server import (
    read_emails,
    list_calendar_events,
    search_onedrive,
    # ... other tools
)

@pytest.mark.asyncio
async def test_read_emails_unread():
    """Test reading unread emails"""
    with patch('o365.mcp_server.get_authenticated_token') as mock_token, \
         patch('o365.mail.get_messages_structured') as mock_get:

        mock_token.return_value = "test_token"
        mock_get.return_value = [
            {"id": "1", "subject": "Test", "from_email": "test@example.com"}
        ]

        result = await read_emails(unread=True, limit=10)

        assert len(result) == 1
        assert result[0]["subject"] == "Test"
        mock_get.assert_called_once_with(
            access_token="test_token",
            unread=True,
            since=None,
            search=None,
            limit=10
        )

@pytest.mark.asyncio
async def test_list_calendar_events_today():
    """Test listing today's calendar events"""
    with patch('o365.mcp_server.get_authenticated_token') as mock_token, \
         patch('o365.calendar.get_events_structured') as mock_get:

        mock_token.return_value = "test_token"
        mock_get.return_value = [
            {"id": "1", "subject": "Team Meeting", "start": "2025-01-15T10:00:00Z"}
        ]

        result = await list_calendar_events(today=True)

        assert len(result) == 1
        assert result[0]["subject"] == "Team Meeting"

# ... more tests for each tool ...
```

**Validation:**
- All tests pass: `pytest tests/test_mcp_server.py`
- Coverage >80%: `pytest --cov=o365.mcp_server tests/test_mcp_server.py`

### Task 4.2: Integration Testing with Claude Desktop

**Manual test procedure:**

1. **Install the MCP server:**
   ```bash
   pip install -e ".[mcp]"
   ```

2. **Configure Claude Desktop:**

   Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "office365": {
         "command": "o365",
         "args": ["mcp"],
         "env": {}
       }
     }
   }
   ```

3. **Restart Claude Desktop**

4. **Test queries:**
   - "Show me my unread emails from the last 2 days"
   - "What meetings do I have today?"
   - "Search my OneDrive for files containing 'budget'"
   - "List my recent Teams chats"

5. **Verify:**
   - Tools appear in Claude's tool list
   - Queries trigger correct tool calls
   - Responses contain accurate data
   - Error handling works (test with invalid IDs)

### Task 4.3: End-to-End Tests

**New file:** `tests/test_e2e_mcp.py`

Test the full MCP lifecycle:
- Server startup
- Tool discovery
- Tool execution
- Resource access
- Prompt templates
- Error scenarios

---

## Phase 5: Documentation

### Task 5.1: User Documentation

**New file:** `docs/MCP_USER_GUIDE.md`

Contents:
- What is MCP and why use it?
- Installation instructions
- Configuration for Claude Desktop
- Configuration for other MCP clients
- Example queries and use cases
- Troubleshooting

### Task 5.2: Developer Documentation

**New file:** `docs/MCP_DEVELOPER_GUIDE.md`

Contents:
- Architecture overview
- How to add new tools
- How to add new resources
- How to add new prompts
- Testing guidelines
- Contributing to MCP server

### Task 5.3: Update README

**Files to modify:**
- `README.md`

**Add section:**
```markdown
## MCP Server (LLM Integration)

o365-cli includes a Model Context Protocol (MCP) server for integration with Claude Desktop and other MCP-compatible LLM clients.

### Installation

```bash
pip install o365-cli[mcp]
```

### Configuration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "office365": {
      "command": "o365",
      "args": ["mcp"]
    }
  }
}
```

### Usage

Once configured, you can interact with Office 365 through natural language in Claude:

- "Show my unread emails from this week"
- "What meetings do I have tomorrow?"
- "Search OneDrive for the Q4 budget spreadsheet"

See [MCP User Guide](docs/MCP_USER_GUIDE.md) for details.
```

### Task 5.4: API Documentation

**Generate tool/resource reference:**

Create script to auto-generate documentation from docstrings:

```bash
python scripts/generate_mcp_docs.py > docs/MCP_API_REFERENCE.md
```

---

## Phase 6: Optimization and Polish

### Task 6.1: Performance Optimization

- Add caching for frequently accessed resources
- Implement connection pooling for Graph API
- Optimize batch requests where possible
- Profile and optimize slow tools

### Task 6.2: Error Handling

- Comprehensive error messages
- Graceful degradation when permissions missing
- Retry logic for transient failures
- User-friendly error responses

### Task 6.3: Logging and Monitoring

- Structured logging for all tool calls
- Performance metrics
- Usage analytics (optional, privacy-respecting)
- Debug mode for troubleshooting

---

## Success Criteria

### Functional Requirements

- [ ] All 15+ tools implemented and working
- [ ] At least 3 resources defined and accessible
- [ ] At least 3 prompt templates available
- [ ] Authentication works seamlessly
- [ ] Error handling is robust

### Quality Requirements

- [ ] Test coverage >80%
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Works with Claude Desktop
- [ ] Works with other MCP clients (e.g., Continue, Cody)

### User Experience

- [ ] Natural language queries work intuitively
- [ ] Response times <3 seconds for most operations
- [ ] Error messages are helpful
- [ ] Installation is straightforward

---

## Timeline Estimate

| Phase | Tasks | Estimated Time | Dependencies |
|-------|-------|----------------|--------------|
| Phase 1: Setup | 1.1 - 1.3 | 2 hours | None |
| Phase 2: Refactoring | 2.1 - 2.5 | 1-2 days | Phase 1 |
| Phase 3: MCP Server | 3.1 - 3.2 | 2-3 days | Phase 2 |
| Phase 4: Testing | 4.1 - 4.3 | 1-2 days | Phase 3 |
| Phase 5: Documentation | 5.1 - 5.4 | 1 day | Phase 4 |
| Phase 6: Polish | 6.1 - 6.3 | 1 day | Phase 5 |
| **Total** | | **6-10 days** | |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking changes to existing CLI | High | Keep old functions, add new ones |
| Python version incompatibility | Medium | Make MCP optional dependency |
| Graph API rate limiting | Medium | Implement caching and throttling |
| Authentication token expiry | Medium | Auto-refresh tokens in server |
| MCP spec changes | Low | Pin MCP SDK version, monitor updates |

---

## Future Enhancements

After initial implementation, consider:

1. **Real-time notifications** via MCP sampling
2. **Webhook support** for incoming emails/events
3. **Batch operations** (e.g., archive multiple emails)
4. **Advanced search** with complex filters
5. **Integration with other MCP servers** (e.g., GitHub, Slack)
6. **AI-powered email summarization** built into tools
7. **Calendar intelligence** (suggest meeting times, detect conflicts)
8. **File content extraction** (read Excel, Word, PDF content)

---

## Getting Started

To begin implementation:

1. **Review this plan** with team/stakeholders
2. **Set up development environment** (Python 3.10+, install dependencies)
3. **Create feature branch**: `git checkout -b feature/mcp-server`
4. **Start with Phase 1**: Update Python version and dependencies
5. **Iterate through phases**, validating each before moving on
6. **Test early and often** with Claude Desktop

---

## Questions and Decisions Needed

Before starting, clarify:

1. **Python version bump**: OK to require Python 3.10+?
2. **Breaking changes**: OK to refactor internal APIs?
3. **Scope**: Include all features or start with core (mail, calendar)?
4. **Timeline**: Any hard deadlines?
5. **Deployment**: How will users install/upgrade?

---

## Resources

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP Documentation](https://gofastmcp.com/)
- [Claude Desktop Config](https://docs.claude.com/en/docs/mcp)
- [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/api/overview)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-18
**Author:** Planning Session with Claude Code
**Status:** Ready for Review
