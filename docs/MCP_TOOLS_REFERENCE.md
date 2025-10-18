# Office 365 MCP Tools Reference

Complete reference for all 20 MCP tools provided by the Office 365 server.

## Email Tools

### read_emails

Read emails from Office 365 mailbox.

**Parameters:**
- `folder` (string, default: "Inbox") - Mail folder name
- `unread` (boolean, default: false) - Only show unread emails
- `since` (string, optional) - Show emails since this time (e.g., "2 days ago", "1 week", "2025-01-15")
- `search` (string, optional) - Search query to filter emails
- `limit` (integer, default: 10) - Maximum number of emails to return

**Returns:**
```json
{
  "status": "success",
  "count": 5,
  "messages": [
    {
      "id": "AAMkAGI2...",
      "subject": "Meeting Reminder",
      "from_email": "sender@example.com",
      "from_name": "John Doe",
      "received_datetime": "2025-10-18T10:30:00Z",
      "is_read": false,
      "has_attachments": true,
      "body_preview": "Don't forget about our meeting..."
    }
  ]
}
```

### get_email_content

Get full content of a specific email by ID.

**Parameters:**
- `message_id` (string, required) - The email message ID

**Returns:**
```json
{
  "status": "success",
  "message": {
    "id": "AAMkAGI2...",
    "subject": "Meeting Reminder",
    "from_email": "sender@example.com",
    "body_content": "Full email body...",
    "attachments": [...]
  }
}
```

### send_email

Send an email via Office 365.

**Parameters:**
- `to` (list of strings, required) - Recipient email addresses
- `subject` (string, required) - Email subject
- `body` (string, required) - Email body content
- `cc` (list of strings, optional) - CC email addresses
- `bcc` (list of strings, optional) - BCC email addresses
- `is_html` (boolean, default: true) - Whether body is HTML

**Returns:**
```json
{
  "status": "success",
  "message": "Email sent successfully"
}
```

---

## Calendar Tools

### list_calendar_events

List calendar events from Office 365.

**Parameters:**
- `start_date` (string, optional) - Start date (e.g., "today", "tomorrow", "2025-01-15")
- `end_date` (string, optional) - End date (e.g., "2025-01-20", "7 days")
- `days_ahead` (integer, default: 7) - If no dates specified, show this many days ahead

**Returns:**
```json
{
  "status": "success",
  "count": 3,
  "events": [
    {
      "id": "AAMkAGI2...",
      "subject": "Team Standup",
      "start_datetime": "2025-10-18T09:00:00Z",
      "end_datetime": "2025-10-18T09:30:00Z",
      "location": "Conference Room A",
      "organizer_name": "Alice Smith",
      "attendees": [...],
      "is_online_meeting": true,
      "online_meeting_url": "https://teams.microsoft.com/..."
    }
  ]
}
```

### create_calendar_event

Create a new calendar event in Office 365.

**Parameters:**
- `title` (string, required) - Event title/subject
- `start_time` (string, required) - When the event starts (e.g., "tomorrow at 2pm", "2025-01-15 14:00")
- `duration` (string, default: "1h") - Event duration (e.g., "1h", "30m", "1h30m")
- `required_attendees` (list of strings, optional) - Required attendee emails
- `optional_attendees` (list of strings, optional) - Optional attendee emails
- `description` (string, optional) - Event description
- `location` (string, optional) - Event location
- `online_meeting` (boolean, default: true) - Create as Teams online meeting

**Returns:**
```json
{
  "status": "success",
  "event": {
    "id": "AAMkAGI2...",
    "subject": "Project Sync",
    "start_datetime": "2025-10-19T14:00:00Z",
    "online_meeting_url": "https://teams.microsoft.com/..."
  }
}
```

### delete_calendar_event

Delete a calendar event by ID.

**Parameters:**
- `event_id` (string, required) - The calendar event ID to delete

**Returns:**
```json
{
  "status": "success",
  "message": "Event deleted successfully"
}
```

---

## Files Tools

### list_onedrive_files

List files and folders in OneDrive or SharePoint.

**Parameters:**
- `path` (string, default: "/") - Path to list
- `drive_id` (string, optional) - Specific drive ID (default: personal OneDrive)
- `recursive` (boolean, default: false) - List subdirectories recursively

**Returns:**
```json
{
  "status": "success",
  "count": 10,
  "files": [
    {
      "id": "01BYE5RZ...",
      "name": "Budget 2025.xlsx",
      "type": "file",
      "size": 245760,
      "size_formatted": "240.0KB",
      "modified_datetime": "2025-10-15T12:30:00Z",
      "web_url": "https://...",
      "download_url": "https://..."
    }
  ]
}
```

### search_onedrive

Search for files in OneDrive and SharePoint.

**Parameters:**
- `query` (string, required) - Search query (filename or content)
- `file_type` (string, optional) - File extension filter (e.g., "pdf", "xlsx", "docx")
- `count` (integer, default: 50) - Maximum results to return

**Returns:**
Similar to `list_onedrive_files`

### download_onedrive_file

Download a file from OneDrive or SharePoint.

**Parameters:**
- `item_id` (string, required) - File item ID from list/search
- `dest_path` (string, required) - Local destination path
- `drive_id` (string, optional) - Drive ID (default: personal OneDrive)

**Returns:**
```json
{
  "status": "success",
  "item_id": "01BYE5RZ...",
  "dest_path": "/tmp/document.pdf"
}
```

### upload_onedrive_file

Upload a file to OneDrive or SharePoint.

**Parameters:**
- `source_path` (string, required) - Local file path to upload
- `dest_path` (string, required) - Remote destination path
- `drive_id` (string, optional) - Drive ID (default: personal OneDrive)
- `overwrite` (boolean, default: false) - Overwrite existing file

