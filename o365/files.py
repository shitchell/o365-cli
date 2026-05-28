"""
OneDrive and SharePoint file management commands for Office365

List, search, download, upload, and share files across personal OneDrive and shared drives.
"""

import sys
import os
import json
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

from .common import get_access_token, make_graph_request, GRAPH_API_BASE, global_parent_parser, is_json_mode, emit_json
from .calendar import parse_since_expression


def get_drives(access_token):
    """Get all available drives (personal OneDrive and shared sites)

    Args:
        access_token: OAuth2 access token

    Returns:
        List of drive objects
    """
    drives = []

    # Get personal OneDrive
    personal_drive = make_graph_request('/me/drive', access_token)
    if personal_drive:
        drives.append(personal_drive)

    # Get all accessible drives (includes shared sites)
    url = f"{GRAPH_API_BASE}/me/drives"

    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        drives.extend(result.get('value', []))
        url = result.get('@odata.nextLink')

    # Deduplicate by ID
    seen_ids = set()
    unique_drives = []
    for drive in drives:
        if drive['id'] not in seen_ids:
            seen_ids.add(drive['id'])
            unique_drives.append(drive)

    return unique_drives


def resolve_drive(drive_query, access_token):
    """Resolve a drive name or ID to a drive object

    Args:
        drive_query: Drive name (fuzzy match) or ID
        access_token: OAuth2 access token

    Returns:
        Drive object or None if not found
    """
    drives = get_drives(access_token)

    # Try exact ID match first
    for drive in drives:
        if drive['id'] == drive_query:
            return drive

    # Try fuzzy name match
    query_lower = drive_query.lower()
    matches = []
    for drive in drives:
        name = drive.get('name', '').lower()
        if query_lower in name:
            matches.append(drive)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"Error: Multiple drives match '{drive_query}':", file=sys.stderr)
        for drive in matches:
            print(f"  - {drive['name']} (ID: {drive['id']})", file=sys.stderr)
        print("\nPlease specify a more specific name or use the drive ID", file=sys.stderr)
        return None

    return None


def list_files(access_token, path='/', drive_id=None, recursive=False, since=None):
    """List files and folders in a path

    Args:
        access_token: OAuth2 access token
        path: Path to list (default: root)
        drive_id: Drive ID (default: personal OneDrive)
        recursive: List subdirectories recursively
        since: Optional datetime to filter files modified since

    Returns:
        List of item objects
    """
    # Get personal drive if not specified
    if not drive_id:
        personal_drive = make_graph_request('/me/drive', access_token)
        if not personal_drive:
            return []
        drive_id = personal_drive['id']

    # Build URL for path
    if path == '/' or path == '':
        url = f"{GRAPH_API_BASE}/drives/{drive_id}/root/children"
    else:
        # Remove leading/trailing slashes
        path = path.strip('/')
        encoded_path = urllib.parse.quote(path)
        url = f"{GRAPH_API_BASE}/drives/{drive_id}/root:/{encoded_path}:/children"

    items = []

    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        batch = result.get('value', [])

        # Apply since filter if specified
        if since:
            batch = [item for item in batch
                    if 'lastModifiedDateTime' in item and
                    parse_graph_datetime(item['lastModifiedDateTime']) >= since]

        items.extend(batch)
        url = result.get('@odata.nextLink')

    # Recursive listing
    if recursive:
        folders = [item for item in items if 'folder' in item]
        for folder in folders:
            folder_path = f"{path}/{folder['name']}" if path != '/' else f"/{folder['name']}"
            sub_items = list_files(access_token, folder_path, drive_id, recursive, since)
            items.extend(sub_items)

    return items


