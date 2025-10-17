# Output Formats: TUI vs Plain

## Philosophy

**TUI Mode** (Terminal attached):
- Rich visual formatting
- ANSI colors for clarity
- Icons and emoji for visual cues
- Box drawing characters
- Progress indicators
- Optimized for human readability

**Plain Mode** (No terminal / piped output):
- No ANSI codes
- Simple structure
- Tab/space-aligned where helpful
- Easy to parse with grep/awk/cut
- Still human-readable
- Optimized for machine processing

## Detection Logic

```python
# views/base.py
import sys

class BaseView:
    def __init__(self):
        self.is_tty = sys.stdout.isatty()
        self.use_color = self.is_tty and not os.getenv('NO_COLOR')

    def supports_unicode(self):
        """Check if terminal supports Unicode"""
        encoding = sys.stdout.encoding or ''
        return encoding.lower() in ('utf-8', 'utf8')
```

## Example Outputs

### Mail List

#### TUI Mode
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Inbox (5 messages, 3 unread)                                                │
└─────────────────────────────────────────────────────────────────────────────┘

● 2025-10-17 14:23  John Smith <john.smith@example.com>
  Subject: [external] Q4 Budget Review 📎
  ID: AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3...

● 2025-10-17 12:15  Jane Doe <jane.doe@company.com>
  Subject: Team Sync Notes
  ID: AAMkAGQ3YjU2MTRkLWJhMDQtNDc5Mi1hNzA1LWY4...

  2025-10-16 16:45  System Admin <noreply@company.com>
  Subject: Weekly Security Digest
  ID: AAMkADhmNzk0ZGY4LWM0NzYtNDI5ZS04MjI5LWNk...

Legend: ● unread  📎 has attachments  [external] outside organization
Use 'o365 mail read <ID>' to read a specific message
```

#### Plain Mode
```
INBOX: 5 messages, 3 unread

[U] 2025-10-17 14:23  John Smith <john.smith@example.com>
    [external] Q4 Budget Review [attachments: 1]
    ID: AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3...

[U] 2025-10-17 12:15  Jane Doe <jane.doe@company.com>
    Team Sync Notes
    ID: AAMkAGQ3YjU2MTRkLWJhMDQtNDc5Mi1hNzA1LWY4...

[ ] 2025-10-16 16:45  System Admin <noreply@company.com>
    Weekly Security Digest
    ID: AAMkADhmNzk0ZGY4LWM0NzYtNDI5ZS04MjI5LWNk...

Use 'o365 mail read <ID>' to read a specific message
```

### Calendar List

#### TUI Mode
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Calendar: Today (Friday, October 17, 2025)                                  │
└─────────────────────────────────────────────────────────────────────────────┘

🕐 09:00 - 10:00  Team Standup
   Location: Conference Room A
   Organizer: Sarah Johnson
   Status: Accepted

🕐 10:30 - 11:30  Client Demo - Acme Corp
   Location: Teams Meeting
   Organizer: You
   Attendees: john@acme.com, jane@acme.com (3 more...)
   Status: Organizer

🕐 14:00 - 15:30  Sprint Planning
   Location: Conference Room B
   Organizer: Tech Lead
   Status: Tentative
   ⚠ Response needed

3 events today
```

#### Plain Mode
```
CALENDAR: Today (2025-10-17)

[09:00-10:00] Team Standup
  Location: Conference Room A
  Organizer: Sarah Johnson
  Status: Accepted

[10:30-11:30] Client Demo - Acme Corp
  Location: Teams Meeting
  Organizer: You
  Attendees: john@acme.com, jane@acme.com (3 more...)
  Status: Organizer

[14:00-15:30] Sprint Planning
  Location: Conference Room B
  Organizer: Tech Lead
  Status: Tentative [RESPONSE NEEDED]

3 events today
```

### Files List (Long Format)

#### TUI Mode
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ /Documents (12 items)                                                       │
└─────────────────────────────────────────────────────────────────────────────┘

Type  Name                          Size      Modified            Owner
────  ────────────────────────────  ────────  ──────────────────  ──────────────
📁    Projects                      -         2025-10-15 14:23    You
📄    Q4_Report.docx               2.3 MB    2025-10-17 09:15    You
📊    Budget_2025.xlsx             856 KB    2025-10-16 16:30    Sarah Johnson
📄    Meeting_Notes.docx           124 KB    2025-10-17 11:45    You
🖼️     Screenshot.png               1.2 MB    2025-10-15 10:20    You

5 items shown (7 more...)
Use 'o365 files list -a' to show all
```

#### Plain Mode
```
DIRECTORY: /Documents (12 items)

