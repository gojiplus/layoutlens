"""Test cases for CLI functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from layoutlens.cli import create_parser
from layoutlens.cli_commands import cmd_generate, cmd_info, cmd_validate


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "name": "Test Suite",
        "description": "Test suite for CLI testing",
        "test_cases": [
            {
                "name": "Sample Test",
                "html_path": "test.html",
                "queries": ["Is this accessible?"],
                "viewports": ["desktop"],
            }
        ],
    }


@pytest.fixture
def temp_suite_file(sample_config):
    """Create a temporary test suite file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(sample_config, f)
        yield f.name
    Path(f.name).unlink()


class TestCLIParser:
    """Test CLI argument parser."""

    def test_parser_creation(self):
        """Test parser is created correctly."""
        parser = create_parser()
        assert parser is not None
        assert "LayoutLens" in parser.description

    def test_test_command_parsing(self):
        """Test parsing of test command."""
        parser = create_parser()

        # Test with page
        args = parser.parse_args(["test", "--page", "test.html"])
        assert args.command == "test"
        assert args.page == "test.html"
        assert args.suite is None

        # Test with suite
        args = parser.parse_args(["test", "--suite", "suite.yaml"])
        assert args.command == "test"
        assert args.suite == "suite.yaml"
        assert args.page is None

    def test_compare_command_parsing(self):
        """Test parsing of compare command."""
        parser = create_parser()
        args = parser.parse_args(["compare", "page1.html", "page2.html"])

        assert args.command == "compare"
        assert args.page_a == "page1.html"
        assert args.page_b == "page2.html"
        assert args.query == "Which page has a better layout design?"

    def test_batch_command_parsing(self):
        """Test parsing of batch command."""
        parser = create_parser()
        args = parser.parse_args(["batch", "--sources", "page1.html,page2.html"])

        assert args.command == "batch"
        assert args.sources == "page1.html,page2.html"

    def test_global_options(self):
        """Test global CLI options."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "--verbose",
                "--api-key",
                "test-key",
                "--provider",
                "openai",
                "--model",
                "gpt-4",
                "--max-concurrent",
                "5",
                "info",
            ]
        )

        assert args.verbose is True
        assert args.api_key == "test-key"
        assert args.provider == "openai"
        assert args.model == "gpt-4"
        assert args.max_concurrent == 5


class TestCLICommands:
    """Test CLI command implementations."""

    def test_cmd_generate_config(self):
        """Test generate config command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = str(Path(temp_dir) / "test_config.yaml")

            args = MagicMock()
            args.type = "config"
            args.output = config_path

            cmd_generate(args)

            assert Path(config_path).exists()

    def test_cmd_generate_suite(self):
        """Test generate suite command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            suite_path = str(Path(temp_dir) / "test_suite.yaml")

            args = MagicMock()
            args.type = "suite"
            args.output = suite_path

            cmd_generate(args)

            assert Path(suite_path).exists()

            # Verify content
            with open(suite_path) as f:
                data = yaml.safe_load(f)
                assert "name" in data
                assert "test_cases" in data

    def test_cmd_generate_unknown_type(self):
        """Test generate with unknown type."""
        args = MagicMock()
        args.type = "unknown"

        with pytest.raises(SystemExit):
            cmd_generate(args)

    def test_cmd_info(self):
        """Test info command."""
        args = MagicMock()

        with patch("layoutlens.cli_commands.LayoutLens") as mock_lens:
            mock_lens.return_value = MagicMock()
            cmd_info(args)

    def test_cmd_validate_suite(self, temp_suite_file):
        """Test validate suite command."""
        args = MagicMock()
        args.config = None
        args.suite = temp_suite_file

        cmd_validate(args)  # Should not raise exception

    def test_cmd_validate_invalid_suite(self):
        """Test validate with invalid suite."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Write invalid YAML structure
            yaml.dump({"invalid": "structure"}, f)
            invalid_suite = f.name

        args = MagicMock()
        args.config = None
        args.suite = invalid_suite

        with pytest.raises(SystemExit):
            cmd_validate(args)

        Path(invalid_suite).unlink()

    def test_cmd_validate_missing_file(self):
        """Test validate with missing file."""
        args = MagicMock()
        args.config = None
        args.suite = "nonexistent.yaml"

        with pytest.raises(SystemExit):
            cmd_validate(args)

    def test_cmd_validate_no_args(self):
        """Test validate with no config or suite specified."""
        args = MagicMock()
        args.config = None
        args.suite = None

        with pytest.raises(SystemExit):
            cmd_validate(args)


class TestCLIStructure:
    """Test CLI module structure and imports."""

    def test_cli_imports(self):
        """Test that CLI modules can be imported successfully."""
        from layoutlens import cli, cli_commands, cli_interactive

        assert cli is not None
        assert cli_commands is not None
        assert cli_interactive is not None

    def test_parser_has_all_commands(self):
        """Test that parser includes all expected commands."""
        parser = create_parser()

        # Get subparser actions by checking for _SubParsersAction type
        subparsers_actions = [
            action for action in parser._actions if hasattr(action, "choices") and action.dest == "command"
        ]

        # Should have one subparser
        assert len(subparsers_actions) == 1

        # Get available commands
        subparsers = subparsers_actions[0]
        commands = list(subparsers.choices.keys())

        expected_commands = ["test", "compare", "batch", "generate", "info", "interactive", "validate"]
        for cmd in expected_commands:
            assert cmd in commands

    def test_entry_point_exists(self):
        """Test that the main entry point is callable."""
        from layoutlens.cli import main

        assert callable(main)


if __name__ == "__main__":
    pytest.main([__file__])