def parse_graph_datetime(dt_str):
    """Parse Microsoft Graph datetime format

    Args:
        dt_str: ISO 8601 datetime string

    Returns:
        datetime object
    """
    from datetime import datetime
    # Remove excess fractional seconds (keep max 6 digits)
    import re
    dt_str = re.sub(r'\.(\d{6})\d*', r'.\1', dt_str)
    # Handle timezone
    if not dt_str.endswith('Z') and '+' not in dt_str and '-' not in dt_str[-6:]:
        dt_str += 'Z'
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def search_files(access_token, query, drive_id=None, file_type=None, since=None, count=50):
    """Search for files across OneDrive and SharePoint

    Args:
        access_token: OAuth2 access token
        query: Search query (filename or content)
        drive_id: Optional drive ID to limit search
        file_type: Optional file extension filter (pdf, xlsx, docx, etc.)
        since: Optional datetime to filter files modified since
        count: Maximum results to return

    Returns:
        List of item objects
    """
    # Build search URL
    if drive_id:
        url = f"{GRAPH_API_BASE}/drives/{drive_id}/root/search(q='{query}')"
    else:
        url = f"{GRAPH_API_BASE}/me/drive/root/search(q='{query}')"

    items = []

    while url:
        result = make_graph_request(url, access_token)
        if not result:
            break

        batch = result.get('value', [])

        # Apply file type filter
        if file_type:
            extension = file_type if file_type.startswith('.') else f'.{file_type}'
            batch = [item for item in batch if item.get('name', '').lower().endswith(extension.lower())]

        # Apply since filter
        if since:
            batch = [item for item in batch
                    if 'lastModifiedDateTime' in item and
                    parse_graph_datetime(item['lastModifiedDateTime']) >= since]

        items.extend(batch)

        # Respect count limit
        if len(items) >= count:
            items = items[:count]
            break

        url = result.get('@odata.nextLink')

    return items[:count]


def download_file(access_token, item_id, dest_path, drive_id=None):
    """Download a file from OneDrive/SharePoint

    Args:
        access_token: OAuth2 access token
        item_id: File item ID
        dest_path: Local destination path
        drive_id: Drive ID (default: personal OneDrive)

    Returns:
        True on success, False on error
    """
    # Get personal drive if not specified
    if not drive_id:
        personal_drive = make_graph_request('/me/drive', access_token)
        if not personal_drive:
            return False
        drive_id = personal_drive['id']

    # Get download URL
    url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{item_id}/content"

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    try:
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req) as response:
            # Ensure destination directory exists
            dest = Path(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Download file
            with open(dest, 'wb') as f:
                f.write(response.read())

        return True

    except Exception as e:
        print(f"Error downloading file: {e}", file=sys.stderr)
        return False


def upload_file(access_token, source_path, dest_path, drive_id=None, overwrite=False):
    """Upload a file to OneDrive/SharePoint

    Args:
        access_token: OAuth2 access token
        source_path: Local file path
        dest_path: Remote destination path
        drive_id: Drive ID (default: personal OneDrive)
        overwrite: Overwrite existing file

    Returns:
        Uploaded item object or None on error
    """
    # Get personal drive if not specified
    if not drive_id:
        personal_drive = make_graph_request('/me/drive', access_token)
        if not personal_drive:
            return None
        drive_id = personal_drive['id']

    source = Path(source_path)
    if not source.exists():
        print(f"Error: File not found: {source_path}", file=sys.stderr)
        return None

    # Get file size
    file_size = source.stat().st_size

    # For small files (<4MB), use simple upload
    if file_size < 4 * 1024 * 1024:
        # Remove leading/trailing slashes from dest_path; URL-encode each
        # path segment (preserve slashes) so spaces/special chars work.
        dest_path = dest_path.strip('/')
        filename = urllib.parse.quote(source.name, safe='')

        if dest_path:
            encoded_dest = urllib.parse.quote(dest_path, safe='/')
            url = f"{GRAPH_API_BASE}/drives/{drive_id}/root:/{encoded_dest}/{filename}:/content"
        else:
            url = f"{GRAPH_API_BASE}/drives/{drive_id}/root:/{filename}:/content"

        # Graph defaults to "replace" on PUT; pass "fail" explicitly when the
        # caller didn't ask to overwrite, so a name conflict returns 409.
        conflict = 'replace' if overwrite else 'fail'
        url += f"?@microsoft.graph.conflictBehavior={conflict}"

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/octet-stream'
        }

        try:
            with open(source, 'rb') as f:
                data = f.read()

            req = urllib.request.Request(url, data=data, headers=headers, method='PUT')

            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())

        except Exception as e:
            print(f"Error uploading file: {e}", file=sys.stderr)
            return None
    else:
        # For large files (>=4MB), use a resumable upload session.
        return _upload_large_file(
            access_token, source, dest_path, drive_id, overwrite, file_size
        )


