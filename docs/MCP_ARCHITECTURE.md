# MCP Server Architecture for o365-cli

## System Overview

This document describes the architecture of the MCP (Model Context Protocol) server integration for o365-cli, explaining how components interact and data flows through the system.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Client (Claude Desktop)                 │
│                                                                   │
│  User Query: "Show my unread emails from today"                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ JSON-RPC over stdio
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                     o365 MCP Server                              │
│                   (o365/mcp_server.py)                           │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    MCP Protocol Layer                       │ │
│  │  - Tool discovery                                           │ │
│  │  - Resource listing                                         │ │
│  │  - Prompt templates                                         │ │
│  │  - Request/response handling                                │ │
│  └────────────────────┬───────────────────────────────────────┘ │
│                       │                                           │
│  ┌────────────────────▼───────────────────────────────────────┐ │
│  │                   Tool Layer                                │ │
│  │  @mcp.tool()                                                │ │
│  │  - read_emails()                                            │ │
│  │  - list_calendar_events()                                   │ │
│  │  - search_onedrive()                                        │ │
│  │  - list_teams_chats()                                       │ │
│  │  - ... 15+ tools total                                      │ │
│  └────────────────────┬───────────────────────────────────────┘ │
│                       │                                           │
│  ┌────────────────────▼───────────────────────────────────────┐ │
│  │                Authentication Layer                         │ │
│  │  - get_authenticated_token()                                │ │
│  │  - Auto token refresh                                       │ │
│  │  - Config loading                                           │ │
│  └────────────────────┬───────────────────────────────────────┘ │
└───────────────────────┼───────────────────────────────────────┘
                        │
                        │ Uses existing modules
                        │
┌───────────────────────▼───────────────────────────────────────┐
│                  o365-cli Core Modules                         │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  mail.py │  │calendar  │  │ files.py │  │  chat.py │      │
│  │          │  │   .py    │  │          │  │          │      │
│  │  NEW:    │  │          │  │  NEW:    │  │  NEW:    │      │
│  │  get_    │  │  NEW:    │  │  list_   │  │  get_    │      │
│  │  messages│  │  get_    │  │  files_  │  │  chats_  │      │
│  │  _struct │  │  events_ │  │  struct  │  │  struct  │      │
│  │  ured()  │  │  struct  │  │  ured()  │  │  ured()  │      │
│  └──────────┘  │  ured()  │  └──────────┘  └──────────┘      │
│                 └──────────┘                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │
│  │contacts  │  │recordings│  │ common.py│                     │
│  │   .py    │  │   .py    │  │          │                     │
│  │          │  │          │  │ - Graph  │                     │
│  │  NEW:    │  │  NEW:    │  │   API    │                     │
│  │  search_ │  │  get_    │  │ - Token  │                     │
│  │  contacts│  │  record  │  │   mgmt   │                     │
│  │  _struct │  │  ings_   │  │ - Config │                     │
│  │  ured()  │  │  struct  │  │          │                     │
│  └──────────┘  │  ured()  │  └──────────┘                     │
│                 └──────────┘                                    │
└───────────────────────┬───────────────────────────────────────┘
                        │
                        │ HTTPS requests
                        │
┌───────────────────────▼───────────────────────────────────────┐
│              Microsoft Graph API (api.graph.microsoft.com)     │
│                                                                 │
│  - /me/messages                                                │
│  - /me/calendar/events                                         │
│  - /me/drive/root/children                                     │
│  - /me/chats                                                   │
│  - /users                                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. MCP Server (`o365/mcp_server.py`)

**Responsibilities:**
- Implements MCP protocol using FastMCP
- Defines tools, resources, and prompts
- Handles authentication for all requests
- Marshals data between MCP format and o365-cli modules
- Logging and error handling

**Key Functions:**
```python
# Tools
@mcp.tool() async def read_emails(...)
@mcp.tool() async def list_calendar_events(...)
@mcp.tool() async def search_onedrive(...)

# Resources
@mcp.resource("o365://mail/unread") async def unread_emails_resource()
@mcp.resource("o365://calendar/today") async def today_calendar_resource()

# Prompts
@mcp.prompt() async def review_unread_emails()
@mcp.prompt() async def summarize_todays_meetings()

# Authentication
def get_authenticated_token() -> str
```

**Configuration:**
- Uses existing o365-cli config (`~/.config/o365/config`)
- Leverages existing token storage (`~/.config/o365/tokens.json`)
- No new configuration files needed

### 2. Data Layer (Refactored Modules)

**Current State:**
```python
# mail.py (current)
def cmd_read(args):
    """CLI command - prints formatted output to stdout"""
    messages = get_messages_stream(...)
    for msg in messages:
        print(f"● [{date}] {from_name}")
        print(f"  Subject: {subject}")
```

