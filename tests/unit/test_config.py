"""Unit tests for the layoutlens.config module."""

import pytest
import os
import tempfile
from unittest.mock import patch
from pathlib import Path

import sys
sys.path.append('.')
from layoutlens.config import Config, ViewportConfig, LLMConfig, create_default_config


@pytest.mark.unit
class TestViewportConfig:
    """Test cases for ViewportConfig dataclass."""
    
    def test_viewport_config_creation(self):
        """Test ViewportConfig creation with all parameters."""
        viewport = ViewportConfig(
            name="test_mobile",
            width=375,
            height=667,
            device_scale_factor=2.0,
            is_mobile=True,
            has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
        )
        
        assert viewport.name == "test_mobile"
        assert viewport.width == 375
        assert viewport.height == 667
        assert viewport.device_scale_factor == 2.0
        assert viewport.is_mobile is True
        assert viewport.has_touch is True
        assert "iPhone" in viewport.user_agent
    
    def test_viewport_config_defaults(self):
        """Test ViewportConfig with default values."""
        viewport = ViewportConfig(name="desktop", width=1440, height=900)
        
        assert viewport.name == "desktop"
        assert viewport.width == 1440
        assert viewport.height == 900
        assert viewport.device_scale_factor == 1.0
        assert viewport.is_mobile is False
        assert viewport.has_touch is False
        assert viewport.user_agent is None


@pytest.mark.unit
class TestLLMConfig:
    """Test cases for LLMConfig dataclass."""
    
    def test_llm_config_defaults(self):
        """Test LLMConfig default values."""
        config = LLMConfig()
        
        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert config.api_key is None
        assert config.api_key_env == "OPENAI_API_KEY"
        assert config.max_retries == 3
        assert config.timeout == 60
        assert config.temperature == 0.1
        assert config.custom_params == {}
    
    def test_llm_config_custom_values(self):
        """Test LLMConfig with custom values."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3",
            api_key="test-key",
            max_retries=5,
            temperature=0.5,
            custom_params={"top_p": 0.9}
        )
        
        assert config.provider == "anthropic"
        assert config.model == "claude-3"
        assert config.api_key == "test-key"
        assert config.max_retries == 5
        assert config.temperature == 0.5
        assert config.custom_params == {"top_p": 0.9}


@pytest.mark.unit
class TestConfig:
    """Test cases for the main Config class."""
    
    def test_config_initialization_defaults(self):
        """Test Config initialization with default values."""
        config = Config()
        
        # Check LLM defaults
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o-mini"
        
        # Check screenshot defaults
        assert config.screenshot.format == "png"
        assert config.screenshot.full_page is True
        
        # Check test defaults
        assert config.test.auto_generate_queries is True
        assert "typography" in config.test.focus_areas
        
        # Check output defaults
        assert config.output.base_dir == "layoutlens_output"
        assert config.output.format == "json"
        
        # Check default viewports
        assert len(config.viewports) == 4
        viewport_names = [vp.name for vp in config.viewports]
        assert "mobile_portrait" in viewport_names
        assert "desktop" in viewport_names
    
    def test_config_load_from_yaml_file(self, temp_dir):
        """Test loading configuration from YAML file."""
        # Create test YAML file
        yaml_content = """
llm:
  provider: "anthropic"
  model: "claude-3"
  temperature: 0.2

screenshot:
  format: "jpeg"
  quality: 95
  full_page: false

test:
  parallel_execution: true
  max_workers: 8

