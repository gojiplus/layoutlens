"""
Layout comparison system for analyzing multiple screenshots.

This module provides intelligent comparison of multiple UI screenshots
to detect differences, consistency issues, and design variations.
"""

import base64
from typing import List, Dict, Any, Optional
from pathlib import Path

from .analyzer import VisionAnalyzer


class LayoutComparator:
    """
    Compare multiple UI screenshots to detect differences and consistency.
    
    Uses AI vision analysis to intelligently compare layouts, detect
    changes, and assess design consistency across multiple screenshots.
    """
    
    def __init__(self, analyzer: VisionAnalyzer):
        """
        Initialize layout comparator.
        
        Parameters
        ----------
        analyzer : VisionAnalyzer
            Vision analyzer instance for AI-powered analysis
        """
        self.analyzer = analyzer
    
    def compare_layouts(
        self,
        screenshot_paths: list[str],
        query: str = "Are these layouts consistent?",
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Compare multiple screenshots with a natural language query.
        
        Parameters
        ----------
        screenshot_paths : list[str]
            List of screenshot file paths to compare
        query : str, default "Are these layouts consistent?"
            Natural language question for comparison
        context : dict, optional
            Additional context for analysis
            
        Returns
        -------
        dict
            Comparison results with answer, confidence, and reasoning
        """
        if len(screenshot_paths) < 2:
            raise ValueError("At least 2 screenshots required for comparison")
        
        # Validate all files exist
        for path in screenshot_paths:
            if not Path(path).exists():
                raise FileNotFoundError(f"Screenshot not found: {path}")
        
        # Encode all images to base64
        images_b64 = []
        for path in screenshot_paths:
            with open(path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')
                images_b64.append(img_b64)
        
        # Build comparison prompt
        system_prompt = self._build_comparison_system_prompt(context)
        user_prompt = self._build_comparison_user_prompt(query, len(screenshot_paths), context)
        
        try:
            # Prepare messages with multiple images
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt
                        }
                    ]
                }
            ]
            
            # Add all images to the message
            for i, img_b64 in enumerate(images_b64):
                messages[1]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_b64}",
                        "detail": "high"
                    }
                })
            
            response = self.analyzer.client.chat.completions.create(
                model=self.analyzer.model,
                messages=messages,
                max_tokens=1500,
                temperature=0.1
            )
            
            raw_response = response.choices[0].message.content
            
            # Parse structured response
            analysis = self.analyzer._parse_response(raw_response)
            
            return {
                "answer": analysis.get("answer", raw_response),
                "confidence": analysis.get("confidence", 0.8),
                "reasoning": analysis.get("reasoning", "Comparison completed"),
                "metadata": {
                    "model": self.analyzer.model,
                    "tokens_used": response.usage.total_tokens,
                    "screenshot_count": len(screenshot_paths),
                    "context": context or {}
                }
            }
            
        except Exception as e:
            return {
                "answer": f"Error during comparison: {str(e)}",
                "confidence": 0.0,
                "reasoning": "Comparison failed due to API error",
                "metadata": {"error": str(e)}
            }
    
    def compare_before_after(
        self,
        before_path: str,
        after_path: str,
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Compare before/after screenshots for changes.
        
        Parameters
        ----------
        before_path : str
            Path to "before" screenshot
        after_path : str
            Path to "after" screenshot
        context : dict, optional
            Additional context
            
        Returns
        -------
        dict
            Comparison analysis focusing on changes and improvements
        """
        query = """
        Compare these before and after screenshots:
        
        1. What are the main visual differences?
        2. Which changes improve the user experience?
        3. Are there any regressions or issues introduced?
        4. How do the changes affect usability and accessibility?
        5. Overall, is this a positive or negative change?
        
        Provide specific feedback on the design changes.
        """
        
        return self.compare_layouts([before_path, after_path], query, context)
    
    def check_cross_browser_consistency(
        self,
        screenshot_paths: list[str],
        browser_names: list[str],
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Check consistency across different browsers.
        
        Parameters
        ----------
        screenshot_paths : list[str]
            Screenshots from different browsers
        browser_names : list[str]
            Names of browsers corresponding to screenshots
        context : dict, optional
            Additional context
            
        Returns
        -------
        dict
            Cross-browser consistency analysis
        """
        if len(screenshot_paths) != len(browser_names):
            raise ValueError("Number of screenshots must match number of browser names")
        
        browser_info = ", ".join(f"{i+1}. {name}" for i, name in enumerate(browser_names))
        
        query = f"""
        Compare these screenshots from different browsers ({browser_info}):
        
        1. Are the layouts consistent across browsers?
        2. Are there any significant rendering differences?
        3. Do all interactive elements appear correctly?
        4. Are fonts and styling consistent?
        5. Are there any browser-specific issues?
        
        Identify any cross-browser compatibility problems.
        """
        
        enhanced_context = dict(context or {})
        enhanced_context["browsers"] = browser_names
        
        return self.compare_layouts(screenshot_paths, query, enhanced_context)
    
    def check_responsive_consistency(
        self,
        screenshot_paths: list[str],
        viewport_names: list[str],
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Check responsive design consistency across viewports.
        
        Parameters
        ----------
        screenshot_paths : list[str]
            Screenshots from different viewports
        viewport_names : list[str]
            Names of viewports corresponding to screenshots
        context : dict, optional
            Additional context
            
        Returns
        -------
        dict
            Responsive design consistency analysis
        """
        if len(screenshot_paths) != len(viewport_names):
            raise ValueError("Number of screenshots must match number of viewport names")
        
        viewport_info = ", ".join(f"{i+1}. {name}" for i, name in enumerate(viewport_names))
        
        query = f"""
        Compare these responsive design screenshots from different viewports ({viewport_info}):
        
        1. Does the layout adapt appropriately to each screen size?
        2. Are touch targets adequately sized for mobile viewports?
        3. Is content properly organized and readable across devices?
        4. Are navigation patterns consistent but appropriate for each device?
        5. Are there any responsive design issues or broken layouts?
        
        Evaluate the responsive design quality and identify improvements.
        """
        
        enhanced_context = dict(context or {})
        enhanced_context["viewports"] = viewport_names
        enhanced_context["analysis_type"] = "responsive"
        
        return self.compare_layouts(screenshot_paths, query, enhanced_context)
    
    def _build_comparison_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        """Build system prompt for comparison analysis."""
        
        base_prompt = """You are an expert UI/UX analyst specializing in comparative visual design analysis.

Your role is to analyze multiple UI screenshots and provide detailed comparative feedback based on:
- Visual consistency and design coherence
- User experience differences and improvements
- Layout adaptation and responsiveness  
- Accessibility and usability variations
- Design system compliance

When comparing screenshots:
1. Look for both obvious and subtle differences
2. Assess the impact of changes on user experience
3. Consider consistency across different contexts (devices, browsers, etc.)
4. Provide specific, actionable feedback
5. Explain your confidence level and reasoning

Format your response as:
ANSWER: [Direct answer to the comparison question]
CONFIDENCE: [0.0-1.0 confidence score]
REASONING: [Detailed explanation comparing the screenshots]"""

        if context:
            contextual_info = []
            if context.get("browsers"):
                contextual_info.append(f"Browser comparison: {context['browsers']}")
            if context.get("viewports"):
                contextual_info.append(f"Viewport comparison: {context['viewports']}")
            if context.get("analysis_type"):
                contextual_info.append(f"Analysis focus: {context['analysis_type']}")
            
            if contextual_info:
                base_prompt += f"\n\nContext for this comparison:\n" + "\n".join(f"- {info}" for info in contextual_info)
        
        return base_prompt
    
    def _build_comparison_user_prompt(
        self, 
        query: str, 
        image_count: int, 
        context: dict[str, Any] | None = None
    ) -> str:
        """Build user prompt for comparison."""
        
        prompt = f"Please compare these {image_count} UI screenshots and answer: {query}"
        
        if context:
            if context.get("focus_areas"):
                prompt += f"\n\nPay special attention to: {context['focus_areas']}"
        
        prompt += "\n\nAnalyze the images in order and provide your response in the specified format."
        
        return prompt