**New State:**
```python
# mail.py (refactored)
def cmd_read(args):
    """CLI command - prints formatted output to stdout"""
    messages = get_messages_structured(...)  # Get raw data
    for msg in messages:
        # Format and print
        print(f"● [{msg['received_datetime']}] {msg['from_name']}")
        print(f"  Subject: {msg['subject']}")

def get_messages_structured(...) -> list[dict]:
    """
    Get messages as structured data (for MCP).
    Returns list of dicts instead of formatted strings.
    """
    # Graph API call logic (shared)
    messages = []
    # ... fetch from Graph API ...
    return messages
```

**Pattern:**
- **CLI commands** (`cmd_*`) → Format data for terminal display
- **Structured functions** (`*_structured`) → Return raw dict/list data
- **Graph API logic** → Shared by both

**Benefits:**
- No duplication of Graph API calls
- CLI remains unchanged
- MCP gets structured data
- Single source of truth

### 3. Authentication Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. MCP Tool Called (e.g., read_emails)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  2. get_authenticated_token()                                │
│     - Load config from ~/.config/o365/config                 │
│     - Load tokens from ~/.config/o365/tokens.json            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
                    ┌────────┐
                    │ Token  │
                    │ Valid? │
                    └───┬────┘
                        │
            ┌───────────┴───────────┐
            │                       │
           Yes                     No
            │                       │
            ▼                       ▼
    ┌───────────────┐      ┌─────────────────┐
    │ Return token  │      │ Refresh token   │
    │ (use within   │      │ (POST to OAuth) │
    │  5 min buffer)│      └────────┬────────┘
    └───────────────┘               │
                                    ▼
                            ┌───────────────────┐
                            │ Save new tokens   │
                            │ Return new token  │
                            └───────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Call Graph API with access_token                         │
│     Authorization: Bearer {token}                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Return structured data to MCP client                     │
└─────────────────────────────────────────────────────────────┘
```

**Token Management:**
- Tokens stored in `~/.config/o365/tokens.json`
- Auto-refresh when <5 minutes from expiry
- Refresh token valid for 90 days (configurable by Azure AD)
- Long-running MCP server handles refreshes transparently

### 4. MCP Protocol Messages

**Tool Discovery (Client → Server):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}
```

**Tool List Response (Server → Client):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "read_emails",
        "description": "Read Office 365 emails with optional filters",
        "inputSchema": {
          "type": "object",
          "properties": {
            "unread": {"type": "boolean"},
            "since": {"type": "string"},
            "search": {"type": "string"},
            "limit": {"type": "integer", "default": 50}
          }
        }
      },
      // ... more tools ...
    ]
  }
}
```

**Tool Call (Client → Server):**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "read_emails",
    "arguments": {
      "unread": true,
      "since": "48 hours ago",
      "limit": 10
    }
  }
}
```

**Tool Result (Server → Client):**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[{\"id\": \"AAMk...\", \"subject\": \"Meeting notes\", ...}, ...]"
      }
    ]
  }
}
```

### 5. Data Schemas

**Email Message Schema:**
```python
{
    "id": str,                      # Graph API message ID
    "subject": str,                 # Email subject
    "from_email": str,              # Sender email address
    "from_name": str,               # Sender display name
    "received_datetime": str,       # ISO 8601 timestamp
    "is_read": bool,                # Read status
    "has_attachments": bool,        # Attachment presence
    "body_preview": str,            # First 255 chars of body
    "is_external": bool,            # External sender flag
    "attachments": [                # Optional, if has_attachments
        {
            "id": str,
            "name": str,
            "size": int,
            "content_type": str
        }
    ]
}
```

**Calendar Event Schema:**
```python
{
    "id": str,
    "subject": str,
    "start": str,                   # ISO 8601
    "end": str,                     # ISO 8601
    "location": str | None,
    "is_all_day": bool,
    "is_online_meeting": bool,
    "online_meeting_url": str | None,
    "organizer_email": str,
    "organizer_name": str,
    "attendees": [
        {
            "email": str,
            "name": str,
            "response_status": str   # "accepted" | "declined" | "tentative" | "none"
        }
    ],
    "body_preview": str
}
```

**File/Folder Schema:**
```python
{
    "id": str,
    "name": str,
    "path": str,
    "type": "file" | "folder",
    "size": int | None,             # Bytes, None for folders
    "modified": str,                # ISO 8601
    "created": str,                 # ISO 8601
    "web_url": str,                 # SharePoint URL
    "download_url": str | None      # Direct download URL, None for folders
}
```

## Process Flows

### 1. Reading Emails

```
User in Claude: "Show my unread emails from today"
                        ↓
