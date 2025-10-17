"""
Microsoft Teams meeting recordings management commands for Office365

List, search, download, and view transcripts of Teams meeting recordings.
"""

import sys
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

from .common import get_access_token, make_graph_request, GRAPH_API_BASE
from .calendar import parse_since_expression


def parse_graph_datetime(dt_str):
    """Parse Microsoft Graph datetime format

    Args:
        dt_str: ISO 8601 datetime string

    Returns:
        datetime object
    """
    import re
    # Remove excess fractional seconds (keep max 6 digits)
    dt_str = re.sub(r'\.(\d{6})\d*', r'.\1', dt_str)
    # Handle timezone
    if not dt_str.endswith('Z') and '+' not in dt_str and '-' not in dt_str[-6:]:
        dt_str += 'Z'
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def list_recordings(access_token, since=None, before=None, organizer=None, count=50):
    """List meeting recordings from OneDrive

    Recordings are stored in OneDrive in special folders. This searches for
    video files in the Recordings folder.

    Args:
        access_token: OAuth2 access token
        since: Optional datetime to filter recordings after
        before: Optional datetime to filter recordings before
        organizer: Optional organizer name/email filter
        count: Maximum number of recordings to return

    Returns:
        List of recording file objects
    """
    # Search for video files in Recordings folder
    # Note: This requires Files.Read or Files.Read.All permissions
    url = f"{GRAPH_API_BASE}/me/drive/root:/Recordings:/children"

    recordings = []

    try:
        while url:
            result = make_graph_request(url, access_token)
            if not result:
                break

            items = result.get('value', [])

            # Filter for video files
            for item in items:
                # Check if it's a video file
                mime_type = item.get('file', {}).get('mimeType', '')
                name = item.get('name', '')

                if 'video' in mime_type or name.endswith(('.mp4', '.webm')):
                    # Apply date filters
                    if since or before:
                        created = parse_graph_datetime(item['createdDateTime'])
                        if since and created < since:
                            continue
                        if before and created > before:
                            continue

                    recordings.append(item)

                    if len(recordings) >= count:
                        return recordings[:count]

            url = result.get('@odata.nextLink')

    except Exception as e:
        # Recordings folder might not exist
        print(f"Note: Could not access Recordings folder: {e}", file=sys.stderr)
        return []

    return recordings[:count]


def search_recordings(access_token, query, since=None, organizer=None, count=50):
    """Search for meeting recordings by name

    Args:
        access_token: OAuth2 access token
        query: Search query (meeting name or keywords)
        since: Optional datetime to filter recordings after
        organizer: Optional organizer name/email filter
        count: Maximum number of results

    Returns:
        List of recording file objects
    """
    # Search OneDrive for video files matching the query
    url = f"{GRAPH_API_BASE}/me/drive/root/search(q='{query}')"

    recordings = []

    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        items = result.get('value', [])

        # Filter for video files in Recordings folder
        for item in items:
            mime_type = item.get('file', {}).get('mimeType', '')
            name = item.get('name', '')
            parent_path = item.get('parentReference', {}).get('path', '')

            # Check if it's a video file in Recordings folder
            if ('video' in mime_type or name.endswith(('.mp4', '.webm'))) and 'Recordings' in parent_path:
                # Apply date filter
                if since:
                    created = parse_graph_datetime(item['createdDateTime'])
                    if created < since:
                        continue

                recordings.append(item)

                if len(recordings) >= count:
                    return recordings[:count]

        url = result.get('@odata.nextLink')

    return recordings[:count]


def download_recording(access_token, item_id, dest_path, filename=None):
    """Download a meeting recording

    Args:
        access_token: OAuth2 access token
        item_id: Recording file item ID
        dest_path: Local destination directory
        filename: Optional custom filename

    Returns:
        True on success, False on error
    """
    # Get file metadata first
    url = f"{GRAPH_API_BASE}/me/drive/items/{item_id}"
    item = make_graph_request(url, access_token)

    if not item:
        print("Error: Recording not found", file=sys.stderr)
        return False

    # Determine filename
    if not filename:
        filename = item.get('name', f'recording_{item_id}.mp4')

    dest = Path(dest_path) / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Get download URL
    download_url = f"{GRAPH_API_BASE}/me/drive/items/{item_id}/content"

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    try:
        print(f"Downloading {filename}...")
        req = urllib.request.Request(download_url, headers=headers)

        with urllib.request.urlopen(req) as response:
            total_size = int(response.headers.get('Content-Length', 0))

            with open(dest, 'wb') as f:
                downloaded = 0
                chunk_size = 1024 * 1024  # 1MB chunks

                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    # Show progress
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\rProgress: {percent:.1f}% ({format_size(downloaded)} / {format_size(total_size)})", end='', flush=True)

        print()  # New line after progress
        return True

    except Exception as e:
        print(f"\nError downloading recording: {e}", file=sys.stderr)
        return False


