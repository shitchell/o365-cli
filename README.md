# Office365 CLI (`o365`)

A unified command-line interface for managing Office365 email, calendar, and contacts.

**✨ NEW: MCP Server Support!** Use Office 365 with Claude Desktop through natural language. [Learn more](#mcp-server)

## Features

### Core Features

- **Email Management**: Read, archive, mark read, and send emails via Graph API
- **Calendar**: View and create calendar events, manage invites
- **Teams Chats**: List, read, send, and search Microsoft Teams chats
- **OneDrive & SharePoint**: List, search, download, and upload files across personal and shared drives
- **Meeting Recordings**: List, search, download, and view transcripts of Teams meeting recordings
- **Contacts**: Search and manage contacts
- **OAuth2 Authentication**: Secure device code flow authentication
- **Streaming Results**: Efficient pagination with immediate display for large result sets
- **External Sender Detection**: Automatic tagging of emails from outside your organization
- **Attachment Support**: Download email attachments with inline image detection
- **Timezone Support**: Automatic timezone handling for calendar queries
- **Git-style Time Parsing**: Natural time expressions like "2 days ago" and "yesterday"

### 🚀 MCP Server (NEW!)

- **Model Context Protocol Server**: Integrate Office 365 with Claude Desktop and other MCP clients
- **20 Tools**: Access email, calendar, files, chats, contacts, and recordings via natural language
- **3 Prompt Templates**: Pre-built workflows for common tasks
- **Natural Language Queries**: Just ask Claude what you need!

**Example MCP queries:**
- "Check my unread emails from the last 2 days"
- "What meetings do I have tomorrow?"
- "Search my OneDrive for budget spreadsheets"
- "Show me my recent Teams chats"

See [MCP Server](#mcp-server) section below for setup instructions.

## Installation

### From PyPI (when published)

```bash
pip install o365-cli
```

### From Source

```bash
git clone https://github.com/yourusername/o365-cli.git
cd o365-cli
pip install -e .
```

### Development Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/o365-cli.git
cd o365-cli

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

## Quick Start

### 1. Authentication

First, authenticate with Office365:

```bash
o365 auth login
```

This will prompt you to visit a URL and enter a device code. Follow the instructions to complete authentication.

### 2. Read Emails

List unread emails:

```bash
o365 mail read --unread
```

### 3. View Calendar

See today's events:

```bash
o365 calendar list --today
```

## Usage

### Mail Commands

```bash
# List emails (streams all results by default)
o365 mail read
o365 mail read --unread                      # Only unread emails
o365 mail read --since "2 days ago"          # Emails from last 2 days
o365 mail read -n 20                         # Limit to 20 most recent
o365 mail read -s "payment"                  # Search for "payment"

# Read specific email by ID (full Graph API message ID)
o365 mail read AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3...

# Archive emails (use full message IDs from mail read output)
o365 mail archive AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3...
o365 mail archive --dry-run AAMkADFhY2VlZWU4...  # Preview first

# Mark emails as read
o365 mail mark-read AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3...
o365 mail mark-read --dry-run AAMkADFhY2VlZWU4...  # Preview first

# Download email attachment
o365 mail download-attachment <MESSAGE_ID> <ATTACHMENT_ID>
o365 mail download-attachment <MESSAGE_ID> <ATTACHMENT_ID> -o ~/Downloads/

# Send email
echo "<p>Hello!</p>" | o365 mail send -r recipient@example.com -S "Subject" -H -
```

**Note**: Message IDs are displayed in full when listing emails. Copy the full ID from the `ID:` line to use with read, archive, or mark-read commands. The `[external]` prefix indicates emails from senders outside your organization.

### Calendar Commands

```bash
# View your calendar
o365 calendar list --today
o365 calendar list --week
o365 calendar list --after "3 days ago"

# View someone else's calendar
o365 calendar list --user john --today
o365 calendar list --user john --week
```

### Chat Commands

```bash
# List chats
o365 chat list
o365 chat list --with john            # Filter to chats with john
o365 chat list --since "2 days ago"    # Recent chats

# Read messages
o365 chat read <chat-id>
o365 chat read --with john            # Read chat with john
o365 chat read --with "Project Team"   # Read group chat

# Send messages
o365 chat send --to john -m "Quick question"
o365 chat send --chat <chat-id> -m "Message here"

# Search messages
o365 chat search "deployment"
o365 chat search "bug fix" --with john   # Search in john's chats
o365 chat search "meeting" --since "1 week ago"
```

### Files Commands

```bash
# List available drives
o365 files drives
o365 files drives -v                   # Show drive IDs and details

# List files
o365 files list                        # List root of personal OneDrive
o365 files list /Documents             # List Documents folder
o365 files list -l --since "1 week ago"     # Recent files with details

# Search files
o365 files search "quarterly report"
o365 files search "budget" --type xlsx              # Excel files only

# Download files
o365 files download /Reports/Q4.xlsx
o365 files download /Reports/Q4.xlsx ~/Desktop/     # To specific location

# Upload files
o365 files upload ~/analysis.pdf /Reports/
```

**Note:** By default, only **personal OneDrive** access is enabled. To access shared drives and SharePoint sites, enable the additional scopes in your config:

```ini
[scopes]
files.all = true   # Enable access to shared drives
sites.all = true   # Enable access to SharePoint sites
```

These permissions (`Files.Read.All`, `Files.ReadWrite.All`, `Sites.Read.All`, `Sites.ReadWrite.All`) may require admin consent in some organizations. See [Azure App Registration](#azure-app-registration) for details.

### Recordings Commands

```bash
# List recordings
o365 recordings list
o365 recordings list --since "1 week ago"     # Recent recordings
o365 recordings list -n 100                   # Last 100 recordings

# Search recordings
o365 recordings search "sprint planning"
o365 recordings search "review" --since "1 month ago"

# Download recording
o365 recordings download <recording-id>
o365 recordings download <recording-id> ~/Videos/

# View transcript
o365 recordings transcript <recording-id>
o365 recordings transcript <recording-id> --output notes.txt
o365 recordings transcript <recording-id> --format vtt
o365 recordings transcript <recording-id> --timestamps --speakers

# Get recording info
o365 recordings info <recording-id>
```

**Note:** Recordings commands require **Files** permissions to be enabled (recordings are stored in OneDrive). Use `o365 recordings list` or `o365 recordings search` to get recording IDs.

### Contacts Commands

```bash
# List all contacts
o365 contacts list

# Search for contacts
o365 contacts search john
o365 contacts search john@example.com

# Resolve contact (for scripting)
o365 contacts search john --resolve
```

### Authentication Commands

```bash
# Initial login
o365 auth login

# Refresh token
o365 auth refresh

# Check status
o365 auth status
```

### Config Commands

```bash
# List all configuration values
o365 config list

# Get a specific value
o365 config get auth.client_id
o365 config get scopes.mail

# Set a value
o365 config set auth.client_id "your-client-id"
o365 config set auth.tenant "common"
o365 config set scopes.files.all "true"

# Remove a value
o365 config unset scopes.custom

# Edit config file in editor
o365 config edit

# Show config file path
o365 config path
```

## Configuration

### Required Setup

Before using o365-cli, you must configure your Azure AD application credentials. There are two ways to do this:

#### Option 1: Config File (Recommended)

Create `~/.config/o365/config`:

```ini
[auth]
client_id = your-azure-ad-application-id
tenant = your-azure-ad-tenant-id

[scopes]
# Enable/disable command groups (all enabled by default)
mail = true
calendar = true
contacts = true
chat = true
files = true

# Optional: Enable .All scopes for shared drives/sites (may require admin consent)
files.all = false      # Access shared drives (Files.Read.All, Files.ReadWrite.All)
sites.all = false      # Access SharePoint sites (Sites.Read.All, Sites.ReadWrite.All)

[paths]
# Optional: customize storage locations
# token_file = ~/.config/o365/tokens.json
# mail_dir = ~/.mail/office365/
```

See `config.example` for a complete configuration template.

#### Option 2: Environment Variables

```bash
export O365_CLIENT_ID=your-azure-ad-application-id
export O365_TENANT=your-azure-ad-tenant-id

# Optional: customize scopes
export O365_SCOPES="https://graph.microsoft.com/Mail.Read,https://graph.microsoft.com/User.Read,offline_access"

# Optional: customize paths
export O365_TOKEN_FILE=~/.config/o365/tokens.json
export O365_MAIL_DIR=~/.mail/office365/
```

**Priority**: Environment variables override config file settings.

### Azure App Registration

To use this tool, you need to register an application in Azure Active Directory:

1. Go to [Azure Portal](https://portal.azure.com) → **App registrations** → **New registration**
2. Set **Redirect URI** to: `Public client/native (mobile & desktop)` with value `https://login.microsoftonline.com/common/oauth2/nativeclient`
3. Under **API permissions**, add these **Microsoft Graph** delegated permissions:
   - `Calendars.Read`
   - `Calendars.ReadWrite`
   - `Calendars.ReadWrite.Shared`
   - `Chat.Read`
   - `Chat.ReadWrite`
   - `ChatMessage.Send`
   - `Contacts.Read`
   - `Contacts.ReadWrite`
   - `Files.Read`
   - `Files.ReadWrite`
   - `Mail.ReadWrite`
   - `Mail.Send`
   - `MailboxSettings.Read`
   - `User.Read`
   - `offline_access`

   **Optional (for shared drives/SharePoint, may require admin consent):**
   - `Files.Read.All`
   - `Files.ReadWrite.All`
   - `Sites.Read.All`
   - `Sites.ReadWrite.All`

4. Copy the **Application (client) ID** and **Directory (tenant) ID** to your config file

**Important**: After adding new permissions to your Azure AD app or changing scopes in your config file, you must re-authenticate:
```bash
o365 auth login
```

**Note**: You can request fewer permissions if you only need specific features. For example, for mail-only access:

```ini
[scopes]
mail = true
calendar = false
contacts = false
chat = false
files = false
```

### Additional Configuration (Mail Sending)

For `o365 mail send`, you also need SMTP configuration in `~/.env`:

```bash
export SMTP_EMAIL=your.email@example.com
export SMTP_PASSWORD=your-app-password
export SMTP_SIGNATURE_FILE=~/.signature.html
```

## Storage Locations

- **Configuration**: `~/.config/o365/config`
- **OAuth Tokens**: `~/.config/o365/tokens.json` (default)

All paths can be customized via config file or environment variables.

**Note**: Email commands now interact directly with Office365 via Graph API rather than syncing to local storage.

## MCP Server

The Office 365 MCP (Model Context Protocol) Server enables natural language interaction with your Office 365 account through Claude Desktop and other MCP-compatible clients.

### What is MCP?

Model Context Protocol (MCP) is an open protocol developed by Anthropic that allows AI assistants like Claude to securely connect to external data sources and tools. With the Office 365 MCP server, you can use natural language to:

- Check and manage your emails
- View and create calendar events
- Search and manage files in OneDrive
- Read and send Teams messages
- Search contacts
- Access meeting recordings and transcripts

### Quick Setup

1. **Install with MCP support:**

```bash
pip install git+https://github.com/shitchell/o365-cli.git
pip install "o365-cli[mcp]"
```

2. **Authenticate with Office 365:**

```bash
o365 auth login
```

3. **Configure Claude Desktop:**

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or equivalent:

```json
{
  "mcpServers": {
    "office365": {
      "command": "/path/to/o365-mcp"
    }
  }
}
```

Find your path with: `which o365-mcp`

4. **Restart Claude Desktop** and look for the 🔨 icon to see 20 available Office 365 tools!

### Available Tools

The MCP server provides **20 tools** across 6 categories:

| Category | Tools | Examples |
|----------|-------|----------|
| **📧 Email** | `read_emails`, `get_email_content`, `send_email` | "Check unread emails from last week" |
| **📅 Calendar** | `list_calendar_events`, `create_calendar_event`, `delete_calendar_event` | "What meetings do I have tomorrow?" |
| **📁 Files** | `list_onedrive_files`, `search_onedrive`, `download_onedrive_file`, `upload_onedrive_file` | "Search OneDrive for budget files" |
| **💬 Teams Chat** | `list_teams_chats`, `read_chat_messages`, `send_chat_message`, `search_teams_messages` | "Show recent Teams messages" |
| **👥 Contacts** | `search_contacts`, `list_contacts` | "Find John Doe's email" |
| **🎥 Recordings** | `list_recordings`, `search_recordings`, `download_recording`, `get_recording_transcript` | "List last week's meeting recordings" |

### Example Queries

Once configured, you can ask Claude Desktop questions like:

```
What unread emails do I have from the last 2 days?

Show me my calendar for next week

Search my OneDrive for files containing "quarterly report"

What are my recent Teams chats?

Create a meeting tomorrow at 2pm titled "Project Sync" with john@example.com

List my Teams meeting recordings from last month
```

### Documentation

- **[MCP User Guide](docs/MCP_USER_GUIDE.md)** - Complete setup and usage guide
- **[Tool Reference](docs/MCP_TOOLS_REFERENCE.md)** - Detailed documentation for all 20 tools
- **[Implementation Plan](docs/MCP_IMPLEMENTATION_PLAN.md)** - Technical architecture and development details

### Entry Points

The MCP server can be started two ways:

```bash
# Dedicated command
o365-mcp

# Subcommand
o365 mcp
```

Both start the same MCP server. Claude Desktop will use the configured command automatically.

## Architecture

The `o365` command is implemented as a Python package with the following structure:

```
o365/
├── __init__.py       # Package initialization
├── __main__.py       # Main entry point and command routing
├── common.py         # Shared utilities (auth, API calls, constants)
├── mail.py           # Mail command implementations
├── calendar.py       # Calendar command implementations
├── contacts.py       # Contacts command implementations
├── chat.py           # Teams chat command implementations
├── files.py          # OneDrive/SharePoint command implementations
├── recordings.py     # Meeting recordings command implementations
├── auth.py           # Authentication command implementations
├── config_cmd.py     # Configuration command implementations
└── mcp_server.py     # MCP server implementation (20 tools, 3 prompts, 1 resource)
```

Each module provides both CLI commands and structured data functions, enabling both command-line usage and MCP integration.

## Requirements

### Core Requirements

- Python 3.10+ (3.10+ required for MCP server)
- `python-dateutil` for time parsing
- `html2text` for email content conversion

### Optional Requirements

- `mcp` SDK for MCP server functionality (install with `pip install "o365-cli[mcp]"`)

### Development Requirements

- `pytest` for testing
- `pytest-mock` for test mocking
- `black` for code formatting
- `flake8` for linting

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black o365/
```

### Linting

```bash
flake8 o365/
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- Uses Microsoft Graph API for Office365 integration
- Device code flow for terminal-friendly OAuth2 authentication
- HTML to text conversion via html2text library
