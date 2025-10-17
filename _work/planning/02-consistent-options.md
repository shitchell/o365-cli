# Consistent CLI Options

## Current State Analysis

### Inconsistencies Found

| Feature | Current Usage | Issue |
|---------|---------------|-------|
| **Search** | `mail read -s`, `files search`, `chat search` | Mixed: option vs subcommand |
| **User Filter** | `chat --with`, `calendar --user` | Inconsistent naming |
| **Verbosity** | `files -v`, `files -l` | Multiple options for similar purpose |
| **Count Limit** | `-n`, `--count` | Consistent (good!) |
| **Time Filter** | `--since`, `--before`, `--after` | Inconsistent availability |
| **Dry Run** | `--dry-run` | Only in mail commands |

## Proposed Standard Options

### Universal Options (Available in ALL commands)

```bash
-h, --help              Show help message
-v, --verbose           Increase output verbosity
-q, --quiet             Decrease output verbosity
--format FORMAT         Output format: auto|table|list|json|csv
                        (auto = TTY-aware, table for TTY, plain for pipes)
--no-color              Disable ANSI colors (even in TTY)
```

### Common Options (Available where applicable)

#### Limiting Results
```bash
-n, --count N           Maximum number of items to return
                        (Use across: mail, calendar, chat, files, recordings)
-a, --all               Return all items (override default limits)
```

#### Time Filtering
```bash
--since EXPR            Items since this time (git-style: "2 days ago", "2025-01-01")
--before EXPR           Items before this time
--after EXPR            Items after this time (synonym for --since)
--today                 Today's items (shortcut)
--week                  This week's items (shortcut)
--month                 This month's items (shortcut)
```

#### Text Search/Filtering
```bash
-s, --search QUERY      Search/filter items by text
--field FIELD           Which field to search (subject|body|from|etc)
```

#### User/Entity Filtering
```bash
-u, --user USER         Filter by user (name, email, or ID)
--folder FOLDER         Filter by folder/container
```

#### Output Control
```bash
-o, --output PATH       Output file or directory
--overwrite             Overwrite existing files
--dry-run               Preview operation without executing
```

#### Detail Level
```bash
-l, --long              Show detailed/long format
--show-ids              Include IDs in output (useful for scripting)
```

## Command-Specific Standardization

### mail read
```bash
o365 mail read [OPTIONS] [ID...]

Options:
  -n, --count N           Limit to N messages (default: all, streamed)
  -f, --folder FOLDER     Folder to read from (default: Inbox)
  -s, --search QUERY      Search for messages matching query
  --field FIELD           Search in specific field: subject|body|from|to
  --since EXPR            Messages since this time
  --unread                Show only unread messages
  --read                  Show only read messages
  -l, --long              Show full message details
  --show-ids              Always show full message IDs
  --format FORMAT         Output format: auto|table|list|json
  --no-color              Disable colors
```

### calendar list
```bash
o365 calendar list [OPTIONS]

Options:
  -u, --user USER         View user's calendar (default: current user)
  --since EXPR            Events since this time
  --before EXPR           Events before this time
  --today                 Today's events
  --week                  This week's events
  --month                 This month's events
  -s, --search QUERY      Search events by title/description
  -l, --long              Show full event details
  --format FORMAT         Output format: auto|table|list|json
```

### chat list
```bash
o365 chat list [OPTIONS]

Options:
  -n, --count N           Number of chats to show (default: 50)
  -u, --user USER         Filter to chats with specific user
  --since EXPR            Chats with activity since this time
  -s, --search QUERY      Search chat names/participants
  --format FORMAT         Output format: auto|table|list|json
```

### files list
```bash
o365 files list [PATH] [OPTIONS]

Options:
  -l, --long              Show detailed file information
  --since EXPR            Files modified since this time
  -s, --search QUERY      Search for files by name
  --type TYPE             Filter by file type (docx|xlsx|pdf|etc)
  --format FORMAT         Output format: auto|table|list|json
```

### recordings list
```bash
o365 recordings list [OPTIONS]

Options:
  -n, --count N           Limit to N recordings (default: 100)
  --since EXPR            Recordings since this time
  -s, --search QUERY      Search by meeting name
  -l, --long              Show detailed recording info
  --format FORMAT         Output format: auto|table|list|json
```

## Format Option Details

### `--format auto` (default)
- Detects TTY attachment
- If TTY: Rich formatted output with colors, boxes, icons
- If not TTY: Plain structured output, easy to parse
- Smart tables with proper alignment

### `--format table`
- Always use table format
- Respects --no-color
- Good for consistent formatting

### `--format list`
- One item per line with key: value pairs
- More detail than table
- Easy to grep/parse

### `--format json`
- Full JSON output
- Includes all fields from API
- Perfect for scripting/automation

### `--format csv`
- CSV output with headers
- Good for spreadsheets
- Only includes commonly-used fields

## Deprecation Plan

Old options that will be deprecated (with warnings):

```bash
# calendar --after → --since (keep --after as alias for now)
# chat --with → --user (keep --with as deprecated alias)
# files -v → -l (keep -v as deprecated alias)
```

Warnings will be shown for 2 releases, then removed in 3rd release.

## Implementation Notes

1. Create `cli/parsers.py` with helper functions:
   ```python
   def add_count_option(parser):
       """Add standard -n/--count option"""
       parser.add_argument('-n', '--count', type=int, metavar='N',
                          help='Maximum number of items to return')

   def add_time_filter_options(parser, shortcuts=True):
       """Add standard time filtering options"""
       parser.add_argument('--since', ...)
       parser.add_argument('--before', ...)
       if shortcuts:
           parser.add_argument('--today', ...)
           parser.add_argument('--week', ...)
   ```

2. Shared validators in `cli/validators.py`:
   ```python
   def validate_time_expression(expr):
       """Validate git-style time expression"""
       # Returns: datetime object or raises ValueError

   def validate_format_choice(format):
       """Validate output format choice"""
       # Returns: normalized format or raises ValueError
   ```

3. Argument groups for clarity:
   ```python
   # Group related options
   filter_group = parser.add_argument_group('Filtering options')
   output_group = parser.add_argument_group('Output options')
   ```