Type   Name                    Size      Modified             Owner
-----  ----------------------  --------  -------------------  --------------
DIR    Projects                -         2025-10-15 14:23     You
DOCX   Q4_Report.docx          2.3M      2025-10-17 09:15     You
XLSX   Budget_2025.xlsx        856K      2025-10-16 16:30     Sarah Johnson
DOCX   Meeting_Notes.docx      124K      2025-10-17 11:45     You
PNG    Screenshot.png          1.2M      2025-10-15 10:20     You

5 items shown (7 more)
```

### Chat Messages

#### TUI Mode
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Chat: John Smith                                                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ You  [14:23] ──────────────────────────────────────────────────────────────┐
│ Hey, can you review the PR when you get a chance?                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ John Smith  [14:25] ────────────────────────────────────────────────────────┐
│ Sure thing! Looking at it now. Just one question about the error handling. │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ You  [14:27] ──────────────────────────────────────────────────────────────┐
│ What's the question?                                                        │
└─────────────────────────────────────────────────────────────────────────────┘

3 messages shown
Type 'o365 chat send --to john -m "message"' to reply
```

#### Plain Mode
```
CHAT: John Smith

[14:23] You:
Hey, can you review the PR when you get a chance?

[14:25] John Smith:
Sure thing! Looking at it now. Just one question about the error handling.

[14:27] You:
What's the question?

3 messages
```

### Message Detail View

#### TUI Mode
```
════════════════════════════════════════════════════════════════════════════════
From:    John Smith <john.smith@external.com>
To:      you@company.com
Date:    Friday, October 17, 2025 at 2:23 PM
Subject: [external] Q4 Budget Review
ID:      AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3...

⚠ Warning: This email is from outside your organization

Attachments (1):
  📎 Q4_Budget_Draft.xlsx (856 KB)
     ID: AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3YmRhYmQwNTI4MABGAAAAAAAv...

────────────────────────────────────────────────────────────────────────────────

Hi team,

Please find attached the Q4 budget draft for review. I'd appreciate your
feedback by EOD Monday.

Key highlights:
  • 15% increase in R&D budget
  • New marketing initiative allocation
  • Cost optimization in operations

Let me know if you have any questions.

Best regards,
John

════════════════════════════════════════════════════════════════════════════════

Commands:
  o365 mail archive <ID>         Archive this message
  o365 mail mark-read <ID>       Mark as read
  o365 mail download-attachment <MESSAGE_ID> <ATTACHMENT_ID>
```

#### Plain Mode
```
================================================================================
From:    John Smith <john.smith@external.com>
To:      you@company.com
Date:    2025-10-17 14:23:00
Subject: [external] Q4 Budget Review
ID:      AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3...

[WARNING] This email is from outside your organization

Attachments:
  [1] Q4_Budget_Draft.xlsx (856 KB)
      ID: AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3YmRhYmQwNTI4MABGAAAAAAAv...

--------------------------------------------------------------------------------

Hi team,

Please find attached the Q4 budget draft for review. I'd appreciate your
feedback by EOD Monday.

Key highlights:
  - 15% increase in R&D budget
  - New marketing initiative allocation
  - Cost optimization in operations

Let me know if you have any questions.

Best regards,
John

================================================================================
```

## Color Scheme (TUI Mode)

### Semantic Colors
```python
COLORS = {
    # Status colors
    'success': '\033[32m',   # Green
    'warning': '\033[33m',   # Yellow
    'error': '\033[31m',     # Red
    'info': '\033[36m',      # Cyan

    # Entity colors
    'sender': '\033[34m',    # Blue
    'subject': '\033[1m',    # Bold
    'date': '\033[90m',      # Bright black (gray)
    'id': '\033[2m',         # Dim

    # Special markers
    'external': '\033[31m',  # Red (security warning)
    'unread': '\033[1;33m',  # Bold yellow
    'attachment': '\033[35m', # Magenta

    # UI elements
    'border': '\033[90m',    # Bright black (gray)
    'header': '\033[1;36m',  # Bold cyan

    'reset': '\033[0m'
}
```

### Icons (Unicode)

When Unicode is available:
```python
ICONS = {
    'unread': '●',
    'attachment': '📎',
    'calendar': '📅',
    'time': '🕐',
    'folder': '📁',
    'file': '📄',
    'spreadsheet': '📊',
    'image': '🖼️',
    'warning': '⚠',
    'success': '✓',
    'error': '✗',
}
```

