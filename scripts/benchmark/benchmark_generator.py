"""Comprehensive benchmark data generation system.

This module creates systematic test cases covering various UI patterns,
layouts, and visual elements for thorough testing of the LayoutLens framework.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

from .template_engine import TemplateEngine


@dataclass
class TestCase:
    """Represents a single UI test case."""
    
    html_path: str
    dom_id: Optional[str] = None
    attribute: Optional[str] = None
    expected_behavior: Optional[str] = None
    query: Optional[str] = None
    category: str = "general"
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class TestSuite:
    """Collection of related test cases."""
    
    name: str
    description: str
    test_cases: List[TestCase] = field(default_factory=list)
    category: str = "general"


class BenchmarkGenerator:
    """Generates comprehensive benchmark datasets for UI testing.
    
    This class creates systematic test cases covering:
    - Text formatting and alignment
    - Layout patterns (flexbox, grid, positioning)
    - Color schemes and themes
    - Responsive design patterns
    - Interactive elements
    - Accessibility features
    """
    
    def __init__(self, output_dir: str = "generated_benchmarks"):
        """Initialize the benchmark generator.
        
        Parameters
        ----------
        output_dir : str
            Directory where benchmark files will be generated.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.template_engine = TemplateEngine()
        self.test_suites: List[TestSuite] = []
    
    def generate_text_formatting_suite(self) -> TestSuite:
        """Generate test cases for text formatting variations."""
        suite = TestSuite(
            name="text_formatting",
            description="Text alignment, styling, and formatting tests",
            category="typography"
        )
        
        # Text alignment tests
        alignments = ["left", "center", "right", "justify"]
        for align in alignments:
            html_content = self.template_engine.render_text_alignment(align)
            html_path = f"text_alignment_{align}.html"
            self._save_html(html_path, html_content)
            
            suite.test_cases.append(TestCase(
                html_path=html_path,
                dom_id="main_text",
                attribute="text-align",
                expected_behavior=align,
                query=f"Is the text {align}-aligned?",
                category="text_alignment",
                description=f"Test text {align} alignment"
            ))
        
        # Text styling tests
        styles = [
            ("bold", "font-weight: bold"),
            ("italic", "font-style: italic"),
            ("underline", "text-decoration: underline"),
            ("strikethrough", "text-decoration: line-through")
        ]
        
        for style_name, css_property in styles:
            html_content = self.template_engine.render_text_style(style_name, css_property)
            html_path = f"text_style_{style_name}.html"
            self._save_html(html_path, html_content)
            
            suite.test_cases.append(TestCase(
                html_path=html_path,
                dom_id="styled_text",
                attribute="style",
                expected_behavior=style_name,
                query=f"Is the text {style_name}?",
                category="text_styling",
                description=f"Test {style_name} text styling"
            ))
        
        return suite
    
    def generate_layout_suite(self) -> TestSuite:
        """Generate test cases for layout patterns."""
        suite = TestSuite(
            name="layout_patterns",
            description="Flexbox, grid, and positioning layout tests",
            category="layout"
        )
        
        # Flexbox layouts
        flex_patterns = [
            ("row", "flex-direction: row"),
            ("column", "flex-direction: column"),
            ("row_reverse", "flex-direction: row-reverse"),
            ("column_reverse", "flex-direction: column-reverse")
        ]
        
        for pattern_name, css_property in flex_patterns:
            html_content = self.template_engine.render_flexbox_layout(pattern_name, css_property)
            html_path = f"flexbox_{pattern_name}.html"
            self._save_html(html_path, html_content)
            
            suite.test_cases.append(TestCase(
                html_path=html_path,
                dom_id="flex_container",
                attribute="layout",
                expected_behavior=pattern_name,
                query=f"Are the items arranged in a {pattern_name.replace('_', ' ')} layout?",
                category="flexbox",
                description=f"Test {pattern_name} flexbox layout"
            ))
        
        # Grid layouts
        grid_patterns = [
            ("two_column", "grid-template-columns: 1fr 1fr"),
            ("three_column", "grid-template-columns: 1fr 1fr 1fr"),
            ("sidebar_main", "grid-template-columns: 250px 1fr"),
            ("asymmetric", "grid-template-columns: 1fr 2fr 1fr")
        ]
        
        for pattern_name, css_property in grid_patterns:
            html_content = self.template_engine.render_grid_layout(pattern_name, css_property)
            html_path = f"grid_{pattern_name}.html"
            self._save_html(html_path, html_content)
            
            suite.test_cases.append(TestCase(
                html_path=html_path,
                dom_id="grid_container", 
                attribute="layout",
                expected_behavior=pattern_name,
                query=f"Is this a {pattern_name.replace('_', ' ')} grid layout?",
                category="grid",
                description=f"Test {pattern_name} grid layout"
            ))
        
        return suite
    
    def generate_color_theme_suite(self) -> TestSuite:
        """Generate test cases for color schemes and themes."""
        suite = TestSuite(
            name="color_themes",
            description="Color schemes, contrast, and theme tests", 
            category="appearance"
        )
        
        themes = [
            ("light", {"bg": "#ffffff", "text": "#333333", "accent": "#007bff"}),
            ("dark", {"bg": "#1a1a1a", "text": "#ffffff", "accent": "#66b3ff"}),
            ("high_contrast", {"bg": "#000000", "text": "#ffffff", "accent": "#ffff00"}),
            ("sepia", {"bg": "#f4ecd8", "text": "#5c4b37", "accent": "#8b4513"})
        ]
        
        for theme_name, colors in themes:
            html_content = self.template_engine.render_themed_page(theme_name, colors)
            html_path = f"theme_{theme_name}.html"
            self._save_html(html_path, html_content)
            
            suite.test_cases.append(TestCase(
                html_path=html_path,
                dom_id="page_content",
                attribute="theme",
                expected_behavior=theme_name,
                query=f"Is this page using a {theme_name.replace('_', ' ')} theme?",
                category="theming",
                description=f"Test {theme_name} color theme",
                metadata={"colors": colors}
            ))
        
        return suite
    
    def generate_responsive_suite(self) -> TestSuite:
        """Generate test cases for responsive design patterns."""
        suite = TestSuite(
            name="responsive_design",
            description="Responsive breakpoints and adaptive layouts",
            category="responsive"
        )
        
        breakpoints = [
            ("mobile", 375, 667),
            ("tablet", 768, 1024),
            ("desktop", 1440, 900),
            ("wide", 1920, 1080)
        ]
        
        for device_name, width, height in breakpoints:
            html_content = self.template_engine.render_responsive_layout(device_name, width, height)
            html_path = f"responsive_{device_name}.html"
            self._save_html(html_path, html_content)
            
            suite.test_cases.append(TestCase(
                html_path=html_path,
                dom_id="responsive_container",
                attribute="layout",
                expected_behavior=f"responsive_{device_name}",
                query=f"Is the layout optimized for {device_name} viewport?",
                category="responsive",
                description=f"Test responsive layout for {device_name}",
                metadata={"viewport": {"width": width, "height": height}}
            ))
        
        return suite
    
    def generate_accessibility_suite(self) -> TestSuite:
        """Generate test cases for accessibility features."""
        suite = TestSuite(
            name="accessibility",
            description="ARIA labels, focus indicators, and accessibility tests",
            category="accessibility"
        )
        
        a11y_patterns = [
            ("focus_visible", "focus indicators visible"),
            ("high_contrast", "sufficient color contrast"),
            ("aria_labels", "proper ARIA labels"),
            ("semantic_markup", "semantic HTML structure")
        ]
        
        for pattern_name, description in a11y_patterns:
            html_content = self.template_engine.render_accessibility_pattern(pattern_name)
            html_path = f"a11y_{pattern_name}.html"
            self._save_html(html_path, html_content)
            
            suite.test_cases.append(TestCase(
                html_path=html_path,
                dom_id="accessible_content",
                attribute="accessibility",
                expected_behavior=pattern_name,
                query=f"Does the page have {description}?",
                category="accessibility",
                description=f"Test {pattern_name} accessibility feature"
            ))
        
        return suite
    
    def generate_all_suites(self) -> List[TestSuite]:
        """Generate all test suites."""
        suites = [
            self.generate_text_formatting_suite(),
            self.generate_layout_suite(),
            self.generate_color_theme_suite(),
            self.generate_responsive_suite(),
            self.generate_accessibility_suite()
        ]
        
        self.test_suites.extend(suites)
        return suites
    
    def export_to_csv(self, suite: TestSuite, filename: Optional[str] = None) -> str:
        """Export a test suite to CSV format."""
        if filename is None:
            filename = f"{suite.name}_benchmark.csv"
        
        csv_path = self.output_dir / filename
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['html_path', 'dom_id', 'attribute', 'expected_behavior', 'query', 'category', 'description']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for test_case in suite.test_cases:
                writer.writerow({
                    'html_path': test_case.html_path,
                    'dom_id': test_case.dom_id or '',
                    'attribute': test_case.attribute or '',
                    'expected_behavior': test_case.expected_behavior or '',
                    'query': test_case.query or '',
                    'category': test_case.category,
                    'description': test_case.description
                })
        
        return str(csv_path)
    
    def export_to_json(self, suite: TestSuite, filename: Optional[str] = None) -> str:
        """Export a test suite to JSON format."""
        if filename is None:
            filename = f"{suite.name}_benchmark.json"
            
        json_path = self.output_dir / filename
        
        suite_dict = {
            'name': suite.name,
            'description': suite.description,
            'category': suite.category,
            'test_cases': [
                {
                    'html_path': tc.html_path,
                    'dom_id': tc.dom_id,
                    'attribute': tc.attribute,
                    'expected_behavior': tc.expected_behavior,
                    'query': tc.query,
                    'category': tc.category,
                    'description': tc.description,
                    'metadata': tc.metadata
                }
                for tc in suite.test_cases
            ]
        }
        
        with open(json_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(suite_dict, jsonfile, indent=2, ensure_ascii=False)
        
        return str(json_path)
    
    def generate_comparison_pairs(self, suite: TestSuite) -> List[Dict[str, str]]:
        """Generate pairwise comparison test cases."""
        pairs = []
        test_cases = suite.test_cases
        
        for i, tc_a in enumerate(test_cases):
            for tc_b in test_cases[i+1:]:
                # Same category comparisons
                if tc_a.category == tc_b.category:
                    expected = "no" if tc_a.expected_behavior != tc_b.expected_behavior else "yes"
                    pairs.append({
                        'html_path_a': tc_a.html_path,
                        'html_path_b': tc_b.html_path,
                        'query': 'Do these two layouts look the same?',
                        'expected': expected,
                        'category': f"{tc_a.category}_comparison"
                    })
        
        return pairs
    
    def export_pairs_to_csv(self, pairs: List[Dict[str, str]], filename: str = "benchmark_pairs.csv") -> str:
        """Export comparison pairs to CSV format."""
        csv_path = self.output_dir / filename
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['html_path_a', 'html_path_b', 'query', 'expected', 'category']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for pair in pairs:
                writer.writerow(pair)
        
        return str(csv_path)
    
    def _save_html(self, filename: str, content: str) -> str:
        """Save HTML content to file."""
        html_path = self.output_dir / filename
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return str(html_path)


def main():
    """Generate comprehensive benchmark datasets."""
    generator = BenchmarkGenerator()
    
    print("Generating comprehensive UI test benchmarks...")
    
    # Generate all test suites
    suites = generator.generate_all_suites()
    
    # Export each suite
    for suite in suites:
        csv_path = generator.export_to_csv(suite)
        json_path = generator.export_to_json(suite)
        print(f"Generated {suite.name}: {len(suite.test_cases)} test cases")
        print(f"  CSV: {csv_path}")
        print(f"  JSON: {json_path}")
    
    # Generate and export comparison pairs
    all_pairs = []
    for suite in suites:
        pairs = generator.generate_comparison_pairs(suite)
        all_pairs.extend(pairs)
    
    pairs_path = generator.export_pairs_to_csv(all_pairs)
    print(f"\nGenerated {len(all_pairs)} comparison pairs: {pairs_path}")
    
    print(f"\nAll benchmark data saved to: {generator.output_dir}")


if __name__ == "__main__":
    main()