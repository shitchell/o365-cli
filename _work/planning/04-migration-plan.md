# Migration Plan

## Overview

Incremental refactoring from monolithic command modules to MVC architecture.

**Strategy**: One command group at a time, with backward compatibility during transition.

## Phase 0: Foundation (Week 1)

### 0.1: Create Base Classes

**Files to create**:
```
o365/models/base.py       # GraphClient, BaseModel
o365/views/base.py        # BaseView, TTY detection
o365/views/colors.py      # ANSI color utilities
o365/views/formatters.py  # Table, list, detail formatters
o365/controllers/base.py  # BaseController
o365/cli/parsers.py       # Shared argument parser utilities
o365/cli/validators.py    # Input validation
```

**Key implementations**:

1. **GraphClient** (models/base.py):
   - Centralized API client
   - Authentication handling
   - Request/response logic
   - Pagination support
   - Error handling

2. **BaseView** (views/base.py):
   - TTY detection: `self.is_tty = sys.stdout.isatty()`
   - Color support detection
   - Unicode support detection
   - Base formatting methods

3. **Color utilities** (views/colors.py):
   ```python
   class Colors:
       def __init__(self, enabled=True):
           self.enabled = enabled

       def apply(self, color, text):
           if not self.enabled:
               return text
           return f"{self.CODES[color]}{text}{self.CODES['reset']}"
   ```

4. **Formatters** (views/formatters.py):
   - TableFormatter (TTY + plain modes)
   - ListFormatter
   - DetailFormatter
   - Box drawing utilities

### 0.2: Update Dependencies

**pyproject.toml**:
```toml
dependencies = [
    "python-dateutil>=2.8.0",
    "html2text>=2020.1.16",
    # New: for better table formatting
    "wcwidth>=0.2.5",  # Unicode width calculation
]
```

### 0.3: Tests Infrastructure

Create test structure:
```
tests/
├── __init__.py
├── test_models/
│   ├── test_base.py
│   └── test_mail.py
├── test_views/
│   ├── test_base.py
│   ├── test_formatters.py
│   └── test_mail.py
└── test_controllers/
    └── test_mail.py
```

**Deliverables**:
- ✅ Base classes implemented
- ✅ Basic tests passing
- ✅ Documentation for base classes

## Phase 1: Migrate Mail Commands (Week 2-3)

### Why Start with Mail?
- Most complex (multiple subcommands)
- Already refactored to pure Graph API
- Good test case for architecture

### 1.1: Create Mail Model

**File**: `o365/models/mail.py`

```python
from .base import BaseModel, GraphClient

class MailModel(BaseModel):
    def __init__(self, access_token):
        self.client = GraphClient(access_token)
        self._user_domain = None

    def get_user_domain(self):
        """Get current user's email domain"""
        if self._user_domain is None:
            user = self.client.get('/me')
            email = user.get('mail') or user.get('userPrincipalName', '')
            self._user_domain = email.split('@')[1].lower() if '@' in email else ''
        return self._user_domain

    def get_messages_stream(self, folder='Inbox', max_count=None,
                           since=None, unread=None, search=None):
        """Stream messages from folder (generator)"""
        # Move logic from mail.py cmd_read()
        # Yields: List[dict] (pages of messages)
        pass

    def get_message(self, message_id):
        """Get single message by ID"""
        # Returns: dict
        pass

    def archive_message(self, message_id):
        """Move message to Archive folder"""
        # Returns: dict
        pass

    def mark_read(self, message_id):
        """Mark message as read"""
        # Returns: dict
        pass

    def get_attachment(self, message_id, attachment_id):
        """Get attachment data"""
        # Returns: dict with contentBytes
        pass
```

### 1.2: Create Mail View

**File**: `o365/views/mail.py`

```python
from .base import BaseView
from .formatters import TableFormatter, DetailFormatter

class MailView(BaseView):
    def __init__(self):
        super().__init__()
        self.table = TableFormatter(self.is_tty, self.use_color)

    def format_message_list_header(self, folder, total, unread):
        """Format folder header"""
        if self.is_tty:
            return self._box_header(f"{folder} ({total} messages, {unread} unread)")
        else:
            return f"{folder.upper()}: {total} messages, {unread} unread\n"

    def format_message_summary(self, msg, user_domain):
        """Format single message in list"""
        # See 03-output-formats.md for implementation
        pass

    def format_message_detail(self, msg, html=False):
        """Format full message view"""
        # See 03-output-formats.md for implementation
        pass

    def format_attachment_list(self, attachments):
        """Format attachment section"""
        pass
```