def _upload_large_file(access_token, source, dest_path, drive_id, overwrite, file_size):
    """Upload a file via a resumable upload session.

    Required by Graph for files >=4MB. Streams the file in 10 MiB chunks
    (a multiple of the 320 KiB chunk-size requirement) so we don't hold the
    whole file in memory, and emits a per-chunk progress line to stderr.
    """
    dest_path = dest_path.strip('/')
    filename = urllib.parse.quote(source.name, safe='')

    if dest_path:
        encoded_dest = urllib.parse.quote(dest_path, safe='/')
        session_path = f"/drives/{drive_id}/root:/{encoded_dest}/{filename}:/createUploadSession"
    else:
        session_path = f"/drives/{drive_id}/root:/{filename}:/createUploadSession"

    conflict = 'replace' if overwrite else 'fail'
    session = make_graph_request(
        session_path, access_token, method='POST',
        data={'item': {'@microsoft.graph.conflictBehavior': conflict}},
    )
    if not session or 'uploadUrl' not in session:
        print("Error: Failed to create upload session", file=sys.stderr)
        return None
    upload_url = session['uploadUrl']

    # Chunk size must be a multiple of 320 KiB. 10 MiB is a good default —
    # large enough to be efficient, small enough to keep memory + per-chunk
    # latency reasonable.
    CHUNK_SIZE = 10 * 1024 * 1024

    body = b''
    try:
        with open(source, 'rb') as f:
            offset = 0
            while offset < file_size:
                chunk = f.read(CHUNK_SIZE)
                end = offset + len(chunk) - 1
                req = urllib.request.Request(
                    upload_url, data=chunk,
                    headers={
                        'Content-Length': str(len(chunk)),
                        'Content-Range': f'bytes {offset}-{end}/{file_size}',
                    },
                    method='PUT',
                )
                try:
                    with urllib.request.urlopen(req) as response:
                        body = response.read()
                except urllib.error.HTTPError as e:
                    err = e.read().decode(errors='replace')[:500]
                    print(f"Error: HTTP {e.code} during chunk upload: {err}", file=sys.stderr)
                    return None

                pct = (end + 1) * 100.0 / file_size
                print(
                    f"  {format_size(end + 1)}/{format_size(file_size)} ({pct:.1f}%)",
                    file=sys.stderr,
                )
                offset += len(chunk)
    except Exception as e:
        print(f"Error during chunked upload: {e}", file=sys.stderr)
        return None

    # Final chunk's response is 200/201 with the created DriveItem JSON.
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        print(f"Error parsing upload response: {e}", file=sys.stderr)
        return None


# ============================================================================
# STRUCTURED DATA FUNCTIONS (for MCP and programmatic access)
# ============================================================================

def get_drives_structured(access_token):
    """
    Get all available drives as structured data (for MCP/programmatic use).

    Args:
        access_token: OAuth2 access token

    Returns:
        list[dict]: List of drive dictionaries with schema:
            {
                'id': str,
                'name': str,
                'drive_type': str,
                'owner_name': str,
                'owner_email': str,
                'web_url': str
            }
    """
    drives = get_drives(access_token)

    structured_drives = []
    for drive in drives:
        owner = drive.get('owner', {}).get('user', {})
        structured_drives.append({
            'id': drive.get('id', ''),
            'name': drive.get('name', ''),
            'drive_type': drive.get('driveType', ''),
            'owner_name': owner.get('displayName', ''),
            'owner_email': owner.get('email', ''),
            'web_url': drive.get('webUrl', '')
        })

    return structured_drives


def list_files_structured(access_token, path='/', drive_id=None, recursive=False, since=None):
    """
    List files and folders as structured data (for MCP/programmatic use).

    Args:
        access_token: OAuth2 access token
        path: Path to list (default: root)
        drive_id: Drive ID (default: personal OneDrive)
        recursive: List subdirectories recursively
        since: Optional datetime to filter files modified since

    Returns:
        list[dict]: List of file/folder dictionaries with schema:
            {
                'id': str,
                'name': str,
                'type': 'file' | 'folder',
                'size': int,
                'size_formatted': str,
                'modified_datetime': str (ISO 8601),
                'web_url': str,
                'download_url': str,
                'parent_path': str
            }
    """
    items = list_files(access_token, path, drive_id, recursive, since)

    structured_items = []
    for item in items:
        item_type = 'folder' if 'folder' in item else 'file'
        size = item.get('size', 0) if 'size' in item else 0
        modified = item.get('lastModifiedDateTime', '')

        parent_ref = item.get('parentReference', {})
        parent_path = parent_ref.get('path', '').replace('/drive/root:', '') or '/'

        structured_items.append({
            'id': item.get('id', ''),
            'name': item.get('name', ''),
            'type': item_type,
            'size': size,
            'size_formatted': format_size(size) if size else '-',
            'modified_datetime': modified,
            'web_url': item.get('webUrl', ''),
            'download_url': item.get('@microsoft.graph.downloadUrl', ''),
            'parent_path': parent_path
        })

    return structured_items