viewports:
  - name: "custom_mobile"
    width: 390
    height: 844
    is_mobile: true
    has_touch: true
        """
        
        config_file = temp_dir / "test_config.yaml"
        config_file.write_text(yaml_content)
        
        # Load configuration
        config = Config(str(config_file))
        
        # Verify loaded values
        assert config.llm.provider == "anthropic"
        assert config.llm.model == "claude-3"
        assert config.llm.temperature == 0.2
        
        assert config.screenshot.format == "jpeg"
        assert config.screenshot.quality == 95
        assert config.screenshot.full_page is False
        
        assert config.test.parallel_execution is True
        assert config.test.max_workers == 8
        
        # Check custom viewport
        assert len(config.viewports) == 1
        assert config.viewports[0].name == "custom_mobile"
        assert config.viewports[0].width == 390
        assert config.viewports[0].is_mobile is True
    
    def test_config_load_from_nonexistent_file(self):
        """Test loading from non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            Config("nonexistent_config.yaml")
    
    def test_config_load_from_env_variables(self):
        """Test configuration override from environment variables."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'env-api-key',
            'LAYOUTLENS_MODEL': 'gpt-4o',
            'LAYOUTLENS_OUTPUT_DIR': '/custom/output',
            'LAYOUTLENS_PARALLEL': 'true'
        }):
            config = Config()
            
            assert config.llm.api_key == 'env-api-key'
            assert config.llm.model == 'gpt-4o'
            assert config.output.base_dir == '/custom/output'
            assert config.test.parallel_execution is True
    
    def test_config_save_to_file(self, temp_dir):
        """Test saving configuration to YAML file."""
        config = Config()
        config.llm.model = "gpt-4o"
        config.test.max_workers = 6
        
        output_file = temp_dir / "saved_config.yaml"
        config.save_to_file(str(output_file))
        
        assert output_file.exists()
        
        # Load saved config to verify
        loaded_config = Config(str(output_file))
        assert loaded_config.llm.model == "gpt-4o"
        assert loaded_config.test.max_workers == 6
    
    def test_config_get_output_path(self):
        """Test get_output_path method."""
        config = Config()
        config.output.base_dir = "/test/output"
        
        screenshots_path = config.get_output_path("screenshots")
        results_path = config.get_output_path("results")
        custom_path = config.get_output_path("custom")
        
        assert str(screenshots_path) == "/test/output/screenshots"
        assert str(results_path) == "/test/output/results"
        assert str(custom_path) == "/test/output/custom"
    
    def test_config_viewport_management(self):
        """Test viewport configuration management."""
        config = Config()
        
        # Test getting viewport by name
        desktop_viewport = config.get_viewport_by_name("desktop")
        assert desktop_viewport is not None
        assert desktop_viewport.name == "desktop"
        assert desktop_viewport.width == 1440
        
        # Test getting non-existent viewport
        missing_viewport = config.get_viewport_by_name("nonexistent")
        assert missing_viewport is None
        
        # Test adding new viewport
        new_viewport = ViewportConfig("ultrawide", 3440, 1440)
        config.add_viewport(new_viewport)
        
        added_viewport = config.get_viewport_by_name("ultrawide")
        assert added_viewport is not None
        assert added_viewport.width == 3440
        
        # Test replacing existing viewport
        modified_desktop = ViewportConfig("desktop", 1920, 1080)
        original_count = len(config.viewports)
        config.add_viewport(modified_desktop)
        
        # Should replace, not add
        assert len(config.viewports) == original_count
        updated_desktop = config.get_viewport_by_name("desktop")
        assert updated_desktop.width == 1920
    
    def test_config_custom_queries_management(self):
        """Test custom queries management."""
        config = Config()
        
        # Add custom queries
        config.add_custom_queries("accessibility", [
            "Is the color contrast sufficient?",
            "Are form fields properly labeled?"
        ])
        
        assert "accessibility" in config.custom_queries
        assert len(config.custom_queries["accessibility"]) == 2
        assert "color contrast" in config.custom_queries["accessibility"][0]
        
        # Add more queries to existing category
        config.add_custom_queries("accessibility", [
            "Is keyboard navigation supported?"
        ])
        
        assert len(config.custom_queries["accessibility"]) == 3
    
    def test_config_validation_success(self):
        """Test configuration validation with valid config."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            config = Config()
            errors = config.validate()
            
            assert len(errors) == 0
    
    def test_config_validation_missing_api_key(self):
        """Test configuration validation with missing API key."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            config.llm.api_key = None
            
            errors = config.validate()
            
            assert len(errors) > 0
            assert any("API key" in error for error in errors)
    
    def test_config_validation_invalid_viewport(self):
        """Test configuration validation with invalid viewport."""
        config = Config()
        config.viewports = [ViewportConfig("invalid", -100, 0)]
        
        errors = config.validate()
        
        assert len(errors) > 0
        assert any("viewport size" in error.lower() for error in errors)
    
    def test_config_validation_empty_viewports(self):
        """Test configuration validation with no viewports."""
        config = Config()
        config.viewports = []
        
        errors = config.validate()
        
        assert len(errors) > 0
        assert any("viewports" in error.lower() for error in errors)


@pytest.mark.unit 
class TestConfigUtilities:
    """Test utility functions for configuration."""
    
    def test_create_default_config(self, temp_dir):
        """Test create_default_config utility function."""
        config_path = temp_dir / "default_config.yaml"
        
        config = create_default_config(str(config_path))
        
        # File should be created
        assert config_path.exists()
        
        # Should return valid Config instance
        assert isinstance(config, Config)
        assert config.llm.provider == "openai"
        assert len(config.viewports) > 0
        
        # Should be loadable
        loaded_config = Config(str(config_path))
        assert loaded_config.llm.provider == config.llm.provider