### 1.3: Create Mail Controller

**File**: `o365/controllers/mail.py`

```python
from .base import BaseController
from ..models.mail import MailModel
from ..views.mail import MailView
from ..common import get_access_token

class MailController(BaseController):
    def __init__(self, args):
        super().__init__(args)
        self.model = MailModel(get_access_token())
        self.view = MailView()

    def read(self):
        """Handle 'o365 mail read' command"""
        if self.args.ids:
            self._read_specific_messages()
        else:
            self._list_messages()

    def _read_specific_messages(self):
        """Read specific message(s) by ID"""
        for msg_id in self.args.ids:
            try:
                msg = self.model.get_message(msg_id)
                print(self.view.format_message_detail(msg, html=self.args.html))
            except Exception as e:
                self.error(f"Failed to read message {msg_id}: {e}")

    def _list_messages(self):
        """List messages with filters"""
        user_domain = self.model.get_user_domain()

        # Parse filters
        since = self.parse_time_expression(self.args.since) if self.args.since else None
        unread_filter = None
        if self.args.unread:
            unread_filter = True
        elif self.args.read:
            unread_filter = False

        # Stream and display
        total_displayed = 0
        for page in self.model.get_messages_stream(
            folder=self.args.folder or 'Inbox',
            max_count=self.args.count,
            since=since,
            unread=unread_filter,
            search=self.args.search
        ):
            for msg in page:
                print(self.view.format_message_summary(msg, user_domain))
                total_displayed += 1

        if total_displayed == 0:
            print(self.view.format_no_results("No messages found"))
        else:
            print(self.view.format_footer(
                f"Use 'o365 mail read <ID>' to read a specific message"
            ))

    def archive(self):
        """Handle 'o365 mail archive' command"""
        for msg_id in self.args.ids:
            try:
                if self.args.dry_run:
                    msg = self.model.get_message(msg_id)
                    print(f"Would archive: {msg.get('subject')} (ID: {msg_id})")
                else:
                    msg = self.model.archive_message(msg_id)
                    print(self.view.format_success(
                        f"Archived: {msg.get('subject')}"
                    ))
            except Exception as e:
                self.error(f"Failed to archive {msg_id}: {e}")

    def mark_read(self):
        """Handle 'o365 mail mark-read' command"""
        # Similar to archive()
        pass

    def download_attachment(self):
        """Handle 'o365 mail download-attachment' command"""
        # Implementation
        pass
```

### 1.4: Update Mail CLI Entry Point

**File**: `o365/mail.py` (temporary compatibility shim)

```python
"""
Mail commands - Compatibility shim

This module maintains backward compatibility while routing to new MVC implementation.
Will be removed in future version.
"""

from .controllers.mail import MailController

def cmd_read(args):
    """Legacy entry point for 'o365 mail read'"""
    controller = MailController(args)
    controller.read()

def cmd_archive(args):
    """Legacy entry point for 'o365 mail archive'"""
    controller = MailController(args)
    controller.archive()

# ... other legacy entry points

def setup_parser(subparsers):
    """Setup argparse - delegate to new CLI module"""
    from .cli.parsers import setup_mail_parser
    setup_mail_parser(subparsers)

def handle_command(args):
    """Route to controller"""
    controller = MailController(args)
    if args.mail_command == 'read':
        controller.read()
    elif args.mail_command == 'archive':
        controller.archive()
    # ... etc
```

### 1.5: Testing

**Tests to write**:
```
tests/test_models/test_mail.py
  - Test API calls (mocked)
  - Test data parsing
  - Test pagination

tests/test_views/test_mail.py
  - Test TTY vs plain formatting
  - Test color application
  - Test Unicode handling

tests/test_controllers/test_mail.py
  - Test command routing
  - Test error handling
  - Test argument validation
```

### 1.6: Documentation Update

Update README.md with:
- Examples showing new output formats
- Note about TTY detection
- Environment variables (NO_COLOR)

**Deliverables**:
- ✅ Mail commands fully migrated
- ✅ Tests passing (>80% coverage)
- ✅ Documentation updated
- ✅ Backward compatible

## Phase 2: Migrate Calendar Commands (Week 4)

### 2.1: Create Calendar Model