**Returns:**
```json
{
  "status": "success",
  "item": {
    "id": "01BYE5RZ...",
    "name": "uploaded.pdf",
    "size": 123456,
    "web_url": "https://..."
  }
}
```

---

## Teams Chat Tools

### list_teams_chats

List Teams chats.

**Parameters:**
- `count` (integer, default: 50) - Maximum number of chats to return

**Returns:**
```json
{
  "status": "success",
  "count": 15,
  "chats": [
    {
      "id": "19:abc123...",
      "chat_type": "oneOnOne",
      "topic": "",
      "display_name": "Chat with Alice",
      "members": [...],
      "last_message_datetime": "2025-10-18T10:30:00Z",
      "last_message_preview": "Thanks for the update"
    }
  ]
}
```

### read_chat_messages

Read messages from a Teams chat.

**Parameters:**
- `chat_id` (string, required) - Chat ID from list_teams_chats
- `count` (integer, default: 50) - Maximum number of messages to return
- `since` (string, optional) - Show messages since this time (e.g., "1 day ago")

**Returns:**
```json
{
  "status": "success",
  "count": 10,
  "messages": [
    {
      "id": "1234567890",
      "created_datetime": "2025-10-18T10:30:00Z",
      "sender_name": "Alice Smith",
      "sender_email": "alice@example.com",
      "content": "Great work everyone!",
      "content_type": "text"
    }
  ]
}
```

### send_chat_message

Send a message to a Teams chat.

**Parameters:**
- `chat_id` (string, required) - Chat ID from list_teams_chats
- `content` (string, required) - Message content (plain text)

**Returns:**
```json
{
  "status": "success",
  "message_id": "1234567890",
  "created_datetime": "2025-10-18T11:00:00Z"
}
```

### search_teams_messages

Search for messages in Teams chats.

**Parameters:**
- `query` (string, required) - Search query string
- `count` (integer, default: 50) - Maximum results to return
- `since` (string, optional) - Search messages since this time (e.g., "1 week ago")

**Returns:**
```json
{
  "status": "success",
  "count": 5,
  "results": [
    {
      "chat_id": "19:abc123...",
      "chat_name": "Project Team",
      "message_id": "1234567890",
      "created_datetime": "2025-10-17T15:00:00Z",
      "sender_name": "Bob Jones",
      "content": "Updated the project timeline..."
    }
  ]
}
```

---

## Contacts Tools

### search_contacts

Search for contacts and users in Office 365.

**Parameters:**
- `query` (string, required) - Name or email to search for

**Returns:**
```json
{
  "status": "success",
  "count": 2,
  "users": [
    {
      "name": "John Doe",
      "email": "john.doe@example.com",
      "id": "abc123",
      "source": "contact"
    }
  ]
}
```

### list_contacts

List all contacts from Office 365.

**Parameters:** None

**Returns:**
Similar to `search_contacts`

---

## Recordings Tools

### list_recordings

List Teams meeting recordings.

**Parameters:**
- `since` (string, optional) - Show recordings since this time (e.g., "1 week ago")
- `count` (integer, default: 50) - Maximum results to return

**Returns:**
```json
{
  "status": "success",
  "count": 3,
  "recordings": [
    {
      "id": "01BYE5RZ...",
      "name": "Team Standup-20251018.mp4",
      "created_datetime": "2025-10-18T09:30:00Z",
      "size": 52428800,
      "size_formatted": "50.0MB",
      "mime_type": "video/mp4",
      "web_url": "https://...",
      "download_url": "https://..."
    }
  ]
}
```

### search_recordings

Search for Teams meeting recordings.

**Parameters:**
- `query` (string, required) - Search query (meeting name or keywords)
- `count` (integer, default: 50) - Maximum results to return

**Returns:**
Similar to `list_recordings`

### download_recording

Download a Teams meeting recording.

**Parameters:**
- `recording_id` (string, required) - Recording ID from list/search
- `dest_path` (string, required) - Local destination directory
- `filename` (string, optional) - Optional custom filename

**Returns:**
```json
{
  "status": "success",
  "item_id": "01BYE5RZ...",
  "file_path": "/tmp/recording.mp4"
}
```

### get_recording_transcript

Get transcript for a Teams meeting recording.

**Parameters:**
- `recording_id` (string, required) - Recording ID from list/search

**Returns:**
```json
{
  "status": "success",
  "has_transcript": true,
  "entries": [
    {
      "timestamp": "00:00:10",
      "text": "Welcome everyone to today's meeting"
    }
  ],
  "raw_vtt": "WEBVTT\n\n00:00:10.000 --> 00:00:15.000\nWelcome everyone..."
}
```

---

## Error Responses

All tools return error responses in this format:

```json
{
  "status": "error",
  "error": "Description of what went wrong",
  "message": "User-friendly error message"
}
```

Common error types:
- **Authentication errors**: Token expired or invalid
- **Permission errors**: Missing required permissions
- **Not found errors**: Resource doesn't exist
- **Validation errors**: Invalid parameters
- **Rate limit errors**: Too many requests

---

## Date Format Examples

Many tools accept `since`, `start_date`, or `end_date` parameters. Supported formats:

- **Relative**: "2 days ago", "1 week ago", "3 months ago"
- **Simple**: "today", "yesterday", "tomorrow"
- **Absolute**: "2025-01-15", "2025-01-15 14:30"
- **Numeric**: "7 days" (for future dates in calendar tools)

## Duration Format Examples

For `create_calendar_event` duration:

- **Hours**: "1h", "2h", "0.5h"
- **Minutes**: "30m", "15m", "90m"
- **Combined**: "1h30m", "2h15m"

---

**Last updated:** 2025-10-18