def get_transcript(access_token, item_id):
    """Get transcript for a recording

    Looks for .vtt transcript file alongside the recording.

    Args:
        access_token: OAuth2 access token
        item_id: Recording file item ID

    Returns:
        Transcript text or None if not found
    """
    # Get the recording item
    url = f"{GRAPH_API_BASE}/me/drive/items/{item_id}"
    item = make_graph_request(url, access_token)

    if not item:
        return None

    # Get parent folder
    parent_id = item.get('parentReference', {}).get('id')
    if not parent_id:
        return None

    # Look for .vtt file with similar name
    recording_name = item.get('name', '')
    base_name = recording_name.rsplit('.', 1)[0]

    # List files in parent folder
    parent_url = f"{GRAPH_API_BASE}/me/drive/items/{parent_id}/children"
    result = make_graph_request(parent_url, access_token)

    if not result:
        return None

    # Find matching transcript file
    for file_item in result.get('value', []):
        file_name = file_item.get('name', '')
        if base_name in file_name and file_name.endswith('.vtt'):
            # Download and return transcript content
            transcript_id = file_item['id']
            transcript_url = f"{GRAPH_API_BASE}/me/drive/items/{transcript_id}/content"

            headers = {'Authorization': f'Bearer {access_token}'}
            req = urllib.request.Request(transcript_url, headers=headers)

            try:
                with urllib.request.urlopen(req) as response:
                    return response.read().decode('utf-8')
            except Exception:
                return None

    return None