**File**: `o365/models/calendar.py`

Similar structure to MailModel:
```python
class CalendarModel(BaseModel):
    def get_events(self, user=None, after=None, before=None):
        """Get calendar events"""
        pass

    def create_event(self, title, when, duration, **kwargs):
        """Create calendar event"""
        pass

    def delete_event(self, event_id):
        """Delete calendar event"""
        pass
```

### 2.2: Create Calendar View

**File**: `o365/views/calendar.py`

```python
class CalendarView(BaseView):
    def format_event_list(self, events, date_range):
        """Format event list with date headers"""
        # Group by day in TUI mode
        # Simple list in plain mode
        pass

    def format_event_detail(self, event):
        """Format single event details"""
        pass
```

### 2.3: Create Calendar Controller

Similar pattern to MailController.

**Deliverables**:
- ✅ Calendar commands migrated
- ✅ Tests passing
- ✅ Documentation updated

## Phase 3: Migrate Remaining Commands (Week 5-6)

Apply same pattern to:
1. **Chat** (Week 5)
2. **Files** (Week 5)
3. **Recordings** (Week 6)
4. **Contacts** (Week 6)

Each follows same steps:
- Create model
- Create view
- Create controller
- Write tests
- Update documentation

## Phase 4: Implement Enhanced Features (Week 7)

### 4.1: Add Format Options

Implement `--format` flag:
- JSON output
- CSV output
- Table output (explicit)
- List output (explicit)

### 4.2: Add Consistent Options

Roll out standardized options:
- `--verbose` / `--quiet`
- `--show-ids`
- `--no-color`
- Unified time filtering

### 4.3: Enhanced TUI Features

Add rich TUI features:
- Better table rendering
- Box drawing for sections
- Progress bars for operations
- Color-coded status indicators

## Phase 5: Cleanup (Week 8)

### 5.1: Remove Legacy Code

Once all commands migrated:
- Remove old `o365/mail.py` (replace with controller import)
- Remove old `o365/calendar.py`
- Remove `o365/common.py` (consolidate into models/base.py)
- Update all imports

### 5.2: Final Documentation

- Architecture documentation
- Developer guide
- API documentation
- Examples gallery

### 5.3: Final Testing

- End-to-end testing
- Performance testing
- Cross-platform testing (Windows, macOS, Linux)
- Both TTY and non-TTY scenarios

**Deliverables**:
- ✅ All legacy code removed
- ✅ Complete documentation
- ✅ 100% test coverage
- ✅ Performance benchmarks

## Testing Strategy

### Unit Tests
```bash
# Test individual components
pytest tests/test_models/
pytest tests/test_views/
pytest tests/test_controllers/
```

### Integration Tests
```bash
# Test full command flows (with mocked API)
pytest tests/integration/
```

### Manual Testing Checklist

For each command:
- [ ] Works in TTY (colors, formatting)
- [ ] Works piped (plain output)
- [ ] Works with `--no-color`
- [ ] Works with `--format json`
- [ ] Works with `--format csv`
- [ ] Help text displays correctly
- [ ] Error messages are clear
- [ ] Edge cases handled (empty results, API errors, etc.)

## Backward Compatibility

During migration:
- All existing commands continue to work
- Existing CLI flags remain valid
- New flags are additive
- Deprecation warnings for changed behavior
- Old code paths maintained until Phase 5

## Rollout Plan

### Version 1.1.0 (Phase 0-1)
- MVC foundation
- Mail commands migrated
- Feature flag: `O365_USE_NEW_FORMATTING=1`

### Version 1.2.0 (Phase 2-3)
- All commands migrated
- New formatting enabled by default
- `O365_USE_LEGACY_FORMATTING=1` to revert

### Version 2.0.0 (Phase 4-5)
- Legacy code removed
- Enhanced features
- Breaking changes (if any)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing scripts | High | Maintain compatibility, deprecation warnings |
| Performance regression | Medium | Benchmark each phase |
| Testing gaps | Medium | >80% coverage requirement |
| API changes from Microsoft | Low | Abstract API calls in model layer |
| Unicode issues on Windows | Low | Fallback ASCII icons |

## Success Metrics

- [ ] All commands migrated to MVC
- [ ] Test coverage >90%
- [ ] No performance regression
- [ ] Documentation complete
- [ ] Zero P0/P1 bugs in new code
- [ ] Positive user feedback on new formatting
