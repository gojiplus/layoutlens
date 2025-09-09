"""Integration tests for end-to-end page testing workflows."""

import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import sys
sys.path.append('.')
from layoutlens.vision.page_tester import PageTester, TestResult, PageTestResult
from layoutlens.capture.screenshot_manager import ViewportConfig, ScreenshotResult
from layoutlens.core import LayoutLens


@pytest.mark.integration
class TestPageTestingWorkflow:
    """Integration tests for complete page testing workflow."""
    
    def test_page_tester_initialization(self, temp_dir):
        """Test PageTester initialization with directories."""
        screenshot_dir = temp_dir / "screenshots"
        results_dir = temp_dir / "results"
        
        with patch('layoutlens.vision.page_tester.openai') as mock_openai:
            mock_client = Mock()
            mock_openai.OpenAI.return_value = mock_client
            
            page_tester = PageTester(
                screenshot_dir=str(screenshot_dir),
                results_dir=str(results_dir),
                openai_api_key="test-key"
            )
            
            assert page_tester.screenshot_dir == screenshot_dir
            assert page_tester.results_dir == results_dir
            assert screenshot_dir.exists()
            assert results_dir.exists()
            assert page_tester.openai_client == mock_client
    
    @patch('layoutlens.vision.page_tester.ScreenshotManager')
    @patch('layoutlens.vision.page_tester.openai')
    def test_complete_page_testing_workflow(self, mock_openai, mock_screenshot_class, temp_dir, sample_html_file):
        """Test complete page testing from screenshot to results."""
        # Setup OpenAI mock
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices[0].message.content = "Yes, the layout looks correct."
        mock_client.chat.completions.create.return_value = mock_response
        
        mock_screenshot_manager = Mock()
        mock_screenshot_class.return_value.__enter__.return_value = mock_screenshot_manager
        
        # Mock screenshot results
        mock_screenshot_result = ScreenshotResult(
            path=str(temp_dir / "test_screenshot.png"),
            viewport=ViewportConfig("desktop", 1440, 900),
            timestamp="1234567890",
            file_size=12345
        )
        mock_screenshot_manager.capture_multiple_viewports.return_value = [mock_screenshot_result]
        
        # Test
        page_tester = PageTester(
            screenshot_dir=str(temp_dir / "screenshots"),
            results_dir=str(temp_dir / "results"),
            openai_api_key="test-key"
        )
        
        result = page_tester.test_page(
            html_path=sample_html_file,
            custom_queries=["Is the layout correct?", "Is the text readable?"],
            auto_generate_queries=False
        )
        
        # Verify results
        assert isinstance(result, PageTestResult)
        assert result.html_path == sample_html_file
        assert result.total_tests == 2  # 2 queries × 1 screenshot
        assert len(result.screenshots) == 1
        assert len(result.test_results) == 2
        
        # Verify screenshot capture was called
        mock_screenshot_manager.capture_multiple_viewports.assert_called_once()
        
        # Verify LLM queries were made
        assert mock_client.chat.completions.create.call_count == 2
    
    @patch('layoutlens.vision.page_tester.ScreenshotManager')
    @patch('layoutlens.vision.page_tester.openai')
    def test_page_testing_with_multiple_viewports(self, mock_openai, mock_screenshot_class, temp_dir, sample_html_file):
        """Test page testing across multiple viewports."""
        # Setup OpenAI mock
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices[0].message.content = "The layout is responsive."
        mock_client.chat.completions.create.return_value = mock_response
        
        mock_screenshot_manager = Mock()
        mock_screenshot_class.return_value.__enter__.return_value = mock_screenshot_manager
        
        # Mock multiple screenshot results
        desktop_result = ScreenshotResult(
            path=str(temp_dir / "desktop.png"),
            viewport=ViewportConfig("desktop", 1440, 900),
            timestamp="1234567890",
            file_size=12345
        )
        mobile_result = ScreenshotResult(
            path=str(temp_dir / "mobile.png"),
            viewport=ViewportConfig("mobile", 375, 667),
            timestamp="1234567891",
            file_size=8765
        )
        mock_screenshot_manager.capture_multiple_viewports.return_value = [desktop_result, mobile_result]
        
        # Test
        page_tester = PageTester(
            screenshot_dir=str(temp_dir / "screenshots"),
            results_dir=str(temp_dir / "results"),
            openai_api_key="test-key"
        )
        
        viewports = [
            ViewportConfig("desktop", 1440, 900),
            ViewportConfig("mobile", 375, 667)
        ]
        
        result = page_tester.test_page(
            html_path=sample_html_file,
            viewports=viewports,
            custom_queries=["Is the layout responsive?"],
            auto_generate_queries=False
        )
        
        # Verify results
        assert result.total_tests == 2  # 1 query × 2 viewports
        assert len(result.screenshots) == 2
        assert len(result.test_results) == 2
        
        # Check that different viewports were tested
        viewport_names = {tr.viewport for tr in result.test_results}
        assert "desktop" in viewport_names
        assert "mobile" in viewport_names
    
    @patch('layoutlens.vision.page_tester.ScreenshotManager')
    @patch('layoutlens.vision.page_tester.openai')
    @patch('layoutlens.vision.page_tester.QueryGenerator')
    def test_page_testing_with_auto_generated_queries(self, mock_query_gen_class, mock_openai, mock_screenshot_class, temp_dir, sample_html_file):
        """Test page testing with auto-generated queries."""
        # Setup OpenAI mock
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices[0].message.content = "The element looks correct."
        mock_client.chat.completions.create.return_value = mock_response
        
        mock_screenshot_manager = Mock()
        mock_screenshot_class.return_value.__enter__.return_value = mock_screenshot_manager
        mock_screenshot_result = ScreenshotResult(
            path=str(temp_dir / "test.png"),
            viewport=ViewportConfig("desktop", 1440, 900),
            timestamp="1234567890",
            file_size=12345
        )
        mock_screenshot_manager.capture_multiple_viewports.return_value = [mock_screenshot_result]
        
        # Mock query generator
        mock_query_generator = Mock()
        mock_query_gen_class.return_value = mock_query_generator
        
        from layoutlens.analysis.query_generator import GeneratedQuery
        mock_generated_queries = [
            GeneratedQuery("Is the heading visible?", element_id="main_heading", category="visibility"),
            GeneratedQuery("Is the text centered?", element_id="main_text", category="text_alignment")
        ]
        mock_query_generator.generate_queries_from_file.return_value = mock_generated_queries
        
        # Test
        page_tester = PageTester(
            screenshot_dir=str(temp_dir / "screenshots"),
            results_dir=str(temp_dir / "results"),
            openai_api_key="test-key"
        )
        
        result = page_tester.test_page(
            html_path=sample_html_file,
            auto_generate_queries=True
        )
        
        # Verify auto-generated queries were used
        mock_query_generator.generate_queries_from_file.assert_called_once_with(sample_html_file)
        assert result.total_tests == 2  # 2 auto-generated queries
        
        # Verify test result details
        for test_result in result.test_results:
            assert test_result.query in ["Is the heading visible?", "Is the text centered?"]
            assert test_result.category in ["visibility", "text_alignment"]
    
    @patch('layoutlens.vision.page_tester.ScreenshotManager')
    @patch('layoutlens.vision.page_tester.openai')
    def test_page_comparison_workflow(self, mock_openai, mock_screenshot_class, temp_dir):
        """Test page comparison workflow."""
        # Setup OpenAI mock
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices[0].message.content = "The layouts look very similar with minor differences."
        mock_client.chat.completions.create.return_value = mock_response
        
        mock_screenshot_manager = Mock()
        mock_screenshot_class.return_value.__enter__.return_value = mock_screenshot_manager
        
        # Mock before/after screenshot results
        before_result = ScreenshotResult(
            path=str(temp_dir / "before.png"),
            viewport=ViewportConfig("desktop", 1440, 900),
            timestamp="1234567890",
            file_size=12345
        )
        after_result = ScreenshotResult(
            path=str(temp_dir / "after.png"), 
            viewport=ViewportConfig("desktop", 1440, 900),
            timestamp="1234567891",
            file_size=12346
        )
        
        mock_screenshot_manager.capture_single.side_effect = [before_result, after_result]
        
        # Create test HTML files
        before_html = temp_dir / "before.html"
        before_html.write_text("<html><body><h1>Before</h1></body></html>")
        
        after_html = temp_dir / "after.html"
        after_html.write_text("<html><body><h1>After</h1></body></html>")
        
        # Test
        page_tester = PageTester(
            screenshot_dir=str(temp_dir / "screenshots"),
            results_dir=str(temp_dir / "results"),
            openai_api_key="test-key"
        )
        
        result = page_tester.compare_pages(
            page_a_path=str(before_html),
            page_b_path=str(after_html)
        )
        
        # Verify results
        assert result["page_a"] == str(before_html)
        assert result["page_b"] == str(after_html)
        assert "similar" in result["answer"].lower()
        assert result["viewport"] == "desktop"
        
        # Verify two screenshots were taken
        assert mock_screenshot_manager.capture_single.call_count == 2
        
        # Verify comparison query was made
        mock_lens.ask.assert_called_once()
        call_args = mock_lens.ask.call_args
        assert len(call_args[0][0]) == 2  # Two image paths
    
    @patch('layoutlens.vision.page_tester.ScreenshotManager')
    def test_page_testing_without_llm(self, mock_screenshot_class, temp_dir, sample_html_file):
        """Test page testing workflow without LLM (screenshot only)."""
        mock_screenshot_manager = Mock()
        mock_screenshot_class.return_value.__enter__.return_value = mock_screenshot_manager
        
        mock_screenshot_result = ScreenshotResult(
            path=str(temp_dir / "test.png"),
            viewport=ViewportConfig("desktop", 1440, 900),
            timestamp="1234567890",
            file_size=12345
        )
        mock_screenshot_manager.capture_multiple_viewports.return_value = [mock_screenshot_result]
        
        # Test without LLM (no API key)
        page_tester = PageTester(
            screenshot_dir=str(temp_dir / "screenshots"),
            results_dir=str(temp_dir / "results")
            # No openai_api_key provided
        )
        
        result = page_tester.test_page(
            html_path=sample_html_file,
            custom_queries=["Is the layout correct?"],
            auto_generate_queries=False
        )
        
        # Should still capture screenshots
        assert len(result.screenshots) == 1
        
        # But no visual tests should be executed
        assert len(result.test_results) == 0
        assert result.total_tests == 0


