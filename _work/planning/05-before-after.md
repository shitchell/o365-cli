# Before & After Comparison

Visual comparison showing current output vs proposed MVC formatting.

## Mail Read Command

### Current Output (Before)

```
● [2025-10-17 14:23] John Smith <john.smith@external.com>
  Subject: [external] Q4 Budget Review 📎
  ID: AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3...

● [2025-10-17 12:15] Jane Doe <jane.doe@company.com>
  Subject: Team Sync Notes
  ID: AAMkAGQ3YjU2MTRkLWJhMDQtNDc5Mi1hNzA1LWY4...

  [2025-10-16 16:45] System Admin <noreply@company.com>
  Subject: Weekly Security Digest
  ID: AAMkADhmNzk0ZGY4LWM0NzYtNDI5ZS04MjI5LWNk...

Use 'o365 mail read <ID>' to read a specific message
```

**Issues**:
- No header showing folder/count
- Inconsistent formatting
- Markers not aligned
- No clear separation between messages
- Footer message not styled

### Proposed Output (After) - TUI Mode

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Inbox (3 messages, 2 unread)                                                │
└─────────────────────────────────────────────────────────────────────────────┘

● 2025-10-17 14:23  John Smith <john.smith@external.com>
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

**Improvements**:
- Clear header box with message count
- Consistent spacing and alignment
- Legend for symbols
- Styled footer
- Colors applied (shown with ANSI codes in actual terminal)

### Proposed Output (After) - Plain Mode

```
INBOX: 3 messages, 2 unread

[U] 2025-10-17 14:23  John Smith <john.smith@external.com>
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

**Benefits**:
- No ANSI codes
- Clear text markers ([U] vs [ ])
- Text labels instead of emoji
- Easy to parse with grep/awk
- Still human-readable

## Calendar List Command

### Current Output (Before)

```
2025-10-17 09:00 - 10:00  Team Standup
  Location: Conference Room A
  Organizer: Sarah Johnson
  Status: Accepted

2025-10-17 10:30 - 11:30  Client Demo - Acme Corp
  Location: Teams Meeting
  Organizer: You
  Attendees: john@acme.com, jane@acme.com, bob@acme.com
  Status: Organizer

2025-10-17 14:00 - 15:30  Sprint Planning
  Location: Conference Room B
  Organizer: Tech Lead
  Status: Tentative
```

**Issues**:
- No header/context
- No visual hierarchy
- No indication of response needed
- No summary/footer

### Proposed Output (After) - TUI Mode

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Calendar: Today (Friday, October 17, 2025)                                  │
└─────────────────────────────────────────────────────────────────────────────┘

🕐 09:00 - 10:00  Team Standup
   Location: Conference Room A
   Organizer: Sarah Johnson
   Status: Accepted ✓

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

3 events today • 1 needs response
```

**Improvements**:
- Header with day name
- Time icons for visual scanning
- Truncated attendee lists with count
- Warning for events needing response
- Summary footer
- Color-coded status (in terminal)

### Proposed Output (After) - Plain Mode

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

3 events today, 1 needs response
```

**Benefits**:
- Clear time blocks
- All-caps warnings
- Summary line
- No special characters

## Files List Command

### Current Output (Before)

```
Projects
Q4_Report.docx  2.3 MB  2025-10-17 09:15
Budget_2025.xlsx  856 KB  2025-10-16 16:30
Meeting_Notes.docx  124 KB  2025-10-17 11:45
Screenshot.png  1.2 MB  2025-10-15 10:20
```

**Issues**:
- No type indication
- Inconsistent alignment
- No owner information
- No header/context
- Directories not distinguished

### Proposed Output (After) - TUI Mode

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ /Documents (5 items)                                                        │
└─────────────────────────────────────────────────────────────────────────────┘

Type  Name                          Size      Modified            Owner
────  ────────────────────────────  ────────  ──────────────────  ──────────────
📁    Projects                      -         2025-10-15 14:23    You
📄    Q4_Report.docx               2.3 MB    2025-10-17 09:15    You
📊    Budget_2025.xlsx             856 KB    2025-10-16 16:30    Sarah Johnson
📄    Meeting_Notes.docx           124 KB    2025-10-17 11:45    You
🖼️     Screenshot.png               1.2 MB    2025-10-15 10:20    You

5 items (12 GB total)
```

**Improvements**:
- Header box with path and count
- Table format with proper alignment
- File type icons
- Owner column
- Summary footer
- Color-coded types

### Proposed Output (After) - Plain Mode

```
DIRECTORY: /Documents (5 items)

Type   Name                    Size      Modified             Owner
-----  ----------------------  --------  -------------------  --------------
DIR    Projects                -         2025-10-15 14:23     You
DOCX   Q4_Report.docx          2.3M      2025-10-17 09:15     You
XLSX   Budget_2025.xlsx        856K      2025-10-16 16:30     Sarah Johnson
DOCX   Meeting_Notes.docx      124K      2025-10-17 11:45     You
PNG    Screenshot.png          1.2M      2025-10-15 10:20     You

5 items (12 GB total)
```

**Benefits**:
- Text type labels
- Tab-friendly alignment
- Complete information
- Easy to parse

## Message Detail View

### Current Output (Before)

```

================================================================================
From:    John Smith <john.smith@external.com>
To:      you@company.com
Date:    2025-10-17 14:23:00
Subject: [external] Q4 Budget Review
ID:      AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3...

Attachments (1):
  📎 Q4_Budget_Draft.xlsx (856 KB)
     ID: AAMkADFhY2VlZWU4LWMxMTItNGRiYy04ZjlkLTc3YmRhYmQwNTI4MABGAAAAAAAv...

================================================================================

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

================================================================================

```

**Issues**:
- ASCII separators only
- No color or emphasis
- No actionable hints
- External warning not prominent

### Proposed Output (After) - TUI Mode

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

Quick Actions:
  o365 mail archive AAMkA...         Archive this message
  o365 mail mark-read AAMkA...       Mark as read
  o365 mail download-attachment AAMkA... AAMkA...  Download attachment
```

**Improvements**:
- Unicode box characters
- Prominent external warning with icon
- Human-friendly date format
- Quick action hints at bottom
- Color highlighting (in terminal)

## Chat Messages

### Current Output (Before)
*(No current implementation for comparison)*

### Proposed Output (After) - TUI Mode

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

**Features**:
- Chat bubbles with box drawing
- Clear speaker labels
- Timestamps
- Helpful reply hint
- Color per speaker (in terminal)

### Proposed Output (After) - Plain Mode

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

**Features**:
- Clear message blocks
- Simple timestamps
- No special characters
- Easy to follow

## Summary of Improvements

### Visual Hierarchy
- **Before**: Flat text, hard to scan
- **After**: Headers, sections, clear separation

### Context
- **Before**: No folder/date/count information
- **After**: Clear headers with all context

### Consistency
- **Before**: Different styles across commands
- **After**: Unified look and feel

### Actionability
- **Before**: No hints on next steps
- **After**: Quick action commands shown

### Accessibility
- **Before**: Only one output mode
- **After**: TTY and plain modes for different contexts

### Machine Readability
- **Before**: Inconsistent formats
- **After**: Structured plain mode + optional JSON/CSV

### Information Density
- **Before**: Sometimes too sparse, sometimes cluttered
- **After**: Right balance, can use -l for more detail

### Error States
- **Before**: Generic error messages
- **After**: Color-coded, actionable error messages with suggestions
