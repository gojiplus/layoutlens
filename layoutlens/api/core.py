"""
Simple LayoutLens API for natural language UI testing.

This is the main entry point for the new simplified API that focuses on
real-world developer workflows and live website testing.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from urllib.parse import urlparse

# Import vision components
from ..vision.analyzer import VisionAnalyzer
from ..vision.capture import URLCapture
from ..vision.comparator import LayoutComparator


@dataclass
class AnalysisResult:
    """Result from analyzing a single URL or screenshot."""
    
    source: str
    query: str
    answer: str
    confidence: float
    reasoning: str
    screenshot_path: Optional[str] = None
    viewport: str = "desktop"
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass  
class ComparisonResult:
    """Result from comparing multiple sources."""
    
    sources: List[str]
    query: str
    answer: str
    confidence: float
    reasoning: str
    individual_analyses: List[AnalysisResult] = field(default_factory=list)
    screenshot_paths: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result from batch analysis."""
    
    results: List[AnalysisResult]
    total_queries: int
    successful_queries: int
    average_confidence: float
    total_execution_time: float
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


class LayoutLens:
    """
    Simple API for AI-powered UI testing with natural language.
    
    This class provides an intuitive interface for analyzing websites and
    screenshots using natural language queries, designed for developer
    workflows and CI/CD integration.
    
    Examples
    --------
    >>> lens = LayoutLens(api_key="sk-...")
    >>> result = lens.analyze("https://example.com", "Is the navigation clearly visible?")
    >>> print(result.answer)
    
    >>> # Compare two designs
    >>> result = lens.compare(
    ...     ["before.png", "after.png"], 
    ...     "Are these layouts consistent?"
    ... )
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        output_dir: str = "layoutlens_output"
    ):
        """
        Initialize LayoutLens with OpenAI credentials.
        
        Parameters
        ----------
        api_key : str, optional
            OpenAI API key. If not provided, will try OPENAI_API_KEY env var
        model : str, default "gpt-4o-mini"
            OpenAI model to use for analysis
        output_dir : str, default "layoutlens_output"
            Directory for storing screenshots and results
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key parameter.")
        
        self.model = model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.analyzer = VisionAnalyzer(
            api_key=self.api_key,
            model=self.model
        )
        self.capture = URLCapture(
            output_dir=str(self.output_dir / "screenshots")
        )
        self.comparator = LayoutComparator(
            analyzer=self.analyzer
        )
    
    def analyze(
        self,
        source: Union[str, Path],
        query: str,
        viewport: str = "desktop",
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        Analyze a URL or screenshot with a natural language query.
        
        Parameters
        ----------
        source : str or Path
            URL to analyze or path to screenshot image
        query : str  
            Natural language question about the UI
        viewport : str, default "desktop"
            Viewport size for URL capture ("desktop", "mobile", "tablet")
        context : dict, optional
            Additional context for analysis (user_type, browser, etc.)
            
        Returns
        -------
        AnalysisResult
            Detailed analysis with answer, confidence, and reasoning
            
        Examples
        --------
        >>> result = lens.analyze("https://github.com", "Is the search bar easy to find?")
        >>> result = lens.analyze("screenshot.png", "Are the buttons large enough for mobile?")
        """
        start_time = time.time()
        
        try:
            # Determine if source is URL or image file
            if self._is_url(source):
                # Capture screenshot from URL
                screenshot_path = self.capture.capture_url(
                    url=str(source),
                    viewport=viewport
                )
            else:
                # Use existing image file
                screenshot_path = str(source)
                if not Path(screenshot_path).exists():
                    raise FileNotFoundError(f"Screenshot file not found: {screenshot_path}")
            
            # Analyze with vision model
            analysis = self.analyzer.analyze_screenshot(
                screenshot_path=screenshot_path,
                query=query,
                context=context or {}
            )
            
            execution_time = time.time() - start_time
            
            return AnalysisResult(
                source=str(source),
                query=query,
                answer=analysis['answer'],
                confidence=analysis['confidence'],
                reasoning=analysis['reasoning'],
                screenshot_path=screenshot_path,
                viewport=viewport,
                execution_time=execution_time,
                metadata=analysis.get('metadata', {})
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return AnalysisResult(
                source=str(source),
                query=query,
                answer=f"Error during analysis: {str(e)}",
                confidence=0.0,
                reasoning="Analysis failed due to error",
                execution_time=execution_time,
                metadata={"error": str(e)}
            )
    
    def compare(
        self,
        sources: List[Union[str, Path]],
        query: str = "Are these layouts consistent?",
        viewport: str = "desktop",
        context: Optional[Dict[str, Any]] = None
    ) -> ComparisonResult:
        """
        Compare multiple URLs or screenshots.
        
        Parameters
        ----------
        sources : List[str or Path]
            List of URLs or screenshot paths to compare
        query : str, default "Are these layouts consistent?"
            Natural language question for comparison
        viewport : str, default "desktop"
            Viewport size for URL captures
        context : dict, optional
            Additional context for analysis
            
        Returns
        -------
        ComparisonResult
            Comparison analysis with overall assessment
            
        Examples
        --------
        >>> result = lens.compare([
        ...     "https://mysite.com/before",
        ...     "https://mysite.com/after"
        ... ], "Did the redesign improve the user experience?")
        """
        start_time = time.time()
        
        try:
            # Analyze each source individually first
            individual_results = []
            screenshot_paths = []
            
            for source in sources:
                if self._is_url(source):
                    screenshot_path = self.capture.capture_url(str(source), viewport)
                else:
                    screenshot_path = str(source)
                
                screenshot_paths.append(screenshot_path)
                
                # Individual analysis
                individual_result = self.analyze(source, query, viewport, context)
                individual_results.append(individual_result)
            
            # Comparative analysis
            comparison = self.comparator.compare_layouts(
                screenshot_paths=screenshot_paths,
                query=query,
                context=context or {}
            )
            
            execution_time = time.time() - start_time
            
            return ComparisonResult(
                sources=[str(s) for s in sources],
                query=query,
                answer=comparison['answer'],
                confidence=comparison['confidence'],
                reasoning=comparison['reasoning'],
                individual_analyses=individual_results,
                screenshot_paths=screenshot_paths,
                execution_time=execution_time,
                metadata=comparison.get('metadata', {})
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return ComparisonResult(
                sources=[str(s) for s in sources],
                query=query,
                answer=f"Error during comparison: {str(e)}",
                confidence=0.0,
                reasoning="Comparison failed due to error",
                execution_time=execution_time,
                metadata={"error": str(e)}
            )
    
    def analyze_batch(
        self,
        sources: List[Union[str, Path]],
        queries: List[str],
        viewport: str = "desktop",
        context: Optional[Dict[str, Any]] = None
    ) -> BatchResult:
        """
        Analyze multiple sources with multiple queries efficiently.
        
        Parameters
        ----------
        sources : List[str or Path]
            List of URLs or screenshot paths
        queries : List[str]
            List of natural language queries
        viewport : str, default "desktop"
            Viewport size for URL captures
        context : dict, optional
            Additional context for analysis
            
        Returns
        -------
        BatchResult
            Batch analysis results with aggregated metrics
        """
        start_time = time.time()
        results = []
        
        for source in sources:
            for query in queries:
                result = self.analyze(source, query, viewport, context)
                results.append(result)
        
        # Calculate aggregate metrics
        successful_results = [r for r in results if r.confidence > 0]
        total_execution_time = time.time() - start_time
        
        return BatchResult(
            results=results,
            total_queries=len(results),
            successful_queries=len(successful_results),
            average_confidence=sum(r.confidence for r in successful_results) / len(successful_results) if successful_results else 0.0,
            total_execution_time=total_execution_time
        )
    
    def _is_url(self, source: Union[str, Path]) -> bool:
        """Check if source is a URL or file path."""
        if isinstance(source, Path):
            return False
        
        parsed = urlparse(str(source))
        return bool(parsed.scheme and parsed.netloc)

    # Developer convenience methods
    def check_accessibility(
        self,
        source: Union[str, Path],
        viewport: str = "desktop"
    ) -> AnalysisResult:
        """Quick accessibility check with common WCAG queries."""
        query = """
        Analyze this page for accessibility issues. Check:
        1. Color contrast and readability
        2. Button and link sizing for touch targets  
        3. Visual hierarchy and heading structure
        4. Form labels and input clarity
        5. Overall usability for users with disabilities
        
        Provide specific feedback on what works well and what needs improvement.
        """
        return self.analyze(source, query, viewport)
    
    def check_mobile_friendly(
        self,
        source: Union[str, Path]
    ) -> AnalysisResult:
        """Quick mobile responsiveness check."""
        query = """
        Evaluate this page for mobile usability:
        1. Are touch targets large enough (minimum 44px)?
        2. Is text readable without zooming?
        3. Is navigation accessible on small screens?
        4. Does content fit properly without horizontal scrolling?
        5. Are forms easy to use on mobile?
        
        Rate the mobile experience and suggest improvements.
        """
        return self.analyze(source, query, "mobile")
    
    def check_conversion_optimization(
        self,
        source: Union[str, Path],
        viewport: str = "desktop"
    ) -> AnalysisResult:
        """Check for conversion-focused design elements."""
        query = """
        Analyze this page for conversion optimization:
        1. Is the primary call-to-action prominent and clear?
        2. Is the value proposition immediately obvious?
        3. Are there any friction points in the user flow?
        4. Does the design build trust and credibility?
        5. Is the page focused or too cluttered?
        
        Provide specific recommendations to improve conversions.
        """
        return self.analyze(source, query, viewport)