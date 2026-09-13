"""Pytest configuration and fixtures for LayoutLens tests."""

import os
import tempfile
from pathlib import Path

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


@pytest.fixture(autouse=True)
def _test_env():
    """Guard against tests accidentally using a real API key."""
    original_api_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "test-api-key-do-not-use"

    yield

    if original_api_key:
        os.environ["OPENAI_API_KEY"] = original_api_key
    elif "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]


@pytest.fixture
def render_state():
    """A browser-free render state with complete empty detector evidence."""
    from io import BytesIO

    from PIL import Image

    from layoutlens.layout import LayoutScorer
    from layoutlens.regression.models import (
        CaptureEnvironment,
        LayoutGraph,
        RenderState,
    )

    image = BytesIO()
    Image.new("RGB", (10, 10), "white").save(image, format="PNG")
    return RenderState(
        screenshot=image.getvalue(),
        source="fixture.html",
        environment=CaptureEnvironment(
            browser_version="fixture",
            viewport=(1280, 720),
            dpr=1,
            user_agent="fixture",
            platform="test",
            locale="en-US",
            timezone="UTC",
        ),
        graph=LayoutGraph(),
        detector_config=vars(LayoutScorer(probe_focus=False)),
        detector_evidence={
            key: []
            for key in (
                "contrast",
                "overlaps",
                "clipping",
                "protrusion",
                "page_overflow",
                "truncation",
                "small_targets",
                "text_occlusion",
                "focus_obscured",
            )
        },
    )
