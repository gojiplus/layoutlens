"""Pytest configuration and fixtures for LayoutLens tests."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_html_file(temp_dir):
    """Create a sample HTML file for testing."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Test Page</title>
        <style>
            #main_text { text-align: center; font-weight: bold; }
            .highlight { background-color: #ffff00; }
        </style>
    </head>
    <body>
        <h1 id="main_heading">Test Page</h1>
        <div id="main_text" class="highlight">
            This is a test page for LayoutLens testing.
        </div>
        <button id="test_button">Click Me</button>
    </body>
    </html>
    """

    html_file = temp_dir / "test_page.html"
    html_file.write_text(html_content)
    return str(html_file)


@pytest.fixture
def sample_config_file(temp_dir):
    """Create a sample configuration file."""
    config_data = {
        "llm": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
        },
        "screenshot": {"format": "png", "full_page": True},
        "test": {"auto_generate_queries": True, "parallel_execution": False},
        "output": {"base_dir": "test_output"},
        "viewports": [
            {
                "name": "desktop",
                "width": 1440,
                "height": 900,
                "device_scale_factor": 1.0,
                "is_mobile": False,
                "has_touch": False,
            }
        ],
    }

    import yaml

    config_file = temp_dir / "test_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    return str(config_file)


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock_response = Mock()
    mock_response.output_text = "Yes, the layout appears correct and well-structured."
    return mock_response


@pytest.fixture
def mock_layout_lens(mock_openai_response):
    """Mock LayoutLens instance."""
    mock_lens = Mock()
    mock_lens.ask.return_value = mock_openai_response.output_text
    mock_lens.compare_layouts.return_value = "Yes, the layouts look the same."
    return mock_lens


@pytest.fixture
def mock_playwright_browser():
    """Mock Playwright browser for screenshot testing."""
    mock_browser = Mock()
    mock_page = Mock()
    mock_context = Mock()

    # Setup mock chain
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page
    mock_page.screenshot.return_value = None
    mock_page.goto.return_value = None
    mock_page.wait_for_load_state.return_value = None

    return mock_browser


@pytest.fixture
def sample_test_suite_data():
    """Sample test suite configuration."""
    return {
        "name": "Sample Test Suite",
        "description": "Test suite for unit testing",
        "test_cases": [
            {
                "name": "Homepage Test",
                "html_path": "test_page.html",
                "queries": ["Is the heading visible?", "Is the text centered?"],
                "viewports": ["desktop"],
                "expected_results": {},
                "metadata": {"priority": "high"},
            }
        ],
        "metadata": {"version": "1.0"},
    }


@pytest.fixture
def mock_screenshot_result():
    """Mock screenshot result."""
    return {
        "path": "/mock/screenshot.png",
        "viewport": {"name": "desktop", "width": 1440, "height": 900},
        "timestamp": "1234567890",
        "file_size": 12345,
        "metadata": {},
    }


@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    # Ensure we don't accidentally use real API keys in tests
    original_api_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "test-api-key-do-not-use"

    yield

    # Restore original API key
    if original_api_key:
        os.environ["OPENAI_API_KEY"] = original_api_key
    elif "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]


@pytest.fixture
def mock_dom_elements():
    """Mock DOM elements for query generation testing."""
    return [
        {
            "tag": "h1",
            "id": "main_heading",
            "classes": [],
            "text_content": "Test Page",
            "computed_styles": {"font-size": "24px", "font-weight": "bold"},
        },
        {
            "tag": "div",
            "id": "main_text",
            "classes": ["highlight"],
            "text_content": "This is a test page",
            "computed_styles": {"text-align": "center", "background-color": "#ffff00"},
        },
        {
            "tag": "button",
            "id": "test_button",
            "classes": [],
            "text_content": "Click Me",
            "computed_styles": {"padding": "10px", "border": "1px solid #ccc"},
        },
    ]


# Pytest markers for test categorization
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "requires_api: mark test as requiring API access")
