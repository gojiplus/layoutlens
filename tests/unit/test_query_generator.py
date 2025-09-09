"""Unit tests for the query_generator module."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from bs4 import BeautifulSoup, Tag

import sys
sys.path.append('.')
from layoutlens.analysis.query_generator import QueryGenerator, GeneratedQuery, ElementInfo, generate_queries_from_file


@pytest.mark.unit
class TestElementInfo:
    """Test cases for ElementInfo dataclass."""
    
    def test_element_info_creation(self):
        """Test ElementInfo creation with all parameters."""
        element = ElementInfo(
            tag="div",
            id="main_content",
            classes=["container", "highlight"],
            attributes={"role": "main", "aria-label": "Main content"},
            text_content="This is the main content area",
            computed_styles={"text-align": "center", "color": "#333"},
            position={"x": 100, "y": 200},
            children_count=3,
            parent_tag="body"
        )
        
        assert element.tag == "div"
        assert element.id == "main_content"
        assert "container" in element.classes
        assert element.attributes["role"] == "main"
        assert "main content" in element.text_content.lower()
        assert element.computed_styles["text-align"] == "center"
        assert element.position["x"] == 100
        assert element.children_count == 3
        assert element.parent_tag == "body"


@pytest.mark.unit
class TestGeneratedQuery:
    """Test cases for GeneratedQuery dataclass."""
    
    def test_generated_query_creation(self):
        """Test GeneratedQuery creation."""
        query = GeneratedQuery(
            query="Is the text centered?",
            element_id="main_text",
            element_selector="#main_text",
            category="text_alignment",
            confidence=0.9,
            expected_answer="yes",
            metadata={"property": "text-align", "value": "center"}
        )
        
        assert query.query == "Is the text centered?"
        assert query.element_id == "main_text"
        assert query.element_selector == "#main_text"
        assert query.category == "text_alignment"
        assert query.confidence == 0.9
        assert query.expected_answer == "yes"
        assert query.metadata["property"] == "text-align"


@pytest.mark.unit
class TestQueryGenerator:
    """Test cases for QueryGenerator class."""
    
    def test_query_generator_initialization(self):
        """Test QueryGenerator initialization."""
        generator = QueryGenerator()
        
        # Check that visual properties are loaded
        assert "text-align" in generator.VISUAL_PROPERTIES
        assert "font-weight" in generator.VISUAL_PROPERTIES
        
        # Check semantic elements
        assert "header" in generator.SEMANTIC_ELEMENTS
        assert "nav" in generator.SEMANTIC_ELEMENTS
        
        # Check ARIA attributes
        assert "aria-label" in generator.ARIA_ATTRIBUTES
    
    def test_query_generator_without_beautifulsoup(self):
        """Test QueryGenerator raises error without BeautifulSoup."""
        with patch('layoutlens.analysis.query_generator.BeautifulSoup', None):
            with pytest.raises(ImportError, match="beautifulsoup4 is required"):
                QueryGenerator()
    
    @patch('layoutlens.analysis.query_generator.BeautifulSoup')
    def test_analyze_html_content(self, mock_bs):
        """Test HTML content analysis."""
        # Setup mock BeautifulSoup
        mock_soup = Mock()
        mock_bs.return_value = mock_soup
        
        # Mock elements
        mock_element1 = Mock()
        mock_element1.name = "h1"
        mock_element1.get.return_value = "main_heading"
        mock_element1.attrs = {"id": "main_heading"}
        
        mock_element2 = Mock() 
        mock_element2.name = "div"
        mock_element2.get.side_effect = lambda attr, default=None: {"id": "content", "class": ["highlight"]}.get(attr, default)
        mock_element2.attrs = {"id": "content", "class": ["highlight"]}
        
        mock_soup.find_all.return_value = [mock_element1, mock_element2]
        
        # Mock significant element checks
        generator = QueryGenerator()
        
        with patch.object(generator, '_is_significant_element', return_value=True), \
             patch.object(generator, '_extract_element_info') as mock_extract:
            
            mock_extract.side_effect = [
                ElementInfo("h1", "main_heading"),
                ElementInfo("div", "content", ["highlight"])
            ]
            
            html_content = "<html><h1 id='main_heading'>Title</h1><div id='content'>Content</div></html>"
            elements = generator.analyze_html_content(html_content)
            
            assert len(elements) == 2
            assert elements[0].tag == "h1"
            assert elements[1].tag == "div"
    
    def test_analyze_html_file(self, temp_dir):
        """Test HTML file analysis."""
        # Create test HTML file
        html_content = """
        <html>
            <body>
                <h1 id="title">Test Page</h1>
                <div id="content" class="main">Content here</div>
            </body>
        </html>
        """
        html_file = temp_dir / "test.html"
        html_file.write_text(html_content)
        
        generator = QueryGenerator()
        
        with patch.object(generator, 'analyze_html_content') as mock_analyze:
            mock_analyze.return_value = [ElementInfo("h1", "title")]
            
            elements = generator.analyze_html_file(str(html_file))
            
            mock_analyze.assert_called_once_with(html_content)
            assert len(elements) == 1
    
    def test_is_significant_element(self):
        """Test significant element detection."""
        generator = QueryGenerator()
        
        # Create real BeautifulSoup elements for testing
        soup = BeautifulSoup('<html></html>', 'html.parser')
        
        # Element with ID - should be significant
        element_with_id = soup.new_tag("div", **{"id": "main_id"})
        
        # Semantic element - should be significant
        element_semantic = soup.new_tag("header")
        
        # Element with class - should be significant
        element_with_class = soup.new_tag("div", **{"class": ["main-content"]})
        
        # Plain element without significant attributes - should not be significant
        element_insignificant = soup.new_tag("span")
        
        # Test significance checks
        assert generator._is_significant_element(element_with_id) is True
        assert generator._is_significant_element(element_semantic) is True
        assert generator._is_significant_element(element_with_class) is True
        assert generator._is_significant_element(element_insignificant) is False
    
    def test_extract_element_info(self):
        """Test element information extraction."""
        generator = QueryGenerator()
        
        # Mock element
        mock_element = Mock()
        mock_element.name = "div"
        mock_element.get.side_effect = lambda attr, default=None: {
            "id": "test_element",
            "class": ["highlight", "main"],
            "style": "text-align: center; color: red;"
        }.get(attr, default)
        mock_element.attrs = {
            "id": "test_element", 
            "class": ["highlight", "main"],
            "style": "text-align: center; color: red;"
        }
        mock_element.get_text.return_value = "Element text content"
        mock_element.find_all.return_value = []  # No children
        
        # Mock parent
        mock_parent = Mock()
        mock_parent.name = "body"
        mock_element.parent = mock_parent
        
        element_info = generator._extract_element_info(mock_element)
        
        assert element_info.tag == "div"
        assert element_info.id == "test_element"
        assert "highlight" in element_info.classes
        assert element_info.text_content == "Element text content"
        assert element_info.computed_styles["text-align"] == "center"
        assert element_info.computed_styles["color"] == "red"
        assert element_info.parent_tag == "body"
        assert element_info.children_count == 0
    
    def test_parse_inline_styles(self):
        """Test inline CSS style parsing."""
        generator = QueryGenerator()
        
        style_string = "text-align: center; color: red; font-size: 16px;"
        styles = generator._parse_inline_styles(style_string)
        
        assert styles["text-align"] == "center"
        assert styles["color"] == "red"
        assert styles["font-size"] == "16px"
        
        # Test empty string
        empty_styles = generator._parse_inline_styles("")
        assert empty_styles == {}
        
        # Test malformed style
        malformed = generator._parse_inline_styles("invalid-style")
        assert malformed == {}
    
    def test_generate_text_alignment_queries(self):
        """Test text alignment query generation."""
        generator = QueryGenerator()
        
        # Element with center alignment
        element = ElementInfo(
            tag="div",
            id="centered_text", 
            text_content="Some text content",
            computed_styles={"text-align": "center"}
        )
        
        queries = generator._generate_text_alignment_queries(element)
        
        assert len(queries) > 0
        assert any("center" in query.query.lower() for query in queries)
        assert any(query.category == "text_alignment" for query in queries)
        assert any(query.element_id == "centered_text" for query in queries)
    
    def test_generate_text_alignment_queries_no_text(self):
        """Test text alignment queries for element without text."""
        generator = QueryGenerator()
        
        element = ElementInfo(
            tag="div",
            id="no_text",
            text_content=None,  # No text content
            computed_styles={"text-align": "center"}
        )
        
        queries = generator._generate_text_alignment_queries(element)
        
        assert len(queries) == 0
    
    def test_generate_styling_queries(self):
        """Test text styling query generation."""
        generator = QueryGenerator()
        
        # Element with bold text
        element = ElementInfo(
            tag="span",
            id="bold_text",
            text_content="Bold text",
            computed_styles={"font-weight": "bold"}
        )
        
        queries = generator._generate_styling_queries(element)
        
        assert len(queries) > 0
        assert any("bold" in query.query.lower() for query in queries)
        assert any(query.category == "text_styling" for query in queries)
    
    def test_generate_layout_queries(self):
        """Test layout query generation."""
        generator = QueryGenerator()
        
        # Element with flexbox
        element = ElementInfo(
            tag="div",
            id="flex_container",
            computed_styles={
                "display": "flex",
                "flex-direction": "column"
            }
        )
        
        queries = generator._generate_layout_queries(element)
        
        assert len(queries) > 0
        assert any("flex" in query.query.lower() for query in queries)
        assert any("column" in query.query.lower() for query in queries)
        assert any(query.category == "layout" for query in queries)
    
    def test_generate_accessibility_queries(self):
        """Test accessibility query generation."""
        generator = QueryGenerator()
        
        # Element with ARIA label
        element = ElementInfo(
            tag="button",
            id="submit_btn",
            attributes={"aria-label": "Submit form"}
        )
        
        queries = generator._generate_accessibility_queries(element)
        
        assert len(queries) > 0
        assert any("accessible" in query.query.lower() or "label" in query.query.lower() for query in queries)
        assert any(query.category == "accessibility" for query in queries)
    
    def test_generate_semantic_queries(self):
        """Test semantic markup query generation."""
        generator = QueryGenerator()
        
        # Semantic header element
        element = ElementInfo(
            tag="header",
            id="page_header"
        )
        
        queries = generator._generate_semantic_queries(element)
        
        assert len(queries) > 0
        assert any("header" in query.query.lower() for query in queries)
        assert any(query.category == "semantic_markup" for query in queries)
    
    def test_generate_queries_from_elements(self):
        """Test complete query generation from elements."""
        generator = QueryGenerator()
        
        elements = [
            ElementInfo(
                tag="h1",
                id="main_title",
                text_content="Page Title",
                computed_styles={"text-align": "center", "font-weight": "bold"}
            ),
            ElementInfo(
                tag="div",
                id="content",
                text_content="Page content",
                computed_styles={"display": "flex"}
            )
        ]
        
        queries = generator.generate_queries_from_elements(elements)
        
        assert len(queries) > 0
        
        # Should have queries from different categories
        categories = {query.category for query in queries}
        assert "text_alignment" in categories or "text_styling" in categories
        assert "layout" in categories
    
    def test_generate_custom_queries(self):
        """Test custom query generation with focus areas."""
        generator = QueryGenerator()
        
        elements = [
            ElementInfo(
                tag="div",
                text_content="Text content",
                computed_styles={"text-align": "center", "display": "flex", "color": "red"}
            )
        ]
        
        # Focus only on typography
        typography_queries = generator.generate_custom_queries(elements, ["typography"])
        typography_categories = {query.category for query in typography_queries}
        
        assert "text_alignment" in typography_categories or "text_styling" in typography_categories
        assert "layout" not in typography_categories  # Should not include layout queries
        
        # Focus only on layout
        layout_queries = generator.generate_custom_queries(elements, ["layout"])
        layout_categories = {query.category for query in layout_queries}
        
        assert "layout" in layout_categories
        assert "text_alignment" not in layout_categories  # Should not include typography queries
    
    def test_describe_color(self):
        """Test color description utility."""
        generator = QueryGenerator()
        
        # Test known colors
        assert generator._describe_color("#000000") == "black"
        assert generator._describe_color("#ffffff") == "white"
        assert generator._describe_color("#ff0000") == "red"
        assert generator._describe_color("rgb(0,0,0)") == "black"
        assert generator._describe_color("transparent") == "transparent"
        
        # Test unknown color
        assert generator._describe_color("#abc123") == "#abc123"


@pytest.mark.unit
class TestQueryGeneratorUtilities:
    """Test utility functions."""
    
    @patch('layoutlens.analysis.query_generator.QueryGenerator')
    def test_generate_queries_from_file(self, mock_generator_class):
        """Test convenience function for generating queries from file."""
        mock_generator = Mock()
        mock_generator_class.return_value = mock_generator
        
        expected_queries = [GeneratedQuery("Test query", category="test")]
        mock_generator.generate_queries_from_file.return_value = expected_queries
        
        result = generate_queries_from_file("test.html")
        
        mock_generator_class.assert_called_once()
        mock_generator.generate_queries_from_file.assert_called_once_with("test.html")
        assert result == expected_queries