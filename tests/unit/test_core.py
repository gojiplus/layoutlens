"""Unit tests for the layoutlens.core module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path

import sys
sys.path.append('.')
from layoutlens.core import LayoutLens, TestCase, TestSuite
from layoutlens.config import Config


@pytest.mark.unit
class TestTestCase:
    """Test cases for the TestCase dataclass."""
    
    def test_test_case_creation(self):
        """Test TestCase creation with all parameters."""
        test_case = TestCase(
            name="Homepage Test",
            html_path="homepage.html",
            queries=["Is the logo visible?", "Is the navigation clear?"],
            viewports=["desktop", "mobile"],
            expected_results={"logo": "visible"},
            metadata={"priority": "high"}
        )
        
        assert test_case.name == "Homepage Test"
        assert test_case.html_path == "homepage.html"
        assert len(test_case.queries) == 2
        assert "desktop" in test_case.viewports
        assert test_case.expected_results["logo"] == "visible"
        assert test_case.metadata["priority"] == "high"
    
    def test_test_case_defaults(self):
        """Test TestCase with default values."""
        test_case = TestCase(name="Simple Test", html_path="test.html")
        
        assert test_case.queries == []
        assert test_case.viewports == []
        assert test_case.expected_results == {}
        assert test_case.metadata == {}


@pytest.mark.unit
class TestTestSuite:
    """Test cases for the TestSuite dataclass."""
    
    def test_test_suite_creation(self):
        """Test TestSuite creation."""
        test_cases = [
            TestCase("Test 1", "page1.html"),
            TestCase("Test 2", "page2.html")
        ]
        
        suite = TestSuite(
            name="Sample Suite",
            description="A test suite for testing",
            test_cases=test_cases,
            metadata={"version": "1.0"}
        )
        
        assert suite.name == "Sample Suite"
        assert suite.description == "A test suite for testing"
        assert len(suite.test_cases) == 2
        assert suite.metadata["version"] == "1.0"


@pytest.mark.unit
class TestLayoutLensCore:
    """Test cases for the enhanced LayoutLens class."""
    
    @patch('layoutlens.core.PageTester')
    @patch('layoutlens.core.BenchmarkGenerator')
    def test_layoutlens_initialization_default(self, mock_benchmark, mock_page_tester):
        """Test LayoutLens initialization with defaults."""
        tester = LayoutLens()
        
        assert isinstance(tester.config, Config)
        assert tester.config.llm.model == "gpt-4o-mini"
        assert tester.config.output.base_dir == "layoutlens_output"
    
    @patch('layoutlens.core.PageTester')
    @patch('layoutlens.core.BenchmarkGenerator')
    def test_layoutlens_initialization_with_config_file(self, mock_benchmark, mock_page_tester, temp_dir):
        """Test LayoutLens initialization with config file."""
        # Create test config file
        config_content = """
        llm:
          model: "gpt-4o"
          temperature: 0.2
        output:
          base_dir: "custom_output"
        """
        config_file = temp_dir / "test_config.yaml"
        config_file.write_text(config_content)
        
        tester = LayoutLens(config=str(config_file))
        
        assert tester.config.llm.model == "gpt-4o"
        assert tester.config.llm.temperature == 0.2
        assert tester.config.output.base_dir == "custom_output"
    
    @patch('layoutlens.core.PageTester')
    @patch('layoutlens.core.BenchmarkGenerator')
    def test_layoutlens_initialization_with_config_object(self, mock_benchmark, mock_page_tester):
        """Test LayoutLens initialization with Config object."""
        config = Config()
        config.llm.model = "gpt-4o"
        config.output.base_dir = "test_output"
        
        tester = LayoutLens(config=config)
        
        assert tester.config.llm.model == "gpt-4o"
        assert tester.config.output.base_dir == "test_output"
    
    @patch('layoutlens.core.PageTester')
    @patch('layoutlens.core.BenchmarkGenerator')
    def test_layoutlens_parameter_overrides(self, mock_benchmark, mock_page_tester):
        """Test that constructor parameters override config."""
        tester = LayoutLens(
            api_key="test-key",
            model="gpt-4o",
            output_dir="custom_dir"
        )
        
        assert tester.config.llm.api_key == "test-key"
        assert tester.config.llm.model == "gpt-4o"
        assert tester.config.output.base_dir == "custom_dir"
    
    @patch('layoutlens.core.PageTester')
    def test_test_page_success(self, mock_page_tester_class):
        """Test successful page testing."""
        # Setup mocks
        mock_page_tester = Mock()
        mock_page_tester_class.return_value = mock_page_tester
        
        mock_result = Mock()
        mock_result.success_rate = 0.9
        mock_result.passed_tests = 9
        mock_result.total_tests = 10
        mock_page_tester.test_page.return_value = mock_result
        
        # Test
        tester = LayoutLens()
        result = tester.test_page(
            html_path="test.html",
            queries=["Is the layout correct?"],
            viewports=["desktop"]
        )
        
        assert result is not None
        assert result.success_rate == 0.9
        mock_page_tester.test_page.assert_called_once()
    
    @patch('layoutlens.core.PageTester')
    def test_test_page_with_auto_queries(self, mock_page_tester_class):
        """Test page testing with auto-generated queries."""
        mock_page_tester = Mock()
        mock_page_tester_class.return_value = mock_page_tester
        
        mock_result = Mock()
        mock_page_tester.test_page.return_value = mock_result
        
        tester = LayoutLens()
        tester.test_page("test.html", auto_generate_queries=True)
        
        # Verify auto_generate_queries was passed correctly
        call_args = mock_page_tester.test_page.call_args
        assert call_args[1]['auto_generate_queries'] is True
    
    @patch('layoutlens.core.PageTester')
    def test_test_page_without_page_tester(self, mock_page_tester_class):
        """Test page testing when PageTester is not available."""
        mock_page_tester_class.return_value = None
        
        tester = LayoutLens()
        tester.page_tester = None
        
        result = tester.test_page("test.html")
        
        assert result is None
    
    @patch('layoutlens.core.PageTester')
    def test_test_page_with_exception(self, mock_page_tester_class):
        """Test page testing when an exception occurs."""
        mock_page_tester = Mock()
        mock_page_tester_class.return_value = mock_page_tester
        mock_page_tester.test_page.side_effect = Exception("Test error")
        
        tester = LayoutLens()
        result = tester.test_page("test.html")
        
        assert result is None
    
    @patch('layoutlens.core.PageTester')
    def test_compare_pages_success(self, mock_page_tester_class):
        """Test successful page comparison."""
        mock_page_tester = Mock()
        mock_page_tester_class.return_value = mock_page_tester
        
        mock_result = {
            "page_a": "before.html",
            "page_b": "after.html",
            "answer": "The layouts are similar but have minor differences.",
            "viewport": "desktop"
        }
        mock_page_tester.compare_pages.return_value = mock_result
        
        tester = LayoutLens()
        result = tester.compare_pages("before.html", "after.html")
        
        assert result is not None
        assert result["answer"] == "The layouts are similar but have minor differences."
        mock_page_tester.compare_pages.assert_called_once()
    
    @patch('layoutlens.core.PageTester')
    def test_compare_pages_unknown_viewport(self, mock_page_tester_class):
        """Test page comparison with unknown viewport."""
        mock_page_tester = Mock()
        mock_page_tester_class.return_value = mock_page_tester
        
        tester = LayoutLens()
        result = tester.compare_pages("a.html", "b.html", viewport="unknown")
        
        assert result is None
        mock_page_tester.compare_pages.assert_not_called()
    
    def test_create_test_suite(self):
        """Test test suite creation."""
        tester = LayoutLens()
        
        test_cases_data = [
            {
                "name": "Homepage",
                "html_path": "homepage.html",
                "queries": ["Is the logo visible?"],
                "viewports": ["desktop"]
            },
            {
                "name": "About Page",
                "html_path": "about.html",
                "queries": ["Is the content readable?"],
                "viewports": ["mobile_portrait"]
            }
        ]
        
        suite = tester.create_test_suite(
            name="Website Tests",
            description="Complete website test suite",
            test_cases=test_cases_data
        )
        
        assert suite.name == "Website Tests"
        assert suite.description == "Complete website test suite"
        assert len(suite.test_cases) == 2
        assert suite.test_cases[0].name == "Homepage"
        assert suite.test_cases[1].queries == ["Is the content readable?"]
    
    def test_create_test_suite_with_save(self, temp_dir):
        """Test test suite creation with file saving."""
        tester = LayoutLens()
        
        test_cases_data = [
            {
                "name": "Test Case",
                "html_path": "test.html",
                "queries": ["Test query"]
            }
        ]
        
        save_path = temp_dir / "test_suite.yaml"
        suite = tester.create_test_suite(
            name="Test Suite",
            description="Test description",
            test_cases=test_cases_data,
            save_path=str(save_path)
        )
        
        assert save_path.exists()
        
        # Verify file content
        import yaml
        with open(save_path, 'r') as f:
            saved_data = yaml.safe_load(f)
        
        assert saved_data['name'] == "Test Suite"
        assert len(saved_data['test_cases']) == 1
    
    @patch('layoutlens.core.BenchmarkGenerator')
    def test_generate_benchmark_data_default(self, mock_benchmark_class):
        """Test benchmark data generation with defaults."""
        mock_generator = Mock()
        mock_benchmark_class.return_value = mock_generator
        
        # Create mock suites with required attributes
        mock_suite1 = Mock()
        mock_suite1.name = "Suite 1"
        mock_suite1.test_cases = [Mock(), Mock()]
        
        mock_suite2 = Mock()
        mock_suite2.name = "Suite 2"
        mock_suite2.test_cases = [Mock()]
        
        mock_suites = [mock_suite1, mock_suite2]
        mock_generator.generate_all_suites.return_value = mock_suites
        mock_generator.export_to_csv.return_value = "test.csv"
        mock_generator.export_to_json.return_value = "test.json"
        mock_generator.output_dir = "/test/output"
        
        tester = LayoutLens()
        tester.generate_benchmark_data()
        
        mock_generator.generate_all_suites.assert_called_once()
        assert mock_generator.export_to_csv.call_count == len(mock_suites)
        assert mock_generator.export_to_json.call_count == len(mock_suites)
    
    @patch('layoutlens.core.BenchmarkGenerator')
    def test_generate_benchmark_data_custom_dir(self, mock_benchmark_class):
        """Test benchmark data generation with custom directory."""
        mock_generator = Mock()
        mock_benchmark_class.return_value = mock_generator
        
        # Create mock suite with required attributes
        mock_suite = Mock()
        mock_suite.name = "Custom Suite"
        mock_suite.test_cases = [Mock()]
        
        mock_generator.generate_all_suites.return_value = [mock_suite]
        mock_generator.export_to_csv.return_value = "test.csv"
        mock_generator.export_to_json.return_value = "test.json"
        mock_generator.output_dir = "custom_output"
        
        tester = LayoutLens()
        tester.generate_benchmark_data("custom_output")
        
        # Should create new generator with custom directory
        mock_benchmark_class.assert_called_with("custom_output")
    
    def test_generate_benchmark_data_without_generator(self):
        """Test benchmark generation when BenchmarkGenerator is not available."""
        with patch('layoutlens.core.BenchmarkGenerator', None):
            tester = LayoutLens()
            tester.benchmark_generator = None
            
            # Should not raise exception
            tester.generate_benchmark_data()
    
    @patch('layoutlens.core.OriginalLayoutLens')
    def test_ask_backward_compatibility(self, mock_original):
        """Test backward compatibility ask method."""
        mock_lens = Mock()
        mock_original.return_value = mock_lens
        mock_lens.ask.return_value = "Test response"
        
        tester = LayoutLens(api_key="test-key")
        result = tester.ask(["image1.png", "image2.png"], "Test query")
        
        assert result == "Test response"
        mock_original.assert_called_once_with(
            api_key="test-key",
            model="gpt-4o-mini"
        )
        mock_lens.ask.assert_called_once_with(
            ["image1.png", "image2.png"], 
            "Test query"
        )
    
    def test_ask_without_original_layoutlens(self):
        """Test ask method when original LayoutLens is not available."""
        with patch('layoutlens.core.OriginalLayoutLens', None):
            tester = LayoutLens(api_key="test-key")
            result = tester.ask(["image.png"], "Test query")
            
            assert "Error" in result
            assert "not available" in result
    
    def test_ask_without_api_key(self):
        """Test ask method without API key."""
        tester = LayoutLens()
        tester.config.llm.api_key = None
        
        result = tester.ask(["image.png"], "Test query")
        
        assert "Error" in result
        assert "API key" in result
    
    def test_compare_layouts_backward_compatibility(self):
        """Test backward compatibility compare_layouts method."""
        with patch.object(LayoutLens, 'ask') as mock_ask:
            mock_ask.return_value = "Yes, they look the same."
            
            tester = LayoutLens()
            result = tester.compare_layouts("image1.png", "image2.png")
            
            assert result == "Yes, they look the same."
            mock_ask.assert_called_once_with(
                ["image1.png", "image2.png"],
                "Do these two layouts look the same?"
            )