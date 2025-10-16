"""
Tests for o365 config commands
"""

import pytest
from pathlib import Path
from configparser import ConfigParser
from unittest.mock import patch, MagicMock
from o365 import config_cmd


class TestConfigList:
    """Tests for 'o365 config list' command"""

    def test_list_empty_config(self, temp_config_file, capsys):
        """Test listing an empty config file"""
        # Clear the config file
        temp_config_file.write_text("")

        args = MagicMock()
        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            config_cmd.cmd_list(args)

        captured = capsys.readouterr()
        assert "Config file is empty" in captured.out

    def test_list_populated_config(self, temp_config_file, capsys):
        """Test listing a populated config file"""
        args = MagicMock()
        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            config_cmd.cmd_list(args)

        captured = capsys.readouterr()
        assert "[auth]" in captured.out
        assert "client_id = test-client-id" in captured.out
        assert "[scopes]" in captured.out


class TestConfigGet:
    """Tests for 'o365 config get' command"""

    def test_get_existing_value(self, temp_config_file, capsys):
        """Test getting an existing config value"""
        args = MagicMock()
        args.key = 'auth.client_id'

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            config_cmd.cmd_get(args)

        captured = capsys.readouterr()
        assert "test-client-id" in captured.out

    def test_get_nonexistent_section(self, temp_config_file):
        """Test getting a value from non-existent section"""
        args = MagicMock()
        args.key = 'nonexistent.option'

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            with pytest.raises(SystemExit):
                config_cmd.cmd_get(args)

    def test_get_nonexistent_option(self, temp_config_file):
        """Test getting a non-existent option"""
        args = MagicMock()
        args.key = 'auth.nonexistent'

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            with pytest.raises(SystemExit):
                config_cmd.cmd_get(args)

    def test_get_invalid_key_format(self, temp_config_file):
        """Test getting with invalid key format (no dot)"""
        args = MagicMock()
        args.key = 'invalid_key'

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            with pytest.raises(SystemExit):
                config_cmd.cmd_get(args)


class TestConfigSet:
    """Tests for 'o365 config set' command"""

    def test_set_new_value(self, temp_config_file, capsys):
        """Test setting a new config value"""
        args = MagicMock()
        args.key = 'test.newvalue'
        args.value = 'hello'

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            config_cmd.cmd_set(args)

        captured = capsys.readouterr()
        assert "Set test.newvalue = hello" in captured.out

        # Verify it was actually written
        parser = ConfigParser()
        parser.read(temp_config_file)
        assert parser.get('test', 'newvalue') == 'hello'

    def test_set_existing_value(self, temp_config_file, capsys):
        """Test overwriting an existing config value"""
        args = MagicMock()
        args.key = 'auth.client_id'
        args.value = 'new-client-id'

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            config_cmd.cmd_set(args)

        captured = capsys.readouterr()
        assert "Set auth.client_id = new-client-id" in captured.out

        # Verify it was updated
        parser = ConfigParser()
        parser.read(temp_config_file)
        assert parser.get('auth', 'client_id') == 'new-client-id'

    def test_set_creates_section(self, temp_config_file):
        """Test that set creates section if it doesn't exist"""
        args = MagicMock()
        args.key = 'newsection.option'
        args.value = 'value'

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            config_cmd.cmd_set(args)

        parser = ConfigParser()
        parser.read(temp_config_file)
        assert parser.has_section('newsection')
        assert parser.get('newsection', 'option') == 'value'


class TestConfigUnset:
    """Tests for 'o365 config unset' command"""

    def test_unset_existing_value(self, temp_config_file, capsys):
        """Test unsetting an existing value"""
        args = MagicMock()
        args.key = 'auth.client_id'

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            config_cmd.cmd_unset(args)

        captured = capsys.readouterr()
        assert "Unset auth.client_id" in captured.out

        # Verify it was removed
        parser = ConfigParser()
        parser.read(temp_config_file)
        assert not parser.has_option('auth', 'client_id')

    def test_unset_removes_empty_section(self, temp_config_file):
        """Test that unset removes section if it becomes empty"""
        # Create a section with only one option
        parser = ConfigParser()
        parser.read(temp_config_file)
        parser.add_section('temp')
        parser.set('temp', 'only_option', 'value')
        with open(temp_config_file, 'w') as f:
            parser.write(f)

        args = MagicMock()
        args.key = 'temp.only_option'

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            config_cmd.cmd_unset(args)

        # Verify section was removed
        parser = ConfigParser()
        parser.read(temp_config_file)
        assert not parser.has_section('temp')

    def test_unset_nonexistent_option(self, temp_config_file):
        """Test unsetting a non-existent option"""
        args = MagicMock()
        args.key = 'auth.nonexistent'

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            with pytest.raises(SystemExit):
                config_cmd.cmd_unset(args)


class TestConfigPath:
    """Tests for 'o365 config path' command"""

    def test_path(self, temp_config_file, capsys):
        """Test showing config file path"""
        args = MagicMock()

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            config_cmd.cmd_path(args)

        captured = capsys.readouterr()
        assert str(temp_config_file) in captured.out


class TestConfigEdit:
    """Tests for 'o365 config edit' command"""

    def test_edit_with_editor(self, temp_config_file, monkeypatch):
        """Test opening config in editor"""
        mock_subprocess = MagicMock()
        monkeypatch.setattr('o365.config_cmd.subprocess', mock_subprocess)
        monkeypatch.setenv('EDITOR', 'vim')

        args = MagicMock()

        with patch('o365.config_cmd.CONFIG_FILE', temp_config_file):
            config_cmd.cmd_edit(args)

        # Verify subprocess.run was called with correct editor
        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args[0][0]
        assert call_args[0] == 'vim'
        assert str(temp_config_file) in call_args

    def test_edit_creates_file_if_not_exists(self, temp_config_dir, monkeypatch):
        """Test that edit creates config file if it doesn't exist"""
        nonexistent_file = temp_config_dir / "nonexistent_config"
        mock_subprocess = MagicMock()
        monkeypatch.setattr('o365.config_cmd.subprocess', mock_subprocess)
        monkeypatch.setenv('EDITOR', 'vi')

        args = MagicMock()

        with patch('o365.config_cmd.CONFIG_FILE', nonexistent_file):
            config_cmd.cmd_edit(args)

        # Verify file was created
        assert nonexistent_file.exists()


class TestParseKey:
    """Tests for parse_key helper function"""

    def test_parse_valid_key(self):
        """Test parsing valid key with dot notation"""
        section, option = config_cmd.parse_key('auth.client_id')
        assert section == 'auth'
        assert option == 'client_id'

    def test_parse_key_with_multiple_dots(self):
        """Test parsing key with multiple dots"""
        section, option = config_cmd.parse_key('scopes.files.all')
        assert section == 'scopes'
        assert option == 'files.all'

    def test_parse_invalid_key_no_dot(self):
        """Test parsing invalid key without dot"""
        with pytest.raises(SystemExit):
            config_cmd.parse_key('invalid')