def format_size(bytes_size):
    """Format byte size to human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f}PB"


def parse_vtt_transcript(vtt_content):
    """Parse VTT transcript and extract text with timestamps

    Args:
        vtt_content: VTT file content

    Returns:
        List of (timestamp, text) tuples
    """
    import re

    lines = vtt_content.split('\n')
    entries = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Look for timestamp lines (format: 00:00:00.000 --> 00:00:00.000)
        if '-->' in line:
            # Extract start time
            start_time = line.split('-->')[0].strip()

            # Next lines are the text until we hit a blank line
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1

            if text_lines:
                entries.append((start_time, ' '.join(text_lines)))

        i += 1

    return entries


# Command handlers

def cmd_list(args):
    """Handle 'o365 recordings list' command"""
    access_token = get_access_token()

    # Parse --since if specified
    since = None
    if args.since:
        try:
            since = parse_since_expression(args.since)
        except ValueError as e:
            print(f"Error in --since: {e}", file=sys.stderr)
            sys.exit(1)

    # Parse --before if specified
    before = None
    if args.before:
        try:
            before = parse_since_expression(args.before)
        except ValueError as e:
            print(f"Error in --before: {e}", file=sys.stderr)
            sys.exit(1)

    # List recordings
    recordings = list_recordings(access_token, since, before, args.organizer, args.count or 50)

    if not recordings:
        print("No recordings found")
        return

    print(f"\n🎥 Meeting Recordings ({len(recordings)} found):\n")

    for i, rec in enumerate(recordings, 1):
        created = parse_graph_datetime(rec['createdDateTime'])
        date_str = created.strftime('%Y-%m-%d %H:%M')
        name = rec['name']
        size = format_size(rec.get('size', 0))
        rec_id = rec['id']

        print(f"{i}. {name}")
        print(f"   Date: {date_str}  Size: {size}")
        print(f"   ID: {rec_id}")
        print()

    print(f"Use 'o365 recordings download <id>' to download a recording")
    print(f"Use 'o365 recordings transcript <id>' to view the transcript")


def cmd_search(args):
    """Handle 'o365 recordings search' command"""
    access_token = get_access_token()

    # Parse --since if specified
    since = None
    if args.since:
        try:
            since = parse_since_expression(args.since)
        except ValueError as e:
            print(f"Error in --since: {e}", file=sys.stderr)
            sys.exit(1)

    # Search recordings
    recordings = search_recordings(access_token, args.query, since, args.organizer, args.count or 50)

    if not recordings:
        print(f"No recordings found matching '{args.query}'")
        return

    print(f"\n🔍 Search results for '{args.query}' ({len(recordings)} found):\n")

    for i, rec in enumerate(recordings, 1):
        created = parse_graph_datetime(rec['createdDateTime'])
        date_str = created.strftime('%Y-%m-%d %H:%M')
        name = rec['name']
        size = format_size(rec.get('size', 0))
        rec_id = rec['id']

        print(f"{i}. {name}")
        print(f"   Date: {date_str}  Size: {size}")
        print(f"   ID: {rec_id}")
        print()

    print(f"Use 'o365 recordings download <id>' to download a recording")


def cmd_download(args):
    """Handle 'o365 recordings download' command"""
    access_token = get_access_token()

    # Determine destination
    dest = Path(args.dest) if args.dest else Path.cwd()

    # Download recording
    if download_recording(access_token, args.recording_id, dest, args.filename):
        print(f"✓ Download complete")
    else:
        sys.exit(1)


def cmd_transcript(args):
    """Handle 'o365 recordings transcript' command"""
    access_token = get_access_token()

    # Get transcript
    transcript = get_transcript(access_token, args.recording_id)

    if not transcript:
        print("No transcript found for this recording", file=sys.stderr)
        sys.exit(1)

    # Parse and format transcript
    if args.format == 'vtt':
        output = transcript
    elif args.format == 'json':
        import json
        entries = parse_vtt_transcript(transcript)
        output = json.dumps([{'timestamp': ts, 'text': txt} for ts, txt in entries], indent=2)
    else:  # txt format
        entries = parse_vtt_transcript(transcript)
        lines = []
        for timestamp, text in entries:
            if args.timestamps:
                if args.speakers:
                    # Try to extract speaker from text (format: "Speaker Name: text")
                    lines.append(f"[{timestamp}] {text}")
                else:
                    lines.append(f"[{timestamp}] {text}")
            else:
                lines.append(text)
        output = '\n'.join(lines)

    # Output to file or stdout
    if args.output:
        Path(args.output).write_text(output)
        print(f"✓ Transcript saved to {args.output}")
    else:
        print(output)


def cmd_info(args):
    """Handle 'o365 recordings info' command"""
    access_token = get_access_token()

    # Get recording details
    url = f"{GRAPH_API_BASE}/me/drive/items/{args.recording_id}"
    item = make_graph_request(url, access_token)

    if not item:
        print("Recording not found", file=sys.stderr)
        sys.exit(1)

    print(f"\n📹 Recording Details:\n")
    print(f"Name:          {item.get('name', 'Unknown')}")
    print(f"ID:            {item['id']}")
    print(f"Size:          {format_size(item.get('size', 0))}")
    print(f"Created:       {parse_graph_datetime(item['createdDateTime']).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Modified:      {parse_graph_datetime(item['lastModifiedDateTime']).strftime('%Y-%m-%d %H:%M:%S')}")

    if 'createdBy' in item:
        creator = item['createdBy'].get('user', {})
        print(f"Created by:    {creator.get('displayName', 'Unknown')}")

    # Check for transcript
    transcript = get_transcript(access_token, args.recording_id)
    print(f"Transcript:    {'Available' if transcript else 'Not available'}")

    # Download URL
    print(f"\nDownload URL:  /me/drive/items/{item['id']}/content")
    print()


# Setup and routing

def setup_parser(subparsers):
    """Setup argparse subcommands for recordings"""

    # o365 recordings list
    list_parser = subparsers.add_parser(
        'list',
        help='List meeting recordings',
        description='List Microsoft Teams meeting recordings.'
    )

    list_parser.add_argument('--since', type=str, metavar='EXPR',
                            help='Show recordings since (git-style: "1 week ago")')
    list_parser.add_argument('--before', type=str, metavar='EXPR',
                            help='Show recordings before')
    list_parser.add_argument('-n', '--count', type=int, metavar='N',
                            help='Maximum results (default: 50)')
    list_parser.add_argument('--organizer', type=str, metavar='USER',
                            help='Filter by meeting organizer')

    list_parser.set_defaults(func=cmd_list)

    # o365 recordings search
    search_parser = subparsers.add_parser(
        'search',
        help='Search meeting recordings',
        description='Search for meeting recordings by name or keywords.'
    )

    search_parser.add_argument('query', help='Search query (meeting name or keywords)')
    search_parser.add_argument('--since', type=str, metavar='EXPR',
                              help='Recordings since (git-style format)')
    search_parser.add_argument('--organizer', type=str, metavar='USER',
                              help='Filter by meeting organizer')
    search_parser.add_argument('-n', '--count', type=int, metavar='N',
                              help='Maximum results (default: 50)')

    search_parser.set_defaults(func=cmd_search)

    # o365 recordings download
    download_parser = subparsers.add_parser(
        'download',
        help='Download a meeting recording',
        description='Download a Microsoft Teams meeting recording.'
    )

    download_parser.add_argument('recording_id', help='Recording ID from list/search')
    download_parser.add_argument('dest', nargs='?', help='Local destination (default: current directory)')
    download_parser.add_argument('--filename', type=str, metavar='NAME',
                                help='Custom filename (default: meeting name + date)')

    download_parser.set_defaults(func=cmd_download)

    # o365 recordings transcript
    transcript_parser = subparsers.add_parser(
        'transcript',
        help='Get meeting transcript',
        description='Get or download meeting transcript.'
    )

    transcript_parser.add_argument('recording_id', help='Recording ID from list/search')
    transcript_parser.add_argument('--format', type=str, choices=['txt', 'vtt', 'json'], default='txt',
                                  help='Output format: txt, vtt, json (default: txt)')
    transcript_parser.add_argument('--output', type=str, metavar='FILE',
                                  help='Save to file (default: print to stdout)')
    transcript_parser.add_argument('--timestamps', action='store_true',
                                  help='Include timestamps (for txt format)')
    transcript_parser.add_argument('--speakers', action='store_true',
                                  help='Include speaker names (for txt format)')

    transcript_parser.set_defaults(func=cmd_transcript)

    # o365 recordings info
    info_parser = subparsers.add_parser(
        'info',
        help='Show recording details',
        description='Show detailed information about a recording.'
    )

    info_parser.add_argument('recording_id', help='Recording ID from list/search')

    info_parser.set_defaults(func=cmd_info)


def handle_command(args):
    """Route to appropriate recordings subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No recordings subcommand specified", file=sys.stderr)
        sys.exit(1)
