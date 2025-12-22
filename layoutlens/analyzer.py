"""
Enhanced vision analyzer using OpenAI's GPT-4 Vision API.

This module provides intelligent visual analysis of UI screenshots
with natural language queries and structured responses.
"""

import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import openai
from pydantic import BaseModel, Field, ValidationError

from .logger import get_logger
from .prompts import Instructions, PromptTemplate
from .prompts.experts import AccessibilityExpert


class VisionAnalysisResponse(BaseModel):
    """Pydantic model for vision analysis responses."""

    answer: str = Field(description="Direct answer to the analysis question")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reasoning: str = Field(description="Detailed explanation of the analysis")

    @classmethod
    def from_raw_response(cls, raw_response: str) -> "VisionAnalysisResponse":
        """Parse raw LLM response into validated structure."""
        # Try JSON first
        json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return cls(**data)
            except (json.JSONDecodeError, ValidationError):
                pass

        # Fallback: treat as unstructured text
        return cls(
            answer=raw_response.strip(),
            confidence=0.3,  # Low confidence for unparseable responses
            reasoning="Response was not in expected JSON format",
        )


class VisionAnalyzer:
    """
    AI-powered visual analyzer for UI screenshots.

    Uses OpenAI's GPT-4 Vision to analyze screenshots and answer
    natural language questions about UI design, usability, and quality.
    """

    def __init__(
        self, api_key: str, model: str = "gpt-4o-mini", max_tokens: int | None = None, temperature: float = 0.1
    ):
        """
        Initialize the vision analyzer.

        Parameters
        ----------
        api_key : str
            OpenAI API key
        model : str, default "gpt-4o-mini"
            OpenAI model to use (gpt-4o, gpt-4o-mini)
        max_tokens : int, optional
            Maximum tokens in response. If None, uses model default.
        temperature : float, default 0.1
            Temperature for response generation (0.0-2.0)
        """
        self.logger = get_logger("vision.analyzer")

        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.logger.info(
            f"VisionAnalyzer initialized with model: {model}, max_tokens: {max_tokens}, temperature: {temperature}"
        )
        self.logger.debug(f"OpenAI client created successfully")

    def analyze_screenshot(
        self,
        screenshot_path: str,
        query: str,
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
    ) -> dict[str, Any]:
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
        self.logger.debug(f"Starting analysis of screenshot: {screenshot_path}")
        self.logger.debug(f"Query: {query[:100]}..." if len(query) > 100 else f"Query: {query}")

        if not Path(screenshot_path).exists():
            self.logger.error(f"Screenshot file not found: {screenshot_path}")
            raise FileNotFoundError(f"Screenshot not found: {screenshot_path}")

        # Encode image to base64
        try:
            image_b64 = self._encode_image(screenshot_path)
            self.logger.debug(f"Successfully encoded image to base64: {len(image_b64)} characters")
        except Exception as e:
            self.logger.error(f"Failed to encode image {screenshot_path}: {e}")
            raise

        # Build expert prompt using template system
        template = self._get_prompt_template(instructions)

        # Convert context dict to Instructions for template rendering
        if context and not instructions:
            instructions = Instructions(user_context=context, focus_areas=context.get("focus_areas", []))

        system_prompt, user_prompt = template.render(query, instructions)

        self.logger.debug("Built prompts for OpenAI API call")

        try:
            self.logger.debug(f"Making API call to {self.model}")
            # Build API call parameters
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
                "temperature": self.temperature,
            }

            # Only add max_tokens if specified (let model use its default otherwise)
            if self.max_tokens is not None:
                api_params["max_tokens"] = self.max_tokens

            response = self.client.chat.completions.create(**api_params)

            raw_response = response.choices[0].message.content
            tokens_used = response.usage.total_tokens

            self.logger.info(f"API call successful - tokens used: {tokens_used}")
            self.logger.debug(f"Raw response length: {len(raw_response)} characters")

            # Parse structured response
            analysis = self._parse_response(raw_response)
            confidence = analysis.get("confidence", 0.8)

            self.logger.info(f"Analysis completed with confidence: {confidence}")

            return {
                "answer": analysis.get("answer", raw_response),
                "confidence": confidence,
                "reasoning": analysis.get("reasoning", "Analysis completed"),
                "metadata": {
                    "model": self.model,
                    "tokens_used": tokens_used,
                    "context": context or {},
                },
            }

        except Exception as e:
            self.logger.error(f"API call failed: {e}")
            return {
                "answer": f"Error during analysis: {str(e)}",
                "confidence": 0.0,
                "reasoning": "Analysis failed due to API error",
                "metadata": {"error": str(e)},
            }

    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _get_prompt_template(self, instructions: Instructions | None = None) -> PromptTemplate:
        """Get appropriate prompt template based on instructions."""
        if instructions and instructions.expert_persona == "accessibility_expert":
            expert = AccessibilityExpert()
            return expert.get_template()

        # Default general UI analysis template
        return PromptTemplate(
            name="general_ui_analysis",
            description="General UI/UX analysis for visual design evaluation",
            system_prompt="""You are an expert UI/UX analyst specializing in visual design evaluation.

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

Format your response as JSON:
{
    "answer": "[Direct answer to the question]",
    "confidence": [0.0-1.0 confidence score],
    "reasoning": "[Detailed explanation of your analysis]"
}""",
            user_prompt_template="Please analyze this UI screenshot and answer: {query}",
        )

    def _parse_response(self, raw_response: str) -> dict[str, Any]:
        """Parse structured response using Pydantic validation."""
        response = VisionAnalysisResponse.from_raw_response(raw_response)
        return response.model_dump()

    def analyze_multiple_screenshots(
        self,
        screenshot_paths: list[str],
        query: str,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Analyze multiple screenshots with the same query.

        Parameters
        ----------
        screenshot_paths : list[str]
            List of screenshot file paths
        query : str
            Natural language question
        context : dict, optional
            Additional context

        Returns
        -------
        list[dict]
            List of analysis results
        """
        results = []
        for screenshot_path in screenshot_paths:
            result = self.analyze_screenshot(screenshot_path, query, context)
            result["screenshot_path"] = screenshot_path
            results.append(result)

        return results
