# Office365 CLI (`o365`)

A unified command-line interface for managing Office365 email, calendar, and contacts.

## Features

- **Email Management**: Sync, read, archive, and send emails
- **Calendar**: View your calendar and others' shared calendars
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
o365 calendar list --user quinn --today
o365 calendar list --user roman --week
```

### Contacts Commands

```bash
# List all contacts
o365 contacts list

# Search for contacts
o365 contacts search quinn
o365 contacts search john@example.com

# Resolve contact (for scripting)
o365 contacts search quinn --resolve
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

### Environment Variables

Create a `~/.env` file with your configuration:

```bash
export SMTP_EMAIL=your.email@example.com
export SMTP_PASSWORD=your-app-password
export SMTP_SIGNATURE_FILE=~/.signature.html

export AZURE_EMAIL_CLIENT_ID=your-client-id
export AZURE_EMAIL_TENANT_ID=your-tenant-id
export AZURE_EMAIL_CLIENT_SECRET=your-client-secret
```

### Azure App Registration

To use this tool, you'll need to register an application in Azure Active Directory with the following Microsoft Graph API permissions:

- `Calendars.Read`
- `Calendars.ReadWrite`
- `Calendars.ReadWrite.Shared`
- `Contacts.Read`
- `Contacts.ReadWrite`
- `Mail.ReadWrite`
- `Mail.Send`
- `MailboxSettings.Read`
- `User.Read`
- `offline_access`

## Storage Locations

- **Local Mail**: `~/.mail/office365/`
  - `INBOX/` - Inbox emails
  - `Sent/` - Sent emails
  - `Drafts/` - Draft emails
  - `Trash/` - Deleted emails
  - `Archive/` - Archived emails

- **OAuth Tokens**: `~/.o365-tokens.json`
- **Sync State**: `~/.mail/office365/.sync-state.json`

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