Claude analyzes query → Decides to use read_emails tool
                        ↓
MCP Client → Server: tools/call
  {
    "name": "read_emails",
    "arguments": {"unread": true, "since": "today"}
  }
                        ↓
MCP Server (o365/mcp_server.py):
  1. read_emails(unread=True, since="today")
  2. get_authenticated_token()
  3. mail.get_messages_structured(token, unread=True, since="today")
                        ↓
mail.py:
  1. Parse "today" → date range
  2. Build Graph API query URL
  3. GET https://graph.microsoft.com/v1.0/me/messages?...
  4. Parse response JSON
  5. Return list[dict]
                        ↓
MCP Server:
  1. Receive structured data
  2. Return to client as JSON
                        ↓
Claude:
  1. Receive email data
  2. Format into natural language response
  3. Present to user: "You have 5 unread emails from today:
     - Meeting notes from Alice...
     - Project update from Bob...
     ..."
```

### 2. Creating Calendar Event

```
User in Claude: "Schedule a team meeting tomorrow at 2pm for 1 hour"
                        ↓
Claude → MCP Server: create_calendar_event
  {
    "subject": "Team Meeting",
    "start": "tomorrow 2pm",
    "end": "tomorrow 3pm"
  }
                        ↓
MCP Server:
  1. create_calendar_event(...)
  2. get_authenticated_token()
  3. calendar.create_event_structured(...)
                        ↓
calendar.py:
  1. Parse "tomorrow 2pm" → ISO 8601 timestamp
  2. Build event JSON payload
  3. POST https://graph.microsoft.com/v1.0/me/events
  4. Return created event with ID
                        ↓
MCP Server → Claude: Event created
                        ↓
Claude → User: "I've scheduled a Team Meeting for tomorrow at 2:00 PM,
                ending at 3:00 PM. Event ID: AAMk..."
```

### 3. Resource Access

```
Claude needs context about unread emails
                        ↓
Claude → MCP Server: resources/read
  {"uri": "o365://mail/unread"}
                        ↓
MCP Server:
  1. @mcp.resource("o365://mail/unread") decorator matches
  2. Call unread_emails_resource()
  3. get_authenticated_token()
  4. mail.get_messages_structured(unread=True, limit=100)
                        ↓
MCP Server → Claude:
  {
    "uri": "o365://mail/unread",
    "mimeType": "application/json",
    "count": 12,
    "messages": [/* first 10 messages */]
  }
                        ↓
Claude uses this context for answering questions
```

## Deployment Architecture

### Development Environment

```
Developer Machine
├── Source Code: <project-root>/
├── Python venv: .venv/ (Python 3.10+)
├── Config: ~/.config/o365/config
├── Tokens: ~/.config/o365/tokens.json
└── Claude Desktop Config: ~/Library/Application Support/Claude/
```

### Production Install (End User)

```bash
# Install from PyPI (or GitHub)
pip install o365-cli[mcp]

# Configure Office 365
o365 config set auth.client_id "..."
o365 config set auth.tenant "..."

# Authenticate
o365 auth login

# Configure Claude Desktop
# Edit: ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "office365": {
      "command": "o365",
      "args": ["mcp"]
    }
  }
}

# Restart Claude Desktop → MCP server auto-starts on demand
```

### Server Lifecycle

```
Claude Desktop starts
        ↓
Reads claude_desktop_config.json
        ↓
Discovers "office365" MCP server config
        ↓
When user starts new conversation:
  1. Spawn process: `o365 mcp`
  2. Communicate via stdio (JSON-RPC)
  3. Keep process alive during conversation
        ↓
When conversation ends:
  1. Close stdio connection
  2. MCP server process terminates
        ↓
Next conversation:
  1. Spawn new process
  2. Repeat cycle
```

**Note:** MCP server is stateless (config/tokens on disk), so process restarts are OK.

## Error Handling

### Error Categories

1. **Authentication Errors**
   - Token expired and refresh failed
   - Invalid client_id/tenant
   - User not authenticated
   - **Mitigation:** Return clear error message, suggest `o365 auth login`

2. **Graph API Errors**
   - Rate limiting (429 Too Many Requests)
   - Permission denied (403 Forbidden)
   - Resource not found (404 Not Found)
   - **Mitigation:** Retry with backoff, return user-friendly error

3. **Input Validation Errors**
   - Invalid date format
   - Invalid email ID
   - Missing required parameters
   - **Mitigation:** Validate in tool, return helpful error with examples

4. **Network Errors**
   - Connection timeout
   - DNS resolution failure
   - **Mitigation:** Retry, return error if persistent

### Error Response Format

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32000,
    "message": "Authentication token expired. Please run: o365 auth login",
    "data": {
      "error_type": "AuthenticationError",
      "suggestion": "o365 auth login"
    }
  }
}
```