def search_files_structured(access_token, query, drive_id=None, file_type=None, since=None, count=50):
    """
    Search for files as structured data (for MCP/programmatic use).

    Args:
        access_token: OAuth2 access token
        query: Search query (filename or content)
        drive_id: Optional drive ID to limit search
        file_type: Optional file extension filter (pdf, xlsx, docx, etc.)
        since: Optional datetime to filter files modified since
        count: Maximum results to return

    Returns:
        list[dict]: List of file dictionaries with schema:
            {
                'id': str,
                'name': str,
                'type': 'file' | 'folder',
                'size': int,
                'size_formatted': str,
                'modified_datetime': str (ISO 8601),
                'web_url': str,
                'download_url': str,
                'parent_path': str
            }
    """
    items = search_files(access_token, query, drive_id, file_type, since, count)

    # Reuse list_files_structured transformation logic
    structured_items = []
    for item in items:
        item_type = 'folder' if 'folder' in item else 'file'
        size = item.get('size', 0) if 'size' in item else 0
        modified = item.get('lastModifiedDateTime', '')

        parent_ref = item.get('parentReference', {})
        parent_path = parent_ref.get('path', '').replace('/drive/root:', '') or '/'

        structured_items.append({
            'id': item.get('id', ''),
            'name': item.get('name', ''),
            'type': item_type,
            'size': size,
            'size_formatted': format_size(size) if size else '-',
            'modified_datetime': modified,
            'web_url': item.get('webUrl', ''),
            'download_url': item.get('@microsoft.graph.downloadUrl', ''),
            'parent_path': parent_path
        })

    return structured_items


def download_file_structured(access_token, item_id, dest_path, drive_id=None):
    """
    Download a file and return status (for MCP/programmatic use).

    Args:
        access_token: OAuth2 access token
        item_id: File item ID
        dest_path: Local destination path
        drive_id: Drive ID (default: personal OneDrive)

    Returns:
        dict: Status dictionary with schema:
            On success:
                {
                    'status': 'success',
                    'message': str,
                    'item_id': str,
                    'dest_path': str
                }
            On error:
                {
                    'status': 'error',
                    'message': str,
                    'error': str,
                    'item_id': str
                }
    """
    try:
        success = download_file(access_token, item_id, dest_path, drive_id)

        if success:
            return {
                'status': 'success',
                'message': 'File downloaded successfully',
                'item_id': item_id,
                'dest_path': str(dest_path)
            }
        else:
            return {
                'status': 'error',
                'message': 'Failed to download file',
                'error': 'Download operation returned False',
                'item_id': item_id
            }

    except Exception as e:
        return {
            'status': 'error',
            'message': 'Failed to download file',
            'error': str(e),
            'item_id': item_id
        }


def upload_file_structured(access_token, source_path, dest_path, drive_id=None, overwrite=False):
    """
    Upload a file and return status (for MCP/programmatic use).

    Args:
        access_token: OAuth2 access token
        source_path: Local file path
        dest_path: Remote destination path
        drive_id: Drive ID (default: personal OneDrive)
        overwrite: Overwrite existing file

    Returns:
        dict: Status dictionary with schema:
            On success:
                {
                    'status': 'success',
                    'message': str,
                    'item': {
                        'id': str,
                        'name': str,
                        'size': int,
                        'web_url': str
                    }
                }
            On error:
                {
                    'status': 'error',
                    'message': str,
                    'error': str
                }
    """
    try:
        result = upload_file(access_token, source_path, dest_path, drive_id, overwrite)

        if result:
            return {
                'status': 'success',
                'message': 'File uploaded successfully',
                'item': {
                    'id': result.get('id', ''),
                    'name': result.get('name', ''),
                    'size': result.get('size', 0),
                    'web_url': result.get('webUrl', '')
                }
            }
        else:
            return {
                'status': 'error',
                'message': 'Failed to upload file',
                'error': 'Upload operation returned None'
            }

    except Exception as e:
        return {
            'status': 'error',
            'message': 'Failed to upload file',
            'error': str(e)
        }


