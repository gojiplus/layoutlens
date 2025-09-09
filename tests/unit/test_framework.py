"""Unit tests for the original framework.py module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os

import sys
sys.path.append('.')
from framework import LayoutLens


@pytest.mark.unit
class TestLayoutLens:
    """Test cases for the original LayoutLens class."""
    
    def test_init_with_api_key(self):
        """Test LayoutLens initialization with API key."""
        with patch('framework.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            lens = LayoutLens(api_key="test-key", model="gpt-4o")
            
            assert lens.api_key == "test-key"
            assert lens.model == "gpt-4o"
            mock_openai.assert_called_once_with(api_key="test-key")
    
    def test_init_with_env_api_key(self):
        """Test LayoutLens initialization with environment variable."""
        with patch('framework.OpenAI') as mock_openai, \
             patch.dict(os.environ, {'OPENAI_API_KEY': 'env-test-key'}):
            
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            lens = LayoutLens()
            
            assert lens.api_key is None  # Constructor doesn't set this directly
            mock_openai.assert_called_once_with(api_key='env-test-key')
    
    def test_init_without_api_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OpenAI API key is required"):
                LayoutLens()
    
    def test_init_without_openai_raises_import_error(self):
        """Test that missing OpenAI library raises ImportError."""
        with patch('framework.OpenAI', None):
            with pytest.raises(ImportError, match="openai package is required"):
                LayoutLens(api_key="test-key")
    
    def test_ask_single_image(self):
        """Test ask method with single image."""
        with patch('framework.OpenAI') as mock_openai, \
             patch('builtins.open', create=True) as mock_open:
            
            # Setup mocks
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            mock_response = Mock()
            mock_response.output_text = "The layout looks good."
            mock_client.responses.create.return_value = mock_response
            
            mock_file = Mock()
            mock_file.read.return_value = b"fake_image_data"
            mock_open.return_value.__enter__.return_value = mock_file
            
            # Test
            lens = LayoutLens(api_key="test-key")
            result = lens.ask(["test_image.png"], "Is this layout correct?")
            
            assert result == "The layout looks good."
            mock_open.assert_called_once_with("test_image.png", "rb")
            mock_client.responses.create.assert_called_once()
    
    def test_ask_multiple_images(self):
        """Test ask method with multiple images."""
        with patch('framework.OpenAI') as mock_openai, \
             patch('builtins.open', create=True) as mock_open:
            
            # Setup mocks
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            mock_response = Mock()
            mock_response.output_text = "Both layouts match."
            mock_client.responses.create.return_value = mock_response
            
            mock_file = Mock()
            mock_file.read.return_value = b"fake_image_data"
            mock_open.return_value.__enter__.return_value = mock_file
            
            # Test
            lens = LayoutLens(api_key="test-key")
            result = lens.ask(["image1.png", "image2.png"], "Do these match?")
            
            assert result == "Both layouts match."
            assert mock_open.call_count == 2
            mock_client.responses.create.assert_called_once()
            
            # Check that the content includes both images
            call_args = mock_client.responses.create.call_args
            input_data = call_args[1]['input'][0]['content']
            
            # Should have 1 text input + 2 image inputs
            assert len(input_data) == 3
            assert input_data[0]['type'] == 'input_text'
            assert input_data[1]['type'] == 'input_image'
            assert input_data[2]['type'] == 'input_image'
    
    def test_ask_with_file_error(self):
        """Test ask method when file cannot be read."""
        with patch('framework.OpenAI') as mock_openai, \
             patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            lens = LayoutLens(api_key="test-key")
            
            with pytest.raises(FileNotFoundError):
                lens.ask(["nonexistent.png"], "Test query")
    
    def test_compare_layouts(self):
        """Test compare_layouts convenience method."""
        with patch('framework.OpenAI') as mock_openai, \
             patch('builtins.open', create=True) as mock_open:
            
            # Setup mocks
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            mock_response = Mock()
            mock_response.output_text = "Yes, the layouts look the same."
            mock_client.responses.create.return_value = mock_response
            
            mock_file = Mock()
            mock_file.read.return_value = b"fake_image_data"
            mock_open.return_value.__enter__.return_value = mock_file
            
            # Test
            lens = LayoutLens(api_key="test-key")
            result = lens.compare_layouts("image1.png", "image2.png")
            
            assert result == "Yes, the layouts look the same."
            assert mock_open.call_count == 2
            
            # Check that it uses the correct query
            call_args = mock_client.responses.create.call_args
            input_data = call_args[1]['input'][0]['content']
            assert input_data[0]['text'] == "Do these two layouts look the same?"
    
    def test_ask_strips_whitespace(self):
        """Test that ask method strips whitespace from response."""
        with patch('framework.OpenAI') as mock_openai, \
             patch('builtins.open', create=True) as mock_open:
            
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            mock_response = Mock()
            mock_response.output_text = "  Response with whitespace  \n"
            mock_client.responses.create.return_value = mock_response
            
            mock_file = Mock()
            mock_file.read.return_value = b"fake_image_data"
            mock_open.return_value.__enter__.return_value = mock_file
            
            lens = LayoutLens(api_key="test-key")
            result = lens.ask(["test.png"], "Test")
            
            assert result == "Response with whitespace"
    
    def test_ask_handles_missing_output_text(self):
        """Test ask method when response has no output_text attribute."""
        with patch('framework.OpenAI') as mock_openai, \
             patch('builtins.open', create=True) as mock_open:
            
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            mock_response = Mock(spec=[])  # Mock without output_text attribute
            mock_client.responses.create.return_value = mock_response
            
            mock_file = Mock()
            mock_file.read.return_value = b"fake_image_data"
            mock_open.return_value.__enter__.return_value = mock_file
            
            lens = LayoutLens(api_key="test-key")
            result = lens.ask(["test.png"], "Test")
            
            assert result == ""  # Should return empty string when no output_text