@pytest.mark.integration
class TestLayoutLensEndToEnd:
    """End-to-end integration tests for the LayoutLens framework."""
    
    @patch('layoutlens.core.PageTester')
    def test_layoutlens_test_page_integration(self, mock_page_tester_class, temp_dir, sample_html_file):
        """Test LayoutLens test_page method integration."""
        # Setup mock PageTester
        mock_page_tester = Mock()
        mock_page_tester_class.return_value = mock_page_tester
        
        # Mock successful test result
        mock_result = Mock()
        mock_result.success_rate = 0.85
        mock_result.passed_tests = 17
        mock_result.total_tests = 20
        mock_page_tester.test_page.return_value = mock_result
        
        # Test LayoutLens integration
        tester = LayoutLens(api_key="test-key", output_dir=str(temp_dir))
        
        result = tester.test_page(
            html_path=sample_html_file,
            queries=["Is the navigation visible?", "Is the content readable?"],
            viewports=["desktop", "mobile_portrait"]
        )
        
        # Verify PageTester was called correctly
        mock_page_tester.test_page.assert_called_once()
        call_args = mock_page_tester.test_page.call_args
        
        assert call_args[1]['html_path'] == sample_html_file
        assert call_args[1]['custom_queries'] == ["Is the navigation visible?", "Is the content readable?"]
        assert len(call_args[1]['viewports']) == 2  # Should convert viewport names to configs
        
        # Verify result
        assert result.success_rate == 0.85
    
    @patch('layoutlens.core.PageTester')
    def test_layoutlens_compare_pages_integration(self, mock_page_tester_class, temp_dir):
        """Test LayoutLens compare_pages method integration."""
        mock_page_tester = Mock()
        mock_page_tester_class.return_value = mock_page_tester
        
        mock_comparison_result = {
            "page_a": "before.html",
            "page_b": "after.html",
            "answer": "The layouts are substantially different.",
            "viewport": "desktop"
        }
        mock_page_tester.compare_pages.return_value = mock_comparison_result
        
        # Create test files
        before_html = temp_dir / "before.html"
        before_html.write_text("<html><body><h1>Before</h1></body></html>")
        
        after_html = temp_dir / "after.html" 
        after_html.write_text("<html><body><h1>After</h1><p>New content</p></body></html>")
        
        # Test
        tester = LayoutLens(api_key="test-key")
        result = tester.compare_pages(str(before_html), str(after_html))
        
        # Verify comparison was called
        mock_page_tester.compare_pages.assert_called_once()
        call_args = mock_page_tester.compare_pages.call_args
        
        assert call_args[1]['page_a_path'] == str(before_html)
        assert call_args[1]['page_b_path'] == str(after_html)
        assert call_args[1]['comparison_query'] == "Do these two layouts look the same?"
        
        # Verify result
        assert result["answer"] == "The layouts are substantially different."
    
    @patch('layoutlens.core.TestRunner')
    def test_layoutlens_run_test_suite_integration(self, mock_runner_class, temp_dir):
        """Test LayoutLens run_test_suite integration."""
        mock_runner = Mock()
        mock_runner_class.return_value = mock_runner
        
        # Mock test session result
        mock_session = Mock()
        mock_session.success_rate = 0.9
        mock_session.total_tests = 50
        mock_session.total_passed = 45
        mock_runner.run_test_suite.return_value = mock_session
        
        # Create test suite file
        test_suite_content = """
        name: "Integration Test Suite"
        description: "Test suite for integration testing"
        test_cases:
          - name: "Homepage Test"
            html_path: "homepage.html"
            queries: ["Is the logo visible?"]
            viewports: ["desktop"]
        """
        
        suite_file = temp_dir / "test_suite.yaml"
        suite_file.write_text(test_suite_content)
        
        # Test
        tester = LayoutLens(api_key="test-key")
        results = tester.run_test_suite(str(suite_file))
        
        # Verify TestRunner was used
        mock_runner_class.assert_called_once_with(tester.config)
        mock_runner.run_test_suite.assert_called_once_with(str(suite_file))
        
        # Verify results
        assert len(results) == 1  # Should return list of results
        assert results[0] == mock_session
    
    @patch('layoutlens.vision.page_tester.openai.OpenAI', side_effect=Exception("API Error"))
    def test_error_handling_in_integration(self, mock_openai_client, temp_dir, sample_html_file):
        """Test error handling in integration scenarios."""
        # Test that PageTester handles LLM initialization errors gracefully
        page_tester = PageTester(
            screenshot_dir=str(temp_dir / "screenshots"),
            results_dir=str(temp_dir / "results"),
            openai_api_key="invalid-key"
        )
        
        # Should not raise exception during initialization
        assert page_tester.layout_lens is None
        
        # Should handle testing without LLM
        with patch('layoutlens.vision.page_tester.ScreenshotManager') as mock_screenshot_class:
            mock_screenshot_manager = Mock()
            mock_screenshot_class.return_value.__enter__.return_value = mock_screenshot_manager
            
            mock_screenshot_result = ScreenshotResult(
                path=str(temp_dir / "test.png"),
                viewport=ViewportConfig("desktop", 1440, 900),
                timestamp="1234567890",
                file_size=12345
            )
            mock_screenshot_manager.capture_multiple_viewports.return_value = [mock_screenshot_result]
            
            result = page_tester.test_page(sample_html_file, custom_queries=["Test query"])
            
            # Should complete but with no visual tests
            assert result.total_tests == 0
            assert len(result.screenshots) == 1