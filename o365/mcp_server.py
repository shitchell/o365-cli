"""
MCP Server for Office 365 CLI

Exposes Office 365 functionality via Model Context Protocol.
Allows LLMs like Claude to interact with Office 365 services.
"""

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: MCP SDK not installed. Install with: pip install o365-cli[mcp]", file=sys.stderr)
    sys.exit(1)

# Import structured data functions from all modules
from .common import get_access_token
from .mail import (
    get_messages_structured,
    get_message_by_id_structured,
    send_email_structured
)
from .calendar import (
    get_events_structured,
    create_event_structured,
    delete_event_structured,
    parse_since_expression,
    parse_duration
)
from .files import (
    get_drives_structured,
    list_files_structured,
    search_files_structured,
    download_file_structured,
    upload_file_structured
)
from .chat import (
    get_chats_structured,
    get_chat_messages_structured,
    send_message_structured,
    search_messages_structured
)
from .contacts import (
    get_contacts_structured,
    search_users_structured
)
from .recordings import (
    list_recordings_structured,
    search_recordings_structured,
    download_recording_structured,
    get_transcript_structured
)

# Create FastMCP server
mcp = FastMCP("Office 365 MCP Server")

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# EMAIL TOOLS
# ============================================================================

@mcp.tool()
def read_emails(
    folder: str = "Inbox",
    unread: bool = False,
    since: str | None = None,
    search: str | None = None,
    limit: int = 10
) -> dict:
    """
    Read emails from Office 365 mailbox.

    Args:
        folder: Mail folder name (default: "Inbox")
        unread: Only show unread emails (default: False)
        since: Show emails since this time (e.g., "2 days ago", "1 week", "2025-01-15")
        search: Search query to filter emails
        limit: Maximum number of emails to return (default: 10)

    Returns:
        Dictionary with 'status' and 'messages' list
    """
    try:
        access_token = get_access_token()

        # Parse since parameter
        since_dt = None
        if since:
            try:
                since_dt = parse_since_expression(since)
            except ValueError as e:
                return {'status': 'error', 'error': f'Invalid since parameter: {e}'}

        messages = get_messages_structured(
            access_token,
            folder=folder,
            unread=unread if unread else None,
            since=since_dt,
            search=search,
            limit=limit
        )

        return {
            'status': 'success',
            'count': len(messages),
            'messages': messages
        }
    except Exception as e:
        logger.error(f"Error reading emails: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def get_email_content(message_id: str) -> dict:
    """
    Get full content of a specific email by ID.

    Args:
        message_id: The email message ID

    Returns:
        Dictionary with full email details including body and attachments
    """
    try:
        access_token = get_access_token()
        message = get_message_by_id_structured(access_token, message_id)

        if message:
            return {'status': 'success', 'message': message}
        else:
            return {'status': 'error', 'error': 'Email not found'}
    except Exception as e:
        logger.error(f"Error getting email content: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def send_email(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    is_html: bool = True
) -> dict:
    """
    Send an email via Office 365.

    Args:
        to: List of recipient email addresses
        subject: Email subject
        body: Email body content
        cc: List of CC email addresses (optional)
        bcc: List of BCC email addresses (optional)
        is_html: Whether body is HTML (default: True)

    Returns:
        Dictionary with send status
    """
    try:
        access_token = get_access_token()
        result = send_email_structured(
            access_token,
            to_addresses=to,
            subject=subject,
            body=body,
            cc_addresses=cc,
            bcc_addresses=bcc,
            is_html=is_html
        )
        return result
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return {'status': 'error', 'error': str(e)}


# ============================================================================
# CALENDAR TOOLS
# ============================================================================

@mcp.tool()
def list_calendar_events(
    start_date: str | None = None,
    end_date: str | None = None,
    days_ahead: int = 7
) -> dict:
    """
    List calendar events from Office 365.

    Args:
        start_date: Start date (e.g., "today", "tomorrow", "2025-01-15")
        end_date: End date (e.g., "2025-01-20", "7 days")
        days_ahead: If no dates specified, show this many days ahead (default: 7)

    Returns:
        Dictionary with 'status' and 'events' list
    """
    try:
        access_token = get_access_token()

        # Parse start_date
        if start_date:
            try:
                start_dt = parse_since_expression(start_date)
            except ValueError as e:
                return {'status': 'error', 'error': f'Invalid start_date: {e}'}
        else:
            # Default to today at midnight
            now = datetime.now()
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Parse end_date
        if end_date:
            try:
                # For end date, treat numbers as future
                if end_date.split()[0].isdigit():
                    end_date = '+' + end_date
                end_dt = parse_since_expression(end_date)
            except ValueError as e:
                return {'status': 'error', 'error': f'Invalid end_date: {e}'}
        else:
            # Default to N days from start
            end_dt = start_dt + timedelta(days=days_ahead)

        events = get_events_structured(access_token, start_dt, end_dt)

        return {
            'status': 'success',
            'count': len(events),
            'events': events
        }
    except Exception as e:
        logger.error(f"Error listing calendar events: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def create_calendar_event(
    title: str,
    start_time: str,
    duration: str = "1h",
    required_attendees: list[str] | None = None,
    optional_attendees: list[str] | None = None,
    description: str | None = None,
    location: str | None = None,
    online_meeting: bool = True
) -> dict:
    """
    Create a new calendar event in Office 365.

    Args:
        title: Event title/subject
        start_time: When the event starts (e.g., "tomorrow at 2pm", "2025-01-15 14:00")
        duration: Event duration (e.g., "1h", "30m", "1h30m") (default: "1h")
        required_attendees: List of required attendee emails (optional)
        optional_attendees: List of optional attendee emails (optional)
        description: Event description (optional)
        location: Event location (optional)
        online_meeting: Create as Teams online meeting (default: True)

    Returns:
        Dictionary with creation status and event details
    """
    try:
        access_token = get_access_token()

        # Parse start time
        try:
            start_dt = parse_since_expression(start_time)
        except ValueError as e:
            return {'status': 'error', 'error': f'Invalid start_time: {e}'}

        # Parse duration
        try:
            duration_td = parse_duration(duration)
        except ValueError as e:
            return {'status': 'error', 'error': f'Invalid duration: {e}'}

        result = create_event_structured(
            access_token,
            title=title,
            start_time=start_dt,
            duration=duration_td,
            required_attendees=required_attendees,
            optional_attendees=optional_attendees,
            description=description,
            location=location,
            online_meeting=online_meeting
        )

        return result
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def delete_calendar_event(event_id: str) -> dict:
    """
    Delete a calendar event by ID.

    Args:
        event_id: The calendar event ID to delete

    Returns:
        Dictionary with deletion status
    """
    try:
        access_token = get_access_token()
        result = delete_event_structured(access_token, event_id)
        return result
    except Exception as e:
        logger.error(f"Error deleting calendar event: {e}")
        return {'status': 'error', 'error': str(e)}


# ============================================================================
# FILES TOOLS
# ============================================================================

@mcp.tool()
def list_onedrive_files(
    path: str = "/",
    drive_id: str | None = None,
    recursive: bool = False
) -> dict:
    """
    List files and folders in OneDrive or SharePoint.

    Args:
        path: Path to list (default: root "/")
        drive_id: Specific drive ID (default: personal OneDrive)
        recursive: List subdirectories recursively (default: False)

    Returns:
        Dictionary with 'status' and 'files' list
    """
    try:
        access_token = get_access_token()
        files = list_files_structured(
            access_token,
            path=path,
            drive_id=drive_id,
            recursive=recursive
        )

        return {
            'status': 'success',
            'count': len(files),
            'files': files
        }
    except Exception as e:
        logger.error(f"Error listing OneDrive files: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def search_onedrive(
    query: str,
    file_type: str | None = None,
    count: int = 50
) -> dict:
    """
    Search for files in OneDrive and SharePoint.

    Args:
        query: Search query (filename or content)
        file_type: File extension filter (e.g., "pdf", "xlsx", "docx") (optional)
        count: Maximum results to return (default: 50)

    Returns:
        Dictionary with 'status' and 'files' list
    """
    try:
        access_token = get_access_token()
        files = search_files_structured(
            access_token,
            query=query,
            file_type=file_type,
            count=count
        )

        return {
            'status': 'success',
            'count': len(files),
            'files': files
        }
    except Exception as e:
        logger.error(f"Error searching OneDrive: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def download_onedrive_file(
    item_id: str,
    dest_path: str,
    drive_id: str | None = None
) -> dict:
    """
    Download a file from OneDrive or SharePoint.

    Args:
        item_id: File item ID from list/search
        dest_path: Local destination path
        drive_id: Drive ID (default: personal OneDrive)

    Returns:
        Dictionary with download status
    """
    try:
        access_token = get_access_token()
        result = download_file_structured(
            access_token,
            item_id=item_id,
            dest_path=dest_path,
            drive_id=drive_id
        )
        return result
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def upload_onedrive_file(
    source_path: str,
    dest_path: str,
    drive_id: str | None = None,
    overwrite: bool = False
) -> dict:
    """
    Upload a file to OneDrive or SharePoint.

    Args:
        source_path: Local file path to upload
        dest_path: Remote destination path
        drive_id: Drive ID (default: personal OneDrive)
        overwrite: Overwrite existing file (default: False)

    Returns:
        Dictionary with upload status
    """
    try:
        access_token = get_access_token()
        result = upload_file_structured(
            access_token,
            source_path=source_path,
            dest_path=dest_path,
            drive_id=drive_id,
            overwrite=overwrite
        )
        return result
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return {'status': 'error', 'error': str(e)}


# ============================================================================
# TEAMS CHAT TOOLS
# ============================================================================

@mcp.tool()
def list_teams_chats(count: int = 50) -> dict:
    """
    List Teams chats.

    Args:
        count: Maximum number of chats to return (default: 50)

    Returns:
        Dictionary with 'status' and 'chats' list
    """
    try:
        access_token = get_access_token()
        chats = get_chats_structured(access_token, count=count)

        return {
            'status': 'success',
            'count': len(chats),
            'chats': chats
        }
    except Exception as e:
        logger.error(f"Error listing Teams chats: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def read_chat_messages(
    chat_id: str,
    count: int = 50,
    since: str | None = None
) -> dict:
    """
    Read messages from a Teams chat.

    Args:
        chat_id: Chat ID from list_teams_chats
        count: Maximum number of messages to return (default: 50)
        since: Show messages since this time (e.g., "1 day ago") (optional)

    Returns:
        Dictionary with 'status' and 'messages' list
    """
    try:
        access_token = get_access_token()

        # Parse since parameter
        since_dt = None
        if since:
            try:
                since_dt = parse_since_expression(since)
            except ValueError as e:
                return {'status': 'error', 'error': f'Invalid since parameter: {e}'}

        messages = get_chat_messages_structured(
            access_token,
            chat_id=chat_id,
            count=count,
            since=since_dt
        )

        return {
            'status': 'success',
            'count': len(messages),
            'messages': messages
        }
    except Exception as e:
        logger.error(f"Error reading chat messages: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def send_chat_message(chat_id: str, content: str) -> dict:
    """
    Send a message to a Teams chat.

    Args:
        chat_id: Chat ID from list_teams_chats
        content: Message content (plain text)

    Returns:
        Dictionary with send status
    """
    try:
        access_token = get_access_token()
        result = send_message_structured(access_token, chat_id, content)
        return result
    except Exception as e:
        logger.error(f"Error sending chat message: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def search_teams_messages(
    query: str,
    count: int = 50,
    since: str | None = None
) -> dict:
    """
    Search for messages in Teams chats.

    Args:
        query: Search query string
        count: Maximum results to return (default: 50)
        since: Search messages since this time (e.g., "1 week ago") (optional)

    Returns:
        Dictionary with 'status' and 'results' list
    """
    try:
        access_token = get_access_token()

        # Parse since parameter
        since_dt = None
        if since:
            try:
                since_dt = parse_since_expression(since)
            except ValueError as e:
                return {'status': 'error', 'error': f'Invalid since parameter: {e}'}

        results = search_messages_structured(
            access_token,
            query=query,
            count=count,
            since=since_dt
        )

        return {
            'status': 'success',
            'count': len(results),
            'results': results
        }
    except Exception as e:
        logger.error(f"Error searching Teams messages: {e}")
        return {'status': 'error', 'error': str(e)}


# ============================================================================
# CONTACTS TOOLS
# ============================================================================

@mcp.tool()
def search_contacts(query: str) -> dict:
    """
    Search for contacts and users in Office 365.

    Args:
        query: Name or email to search for

    Returns:
        Dictionary with 'status' and 'users' list
    """
    try:
        access_token = get_access_token()
        users = search_users_structured(access_token, query)

        return {
            'status': 'success',
            'count': len(users),
            'users': users
        }
    except Exception as e:
        logger.error(f"Error searching contacts: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def list_contacts() -> dict:
    """
    List all contacts from Office 365.

    Returns:
        Dictionary with 'status' and 'contacts' list
    """
    try:
        access_token = get_access_token()
        contacts = get_contacts_structured(access_token)

        return {
            'status': 'success',
            'count': len(contacts),
            'contacts': contacts
        }
    except Exception as e:
        logger.error(f"Error listing contacts: {e}")
        return {'status': 'error', 'error': str(e)}


# ============================================================================
# RECORDINGS TOOLS
# ============================================================================

@mcp.tool()
def list_recordings(
    since: str | None = None,
    count: int = 50
) -> dict:
    """
    List Teams meeting recordings.

    Args:
        since: Show recordings since this time (e.g., "1 week ago") (optional)
        count: Maximum results to return (default: 50)

    Returns:
        Dictionary with 'status' and 'recordings' list
    """
    try:
        access_token = get_access_token()

        # Parse since parameter
        since_dt = None
        if since:
            try:
                since_dt = parse_since_expression(since)
            except ValueError as e:
                return {'status': 'error', 'error': f'Invalid since parameter: {e}'}

        recordings = list_recordings_structured(
            access_token,
            since=since_dt,
            count=count
        )

        return {
            'status': 'success',
            'count': len(recordings),
            'recordings': recordings
        }
    except Exception as e:
        logger.error(f"Error listing recordings: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def search_recordings(query: str, count: int = 50) -> dict:
    """
    Search for Teams meeting recordings.

    Args:
        query: Search query (meeting name or keywords)
        count: Maximum results to return (default: 50)

    Returns:
        Dictionary with 'status' and 'recordings' list
    """
    try:
        access_token = get_access_token()
        recordings = search_recordings_structured(
            access_token,
            query=query,
            count=count
        )

        return {
            'status': 'success',
            'count': len(recordings),
            'recordings': recordings
        }
    except Exception as e:
        logger.error(f"Error searching recordings: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def download_recording(
    recording_id: str,
    dest_path: str,
    filename: str | None = None
) -> dict:
    """
    Download a Teams meeting recording.

    Args:
        recording_id: Recording ID from list/search
        dest_path: Local destination directory
        filename: Optional custom filename

    Returns:
        Dictionary with download status
    """
    try:
        access_token = get_access_token()
        result = download_recording_structured(
            access_token,
            item_id=recording_id,
            dest_path=dest_path,
            filename=filename
        )
        return result
    except Exception as e:
        logger.error(f"Error downloading recording: {e}")
        return {'status': 'error', 'error': str(e)}


@mcp.tool()
def get_recording_transcript(recording_id: str) -> dict:
    """
    Get transcript for a Teams meeting recording.

    Args:
        recording_id: Recording ID from list/search

    Returns:
        Dictionary with transcript data (parsed entries and raw VTT)
    """
    try:
        access_token = get_access_token()
        result = get_transcript_structured(access_token, recording_id)
        return result
    except Exception as e:
        logger.error(f"Error getting transcript: {e}")
        return {'status': 'error', 'error': str(e)}


# ============================================================================
# RESOURCES
# ============================================================================

@mcp.resource("config://current")
def get_current_config() -> str:
    """Get current Office 365 configuration."""
    from .config_cmd import get_config_value
    import json

    try:
        # Get key config values
        config = {
            'auth': {
                'client_id': get_config_value('auth', 'client_id') or 'Not set',
                'tenant_id': get_config_value('auth', 'tenant_id') or 'Not set',
            }
        }
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e)})


# ============================================================================
# PROMPTS
# ============================================================================

@mcp.prompt()
def check_unread_emails() -> str:
    """Prompt template for checking unread emails."""
    return """Please check my unread emails and give me a summary of:
1. How many unread emails I have
2. Any urgent or important emails (based on subject and sender)
3. A brief summary of what they're about

Use the read_emails tool with unread=true."""


@mcp.prompt()
def todays_schedule() -> str:
    """Prompt template for checking today's schedule."""
    return """Please show me my calendar for today and tell me:
1. What meetings I have scheduled
2. When they start and end
3. Who the attendees are
4. If there are any conflicts or back-to-back meetings

Use the list_calendar_events tool with start_date="today" and end_date="today"."""


@mcp.prompt()
def search_recent_chats() -> str:
    """Prompt template for searching recent Teams chats."""
    return """Please help me search my recent Teams chats for:
[User should provide search term]

Use the search_teams_messages tool and summarize the results."""


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Entry point for the MCP server."""
    # Configure logging based on environment
    log_level = logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Starting Office 365 MCP Server...")
    logger.info("Server provides Office 365 integration for email, calendar, files, chat, contacts, and recordings")

    # Run the MCP server (FastMCP handles async internally)
    mcp.run()


if __name__ == "__main__":
    main()