## Performance Considerations

### Caching Strategy

**Token Caching:**
- Tokens cached on disk: `~/.config/o365/tokens.json`
- Refresh only when <5 min from expiry
- No in-memory cache needed (process lifetime < token lifetime)

**Data Caching:**
- **Don't cache by default** (data changes frequently)
- Optional: Cache resources for 60 seconds (e.g., unread count)
- Future: Implement Redis/memcached for shared caching

### Rate Limiting

**Graph API Limits:**
- ~10,000 requests per 10 minutes per user
- Throttling: 429 response with Retry-After header

**Mitigation:**
- Respect Retry-After header
- Implement exponential backoff
- Limit pagination (max 200 items per tool call)
- Use `$top` and `$skip` for pagination

### Parallel Requests

**Opportunities:**
- Fetch multiple resources in parallel (e.g., mail + calendar)
- Batch Graph API requests (future enhancement)

**Implementation:**
```python
import asyncio

async def get_dashboard():
    """Fetch multiple resources in parallel"""
    results = await asyncio.gather(
        read_emails(unread=True, limit=10),
        list_calendar_events(today=True),
        list_teams_chats(limit=5)
    )
    return {
        "emails": results[0],
        "events": results[1],
        "chats": results[2]
    }
```

## Security Considerations

### Token Security

- Tokens stored with `chmod 0o600` (owner read/write only)
- Never log tokens
- Tokens transmitted only over HTTPS to Microsoft Graph API
- MCP communication over local stdio (no network exposure)

### Permissions (OAuth Scopes)

```python
# Minimal scopes (default)
SCOPES = [
    "User.Read",
    "Mail.ReadWrite",
    "Mail.Send",
    "Calendars.ReadWrite",
    "Chat.ReadWrite",
    "Files.ReadWrite",        # Personal OneDrive only
    "Contacts.Read",
]

# Admin-required scopes (optional)
ADMIN_SCOPES = [
    "Files.ReadWrite.All",    # Shared drives
    "Sites.ReadWrite.All",    # SharePoint
]
```

### Input Validation

- Sanitize all user inputs before Graph API calls
- Validate email addresses, dates, file paths
- Prevent path traversal attacks (e.g., `../../etc/passwd`)
- Limit string lengths (prevent DoS)

## Testing Strategy

### Unit Tests

```python
# tests/test_mcp_server.py
- Mock get_authenticated_token()
- Mock Graph API responses
- Test each tool independently
- Test error conditions
```

### Integration Tests

```python
# tests/test_e2e_mcp.py
- Spawn MCP server process
- Send JSON-RPC messages via stdio
- Verify responses
- Test resource access
- Test prompt templates
```

### Manual Testing

```
Claude Desktop:
1. Configure MCP server
2. Test natural language queries
3. Verify tool calls
4. Check error handling
```

## Monitoring and Logging

### Logging Levels

- **DEBUG:** All Graph API requests/responses
- **INFO:** Tool calls, authentication events
- **WARNING:** Retry attempts, deprecations
- **ERROR:** Failed requests, authentication failures

### Log Format

```
2025-10-18 14:32:15 INFO [o365.mcp_server] Tool called: read_emails(unread=True, limit=10)
2025-10-18 14:32:15 DEBUG [o365.mail] Graph API request: GET /me/messages?$filter=isRead eq false&$top=10
2025-10-18 14:32:16 INFO [o365.mcp_server] Retrieved 7 emails in 0.8s
```

### Metrics (Future)

- Tool call counts
- Average response times
- Error rates
- Token refresh frequency

## Future Architecture Evolution

### Phase 2 Enhancements

1. **Webhook Support**
   - Real-time notifications for new emails/events
   - Push updates to MCP client via sampling

2. **Batch Operations**
   - Archive multiple emails in one call
   - Create multiple events from list

3. **Advanced Search**
   - Full-text search across all resources
   - Complex filters (AND/OR/NOT)

4. **Content Extraction**
   - Read Excel files, return structured data
   - Extract text from PDFs
   - Parse Word documents

### Phase 3 - Multi-Tenancy

Support multiple Office 365 accounts:
```json
{
  "mcpServers": {
    "office365-work": {
      "command": "o365",
      "args": ["mcp", "--profile", "work"]
    },
    "office365-personal": {
      "command": "o365",
      "args": ["mcp", "--profile", "personal"]
    }
  }
}
```

---

**Document Version:** 1.0
**Last Updated:** 2025-10-18
**Status:** Architecture Specification
