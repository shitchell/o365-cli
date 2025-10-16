"""
Config management commands for Office365 CLI

Manage configuration file settings.
"""

import sys
from pathlib import Path
from configparser import ConfigParser
from .common import CONFIG_FILE, CONFIG_DIR


def ensure_config_exists():
    """Ensure config file exists, create if needed"""
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.touch()
        CONFIG_FILE.chmod(0o600)
    return CONFIG_FILE


def load_config_parser():
    """Load config file as ConfigParser"""
    ensure_config_exists()
    parser = ConfigParser()
    parser.read(CONFIG_FILE)
    return parser


def save_config_parser(parser):
    """Save ConfigParser to config file"""
    ensure_config_exists()
    with open(CONFIG_FILE, 'w') as f:
        parser.write(f)
    CONFIG_FILE.chmod(0o600)


def parse_key(key):
    """Parse key into section and option (e.g., 'auth.client_id' -> ('auth', 'client_id'))"""
    if '.' not in key:
        print(f"Error: Key must be in format 'section.option' (e.g., 'auth.client_id')", file=sys.stderr)
        sys.exit(1)

    parts = key.split('.', 1)
    return parts[0], parts[1]


# Command handlers

def cmd_list(args):
    """Handle 'o365 config list' command"""
    parser = load_config_parser()

    if not parser.sections():
        print("Config file is empty. Use 'o365 config set' to add values.")
        return

    print(f"\nConfiguration ({CONFIG_FILE}):\n")

    for section in parser.sections():
        print(f"[{section}]")
        for option in parser.options(section):
            value = parser.get(section, option)
            print(f"  {option} = {value}")
        print()


def cmd_get(args):
    """Handle 'o365 config get' command"""
    parser = load_config_parser()
    section, option = parse_key(args.key)

    if not parser.has_section(section):
        print(f"Error: Section [{section}] not found in config", file=sys.stderr)
        sys.exit(1)

    if not parser.has_option(section, option):
        print(f"Error: Option '{option}' not found in section [{section}]", file=sys.stderr)
        sys.exit(1)

    value = parser.get(section, option)
    print(value)


def cmd_set(args):
    """Handle 'o365 config set' command"""
    parser = load_config_parser()
    section, option = parse_key(args.key)

    # Create section if it doesn't exist
    if not parser.has_section(section):
        parser.add_section(section)

    # Set the value
    parser.set(section, option, args.value)
    save_config_parser(parser)

    print(f"Set {section}.{option} = {args.value}")


def cmd_unset(args):
    """Handle 'o365 config unset' command"""
    parser = load_config_parser()
    section, option = parse_key(args.key)

    if not parser.has_section(section):
        print(f"Error: Section [{section}] not found in config", file=sys.stderr)
        sys.exit(1)

    if not parser.has_option(section, option):
        print(f"Error: Option '{option}' not found in section [{section}]", file=sys.stderr)
        sys.exit(1)

    parser.remove_option(section, option)

    # Remove section if empty
    if not parser.options(section):
        parser.remove_section(section)

    save_config_parser(parser)
    print(f"Unset {section}.{option}")


def cmd_edit(args):
    """Handle 'o365 config edit' command"""
    import subprocess
    import os

    ensure_config_exists()

    # Get editor from environment or default to vi
    editor = os.environ.get('EDITOR', os.environ.get('VISUAL', 'vi'))

    try:
        subprocess.run([editor, str(CONFIG_FILE)], check=True)
        print(f"Config file edited successfully")
    except subprocess.CalledProcessError:
        print(f"Error: Failed to open editor", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Editor '{editor}' not found. Set $EDITOR environment variable.", file=sys.stderr)
        sys.exit(1)


def cmd_path(args):
    """Handle 'o365 config path' command"""
    print(CONFIG_FILE)


# Setup and routing

def setup_parser(subparsers):
    """Setup argparse subcommands for config"""

    # o365 config list
    list_parser = subparsers.add_parser(
        'list',
        help='List all configuration values',
        description='Display all configuration values from the config file.'
    )
    list_parser.set_defaults(func=cmd_list)

    # o365 config get
    get_parser = subparsers.add_parser(
        'get',
        help='Get a configuration value',
        description='Get a specific configuration value.',
        epilog="""
Examples:
  o365 config get auth.client_id
  o365 config get scopes.mail
  o365 config get paths.token_file
"""
    )
    get_parser.add_argument('key', help='Config key in format section.option (e.g., auth.client_id)')
    get_parser.set_defaults(func=cmd_get)

    # o365 config set
    set_parser = subparsers.add_parser(
        'set',
        help='Set a configuration value',
        description='Set a configuration value in the config file.',
        epilog="""
Examples:
  o365 config set auth.client_id "your-client-id"
  o365 config set auth.tenant "common"
  o365 config set scopes.mail "true"
  o365 config set paths.token_file "~/.config/o365/tokens.json"
"""
    )
    set_parser.add_argument('key', help='Config key in format section.option (e.g., auth.client_id)')
    set_parser.add_argument('value', help='Value to set')
    set_parser.set_defaults(func=cmd_set)

    # o365 config unset
    unset_parser = subparsers.add_parser(
        'unset',
        help='Remove a configuration value',
        description='Remove a configuration value from the config file.',
        epilog="""
Examples:
  o365 config unset auth.client_id
  o365 config unset scopes.custom
"""
    )
    unset_parser.add_argument('key', help='Config key in format section.option (e.g., auth.client_id)')
    unset_parser.set_defaults(func=cmd_unset)

    # o365 config edit
    edit_parser = subparsers.add_parser(
        'edit',
        help='Edit configuration file in editor',
        description='Open the configuration file in your default editor ($EDITOR or $VISUAL).'
    )
    edit_parser.set_defaults(func=cmd_edit)

    # o365 config path
    path_parser = subparsers.add_parser(
        'path',
        help='Show configuration file path',
        description='Display the path to the configuration file.'
    )
    path_parser.set_defaults(func=cmd_path)


def handle_command(args):
    """Route to appropriate config subcommand"""
    if hasattr(args, 'func'):
        args.func(args)
    else:
        print("Error: No config subcommand specified", file=sys.stderr)
        sys.exit(1)
