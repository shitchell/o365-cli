"""
Mail management commands for Office365

Sync, read, archive, mark read, and send emails.
"""

import sys
import subprocess
from pathlib import Path

# For now, some commands are implemented by calling existing scripts
# Later we can refactor these into pure Python if needed

# Mail storage location
MAILDIR_BASE = Path.home() / ".mail" / "office365"


def cmd_sync(args):
    """Handle 'o365 mail sync' command - calls o365-mail-sync.py"""
    cmd = [str(Path.home() / "bin" / "o365-mail-sync.py")]

    # Pass through all arguments
    if args.folders:
        cmd.extend(['--folders'] + args.folders)
    if args.count:
        cmd.extend(['--count', str(args.count)])
    if args.since:
        cmd.extend(['--since', args.since])
    if args.all:
        cmd.append('--all')
    if args.focused_inbox:
        cmd.append('--focused-inbox')
    if args.list_folders:
        cmd.append('--list-folders')

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: o365-mail-sync.py not found", file=sys.stderr)
        sys.exit(1)


def cmd_read(args):
    """Handle 'o365 mail read' command - calls mail-read"""
    cmd = [str(Path.home() / "bin" / "mail-read")]

    # Pass through all arguments
    if args.ids:
        cmd.extend(args.ids)
    if args.count:
        cmd.extend(['-n', str(args.count)])
    if args.folder:
        cmd.extend(['-f', args.folder])
    if args.read_email:
        cmd.extend(['-r', str(args.read_email)])
    if args.search:
        cmd.extend(['-s', args.search])
    if args.field:
        cmd.extend(['--field', args.field])
    if args.since:
        cmd.extend(['--since', args.since])
    if args.unread:
        cmd.append('--unread')
    if args.read:
        cmd.append('--read')
    if args.html:
        cmd.append('--html')

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: mail-read not found", file=sys.stderr)
        sys.exit(1)


def cmd_archive(args):
    """Handle 'o365 mail archive' command - calls mail-archive"""
    cmd = [str(Path.home() / "bin" / "mail-archive")]

    # Pass through all arguments
    if args.dry_run:
        cmd.append('--dry-run')
    cmd.extend(args.ids)

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: mail-archive not found", file=sys.stderr)
        sys.exit(1)


def cmd_mark_read(args):
    """Handle 'o365 mail mark-read' command - calls mail-mark-read"""
    cmd = [str(Path.home() / "bin" / "mail-mark-read")]

    # Pass through all arguments
    if args.dry_run:
        cmd.append('--dry-run')
    cmd.extend(args.ids)

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: mail-mark-read not found", file=sys.stderr)
        sys.exit(1)


def cmd_send(args):
    """Handle 'o365 mail send' command - calls trinoor.email module"""
    cmd = ['python', '-m', 'trinoor.email']

    # Pass through all arguments from sys.argv
    # We need to find where 'send' starts and pass everything after it
    import sys as sys_module
    try:
        send_idx = sys_module.argv.index('send')
        cmd.extend(sys_module.argv[send_idx + 1:])
    except ValueError:
        # Fallback: just run without args to show help
        pass

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: trinoor.email module not found", file=sys.stderr)
        print("Make sure the trinoor package is installed", file=sys.stderr)
        sys.exit(1)


# Setup and routing

