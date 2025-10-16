#!/usr/bin/env python3
"""
Office365 CLI - Main Entry Point

Unified command-line interface for managing Office365 email, calendar, and contacts.
"""

import sys
import argparse


def main():
    """Main entry point for o365 command"""

    parser = argparse.ArgumentParser(
        prog='o365',
        description='Office365 command-line interface for managing email, calendar, and contacts.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  o365 mail read --unread             # Read unread emails
  o365 calendar list --today          # Show today's calendar
  o365 chat list --with john          # List chats with john
  o365 files list /Documents          # List files in Documents
  o365 recordings list --since "1 week ago"  # List recent recordings
  o365 contacts search john           # Search for a contact
  o365 config set auth.client_id "your-id"   # Set config value
  o365 auth status                    # Check authentication status

For more help on a specific command:
  o365 <command> --help
  o365 <command> <subcommand> --help
"""
    )

    # Create subparsers for main command groups
    subparsers = parser.add_subparsers(dest='command', help='Command groups')

    # Mail commands
    mail_parser = subparsers.add_parser('mail', help='Manage email messages')
    mail_subparsers = mail_parser.add_subparsers(dest='mail_command', help='Mail operations')

    # Calendar commands
    calendar_parser = subparsers.add_parser('calendar', help='Manage calendar events')
    calendar_subparsers = calendar_parser.add_subparsers(dest='calendar_command', help='Calendar operations')

    # Contacts commands
    contacts_parser = subparsers.add_parser('contacts', help='Manage contacts and user directory')
    contacts_subparsers = contacts_parser.add_subparsers(dest='contacts_command', help='Contacts operations')

    # Chat commands
    chat_parser = subparsers.add_parser('chat', help='Manage Teams chats')
    chat_subparsers = chat_parser.add_subparsers(dest='chat_command', help='Chat operations')

    # Files commands
    files_parser = subparsers.add_parser('files', help='Manage OneDrive and SharePoint files')
    files_subparsers = files_parser.add_subparsers(dest='files_command', help='File operations')

    # Recordings commands
    recordings_parser = subparsers.add_parser('recordings', help='Manage Teams meeting recordings')
    recordings_subparsers = recordings_parser.add_subparsers(dest='recordings_command', help='Recording operations')

    # Auth commands
    auth_parser = subparsers.add_parser('auth', help='Manage OAuth2 authentication')
    auth_subparsers = auth_parser.add_subparsers(dest='auth_command', help='Authentication operations')

    # Config commands
    config_parser = subparsers.add_parser('config', help='Manage configuration settings')
    config_subparsers = config_parser.add_subparsers(dest='config_command', help='Configuration operations')

    # Import and setup subcommands (lazy import to avoid loading all modules at startup)
    from . import mail, calendar, contacts, chat, files, recordings, auth, config_cmd

    # Setup each command group's subparsers
    mail.setup_parser(mail_subparsers)
    calendar.setup_parser(calendar_subparsers)
    contacts.setup_parser(contacts_subparsers)
    chat.setup_parser(chat_subparsers)
    files.setup_parser(files_subparsers)
    recordings.setup_parser(recordings_subparsers)
    auth.setup_parser(auth_subparsers)
    config_cmd.setup_parser(config_subparsers)

    # Parse arguments
    args = parser.parse_args()

    # Route to appropriate command handler
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch to command handlers
    if args.command == 'mail':
        if not args.mail_command:
            mail_parser.print_help()
            sys.exit(1)
        mail.handle_command(args)

    elif args.command == 'calendar':
        if not args.calendar_command:
            calendar_parser.print_help()
            sys.exit(1)
        calendar.handle_command(args)

    elif args.command == 'contacts':
        if not args.contacts_command:
            contacts_parser.print_help()
            sys.exit(1)
        contacts.handle_command(args)

    elif args.command == 'chat':
        if not args.chat_command:
            chat_parser.print_help()
            sys.exit(1)
        chat.handle_command(args)

    elif args.command == 'files':
        if not args.files_command:
            files_parser.print_help()
            sys.exit(1)
        files.handle_command(args)

    elif args.command == 'recordings':
        if not args.recordings_command:
            recordings_parser.print_help()
            sys.exit(1)
        recordings.handle_command(args)

    elif args.command == 'auth':
        if not args.auth_command:
            auth_parser.print_help()
            sys.exit(1)
        auth.handle_command(args)

    elif args.command == 'config':
        if not args.config_command:
            config_parser.print_help()
            sys.exit(1)
        config_cmd.handle_command(args)


if __name__ == '__main__':
    main()