# ============================================================================
# CLI COMMAND FUNCTIONS
# ============================================================================

# Command handlers

def _serialize_drive(drive):
    """Compact dict for `files drives` --json output."""
    owner = (((drive.get('owner') or {}).get('user') or {}).get('displayName')) or None
    return {
        'id': drive.get('id'),
        'name': drive.get('name'),
        'drive_type': drive.get('driveType'),
        'owner': owner,
        'web_url': drive.get('webUrl'),
    }


def _serialize_file_item(item):
    """Compact dict for `files list`/`files search` --json output."""
    parent_ref = item.get('parentReference') or {}
    parent_path = (parent_ref.get('path') or '').replace('/drive/root:', '') or '/'
    return {
        'id': item.get('id'),
        'name': item.get('name'),
        'type': 'folder' if 'folder' in item else 'file',
        'size': item.get('size'),
        'last_modified': item.get('lastModifiedDateTime'),
        'created': item.get('createdDateTime'),
        'path': parent_path,
        'web_url': item.get('webUrl'),
        'mime_type': (item.get('file') or {}).get('mimeType'),
    }


def cmd_drives(args):
    """Handle 'o365 files drives' command"""
    access_token = get_access_token()

    drives = get_drives(access_token)

    if is_json_mode(args):
        emit_json({
            'drives': [_serialize_drive(d) for d in drives],
            'count': len(drives),
        })
        return

    if not drives:
        print("No drives found")
        return

    print(f"\n📁 Available Drives ({len(drives)}):\n")

    if args.verbose:
        print(f"{'Name':<40} {'Type':<20} {'ID':<40}")
        print("=" * 100)

        for drive in drives:
            name = drive.get('name', 'Unknown')[:38]
            drive_type = drive.get('driveType', 'unknown')[:18]
            drive_id = drive['id']

            print(f"{name:<40} {drive_type:<20} {drive_id:<40}")
    else:
        for drive in drives:
            name = drive.get('name', 'Unknown')
            drive_type = drive.get('driveType', 'unknown')
            owner = drive.get('owner', {}).get('user', {}).get('displayName', '')

            if owner:
                print(f"  • {name} ({drive_type}) - owned by {owner}")
            else:
                print(f"  • {name} ({drive_type})")

    print(f"\nUse 'o365 files list --drive \"Drive Name\"' to browse a drive")


def cmd_list(args):
    """Handle 'o365 files list' command"""
    access_token = get_access_token()

    # Resolve drive if specified
    drive_id = None
    if args.drive:
        drive = resolve_drive(args.drive, access_token)
        if not drive:
            print(f"Error: Drive not found: {args.drive}", file=sys.stderr)
            sys.exit(1)
        drive_id = drive['id']

    # Parse --since if specified
    since = None
    if args.since:
        try:
            since = parse_since_expression(args.since)
        except ValueError as e:
            print(f"Error in --since: {e}", file=sys.stderr)
            sys.exit(1)

    # List files
    path = args.path or '/'
    items = list_files(access_token, path, drive_id, args.recursive, since)

    if is_json_mode(args):
        emit_json({
            'path': path,
            'drive_id': drive_id,
            'items': [_serialize_file_item(i) for i in items],
            'count': len(items),
        })
        return

    if not items:
        print(f"No files found in {path}")
        return

    print(f"\n📁 Files in {path} ({len(items)} items):\n")

    if args.long:
        print(f"{'Type':<8} {'Size':<12} {'Modified':<20} {'Name':<40}")
        print("=" * 80)

        for item in items:
            item_type = 'folder' if 'folder' in item else 'file'
            size = format_size(item.get('size', 0)) if 'size' in item else '-'
            modified = parse_graph_datetime(item['lastModifiedDateTime']).strftime('%Y-%m-%d %H:%M') if 'lastModifiedDateTime' in item else '-'
            name = item['name'][:38]

            print(f"{item_type:<8} {size:<12} {modified:<20} {name:<40}")
    else:
        for item in items:
            item_type = '📁' if 'folder' in item else '📄'
            name = item['name']
            print(f"  {item_type} {name}")

    print(f"\nUse 'o365 files download <path>' to download files")


