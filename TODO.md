# o365-cli TODO

## Completed Features ✅

- ✅ Mail management (sync, read, archive, send, mark-read)
- ✅ Calendar management (list, create, delete)
- ✅ Contacts management (list, search)
- ✅ Chat management (list, read, send, search)
- ✅ OneDrive/Files management (drives, list, search, download, upload) - **Personal OneDrive only**
- ✅ Authentication (login, refresh, status with auto-refresh)
- ✅ Configuration system (config file + env vars)
- ✅ Automatic token refresh (5-minute buffer)
- ✅ User-friendly error messages

## In Progress 🚧

### 1. Meeting Recordings

## Known Limitations ⚠️

### OneDrive/Files - Shared Drives
**Status**: Personal OneDrive only. Shared SharePoint sites/team drives require admin consent.

**Issue**: The permissions `Files.Read.All`, `Files.ReadWrite.All`, `Sites.Read.All`, and `Sites.ReadWrite.All` are blocked by tenant-level Azure AD consent policies in some organizations, even though they're marked as "Admin consent required: No" in the Azure Portal.

**Workaround**: Organization admins can grant consent via Azure Portal → App registrations → API permissions → "Grant admin consent for [Organization]"

**Current functionality**:
- ✅ Personal OneDrive: List, search, download, upload
- ❌ Shared drives: Requires admin consent for `.All` scopes

---

## Feature Specifications

## 1. OneDrive/Files Commands

### Required Permissions
```
Files.Read
Files.Read.All
Files.ReadWrite
Files.ReadWrite.All
Sites.Read.All
Sites.ReadWrite.All
```

### Main Command
```bash
o365 files --help
```

```
usage: o365 files <command> [options]

Manage files in OneDrive and SharePoint

Available commands:
  drives       List available drives (personal OneDrive + shared sites)
  list         List files and folders
  search       Search for files
  download     Download files or folders
  upload       Upload files to OneDrive/SharePoint
  share        Create a sharing link for a file
  info         Show detailed file information
  delete       Delete a file or folder
  mkdir        Create a folder

Examples:
  o365 files drives                              # List all accessible drives
  o365 files list /Documents                     # List files in Documents
  o365 files search "quarterly report"           # Search your OneDrive
  o365 files download /Reports/Q4.xlsx ~/Desktop/
  o365 files upload ~/analysis.pdf /Work/Projects/

For more help on a specific command:
  o365 files <command> --help
```

### `o365 files drives`
```
usage: o365 files drives [options]

List all available drives (personal OneDrive and shared SharePoint sites)

Options:
  -v, --verbose    Show drive IDs and details

Examples:
  o365 files drives                   # List all drives
  o365 files drives -v                # Show drive IDs and details

Output shows:
  - Your personal OneDrive (default)
  - Shared team sites you have access to
  - Document libraries within sites
```

### `o365 files list`
```
usage: o365 files list [PATH] [options]

List files and folders in OneDrive or SharePoint

Arguments:
  PATH                   Path to list (default: root)

Options:
  --drive DRIVE          Drive name or ID (default: personal OneDrive)
  --site SITE            SharePoint site name
  -l, --long             Show detailed information (size, modified date)
  -r, --recursive        List subdirectories recursively
  --since EXPR           Show files modified since (git-style: "2 days ago")

Examples:
  o365 files list                              # List root of personal OneDrive
  o365 files list /Documents                   # List Documents folder
  o365 files list --drive "Engineering Team"   # List shared drive
  o365 files list --site "ProjectX" /Docs      # List in SharePoint site
  o365 files list -l --since "1 week ago"      # Recent files with details
  o365 files list -r /Projects                 # Recursive listing
```