When Unicode not available (fallback):
```python
ICONS_FALLBACK = {
    'unread': '*',
    'attachment': '@',
    'calendar': '[C]',
    'time': '[T]',
    'folder': '[D]',
    'file': '[F]',
    'spreadsheet': '[X]',
    'image': '[I]',
    'warning': '!',
    'success': '+',
    'error': '-',
}
```

## Implementation Example

```python
# views/mail.py
class MailView(BaseView):
    def format_message_summary(self, msg, user_domain):
        """Format message for list view"""

        # Parse data
        date = self.parse_datetime(msg['receivedDateTime'])
        sender = self.format_email_address(msg['from'])
        subject = msg.get('subject', '(No subject)')
        is_unread = not msg.get('isRead', True)
        has_attachments = self.count_real_attachments(msg)
        is_external = self.is_external_sender(msg['from'], user_domain)

        if self.is_tty:
            return self._format_tty_summary(
                date, sender, subject, is_unread,
                has_attachments, is_external, msg['id']
            )
        else:
            return self._format_plain_summary(
                date, sender, subject, is_unread,
                has_attachments, is_external, msg['id']
            )

    def _format_tty_summary(self, date, sender, subject,
                           is_unread, has_attachments, is_external, msg_id):
        """Rich terminal formatting"""
        parts = []

        # Unread marker
        unread_icon = self.icon('unread') if is_unread else ' '
        parts.append(self.color('unread', unread_icon) if is_unread else unread_icon)

        # Date and sender
        date_str = self.color('date', date.strftime('%Y-%m-%d %H:%M'))
        sender_str = self.color('sender', sender)
        parts.append(f"{date_str}  {sender_str}")

        # Subject line with markers
        subject_parts = []
        if is_external:
            subject_parts.append(self.color('external', '[external]'))
        subject_parts.append(self.color('subject', subject))
        if has_attachments:
            subject_parts.append(self.icon('attachment'))

        subject_line = '  Subject: ' + ' '.join(subject_parts)

        # ID (dimmed)
        id_line = self.color('id', f'  ID: {msg_id}')

        return '\n'.join([parts[0] + ' ' + parts[1], subject_line, id_line, ''])

    def _format_plain_summary(self, date, sender, subject,
                             is_unread, has_attachments, is_external, msg_id):
        """Plain text formatting"""
        unread_mark = '[U]' if is_unread else '[ ]'
        date_str = date.strftime('%Y-%m-%d %H:%M')

        # Subject with markers
        subject_parts = []
        if is_external:
            subject_parts.append('[external]')
        subject_parts.append(subject)
        if has_attachments:
            subject_parts.append(f'[attachments: {has_attachments}]')

        subject_line = ' '.join(subject_parts)

        lines = [
            f"{unread_mark} {date_str}  {sender}",
            f"    {subject_line}",
            f"    ID: {msg_id}",
            ""
        ]

        return '\n'.join(lines)
```

## Format-Specific Output

### JSON Format
```json
{
  "messages": [
    {
      "id": "AAMkADFhY2VlZWU4...",
      "subject": "Q4 Budget Review",
      "from": {
        "name": "John Smith",
        "email": "john.smith@external.com"
      },
      "receivedDateTime": "2025-10-17T14:23:00Z",
      "isRead": false,
      "hasAttachments": true,
      "isExternal": true,
      "attachments": [
        {
          "id": "AAMkADFhY...",
          "name": "Q4_Budget_Draft.xlsx",
          "size": 874496,
          "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }
      ]
    }
  ],
  "total": 5,
  "unread": 3
}
```

### CSV Format
```csv
date,from_name,from_email,subject,is_unread,is_external,has_attachments,id
2025-10-17 14:23,John Smith,john.smith@external.com,Q4 Budget Review,true,true,true,AAMkADFhY2VlZWU4...
2025-10-17 12:15,Jane Doe,jane.doe@company.com,Team Sync Notes,true,false,false,AAMkAGQ3YjU2MTRk...
```

## Progress Indicators (TUI Only)

```python
# For streaming operations
if self.is_tty:
    print(f"\rFetching messages... {count} found", end='', flush=True)
else:
    # No progress indication in plain mode
    pass
```

## Table Formatting

TUI mode uses proper column alignment with box drawing:
```
┌────────┬──────────┬──────────┐
│ Column │ Column 2 │ Column 3 │
├────────┼──────────┼──────────┤
│ Data   │ Data 2   │ Data 3   │
└────────┴──────────┴──────────┘
```

Plain mode uses simple alignment:
```
Column   Column 2   Column 3
-------  ---------  ---------
Data     Data 2     Data 3
```