def cmd_search(args):
    """Handle 'o365 files search' command"""
    access_token = get_access_token()

    # Resolve drive if specified
    drive_id = None
    if args.drive:
        drive = resolve_drive(args.drive, access_token)
        if not drive:
            print(f"Error: Drive not found: {args.drive}", file=sys.stderr)
            sys.exit(1)
        drive_id = drive['id']

    # Parse --since if specified
    since = None
    if args.since:
        try:
            since = parse_since_expression(args.since)
        except ValueError as e:
            print(f"Error in --since: {e}", file=sys.stderr)
            sys.exit(1)

    # Search files
    items = search_files(access_token, args.query, drive_id, args.type, since, args.count or 50)

    if is_json_mode(args):
        emit_json({
            'query': args.query,
            'items': [_serialize_file_item(i) for i in items],
            'count': len(items),
        })
        return

    if not items:
        print(f"No files found matching '{args.query}'")
        return

    print(f"\n🔍 Search results for '{args.query}' ({len(items)} found):\n")
    print(f"{'Type':<8} {'Size':<12} {'Modified':<20} {'Name':<40} {'Path':<40}")
    print("=" * 120)

    for item in items:
        item_type = 'folder' if 'folder' in item else 'file'
        size = format_size(item.get('size', 0)) if 'size' in item else '-'
        modified = parse_graph_datetime(item['lastModifiedDateTime']).strftime('%Y-%m-%d %H:%M') if 'lastModifiedDateTime' in item else '-'
        name = item['name'][:38]

        # Get parent path
        parent_ref = item.get('parentReference', {})
        path = parent_ref.get('path', '').replace('/drive/root:', '') or '/'
        path = path[:38]

        print(f"{item_type:<8} {size:<12} {modified:<20} {name:<40} {path:<40}")