### `o365 files search`
```
usage: o365 files search QUERY [options]

Search for files across OneDrive and SharePoint

Arguments:
  QUERY                  Search query (filename or content)

Options:
  --drive DRIVE          Limit search to specific drive
  --site SITE            Limit search to SharePoint site
  --type TYPE            File type filter (pdf, xlsx, docx, pptx, etc.)
  --since EXPR           Files modified since (git-style format)
  -n, --count N          Maximum results to show (default: 50)

Examples:
  o365 files search "quarterly report"                    # Search everywhere
  o365 files search "budget" --type xlsx                  # Excel files only
  o365 files search "proposal" --drive "Sales Team"       # Search shared drive
  o365 files search "architecture" --since "1 month ago"  # Recent files
  o365 files search "meeting notes" --site "Engineering"  # Site-specific
```

### `o365 files download`
```
usage: o365 files download SOURCE [DEST] [options]

Download files or folders from OneDrive/SharePoint

Arguments:
  SOURCE                 Remote path to download
  DEST                   Local destination (default: current directory)

Options:
  --drive DRIVE          Source drive name or ID
  --site SITE            Source SharePoint site
  -r, --recursive        Download folder recursively
  --overwrite            Overwrite existing files

Examples:
  o365 files download /Reports/Q4.xlsx                       # To current dir
  o365 files download /Reports/Q4.xlsx ~/Desktop/            # To Desktop
  o365 files download /Project --recursive ~/Work/           # Folder download
  o365 files download /Doc.pdf ~/Docs/ --drive "Team Drive"  # From shared drive
```

### `o365 files upload`
```
usage: o365 files upload SOURCE DEST [options]

Upload files to OneDrive or SharePoint

Arguments:
  SOURCE                 Local file or folder to upload
  DEST                   Remote destination path

Options:
  --drive DRIVE          Destination drive name or ID
  --site SITE            Destination SharePoint site
  -r, --recursive        Upload folder recursively
  --overwrite            Overwrite existing files

Examples:
  o365 files upload ~/analysis.pdf /Reports/              # To OneDrive
  o365 files upload ~/project/ /Work/ --recursive         # Upload folder
  o365 files upload ~/data.xlsx /Team/Data/ --drive "Sales"  # To shared drive
  o365 files upload ~/doc.pdf /Docs/ --site "ProjectX"   # To SharePoint site
```

### `o365 files share`
```
usage: o365 files share PATH [options]

Create a sharing link for a file or folder

Arguments:
  PATH                   Path to file or folder

Options:
  --drive DRIVE          Drive name or ID
  --site SITE            SharePoint site
  --type TYPE            Link type: view, edit, embed (default: view)
  --expires EXPR         Expiration time (git-style: "1 week", "30 days")
  --password PASS        Require password to access

Examples:
  o365 files share /Documents/report.pdf                 # View-only link
  o365 files share /Docs/data.xlsx --type edit           # Editable link
  o365 files share /Project/ --expires "1 week"          # 7-day expiration
  o365 files share /Doc.pdf --password "secret123"       # Password protected
  o365 files share /Team/file.docx --drive "Sales"       # Share from shared drive
```

### `o365 files info`
```
usage: o365 files info PATH [options]

Show detailed information about a file or folder

Arguments:
  PATH                   Path to file or folder

Options:
  --drive DRIVE          Drive name or ID
  --site SITE            SharePoint site

Examples:
  o365 files info /Documents/report.pdf
  o365 files info /Project/ --drive "Engineering Team"

Shows:
  - File name, size, type
  - Created/modified dates
  - Sharing status
  - Download URL
  - Version history
```

### `o365 files delete`
```
usage: o365 files delete PATH [options]

Delete a file or folder

Arguments:
  PATH                   Path to file or folder

Options:
  --drive DRIVE          Drive name or ID
  --site SITE            SharePoint site
  --permanent            Permanently delete (skip recycle bin)

Examples:
  o365 files delete /Old/file.pdf
  o365 files delete /Archive/ --drive "Team Drive"
```

### `o365 files mkdir`
```
usage: o365 files mkdir PATH [options]

Create a new folder

Arguments:
  PATH                   Path for new folder

Options:
  --drive DRIVE          Drive name or ID
  --site SITE            SharePoint site

Examples:
  o365 files mkdir /Projects/NewProject
  o365 files mkdir /Team/Q1 --drive "Sales"
```

---

## 2. Meeting Recordings Commands

