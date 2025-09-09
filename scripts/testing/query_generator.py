"""Intelligent test question generation from DOM analysis.

This module analyzes HTML content and generates appropriate
test queries for visual validation using natural language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup, Tag, NavigableString
except ImportError:  # pragma: no cover
    BeautifulSoup = None
    Tag = None
    NavigableString = None


@dataclass
class ElementInfo:
    """Information about a DOM element for test generation."""
    
    tag: str
    id: Optional[str] = None
    classes: List[str] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)
    text_content: Optional[str] = None
    computed_styles: Dict[str, str] = field(default_factory=dict)
    position: Optional[Dict[str, int]] = None
    children_count: int = 0
    parent_tag: Optional[str] = None


@dataclass
class GeneratedQuery:
    """A generated test query with metadata."""
    
    query: str
    element_id: Optional[str] = None
    element_selector: Optional[str] = None
    category: str = "general"
    confidence: float = 1.0
    expected_answer: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class QueryGenerator:
    """Generates intelligent test queries from HTML analysis.
    
    This class analyzes HTML structure, styling, and content to
    generate appropriate natural language test questions for
    visual validation.
    """
    
    # Common CSS properties that indicate visual styling
    VISUAL_PROPERTIES = {
        "text-align": ["left", "center", "right", "justify"],
        "font-weight": ["bold", "normal", "lighter"],
        "font-style": ["italic", "normal", "oblique"],
        "text-decoration": ["underline", "line-through", "overline", "none"],
        "color": [],  # Color values
        "background-color": [],  # Color values
        "display": ["flex", "grid", "block", "inline", "none"],
        "flex-direction": ["row", "column", "row-reverse", "column-reverse"],
        "justify-content": ["flex-start", "center", "flex-end", "space-between", "space-around"],
        "align-items": ["flex-start", "center", "flex-end", "stretch"],
        "position": ["relative", "absolute", "fixed", "sticky"],
        "float": ["left", "right", "none"],
        "visibility": ["visible", "hidden"],
        "opacity": []  # Numeric values
    }
    
    # Semantic HTML elements that have specific meaning
    SEMANTIC_ELEMENTS = {
        "header", "nav", "main", "article", "section", "aside", 
        "footer", "h1", "h2", "h3", "h4", "h5", "h6", "p", 
        "ul", "ol", "li", "table", "form", "button"
    }
    
    # ARIA attributes that indicate accessibility features
    ARIA_ATTRIBUTES = {
        "aria-label", "aria-labelledby", "aria-describedby", "aria-hidden",
        "aria-expanded", "aria-checked", "aria-selected", "role"
    }
    
    def __init__(self):
        """Initialize the query generator."""
        if BeautifulSoup is None:
            raise ImportError("beautifulsoup4 is required for QueryGenerator")
    
    def analyze_html_file(self, html_path: str) -> List[ElementInfo]:
        """Analyze an HTML file and extract element information.
        
        Parameters
        ----------
        html_path : str
            Path to HTML file to analyze
            
        Returns
        -------
        List[ElementInfo]
            List of analyzed elements with their properties
        """
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        return self.analyze_html_content(html_content)
    
    def analyze_html_content(self, html_content: str) -> List[ElementInfo]:
        """Analyze HTML content and extract element information.
        
        Parameters
        ----------
        html_content : str
            HTML content to analyze
            
        Returns
        -------
        List[ElementInfo]
            List of analyzed elements with their properties
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        elements = []
        
        # Find all elements with IDs or significant content
        for element in soup.find_all(True):
            if self._is_significant_element(element):
                element_info = self._extract_element_info(element)
                elements.append(element_info)
        
        return elements
    
    def generate_queries_from_file(self, html_path: str) -> List[GeneratedQuery]:
        """Generate test queries from an HTML file.
        
        Parameters
        ----------
        html_path : str
            Path to HTML file
            
        Returns
        -------
        List[GeneratedQuery]
            Generated test queries
        """
        elements = self.analyze_html_file(html_path)
        return self.generate_queries_from_elements(elements)
    
    def generate_queries_from_elements(self, elements: List[ElementInfo]) -> List[GeneratedQuery]:
        """Generate test queries from analyzed elements.
        
        Parameters
        ----------
        elements : List[ElementInfo]
            List of analyzed elements
            
        Returns
        -------
        List[GeneratedQuery]
            Generated test queries
        """
        queries = []
        
        for element in elements:
            # Generate text alignment queries
            queries.extend(self._generate_text_alignment_queries(element))
            
            # Generate styling queries
            queries.extend(self._generate_styling_queries(element))
            
            # Generate layout queries
            queries.extend(self._generate_layout_queries(element))
            
            # Generate color queries
            queries.extend(self._generate_color_queries(element))
            
            # Generate accessibility queries
            queries.extend(self._generate_accessibility_queries(element))
            
            # Generate semantic markup queries
            queries.extend(self._generate_semantic_queries(element))
        
        # Generate relationship queries between elements
        queries.extend(self._generate_relationship_queries(elements))
        
        return queries
    
    def generate_custom_queries(
        self, 
        elements: List[ElementInfo],
        focus_areas: Optional[List[str]] = None
    ) -> List[GeneratedQuery]:
        """Generate queries focused on specific areas.
        
        Parameters
        ----------
        elements : List[ElementInfo]
            List of analyzed elements
        focus_areas : List[str], optional
            Areas to focus on: 'typography', 'layout', 'color', 'accessibility'
            
        Returns
        -------
        List[GeneratedQuery]
            Focused test queries
        """
        focus_areas = focus_areas or ["typography", "layout", "color", "accessibility"]
        queries = []
        
        for element in elements:
            if "typography" in focus_areas:
                queries.extend(self._generate_text_alignment_queries(element))
                queries.extend(self._generate_styling_queries(element))
            
            if "layout" in focus_areas:
                queries.extend(self._generate_layout_queries(element))
            
            if "color" in focus_areas:
                queries.extend(self._generate_color_queries(element))
                
            if "accessibility" in focus_areas:
                queries.extend(self._generate_accessibility_queries(element))
        
        return queries
    
    def _is_significant_element(self, element: Tag) -> bool:
        """Check if an element is significant for testing."""
        if not isinstance(element, Tag):
            return False
            
        # Elements with IDs are always significant
        if element.get('id'):
            return True
            
        # Semantic elements are significant
        if element.name in self.SEMANTIC_ELEMENTS:
            return True
            
        # Elements with classes are potentially significant
        if element.get('class'):
            return True
            
        # Elements with ARIA attributes are significant
        for attr in element.attrs:
            if attr in self.ARIA_ATTRIBUTES:
                return True
        
        # Elements with text content
        text = element.get_text(strip=True)
        if text and len(text) > 10:  # Meaningful text content
            return True
            
        # Form elements
        if element.name in ['input', 'button', 'select', 'textarea', 'form']:
            return True
            
        return False
    
    def _extract_element_info(self, element: Tag) -> ElementInfo:
        """Extract comprehensive information about an element."""
        # Basic element info
        element_info = ElementInfo(
            tag=element.name,
            id=element.get('id'),
            classes=element.get('class', []),
            attributes=dict(element.attrs),
            text_content=element.get_text(strip=True)[:200],  # Limit text length
            children_count=len(element.find_all(True, recursive=False))
        )
        
        # Parent information
        parent = element.parent
        if parent and hasattr(parent, 'name'):
            element_info.parent_tag = parent.name
        
        # Extract inline styles
        style_attr = element.get('style', '')
        if style_attr:
            element_info.computed_styles = self._parse_inline_styles(style_attr)
        
        return element_info
    
    def _parse_inline_styles(self, style_string: str) -> Dict[str, str]:
        """Parse inline CSS styles."""
        styles = {}
        if not style_string:
            return styles
            
        # Split by semicolon and parse property-value pairs
        for declaration in style_string.split(';'):
            if ':' in declaration:
                prop, value = declaration.split(':', 1)
                styles[prop.strip()] = value.strip()
        
        return styles
    
    def _generate_text_alignment_queries(self, element: ElementInfo) -> List[GeneratedQuery]:
        """Generate queries about text alignment."""
        queries = []
        
        if not element.text_content:
            return queries
            
        # Check for text-align in styles
        text_align = element.computed_styles.get('text-align')
        if text_align and text_align in self.VISUAL_PROPERTIES['text-align']:
            selector = f"#{element.id}" if element.id else element.tag
            
            query = GeneratedQuery(
                query=f"Is the text {text_align}-aligned?",
                element_id=element.id,
                element_selector=selector,
                category="text_alignment",
                expected_answer="yes",
                metadata={"property": "text-align", "value": text_align}
            )
            queries.append(query)
        
        # Infer alignment from classes
        for class_name in element.classes:
            if 'center' in class_name.lower():
                queries.append(GeneratedQuery(
                    query="Is the text center-aligned?",
                    element_id=element.id,
                    category="text_alignment",
                    confidence=0.8,
                    metadata={"inferred_from": f"class '{class_name}'"}
                ))
            elif 'right' in class_name.lower():
                queries.append(GeneratedQuery(
                    query="Is the text right-aligned?",
                    element_id=element.id,
                    category="text_alignment", 
                    confidence=0.8,
                    metadata={"inferred_from": f"class '{class_name}'"}
                ))
        
        return queries
    
    def _generate_styling_queries(self, element: ElementInfo) -> List[GeneratedQuery]:
        """Generate queries about text styling."""
        queries = []
        
        if not element.text_content:
            return queries
        
        # Font weight
        font_weight = element.computed_styles.get('font-weight')
        if font_weight == 'bold' or element.tag in ['b', 'strong']:
            queries.append(GeneratedQuery(
                query="Is the text bold?",
                element_id=element.id,
                category="text_styling",
                expected_answer="yes",
                metadata={"property": "font-weight"}
            ))
        
        # Font style
        font_style = element.computed_styles.get('font-style')
        if font_style == 'italic' or element.tag in ['i', 'em']:
            queries.append(GeneratedQuery(
                query="Is the text italic?",
                element_id=element.id,
                category="text_styling",
                expected_answer="yes",
                metadata={"property": "font-style"}
            ))
        
        # Text decoration
        text_decoration = element.computed_styles.get('text-decoration')
        if text_decoration:
            if 'underline' in text_decoration or element.tag == 'u':
                queries.append(GeneratedQuery(
                    query="Is the text underlined?",
                    element_id=element.id,
                    category="text_styling",
                    expected_answer="yes",
                    metadata={"property": "text-decoration"}
                ))
            elif 'line-through' in text_decoration or element.tag in ['s', 'del']:
                queries.append(GeneratedQuery(
                    query="Is the text struck through?",
                    element_id=element.id,
                    category="text_styling",
                    expected_answer="yes",
                    metadata={"property": "text-decoration"}
                ))
        
        return queries
    
    def _generate_layout_queries(self, element: ElementInfo) -> List[GeneratedQuery]:
        """Generate queries about layout and positioning."""
        queries = []
        
        # Display type
        display = element.computed_styles.get('display')
        if display:
            if display == 'flex':
                queries.append(GeneratedQuery(
                    query="Is this element using flexbox layout?",
                    element_id=element.id,
                    category="layout",
                    expected_answer="yes",
                    metadata={"property": "display", "value": display}
                ))
                
                # Flex direction
                flex_direction = element.computed_styles.get('flex-direction', 'row')
                if flex_direction != 'row':
                    direction_name = flex_direction.replace('-', ' ')
                    queries.append(GeneratedQuery(
                        query=f"Are the flex items arranged in {direction_name} direction?",
                        element_id=element.id,
                        category="layout",
                        expected_answer="yes",
                        metadata={"property": "flex-direction", "value": flex_direction}
                    ))
            
            elif display == 'grid':
                queries.append(GeneratedQuery(
                    query="Is this element using CSS Grid layout?",
                    element_id=element.id,
                    category="layout",
                    expected_answer="yes",
                    metadata={"property": "display", "value": display}
                ))
        
        # Position
        position = element.computed_styles.get('position')
        if position and position != 'static':
            queries.append(GeneratedQuery(
                query=f"Is this element positioned {position}?",
                element_id=element.id,
                category="positioning",
                expected_answer="yes",
                metadata={"property": "position", "value": position}
            ))
        
        # Float
        float_value = element.computed_styles.get('float')
        if float_value and float_value != 'none':
            queries.append(GeneratedQuery(
                query=f"Is this element floated to the {float_value}?",
                element_id=element.id,
                category="positioning",
                expected_answer="yes",
                metadata={"property": "float", "value": float_value}
            ))
        
        return queries
    
    def _generate_color_queries(self, element: ElementInfo) -> List[GeneratedQuery]:
        """Generate queries about colors and visual appearance."""
        queries = []
        
        # Text color
        color = element.computed_styles.get('color')
        if color and color != 'initial' and color != 'inherit':
            queries.append(GeneratedQuery(
                query=f"Is the text color {self._describe_color(color)}?",
                element_id=element.id,
                category="color",
                confidence=0.8,  # Color matching can be subjective
                metadata={"property": "color", "value": color}
            ))
        
        # Background color
        bg_color = element.computed_styles.get('background-color')
        if bg_color and bg_color not in ['transparent', 'initial', 'inherit']:
            queries.append(GeneratedQuery(
                query=f"Is the background color {self._describe_color(bg_color)}?",
                element_id=element.id,
                category="color",
                confidence=0.8,
                metadata={"property": "background-color", "value": bg_color}
            ))
        
        return queries
    
    def _generate_accessibility_queries(self, element: ElementInfo) -> List[GeneratedQuery]:
        """Generate queries about accessibility features."""
        queries = []
        
        # ARIA labels
        if 'aria-label' in element.attributes:
            queries.append(GeneratedQuery(
                query="Does this element have an accessible label?",
                element_id=element.id,
                category="accessibility",
                expected_answer="yes",
                metadata={"aria_feature": "aria-label"}
            ))
        
        # Form labels
        if element.tag == 'input' and element.id:
            queries.append(GeneratedQuery(
                query="Is this form input properly labeled?",
                element_id=element.id,
                category="accessibility",
                confidence=0.9,
                metadata={"check_type": "form_label"}
            ))
        
        # Focus indicators
        if element.tag in ['button', 'input', 'select', 'textarea', 'a']:
            queries.append(GeneratedQuery(
                query="Does this interactive element have a visible focus indicator?",
                element_id=element.id,
                category="accessibility",
                confidence=0.8,
                metadata={"check_type": "focus_indicator"}
            ))
        
        return queries
    
    def _generate_semantic_queries(self, element: ElementInfo) -> List[GeneratedQuery]:
        """Generate queries about semantic markup."""
        queries = []
        
        if element.tag in self.SEMANTIC_ELEMENTS:
            queries.append(GeneratedQuery(
                query=f"Is this content properly marked up as a {element.tag} element?",
                element_id=element.id,
                category="semantic_markup",
                expected_answer="yes",
                metadata={"semantic_element": element.tag}
            ))
        
        # Heading hierarchy
        if element.tag.startswith('h') and element.tag[1:].isdigit():
            level = element.tag[1:]
            queries.append(GeneratedQuery(
                query=f"Is this heading at the correct level {level}?",
                element_id=element.id,
                category="semantic_markup",
                confidence=0.9,
                metadata={"heading_level": level}
            ))
        
        return queries
    
    def _generate_relationship_queries(self, elements: List[ElementInfo]) -> List[GeneratedQuery]:
        """Generate queries about relationships between elements."""
        queries = []
        
        # Find elements with similar roles for comparison
        by_tag = {}
        for element in elements:
            if element.tag not in by_tag:
                by_tag[element.tag] = []
            by_tag[element.tag].append(element)
        
        # Generate size/positioning comparison queries
        for tag, tag_elements in by_tag.items():
            if len(tag_elements) >= 2 and tag in ['div', 'section', 'article']:
                queries.append(GeneratedQuery(
                    query=f"Are the {tag} elements properly aligned?",
                    category="layout_relationship",
                    confidence=0.7,
                    metadata={"comparison_type": "alignment", "element_count": len(tag_elements)}
                ))
        
        return queries
    
    def _describe_color(self, color_value: str) -> str:
        """Convert color values to descriptive names."""
        color_map = {
            '#000000': 'black',
            '#ffffff': 'white',
            '#ff0000': 'red',
            '#00ff00': 'green',
            '#0000ff': 'blue',
            '#ffff00': 'yellow',
            '#ff00ff': 'magenta',
            '#00ffff': 'cyan',
            'rgb(0,0,0)': 'black',
            'rgb(255,255,255)': 'white',
            'rgb(255,0,0)': 'red',
            'transparent': 'transparent'
        }
        
        color_lower = color_value.lower().replace(' ', '')
        return color_map.get(color_lower, color_value)


def generate_queries_from_file(html_path: str) -> List[GeneratedQuery]:
    """Convenience function to generate queries from an HTML file.
    
    Parameters
    ----------
    html_path : str
        Path to HTML file
        
    Returns
    -------
    List[GeneratedQuery]
        Generated test queries
    """
    generator = QueryGenerator()
    return generator.generate_queries_from_file(html_path)