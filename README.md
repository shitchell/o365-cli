# Office365 CLI (`o365`)

A unified command-line interface for managing Office365 email, calendar, and contacts.

## Features

- **Email Management**: Sync, read, archive, and send emails
- **Calendar**: View and create calendar events, manage invites
- **Teams Chats**: List, read, send, and search Microsoft Teams chats
- **OneDrive & SharePoint**: List, search, download, and upload files across personal and shared drives
- **Meeting Recordings**: List, search, download, and view transcripts of Teams meeting recordings
- **Contacts**: Search and manage contacts
- **OAuth2 Authentication**: Secure device code flow authentication
- **Local Storage**: Maildir format for offline email access
- **Timezone Support**: Automatic timezone handling for calendar queries
- **Git-style Time Parsing**: Natural time expressions like "2 days ago" and "yesterday"

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

### 2. Sync Emails

Sync your emails to local storage:

```bash
o365 mail sync
```

### 3. Read Emails

List unread emails:

```bash
o365 mail read --unread
```

### 4. View Calendar

See today's events:

```bash
o365 calendar list --today
```

## Usage

### Mail Commands

```bash
# Sync emails from server
o365 mail sync
o365 mail sync --folders Inbox --count 50

# Read emails
o365 mail read --unread
o365 mail read --since "2 days ago" -n 20
o365 mail read 48608adc f1486a8d  # Read by ID

# Archive emails
o365 mail archive 60d1969a 4ab19245

# Mark as read
o365 mail mark-read f1486a8d 0bc59901

# Send email
echo "<p>Hello!</p>" | o365 mail send -r recipient@example.com -S "Subject" -H -
```

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
- **Local Mail**: `~/.mail/office365/` (default)
  - `INBOX/` - Inbox emails
  - `Sent/` - Sent emails
  - `Drafts/` - Draft emails
  - `Trash/` - Deleted emails
  - `Archive/` - Archived emails
- **Sync State**: `~/.mail/office365/.sync-state.json`

All paths can be customized via config file or environment variables.

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
└── auth.py           # Authentication command implementations
```

## Requirements

- Python 3.7+
- `python-dateutil` for time parsing

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
- Maildir format for local email storage
- Device code flow for terminal-friendly OAuth2 authentication
