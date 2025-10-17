# MVC Architecture Proposal for o365-cli

## Overview

Refactor o365-cli to follow Model-View-Controller architecture for:
- **Consistent formatting** across all commands
- **Context-aware output** (TUI mode vs plain mode)
- **Better testability** and maintainability
- **Unified API client** with shared logic

## Directory Structure

```
o365/
├── __init__.py
├── __main__.py              # Entry point (routing only)
├── common.py                # Shared utilities (legacy, to be deprecated)
│
├── models/                  # MODEL: Data & API Logic
│   ├── __init__.py
│   ├── base.py             # Base model class, Graph API client
│   ├── mail.py             # Mail data operations
│   ├── calendar.py         # Calendar data operations
│   ├── chat.py             # Chat data operations
│   ├── files.py            # Files data operations
│   ├── recordings.py       # Recordings data operations
│   └── contacts.py         # Contacts data operations
│
├── views/                   # VIEW: Output Formatting
│   ├── __init__.py
│   ├── base.py             # Base view classes, TTY detection
│   ├── formatters.py       # Table, list, detail formatters
│   ├── colors.py           # ANSI color utilities
│   ├── mail.py             # Mail-specific formatting
│   ├── calendar.py         # Calendar-specific formatting
│   ├── chat.py             # Chat-specific formatting
│   ├── files.py            # Files-specific formatting
│   └── recordings.py       # Recordings-specific formatting
│
├── controllers/             # CONTROLLER: Command Logic
│   ├── __init__.py
│   ├── base.py             # Base controller class
│   ├── mail.py             # Mail command handlers
│   ├── calendar.py         # Calendar command handlers
│   ├── chat.py             # Chat command handlers
│   ├── files.py            # Files command handlers
│   ├── recordings.py       # Recordings command handlers
│   ├── contacts.py         # Contacts command handlers
│   ├── auth.py             # Auth command handlers
│   └── config.py           # Config command handlers
│
└── cli/                     # CLI Argument Parsing
    ├── __init__.py
    ├── parsers.py          # Shared argument parser utilities
    └── validators.py       # Input validation functions
```

## Layer Responsibilities

### Model Layer (`models/`)

**Purpose**: Pure data operations and API interactions

**Responsibilities**:
- Make Graph API requests
- Parse and validate API responses
- Data transformation and business logic
- Caching and pagination logic
- No formatting or display logic
- No argument parsing

**Example**:
```python
# models/mail.py
class MailModel:
    def __init__(self, access_token):
        self.client = GraphClient(access_token)

    def get_messages(self, folder='Inbox', max_count=None, since=None,
                     unread=None, search=None):
        """Get messages as raw data (generator of dicts)"""
        # Returns: Generator[List[dict]]
        pass

    def get_message(self, message_id):
        """Get single message by ID"""
        # Returns: dict
        pass

    def archive_message(self, message_id):
        """Archive a message, return updated message"""
        # Returns: dict
        pass
```

### View Layer (`views/`)

**Purpose**: Format data for display

**Responsibilities**:
- Detect TTY vs non-TTY mode
- Format data as tables, lists, or detail views
- Apply colors and styling (TTY mode only)
- Handle icons and emoji (TTY mode only)
- Provide both rich and plain formatters
- No business logic
- No API calls

**Example**:
```python
# views/mail.py
class MailView(BaseView):
    def format_message_list(self, messages, user_domain):
        """Format list of messages for display"""
        if self.is_tty:
            return self._format_tty_list(messages, user_domain)
        else:
            return self._format_plain_list(messages, user_domain)

    def format_message_detail(self, message):
        """Format single message for display"""
        if self.is_tty:
            return self._format_tty_detail(message)
        else:
            return self._format_plain_detail(message)
```

### Controller Layer (`controllers/`)

**Purpose**: Coordinate between models and views

**Responsibilities**:
- Receive parsed arguments
- Call model methods to get data
- Pass data to view for formatting
- Handle errors and user feedback
- Implement command-specific logic
- Progress indication and streaming
- No direct API calls
- No direct formatting

**Example**:
```python
# controllers/mail.py
class MailController(BaseController):
    def __init__(self, args):
        self.args = args
        self.model = MailModel(get_access_token())
        self.view = MailView()

    def read(self):
        """Handle 'o365 mail read' command"""
        if self.args.ids:
            # Read specific messages
            for msg_id in self.args.ids:
                msg = self.model.get_message(msg_id)
                print(self.view.format_message_detail(msg))
        else:
            # List messages
            user_domain = self.model.get_user_domain()
            for page in self.model.get_messages_stream(...):
                for msg in page:
                    print(self.view.format_message_summary(msg, user_domain))
```

## Benefits

1. **Testability**: Each layer can be tested independently
2. **Consistency**: Shared formatters ensure uniform output
3. **Flexibility**: Easy to add new output formats (JSON, CSV, etc.)
4. **Maintainability**: Clear separation of concerns
5. **Reusability**: Models can be used by other tools/scripts
6. **Context-awareness**: Automatic TTY detection for appropriate output

## Migration Strategy

See `04-migration-plan.md` for detailed migration steps.

## Next Steps

1. Review and approve architecture
2. Define consistent CLI options (see `02-consistent-options.md`)
3. Design output formats (see `03-output-formats.md`)
4. Implement base classes for each layer
5. Migrate one command group at a time (start with mail)
