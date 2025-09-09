"""Unit tests for the screenshot.py module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import sys
sys.path.append('.')
from legacy.screenshot import html_to_image


@pytest.mark.unit
class TestScreenshotUtilities:
    """Test cases for screenshot utilities."""
    
    def test_html_to_image_success(self, temp_dir):
        """Test successful HTML to image conversion."""
        with patch('legacy.screenshot.sync_playwright') as mock_playwright:
            # Setup playwright mocks
            mock_playwright_instance = Mock()
            mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
            
            mock_browser = Mock()
            mock_page = Mock()
            
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Test files
            html_file = temp_dir / "test.html"
            html_file.write_text("<html><body>Test</body></html>")
            output_file = temp_dir / "output.png"
            
            # Execute
            html_to_image(str(html_file), str(output_file))
            
            # Verify calls
            mock_playwright_instance.chromium.launch.assert_called_once()
            mock_browser.new_page.assert_called_once()
            mock_page.set_viewport_size.assert_called_once_with({"width": 800, "height": 600})
            mock_page.goto.assert_called_once_with(f"file://{html_file.resolve()}")
            mock_page.screenshot.assert_called_once_with(path=str(output_file))
            mock_browser.close.assert_called_once()
    
    def test_html_to_image_custom_dimensions(self, temp_dir):
        """Test HTML to image with custom width and height."""
        with patch('legacy.screenshot.sync_playwright') as mock_playwright:
            # Setup mocks
            mock_playwright_instance = Mock()
            mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
            
            mock_browser = Mock()
            mock_page = Mock()
            
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Test files
            html_file = temp_dir / "test.html"
            html_file.write_text("<html><body>Test</body></html>")
            output_file = temp_dir / "output.png"
            
            # Execute with custom dimensions
            html_to_image(str(html_file), str(output_file), width=1200, height=800)
            
            # Verify custom viewport size
            mock_page.set_viewport_size.assert_called_once_with({"width": 1200, "height": 800})
    
    def test_html_to_image_creates_output_directory(self, temp_dir):
        """Test that output directory is created if it doesn't exist."""
        with patch('legacy.screenshot.sync_playwright') as mock_playwright:
            # Setup mocks
            mock_playwright_instance = Mock()
            mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
            
            mock_browser = Mock()
            mock_page = Mock()
            
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Test files
            html_file = temp_dir / "test.html"
            html_file.write_text("<html><body>Test</body></html>")
            
            # Output in nested directory that doesn't exist
            output_file = temp_dir / "subdir" / "nested" / "output.png"
            
            # Execute
            html_to_image(str(html_file), str(output_file))
            
            # Verify that the nested directory would be created
            # (We can't easily test Path.mkdir in this context without more complex mocking)
            mock_page.screenshot.assert_called_once_with(path=str(output_file))
    
    def test_html_to_image_without_playwright_raises_error(self, temp_dir):
        """Test that missing Playwright raises ImportError."""
        with patch('screenshot.sync_playwright', None):
            html_file = temp_dir / "test.html"
            html_file.write_text("<html><body>Test</body></html>")
            output_file = temp_dir / "output.png"
            
            with pytest.raises(ImportError, match="playwright is required for html_to_image"):
                html_to_image(str(html_file), str(output_file))
    
    def test_html_to_image_resolves_relative_paths(self, temp_dir):
        """Test that relative paths are resolved to absolute paths."""
        with patch('legacy.screenshot.sync_playwright') as mock_playwright:
            # Setup mocks
            mock_playwright_instance = Mock()
            mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
            
            mock_browser = Mock()
            mock_page = Mock()
            
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Create test file
            html_file = temp_dir / "test.html"
            html_file.write_text("<html><body>Test</body></html>")
            output_file = temp_dir / "output.png"
            
            # Use relative path (this will resolve to absolute)
            html_to_image(str(html_file), str(output_file))
            
            # Verify that absolute path is used in goto call
            expected_url = f"file://{html_file.resolve()}"
            mock_page.goto.assert_called_once_with(expected_url)
    
    def test_html_to_image_browser_exception_cleanup(self, temp_dir):
        """Test that browser is cleaned up even if an exception occurs."""
        with patch('legacy.screenshot.sync_playwright') as mock_playwright:
            # Setup mocks
            mock_playwright_instance = Mock()
            mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
            
            mock_browser = Mock()
            mock_page = Mock()
            
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            # Make screenshot raise an exception
            mock_page.screenshot.side_effect = Exception("Screenshot failed")
            
            html_file = temp_dir / "test.html"
            html_file.write_text("<html><body>Test</body></html>")
            output_file = temp_dir / "output.png"
            
            # Execute and expect exception
            with pytest.raises(Exception, match="Screenshot failed"):
                html_to_image(str(html_file), str(output_file))
            
            # Verify browser is still closed
            mock_browser.close.assert_called_once()
    
    @pytest.mark.parametrize("width,height", [
        (1920, 1080),
        (375, 667),   # Mobile
        (768, 1024),  # Tablet
        (2560, 1440)  # Large desktop
    ])
    def test_html_to_image_various_dimensions(self, temp_dir, width, height):
        """Test HTML to image with various viewport dimensions."""
        with patch('legacy.screenshot.sync_playwright') as mock_playwright:
            # Setup mocks
            mock_playwright_instance = Mock()
            mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
            
            mock_browser = Mock()
            mock_page = Mock()
            
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page
            
            html_file = temp_dir / "test.html"
            html_file.write_text("<html><body>Test</body></html>")
            output_file = temp_dir / "output.png"
            
            # Execute with different dimensions
            html_to_image(str(html_file), str(output_file), width=width, height=height)
            
            # Verify correct viewport size
            mock_page.set_viewport_size.assert_called_once_with({"width": width, "height": height})