### Required Permissions
```
OnlineMeetings.Read
OnlineMeetings.ReadWrite
CallRecords.Read.All
Files.Read.All (for recordings stored in OneDrive)
```

### Main Command
```bash
o365 recordings --help
```

```
usage: o365 recordings <command> [options]

Manage Microsoft Teams meeting recordings

Available commands:
  list         List meeting recordings
  search       Search recordings by meeting name
  download     Download a recording
  transcript   Get meeting transcript
  info         Show recording details

Examples:
  o365 recordings list --since "1 week ago"
  o365 recordings search "sprint planning"
  o365 recordings download <recording-id>
  o365 recordings transcript <recording-id> --format txt

For more help on a specific command:
  o365 recordings <command> --help
```

### `o365 recordings list`
```
usage: o365 recordings list [options]

List meeting recordings

Options:
  --since EXPR           Show recordings since (git-style: "1 week ago")
  --before EXPR          Show recordings before
  -n, --count N          Maximum results (default: 50)
  --organizer USER       Filter by meeting organizer
  --attendee USER        Filter by attendee (you or others)

Examples:
  o365 recordings list                              # Recent recordings
  o365 recordings list --since "2 weeks ago"        # Last 2 weeks
  o365 recordings list --organizer quinn            # Quinn's meetings
  o365 recordings list -n 100 --since "1 month ago" # Last 100 from past month

Output format:
  ID           Date                Meeting Name              Organizer       Duration
  abc123...    2025-10-15 14:00    Sprint Planning           Quinn Gribben   1h 30m
```

### `o365 recordings search`
```
usage: o365 recordings search QUERY [options]

Search for meeting recordings by name or attendees

Arguments:
  QUERY                  Search query (meeting name or keywords)

Options:
  --since EXPR           Recordings since (git-style format)
  --organizer USER       Filter by meeting organizer
  --attendee USER        Filter by attendee
  -n, --count N          Maximum results (default: 50)

Examples:
  o365 recordings search "sprint planning"                 # By meeting name
  o365 recordings search "architecture" --since "1 month"  # Recent arch meetings
  o365 recordings search "review" --organizer quinn        # Quinn's review meetings
  o365 recordings search "demo" --attendee roman           # Demos with Roman

Output shows:
  - Recording ID (for download/transcript commands)
  - Meeting date and time
  - Meeting name
  - Organizer
  - Duration
  - Attendee count
```

### `o365 recordings download`
```
usage: o365 recordings download RECORDING_ID [DEST] [options]

Download a meeting recording

Arguments:
  RECORDING_ID           Recording ID from list/search
  DEST                   Local destination (default: current directory)

Options:
  --format FORMAT        Video format: mp4, webm (default: mp4)
  --filename NAME        Custom filename (default: meeting name + date)

Examples:
  o365 recordings download abc123                        # To current dir
  o365 recordings download abc123 ~/Videos/              # To Videos folder
  o365 recordings download abc123 --filename "Sprint-Planning-Oct-15.mp4"

Note: Downloads may take time for large recordings
```

### `o365 recordings transcript`
```
usage: o365 recordings transcript RECORDING_ID [options]

Get or download meeting transcript

Arguments:
  RECORDING_ID           Recording ID from list/search

Options:
  --format FORMAT        Output format: txt, vtt, json (default: txt)
  --output FILE          Save to file (default: print to stdout)
  --timestamps           Include timestamps (for txt format)
  --speakers             Include speaker names (for txt format)

Examples:
  o365 recordings transcript abc123                      # Print to terminal
  o365 recordings transcript abc123 --output notes.txt   # Save to file
  o365 recordings transcript abc123 --format vtt         # VTT subtitle format
  o365 recordings transcript abc123 --timestamps --speakers  # Full details

Output shows:
  [00:01:23] Quinn Gribben: Let's start with the sprint review
  [00:02:45] Shaun Mitchell: I completed the authentication feature
  ...
```

