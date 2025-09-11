"""
Enhanced vision analyzer using OpenAI's GPT-4 Vision API.

This module provides intelligent visual analysis of UI screenshots
with natural language queries and structured responses.
"""

import base64
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class VisionAnalyzer:
    """
    AI-powered visual analyzer for UI screenshots.
    
    Uses OpenAI's GPT-4 Vision to analyze screenshots and answer
    natural language questions about UI design, usability, and quality.
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize the vision analyzer.
        
        Parameters
        ----------
        api_key : str
            OpenAI API key
        model : str, default "gpt-4o-mini"  
            OpenAI model to use (gpt-4o, gpt-4o-mini)
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not available. Run: pip install openai")
        
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
    
    def analyze_screenshot(
        self,
        screenshot_path: str,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a screenshot with a natural language query.
        
        Parameters
        ----------
        screenshot_path : str
            Path to screenshot image file
        query : str
            Natural language question about the UI
        context : dict, optional
            Additional context (viewport, user_type, browser, etc.)
            
        Returns
        -------
        dict
            Analysis results with answer, confidence, and reasoning
        """
        if not Path(screenshot_path).exists():
            raise FileNotFoundError(f"Screenshot not found: {screenshot_path}")
        
        # Encode image to base64
        image_b64 = self._encode_image(screenshot_path)
        
        # Build context-aware prompt
        system_prompt = self._build_system_prompt(context)
        user_prompt = self._build_user_prompt(query, context)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
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
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1  # Low temperature for consistent analysis
            )
            
            raw_response = response.choices[0].message.content
            
            # Parse structured response
            analysis = self._parse_response(raw_response)
            
            return {
                "answer": analysis.get("answer", raw_response),
                "confidence": analysis.get("confidence", 0.8),
                "reasoning": analysis.get("reasoning", "Analysis completed"),
                "metadata": {
                    "model": self.model,
                    "tokens_used": response.usage.total_tokens,
                    "context": context or {}
                }
            }
            
        except Exception as e:
            return {
                "answer": f"Error during analysis: {str(e)}",
                "confidence": 0.0,
                "reasoning": "Analysis failed due to API error",
                "metadata": {"error": str(e)}
            }
    
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def _build_system_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Build context-aware system prompt."""
        base_prompt = """You are an expert UI/UX analyst specializing in visual design evaluation. 

Your role is to analyze user interface screenshots and provide detailed, actionable feedback based on:
- Visual design principles (hierarchy, contrast, spacing, alignment)
- User experience best practices (usability, accessibility, conversion optimization)
- Modern web design standards (responsive design, mobile-first, performance)
- Accessibility guidelines (WCAG compliance, inclusive design)

When analyzing screenshots:
1. Be specific and actionable in your feedback
2. Reference concrete visual elements you observe
3. Consider the context and user needs
4. Provide confidence scores for your assessments
5. Explain your reasoning clearly

Format your response as:
ANSWER: [Direct answer to the question]
CONFIDENCE: [0.0-1.0 confidence score]  
REASONING: [Detailed explanation of your analysis]"""

        if context:
            contextual_info = []
            if context.get("viewport"):
                contextual_info.append(f"Viewport: {context['viewport']}")
            if context.get("user_type"):
                contextual_info.append(f"Target user: {context['user_type']}")
            if context.get("browser"):
                contextual_info.append(f"Browser: {context['browser']}")
            if context.get("accessibility"):
                contextual_info.append("Focus on accessibility compliance")
            
            if contextual_info:
                base_prompt += f"\n\nContext for this analysis:\n" + "\n".join(f"- {info}" for info in contextual_info)
        
        return base_prompt
    
    def _build_user_prompt(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build user query prompt."""
        prompt = f"Please analyze this UI screenshot and answer: {query}"
        
        if context and context.get("specific_elements"):
            prompt += f"\n\nPay special attention to: {context['specific_elements']}"
        
        prompt += "\n\nProvide your response in the format specified in the system prompt."
        
        return prompt
    
    def _parse_response(self, raw_response: str) -> Dict[str, Any]:
        """Parse structured response from the model."""
        try:
            lines = raw_response.strip().split('\n')
            parsed = {}
            
            current_field = None
            current_content = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('ANSWER:'):
                    if current_field:
                        parsed[current_field] = '\n'.join(current_content).strip()
                    current_field = 'answer'
                    current_content = [line[7:].strip()]
                elif line.startswith('CONFIDENCE:'):
                    if current_field:
                        parsed[current_field] = '\n'.join(current_content).strip()
                    current_field = 'confidence'
                    confidence_str = line[11:].strip()
                    try:
                        parsed['confidence'] = float(confidence_str)
                    except ValueError:
                        parsed['confidence'] = 0.8
                    current_field = None
                    current_content = []
                elif line.startswith('REASONING:'):
                    if current_field:
                        parsed[current_field] = '\n'.join(current_content).strip()
                    current_field = 'reasoning'
                    current_content = [line[10:].strip()]
                elif current_field and line:
                    current_content.append(line)
            
            # Handle last field
            if current_field and current_content:
                parsed[current_field] = '\n'.join(current_content).strip()
            
            # Ensure all required fields exist
            if 'answer' not in parsed:
                parsed['answer'] = raw_response
            if 'confidence' not in parsed:
                parsed['confidence'] = 0.8
            if 'reasoning' not in parsed:
                parsed['reasoning'] = "Analysis completed successfully"
                
            return parsed
            
        except Exception:
            # Fallback to raw response if parsing fails
            return {
                "answer": raw_response,
                "confidence": 0.8,
                "reasoning": "Response parsing failed, using raw output"
            }
    
    def analyze_multiple_screenshots(
        self,
        screenshot_paths: List[str],
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple screenshots with the same query.
        
        Parameters
        ----------
        screenshot_paths : List[str]
            List of screenshot file paths
        query : str
            Natural language question
        context : dict, optional
            Additional context
            
        Returns
        -------
        List[dict]
            List of analysis results
        """
        results = []
        for screenshot_path in screenshot_paths:
            result = self.analyze_screenshot(screenshot_path, query, context)
            result['screenshot_path'] = screenshot_path
            results.append(result)
        
        return results