def cmd_download(args):
    """Handle 'o365 files download' command"""
    access_token = get_access_token()

    # Resolve drive if specified
    drive_id = None
    if args.drive:
        drive = resolve_drive(args.drive, access_token)
        if not drive:
            print(f"Error: Drive not found: {args.drive}", file=sys.stderr)
            sys.exit(1)
        drive_id = drive['id']
    else:
        # Get personal drive
        personal_drive = make_graph_request('/me/drive', access_token)
        if not personal_drive:
            print("Error: Could not access personal drive", file=sys.stderr)
            sys.exit(1)
        drive_id = personal_drive['id']

    # Get file item by path
    source_path = args.source.strip('/')
    encoded_path = urllib.parse.quote(source_path)
    url = f"{GRAPH_API_BASE}/drives/{drive_id}/root:/{encoded_path}"

    item = make_graph_request(url, access_token)
    if not item:
        print(f"Error: File not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    # Check if it's a folder
    if 'folder' in item:
        if not args.recursive:
            print(f"Error: '{args.source}' is a folder. Use --recursive to download folders.", file=sys.stderr)
            sys.exit(1)
        else:
            print("Error: Recursive folder downloads not yet implemented", file=sys.stderr)
            sys.exit(1)

    # Determine destination
    if args.dest:
        dest = Path(args.dest)
        if dest.is_dir():
            dest = dest / item['name']
    else:
        dest = Path.cwd() / item['name']

    # Check if file exists
    if dest.exists() and not args.overwrite:
        print(f"Error: File exists: {dest}", file=sys.stderr)
        print("Use --overwrite to overwrite existing files", file=sys.stderr)
        sys.exit(1)

    # Download file
    print(f"Downloading {item['name']} ({format_size(item.get('size', 0))})...")

    if download_file(access_token, item['id'], dest, drive_id):
        print(f"✓ Downloaded to {dest}")
    else:
        print("Error: Download failed", file=sys.stderr)
        sys.exit(1)


def cmd_upload(args):
    """Handle 'o365 files upload' command"""
    access_token = get_access_token()

    # Resolve drive if specified
    drive_id = None
    if args.drive:
        drive = resolve_drive(args.drive, access_token)
        if not drive:
            print(f"Error: Drive not found: {args.drive}", file=sys.stderr)
            sys.exit(1)
        drive_id = drive['id']

    source = Path(args.source)
    if not source.exists():
        print(f"Error: File not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    if source.is_dir():
        if not args.recursive:
            print(f"Error: '{args.source}' is a directory. Use --recursive to upload folders.", file=sys.stderr)
            sys.exit(1)
        else:
            print("Error: Recursive folder uploads not yet implemented", file=sys.stderr)
            sys.exit(1)

    # Upload file
    print(f"Uploading {source.name} ({format_size(source.stat().st_size)})...")

    result = upload_file(access_token, source, args.dest, drive_id, args.overwrite)

    if result:
        print(f"✓ Uploaded to {args.dest}/{source.name}")
    else:
        print("Error: Upload failed", file=sys.stderr)
        sys.exit(1)


def format_size(bytes_size):
    """Format byte size to human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f}PB"


# Setup and routing

def setup_parser(subparsers):
    """Setup argparse subcommands for files"""

    _parent = global_parent_parser()

    # o365 files drives
    drives_parser = subparsers.add_parser(
        'drives',
        parents=[_parent],
        help='List available drives',
        description='List all available drives (personal OneDrive and shared SharePoint sites).'
    )

    drives_parser.add_argument('-v', '--verbose', action='store_true',
                              help='Show drive IDs and details')

    drives_parser.set_defaults(func=cmd_drives)

    # o365 files list
    list_parser = subparsers.add_parser(
        'list',
        parents=[_parent],
        aliases=['ls'],
        help='List files and folders (alias: ls)',
        description='List files and folders in OneDrive or SharePoint.'
    )

    list_parser.add_argument('path', nargs='?', default='/',
                            help='Path to list (default: root)')
    list_parser.add_argument('--drive', type=str, metavar='DRIVE',
                            help='Drive name or ID (default: personal OneDrive)')
    list_parser.add_argument('-l', '--long', action='store_true',
                            help='Show detailed information (size, modified date)')
    list_parser.add_argument('-r', '--recursive', action='store_true',
                            help='List subdirectories recursively')
    list_parser.add_argument('--since', type=str, metavar='EXPR',
                            help='Show files modified since (git-style: "2 days ago")')

    list_parser.set_defaults(func=cmd_list)

    # o365 files search
    search_parser = subparsers.add_parser(
        'search',
        parents=[_parent],
        help='Search for files',
        description='Search for files across OneDrive and SharePoint.'
    )

    search_parser.add_argument('query', help='Search query (filename or content)')
    search_parser.add_argument('--drive', type=str, metavar='DRIVE',
                              help='Limit search to specific drive')
    search_parser.add_argument('--type', type=str, metavar='TYPE',
                              help='File type filter (pdf, xlsx, docx, pptx, etc.)')
    search_parser.add_argument('--since', type=str, metavar='EXPR',
                              help='Files modified since (git-style format)')
    search_parser.add_argument('-n', '--count', type=int, metavar='N',
                              help='Maximum results to show (default: 50)')

    search_parser.set_defaults(func=cmd_search)

    # o365 files download
    download_parser = subparsers.add_parser(
        'download',
        parents=[_parent],
        help='Download files or folders',
        description='Download files or folders from OneDrive/SharePoint.'
    )

    download_parser.add_argument('source', help='Remote path to download')
    download_parser.add_argument('dest', nargs='?', help='Local destination (default: current directory)')
    download_parser.add_argument('--drive', type=str, metavar='DRIVE',
                                help='Source drive name or ID')
    download_parser.add_argument('-r', '--recursive', action='store_true',
                                help='Download folder recursively')
    download_parser.add_argument('--overwrite', action='store_true',
                                help='Overwrite existing files')

    download_parser.set_defaults(func=cmd_download)

    # o365 files upload
    upload_parser = subparsers.add_parser(
        'upload',
        parents=[_parent],
        help='Upload files to OneDrive/SharePoint',
        description='Upload files to OneDrive or SharePoint.'
    )

    upload_parser.add_argument('source', help='Local file or folder to upload')
    upload_parser.add_argument('dest', help='Remote destination path')
    upload_parser.add_argument('--drive', type=str, metavar='DRIVE',
                              help='Destination drive name or ID')
    upload_parser.add_argument('-r', '--recursive', action='store_true',
                              help='Upload folder recursively')
    upload_parser.add_argument('--overwrite', action='store_true',
                              help='Overwrite existing files')

    upload_parser.set_defaults(func=cmd_upload)


def handle_command(args):
    """Route to appropriate files subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No files subcommand specified", file=sys.stderr)
        sys.exit(1)