def setup_parser(subparsers):
    """Setup argparse subcommands for mail"""

    # o365 mail sync
    sync_parser = subparsers.add_parser(
        'sync',
        help='Sync emails from Office365 to local Maildir',
        description='Sync emails from Office365 to local Maildir format.',
        epilog="""
Examples:
  o365 mail sync                              # Sync default folders
  o365 mail sync --folders Inbox --count 50   # Sync last 50 from Inbox
  o365 mail sync --all                        # Sync all folders
"""
    )
    sync_parser.add_argument('--folders', nargs='+', metavar='FOLDER',
                            help='Sync specific folders (e.g., Inbox SentItems Drafts)')
    sync_parser.add_argument('--count', type=int, metavar='N',
                            help='Maximum number of messages to fetch per folder')
    sync_parser.add_argument('--since', type=str, metavar='DATE',
                            help='Sync messages since date (ISO 8601 format)')
    sync_parser.add_argument('--all', action='store_true',
                            help='Sync all available folders')
    sync_parser.add_argument('--focused-inbox', action='store_true',
                            help='Split Inbox into INBOX.Focused and INBOX.Other')
    sync_parser.add_argument('--list-folders', action='store_true',
                            help='List all available mail folders')
    sync_parser.set_defaults(func=cmd_sync)

    # o365 mail read
    read_parser = subparsers.add_parser(
        'read',
        help='List and read emails from local Maildir',
        description='List and read emails from local Maildir.',
        epilog="""
Examples:
  o365 mail read                          # List 10 most recent emails
  o365 mail read --unread                 # Show only unread emails
  o365 mail read --since "2 days ago"     # Show emails from last 2 days
  o365 mail read -r 3                     # Read email #3 from list
  o365 mail read 48608adc f1486a8d        # Read emails by ID
  o365 mail read -s "payment"             # Search for "payment" in subject
"""
    )
    read_parser.add_argument('ids', nargs='*', metavar='ID',
                            help='Email IDs to read (8-character hex strings)')
    read_parser.add_argument('-n', '--count', type=int, metavar='N',
                            help='Number of emails to list (default: 10)')
    read_parser.add_argument('-f', '--folder', type=str, metavar='FOLDER',
                            help='Folder to read from (default: INBOX)')
    read_parser.add_argument('-r', '--read-email', type=int, metavar='N',
                            help='Read email number N from the list')
    read_parser.add_argument('-s', '--search', type=str, metavar='PATTERN',
                            help='Search emails by pattern (regex)')
    read_parser.add_argument('--field', type=str, choices=['subject', 'from', 'to'],
                            help='Field to search in (default: subject)')
    read_parser.add_argument('--since', type=str, metavar='EXPR',
                            help='Only show emails since this time (git-style format)')
    read_parser.add_argument('--unread', action='store_true',
                            help='Show only unread emails')
    read_parser.add_argument('--read', action='store_true',
                            help='Show only read emails')
    read_parser.add_argument('--html', action='store_true',
                            help='Display HTML content as-is (default: convert to text)')
    read_parser.set_defaults(func=cmd_read)

    # o365 mail archive
    archive_parser = subparsers.add_parser(
        'archive',
        help='Archive emails to Archive folder',
        description='Archive emails from Inbox to Archive folder (both locally and on server).',
        epilog="""
Examples:
  o365 mail archive 60d1969a                    # Archive single email
  o365 mail archive 60d1969a 4ab19245 8be667d8  # Archive multiple emails
  o365 mail archive --dry-run 60d1969a          # Preview without archiving
"""
    )
    archive_parser.add_argument('ids', nargs='+', metavar='ID',
                               help='One or more email IDs (8-character hex strings)')
    archive_parser.add_argument('--dry-run', action='store_true',
                               help='Show what would be archived without actually doing it')
    archive_parser.set_defaults(func=cmd_archive)

    # o365 mail mark-read
    mark_read_parser = subparsers.add_parser(
        'mark-read',
        help='Mark emails as read',
        description='Mark emails as read (both locally and on server).',
        epilog="""
Examples:
  o365 mail mark-read f1486a8d                      # Mark single email as read
  o365 mail mark-read f1486a8d 0bc59901 01c77910    # Mark multiple emails
  o365 mail mark-read --dry-run f1486a8d            # Preview without marking
"""
    )
    mark_read_parser.add_argument('ids', nargs='+', metavar='ID',
                                 help='One or more email IDs (8-character hex strings)')
    mark_read_parser.add_argument('--dry-run', action='store_true',
                                 help='Show what would be marked without actually doing it')
    mark_read_parser.set_defaults(func=cmd_mark_read)

    # o365 mail send
    send_parser = subparsers.add_parser(
        'send',
        help='Send email via SMTP',
        description='Send emails via SMTP with automatic signature support. '
                   'This is a wrapper around the trinoor.email module.',
        epilog="""
Examples:
  echo "<p>Hello!</p>" | o365 mail send -r user@example.com -S "Subject" -H -
  o365 mail send -r user@example.com -S "Report" -H - -A report.pdf < msg.html
  o365 mail send -r user1@example.com -r user2@example.com -S "Update" -H - < msg.html

For full options, see: python -m trinoor.email --help
"""
    )
    # Note: We're not adding arguments here because we pass everything through to trinoor.email
    # This allows trinoor.email to handle its own argument parsing
    send_parser.set_defaults(func=cmd_send)


def handle_command(args):
    """Route to appropriate mail subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No mail subcommand specified", file=sys.stderr)
        sys.exit(1)