### `o365 recordings info`
```
usage: o365 recordings info RECORDING_ID

Show detailed information about a recording

Arguments:
  RECORDING_ID           Recording ID from list/search

Examples:
  o365 recordings info abc123

Shows:
  - Meeting name and date
  - Organizer and attendees
  - Duration
  - Recording size
  - Transcript availability
  - Download URL
  - Creation/upload date
```

---

## Typical Workflows

### Find and analyze a meeting:
```bash
# Find the recording
o365 recordings search "sprint planning" --since "1 week ago"

# Download it
o365 recordings download abc123 ~/Videos/

# Get transcript for analysis
o365 recordings transcript abc123 --output sprint-notes.txt
```

### Work with shared files:
```bash
# See what drives you have access to
o365 files drives

# Search for a file in a shared drive
o365 files search "architecture diagram" --drive "Engineering Team"

# Download it
o365 files download /Docs/architecture.pdf ~/Work/ --drive "Engineering Team"

# Edit locally, then upload
o365 files upload ~/Work/architecture-updated.pdf /Docs/ --drive "Engineering Team" --overwrite
```

### Quick file sharing:
```bash
# Upload a file
o365 files upload ~/analysis.xlsx /Reports/

# Share it with the team
o365 files share /Reports/analysis.xlsx --type edit --expires "1 week"
# Returns: https://trinoor.sharepoint.com/...
```

---

## Implementation Notes

### Files to Create/Modify

1. **o365/files.py** - New module for OneDrive/SharePoint operations
2. **o365/recordings.py** - New module for meeting recordings
3. **o365/__main__.py** - Add files and recordings subparsers
4. **o365/common.py** - Add file scopes to DEFAULT_SCOPES and config loading
5. **config.example** - Add files=true and recordings=true to [scopes]
6. **README.md** - Add documentation for new commands

### Graph API Endpoints to Use

**Files:**
- `GET /me/drive` - Personal OneDrive
- `GET /me/drives` - All accessible drives
- `GET /drives/{drive-id}/root/children` - List files
- `GET /drives/{drive-id}/root:/path:/children` - List files by path
- `GET /drives/{drive-id}/root/search(q='{query}')` - Search
- `GET /drives/{drive-id}/items/{item-id}/content` - Download
- `PUT /drives/{drive-id}/items/{parent-id}:/{filename}:/content` - Upload
- `POST /drives/{drive-id}/items/{item-id}/createLink` - Share

**Recordings:**
- Recordings are stored in OneDrive/SharePoint in "Recordings" folder
- Use OneDrive search with filter for .mp4/.webm files
- Transcript files are .vtt alongside recordings
- May need to use `/me/onlineMeetings` for meeting metadata

### Key Considerations

1. **Path handling** - Convert user paths (e.g., /Documents/file.pdf) to Graph API paths
2. **Drive resolution** - Map friendly drive names to drive IDs
3. **Large file uploads** - Use resumable upload sessions for files >4MB
4. **Pagination** - Handle @odata.nextLink for large result sets
5. **Progress indication** - Show progress for downloads/uploads
6. **Error handling** - Graceful handling of permission errors, not found, etc.

### Testing Checklist

- [ ] List personal OneDrive files
- [ ] List shared drive files
- [ ] Search across drives
- [ ] Download file
- [ ] Upload file
- [ ] Create sharing link
- [ ] List recordings
- [ ] Search recordings
- [ ] Download recording
- [ ] Get transcript

---

## Configuration Updates Needed

Add to `config.example`:
```ini
[scopes]
files = true
recordings = true
```

Add to `o365/common.py` DEFAULT_SCOPES:
```python
"https://graph.microsoft.com/Files.Read",
"https://graph.microsoft.com/Files.Read.All",
"https://graph.microsoft.com/Files.ReadWrite",
"https://graph.microsoft.com/Files.ReadWrite.All",
"https://graph.microsoft.com/Sites.Read.All",
"https://graph.microsoft.com/Sites.ReadWrite.All",
"https://graph.microsoft.com/OnlineMeetings.Read",
"https://graph.microsoft.com/OnlineMeetings.ReadWrite",
```

Add scope configuration logic for files and recordings in `load_config()`.
