"""Simple LayoutLens API for natural language UI testing.

This is the main entry point for the new simplified API that focuses on
real-world developer workflows and live website testing.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, overload
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .batch import BatchRequest
    from .judge import JudgeResult
    from .test_suite import UITestResult, UITestSuite

# Import LiteLLM directly
try:
    from litellm import acompletion
except ImportError as e:
    raise ImportError("litellm is required. Install with: pip install litellm") from e

# Import deterministic accessibility engine
from ..a11y import AXE_VERSION, A11yReport, AxeAuditor

# Import shared browser lifecycle (single-session hybrid audits)
from ..browser import open_page

# Import caching
from ..cache import create_cache

# Import vision components
from ..capture import Capture

# Import custom exceptions
from ..exceptions import (
    AuthenticationError,
    LayoutFileNotFoundError,
    LayoutLensError,
    ValidationError,
)

# Import deterministic layout scorers
from ..layout import LayoutReport, LayoutScorer

# Import logging
from ..logger import get_logger, log_function_call, log_performance_metric

# Import per-model parameter policy
from ..param_policy import AUTO, _Auto, completion_params

# Import enhanced prompt system
from ..prompts import Instructions, get_expert

# Import types
from ..types import (
    ComplianceLevel,
    ComplianceLevelType,
    Expert,
    ExpertType,
    Viewport,
    ViewportType,
)

# Maps the provider strings accepted by LayoutLens(provider=...) to the
# environment variable that holds credentials for that provider. ``litellm`` maps
# to ``None``: it is a passthrough provider with no single canonical key, so
# LiteLLM resolves credentials from its own per-model env conventions at call time.
PROVIDER_API_KEY_ENV_VARS: dict[str, str | None] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "litellm": None,
}


def _dataclass_to_json(obj: Any) -> str:
    """Serialize a dataclass instance to an indented JSON string."""
    return json.dumps(asdict(obj), indent=2, default=str)


def _coerce_int(value: Any) -> int:
    """Coerce a token-count value to int, returning 0 if it is not numeric.

    Guards against providers (or test mocks) that leave an attribute as a
    non-numeric placeholder rather than a real count.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _read_usage(response: Any) -> dict[str, int]:
    """Read prompt/completion/total token counts from a response, 0 when absent.

    LiteLLM exposes ``prompt_tokens``/``completion_tokens``/``total_tokens`` on
    ``response.usage`` when the provider reports them; each defaults to 0 so
    downstream accounting always has all three keys.
    """
    usage = getattr(response, "usage", None)
    if not usage:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": _coerce_int(getattr(usage, "prompt_tokens", 0)),
        "completion_tokens": _coerce_int(getattr(usage, "completion_tokens", 0)),
        "total_tokens": _coerce_int(getattr(usage, "total_tokens", 0)),
    }


def _estimate_cost(
    model: str, prompt_tokens: int, completion_tokens: int
) -> float | None:
    """Estimate USD cost from token counts via litellm's price registry.

    Returns None when the model is unknown to litellm (e.g. local models),
    rather than reporting a fake $0.
    """
    if not (prompt_tokens or completion_tokens):
        return 0.0
    try:
        from litellm import cost_per_token

        prompt_cost, completion_cost = cost_per_token(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return round(prompt_cost + completion_cost, 6)
    except Exception:
        return None


@dataclass(slots=True)
class AnalysisResult:
    """Result from analyzing a single URL or screenshot."""

    source: str
    query: str
    answer: str
    confidence: float
    reasoning: str
    screenshot_path: str | None = None
    viewport: str = "desktop"
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Export result to JSON string."""
        return _dataclass_to_json(self)


@dataclass(slots=True)
class ComparisonResult:
    """Result from comparing multiple sources."""

    sources: list[str]
    query: str
    answer: str
    confidence: float
    reasoning: str
    individual_analyses: list[AnalysisResult] = field(default_factory=list)
    screenshot_paths: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Export result to JSON string."""
        return _dataclass_to_json(self)


@dataclass(slots=True)
class BatchResult:
    """Result from batch analysis."""

    results: list[AnalysisResult]
    total_queries: int
    successful_queries: int
    average_confidence: float
    total_execution_time: float
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def to_json(self) -> str:
        """Export result to JSON string."""
        return _dataclass_to_json(self)


class LayoutLens:
    """Simple API for AI-powered UI testing with natural language.

    This class provides an intuitive interface for analyzing websites and
    screenshots using natural language queries, designed for developer
    workflows and CI/CD integration.

    Examples:
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
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        provider: str = "openai",
        output_dir: str = "layoutlens_output",
        cache_enabled: bool = True,
        cache_type: str = "memory",
        cache_ttl: int = 3600,
        api_base: str | None = None,
        temperature: float | None = None,
    ):
        """Initialize LayoutLens with AI provider credentials.

        Args:
            api_key: API key for the provider. If not provided, will try OPENAI_API_KEY
                environment variable.
            model: Model to use for analysis (LiteLLM naming: "gpt-4o", "anthropic/claude-3-5-sonnet", "google/gemini-1.5-pro").
            provider: AI provider to use ("openai", "anthropic", "google", "gemini", "litellm").
            output_dir: Directory for storing screenshots and results.
            cache_enabled: Whether to enable result caching for performance.
            cache_type: Type of cache backend: "memory" or "file".
            cache_ttl: Cache time-to-live in seconds (1 hour default).
            api_base: Optional base URL for an OpenAI-compatible endpoint. When
                set, it is passed as ``api_base`` to every model call, enabling
                self-hosted backends such as Ollama or vLLM. Example::

                    LayoutLens(
                        provider="litellm",
                        model="ollama/qwen2.5vl",
                        api_base="http://localhost:11434",
                    )
            temperature: Optional sampling temperature for the analyze path. When
                None (default) the analyze path uses 0.1 to preserve historical
                behavior. Subject to the per-model parameter policy — models that
                reject non-default sampling params (e.g. Claude Sonnet 5) omit it
                regardless.

        Raises:
            ConfigurationError: If invalid provider or configuration is specified.

        Notes:
            A missing API key does NOT raise here. The requirement is deferred to
            the first LLM call (see :meth:`_ensure_api_key`) so that deterministic,
            keyless operations such as ``check_accessibility(..., mode="axe")`` work
            without any credentials configured.
        """
        # Initialize logger
        self.logger = get_logger("api.core")

        log_function_call(
            "LayoutLens.__init__",
            model=model,
            provider=provider,
            output_dir=output_dir,
            cache_enabled=cache_enabled,
            cache_type=cache_type,
            cache_ttl=cache_ttl,
        )

        # Determine API key based on provider. A missing key is tolerated here and
        # only enforced when an LLM call is actually made.
        self.api_key = api_key or self._get_api_key_for_provider(provider)

        self.model = model
        self.provider = provider
        self.api_base = api_base
        self.temperature = temperature
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.logger.info(
            f"Initialized LayoutLens with {provider} provider using {model} model"
        )
        self.logger.debug(f"Output directory: {self.output_dir}")

        # Components will be created as needed (no persistent instances)
        self.logger.debug("LayoutLens core initialized - components created on demand")

        # Initialize cache
        cache_dir = str(self.output_dir / "cache") if cache_type == "file" else "cache"
        try:
            self.cache = create_cache(
                cache_type=cache_type,
                cache_dir=cache_dir,
                default_ttl=cache_ttl,
                enabled=cache_enabled,
            )
            self.logger.info(
                f"Initialized {cache_type} cache (enabled: {cache_enabled})"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize cache: {e}")
            raise

    def _get_api_key_for_provider(self, provider: str) -> str | None:
        """Get appropriate API key based on provider.

        For the ``litellm`` passthrough provider this returns ``None`` even when
        ``OPENAI_API_KEY`` happens to be set, so an OpenAI key is never silently
        forwarded to, say, an Anthropic model. LiteLLM resolves credentials from
        its own env conventions in that case.
        """
        env_var = PROVIDER_API_KEY_ENV_VARS.get(provider, "OPENAI_API_KEY")
        if env_var is None:
            return None
        return os.getenv(env_var)

    def _ensure_api_key(self) -> None:
        """Enforce that an API key is available before making an LLM call.

        The key requirement is deferred from construction to first LLM use so
        deterministic-only operations (e.g. axe-based accessibility) stay keyless.
        The ``litellm`` passthrough provider is exempt: it has no single
        canonical key, so LiteLLM is left to resolve credentials from its own
        per-model env conventions (its auth errors are already surfaced).

        Raises:
            AuthenticationError: If no API key is configured for a mapped provider.
        """
        if self.provider == "litellm":
            return
        if not self.api_key:
            env_var = PROVIDER_API_KEY_ENV_VARS.get(self.provider, "OPENAI_API_KEY")
            self.logger.error(f"No API key found for {self.provider} provider")
            raise AuthenticationError(
                f"API key required for {self.provider} provider. Set {env_var} env var or pass api_key parameter."
            )

    def _encode_image(self, image_path: str | Path) -> str:
        """Encode image to base64."""
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _model_fingerprint(self) -> str:
        """Identify the model configuration for cache keying."""
        return f"{self.provider}:{self.model}@{self.api_base or ''}"

    @staticmethod
    def _instructions_fingerprint(instructions: Instructions | None) -> str:
        """Stable short hash of an Instructions object for cache keying."""
        if instructions is None:
            return ""
        payload = json.dumps(asdict(instructions), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    def _image_content_part(self, image_path: str | Path) -> dict[str, Any]:
        """Build one image_url content part with a suffix-appropriate MIME type."""
        mime = (
            "image/jpeg"
            if Path(image_path).suffix.lower() in {".jpg", ".jpeg"}
            else "image/png"
        )
        image_b64 = self._encode_image(image_path)
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{image_b64}"},
        }

    def _format_query_prompt(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
    ) -> str:
        """Format the query into a proper prompt using enhanced instruction system."""
        # Use enhanced prompt system if instructions provided
        if instructions and instructions.expert_persona:
            expert = get_expert(instructions.expert_persona)
            if expert:
                system_prompt, user_prompt = expert.analyze(query, instructions)
                # Combine system and user prompts for the current API
                return f"{system_prompt}\n\nUSER QUERY: {user_prompt}"

        # Fallback to original prompt format for backward compatibility
        prompt = f"""
Analyze this UI screenshot and answer the following question:

Question: {query}

Please provide:
1. A direct answer to the question
2. Your confidence level (0.0 to 1.0)
3. Detailed reasoning for your assessment

Focus on:
- Visual layout and design elements
- User experience and usability
- Accessibility considerations
- Overall quality and professionalism
"""

        # Add context from either instructions or legacy context dict
        if instructions:
            if instructions.focus_areas:
                prompt += f"\n\nFocus areas: {', '.join(instructions.focus_areas)}"
            if instructions.evaluation_criteria:
                prompt += f"\n\nEvaluation criteria: {instructions.evaluation_criteria}"
            if instructions.user_context:
                context_str = instructions.user_context.to_prompt_text()
                if context_str:
                    prompt += f"\n\nUser context: {context_str}"
        elif context:
            context_str = ", ".join(f"{k}: {v}" for k, v in context.items())
            prompt += f"\n\nAdditional context: {context_str}"

        prompt += "\n\nRespond in this JSON format:\n"
        prompt += '{"answer": "your answer", "confidence": 0.0-1.0, "reasoning": "detailed explanation"}'

        return prompt

    def _parse_structured_response(self, content: str) -> tuple[str, float, str]:
        """Parse structured response and return answer, confidence, and reasoning."""
        # Balanced-object JSON extraction shared with the judge path: tolerates
        # code fences, surrounding prose, and nested objects — the old regex
        # here rejected any nested braces, silently degrading answers to the
        # text fallback. Imported locally because judge imports this module.
        from .judge import _extract_json_object

        parsed = _extract_json_object(content)
        if parsed is not None and "answer" in parsed:
            reasoning = parsed.get("reasoning") or parsed.get("rationale") or ""
            try:
                confidence = float(parsed.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            return (
                str(parsed["answer"]),
                min(max(confidence, 0.0), 1.0),
                str(reasoning) or "Analysis completed",
            )

        # Fallback: parse confidence from text patterns
        confidence = 0.5
        confidence_patterns = [
            r"confidence[:\s]+(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)(?:\s*(?:%|percent))?[^\w]*confident",
            r"certainty[:\s]+(\d+(?:\.\d+)?)",
        ]

        for pattern in confidence_patterns:
            match = re.search(pattern, content.lower())
            if match:
                try:
                    confidence = float(match.group(1))
                    if confidence > 1.0:
                        confidence = confidence / 100.0
                    break
                except (ValueError, IndexError):
                    continue

        # Extract answer and reasoning (simplified)
        answer = content.strip()[:200] if len(content) > 200 else content.strip()
        reasoning = content.strip()

        return answer, confidence, reasoning

    async def _call_vision_api(
        self,
        image_path: str | list[str],
        query: str,
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
    ) -> dict[str, Any]:
        """Call LiteLLM vision API with one image, or several (comparisons)."""
        # Enforce the API-key requirement at the first point of LLM use. Raised
        # (not swallowed) so it propagates through analyze as an AuthenticationError.
        self._ensure_api_key()

        paths = [image_path] if isinstance(image_path, str) else list(image_path)
        try:
            image_parts = [self._image_content_part(p) for p in paths]
            self.logger.debug(f"Encoded {len(image_parts)} image(s)")
        except Exception as e:
            self.logger.error(f"Image encoding failed: {e}")
            return {
                "answer": f"Error during analysis: Image encoding failed: {e}",
                "confidence": 0.0,
                "reasoning": f"Analysis failed: Image encoding failed: {e}",
                "metadata": {"error": str(e), "error_type": "encoding_error"},
            }

        # Build prompt
        prompt = self._format_query_prompt(query, context, instructions)

        try:
            self.logger.debug(f"Making API call with LiteLLM to model: {self.model}")

            # Resolve temperature: honor the constructor override when set,
            # otherwise keep the historical analyze default of 0.1. The policy
            # then drops it for models that reject non-default sampling params.
            temperature = self.temperature if self.temperature is not None else 0.1
            completion_kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}, *image_parts],
                    }
                ],
                "timeout": 30.0,
                **completion_params(
                    self.model, temperature=temperature, max_tokens=1000
                ),
            }
            # Only pass api_key when we actually resolved one; otherwise let
            # LiteLLM fall back to its own provider-specific env resolution.
            if self.api_key:
                completion_kwargs["api_key"] = self.api_key
            if self.api_base:
                completion_kwargs["api_base"] = self.api_base

            response = await acompletion(**completion_kwargs)

            self.logger.debug(f"API call successful")

            # Extract content. stream is never enabled here, so the response is
            # a plain ModelResponse despite litellm's broader union.
            content = response.choices[0].message.content or ""  # pyright: ignore[reportAttributeAccessIssue]
            usage = _read_usage(response)

            # Parse structured response
            answer, confidence, reasoning = self._parse_structured_response(content)

            self.logger.debug(f"Parsed response - confidence: {confidence:.2f}")

            return {
                "answer": answer,
                "confidence": confidence,
                "reasoning": reasoning,
                "metadata": {
                    "raw_response": content,
                    "tokens_used": usage["total_tokens"],
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "model_used": self.model,
                    "provider": "litellm",
                },
            }

        except Exception as e:
            self.logger.error(f"LiteLLM API call failed: {e}")
            return {
                "answer": f"Error during analysis: API call failed: {e}",
                "confidence": 0.0,
                "reasoning": f"Analysis failed: API call failed: {e}",
                "metadata": {"error": str(e), "error_type": "api_error"},
            }

    @overload
    async def analyze(
        self,
        source: str | Path,
        query: str,
        viewport: ViewportType = "desktop",
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
        max_concurrent: int = 5,
    ) -> AnalysisResult: ...

    @overload
    async def analyze(
        self,
        source: list[str | Path],
        query: str | list[str],
        viewport: ViewportType = "desktop",
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
        max_concurrent: int = 5,
    ) -> BatchResult: ...

    @overload
    async def analyze(
        self,
        source: str | Path,
        query: list[str],
        viewport: ViewportType = "desktop",
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
        max_concurrent: int = 5,
    ) -> BatchResult: ...

    async def analyze(
        self,
        source: str | Path | list[str | Path],
        query: str | list[str],
        viewport: ViewportType = "desktop",
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
        max_concurrent: int = 5,
    ) -> AnalysisResult | BatchResult:
        """Smart analyze method that handles single or multiple sources and queries.

        Args:
            source: Single URL/path or list of URLs/paths to analyze.
            query: Single question or list of questions about the UI.
            viewport: Viewport for capture (Viewport.DESKTOP, "desktop", etc.).
            context: Additional context for analysis (user_type, browser, etc.). Legacy format.
            instructions: Rich instruction set with expert personas and structured context.
                         Takes precedence over context if both provided.
            max_concurrent: Maximum concurrent operations for batch analysis.

        Returns:
            AnalysisResult for single source+query, BatchResult for multiple.

        Examples:
            # Single analysis
            >>> result = await lens.analyze("https://github.com", "Is it accessible?")

            # Multiple queries on one source
            >>> result = await lens.analyze("https://github.com", ["Is it accessible?", "Mobile-friendly?"])

            # Multiple sources, one query
            >>> result = await lens.analyze(["page1.html", "page2.html"], "Is it good?")

            # Multiple sources and queries
            >>> result = await lens.analyze(["page1.html", "page2.html"], ["Accessible?", "Mobile?"])
        """
        # Handle enum/string for viewport
        viewport_value = (
            viewport.value if isinstance(viewport, Viewport) else str(viewport)
        )

        # Normalize inputs to lists
        sources = [source] if not isinstance(source, list) else source
        queries = [query] if not isinstance(query, list) else query

        # Determine if we should return single result or batch result
        is_single_result = len(sources) == 1 and len(queries) == 1

        start_time = time.time()

        log_function_call(
            "LayoutLens.analyze",
            source_count=len(sources),
            query_count=len(queries),
            total_combinations=len(sources) * len(queries),
            viewport=viewport_value,
            is_single_result=is_single_result,
        )

        # Input validation for all queries
        for q in queries:
            if not q or not q.strip():
                self.logger.error(f"Empty query provided: '{q}'")
                raise ValidationError("Query cannot be empty", field="query", value=q)

        # Use unified batch processing logic for all cases
        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_single_combination(
            source: str | Path, query: str
        ) -> AnalysisResult:
            """Analyze single source+query combination with concurrency control."""
            async with semaphore:
                combination_start_time = time.time()

                # Check cache first
                cache_key = self.cache.get_analysis_key(
                    source=str(source),
                    query=query,
                    viewport=viewport_value,
                    context=context,
                    model=self._model_fingerprint(),
                    instructions_fingerprint=self._instructions_fingerprint(
                        instructions
                    ),
                )
                # ``AnalysisCache.get`` returns a defensive deep copy, so mutating
                # the result here (and by downstream callers such as the hybrid
                # axe override) can never corrupt the shared cached entry.
                cached_result = self.cache.get(cache_key)
                if cached_result and isinstance(cached_result, AnalysisResult):
                    cached_result.execution_time = time.time() - combination_start_time
                    cached_result.metadata["cache_hit"] = True
                    self.logger.info(
                        f"Cache hit for {str(source)[:50]}... - confidence: {cached_result.confidence}"
                    )
                    return cached_result

                try:
                    # Determine if source is URL, HTML file, or image file
                    if self._is_url(source):
                        self.logger.debug(f"Capturing screenshot from URL: {source}")
                        capture_engine = Capture(
                            output_dir=self.output_dir / "screenshots"
                        )
                        screenshot_paths = await capture_engine.screenshots(
                            [str(source)], viewport_value
                        )
                        screenshot_path = screenshot_paths[0]
                        self.logger.info(
                            f"Successfully captured screenshot: {screenshot_path}"
                        )
                    elif self._is_html_file(source):
                        self.logger.debug(
                            f"Capturing screenshot from HTML file: {source}"
                        )
                        screenshot_path = await self.capture(source, viewport=viewport)
                        self.logger.info(
                            f"Successfully captured HTML file screenshot: {screenshot_path}"
                        )
                    else:
                        # Use existing image file
                        screenshot_path = str(source)
                        if not Path(screenshot_path).exists():
                            self.logger.error(
                                f"Screenshot file not found: {screenshot_path}"
                            )
                            raise LayoutFileNotFoundError(
                                f"Screenshot file not found: {screenshot_path}",
                                file_path=screenshot_path,
                            )
                        self.logger.debug(
                            f"Using existing screenshot: {screenshot_path}"
                        )

                    # Analyze with direct API call

                    self.logger.debug(
                        f"Starting vision analysis for query: {query[:50]}..."
                    )
                    vision_response = await self._call_vision_api(
                        image_path=screenshot_path,
                        query=query,
                        context=context,
                        instructions=instructions,
                    )
                    self.logger.debug(
                        f"Vision analysis completed with confidence: {vision_response['confidence']}"
                    )

                    combination_execution_time = time.time() - combination_start_time

                    result = AnalysisResult(
                        source=str(source),
                        query=query,
                        answer=str(vision_response["answer"]),
                        confidence=float(vision_response["confidence"]),
                        reasoning=str(vision_response["reasoning"]),
                        screenshot_path=screenshot_path,
                        viewport=viewport_value,
                        execution_time=combination_execution_time,
                        metadata={
                            **vision_response["metadata"],
                            "cache_hit": False,
                            "provider": self.provider,
                            "model": self.model,
                            "pipeline_mode": "unified",
                        },
                    )

                    # Cache the result
                    self.cache.set(cache_key, result)
                    return result

                except Exception as e:
                    if isinstance(e, LayoutLensError):
                        raise
                    self.logger.warning(
                        f"Analysis failed for {source} + query '{query[:50]}...': {e}"
                    )
                    return AnalysisResult(
                        source=str(source),
                        query=query,
                        answer=f"Error analyzing {source}: {e!s}",
                        confidence=0.0,
                        reasoning=f"Analysis failed due to: {e!s}",
                        execution_time=time.time() - combination_start_time,
                        metadata={
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )

        # Create tasks for all source/query combinations
        tasks = []
        for source in sources:
            for query in queries:
                task = analyze_single_combination(source, query)
                tasks.append(task)

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle any remaining exceptions
        processed_results = []
        for i, result in enumerate(results):
            source_idx = i // len(queries)
            query_idx = i % len(queries)
            source = sources[source_idx]
            query = queries[query_idx]

            if isinstance(result, Exception):
                # A single source+query call propagates typed errors to the
                # caller; batch runs isolate them per item instead, so one bad
                # source never sinks the rest.
                if is_single_result and isinstance(result, LayoutLensError):
                    raise result
                self.logger.warning(f"Unexpected error for {source}: {result}")
                error_result = AnalysisResult(
                    source=str(source),
                    query=query,
                    answer=f"Error analyzing {source}: {result!s}",
                    confidence=0.0,
                    reasoning=f"Analysis failed due to: {result!s}",
                    metadata={
                        "error": str(result),
                        "error_type": type(result).__name__,
                    },
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)

        # Determine return type based on input
        if is_single_result:
            # Single source + single query: return AnalysisResult directly
            return processed_results[0]
        else:
            # Multiple combinations: return BatchResult
            successful_results = [r for r in processed_results if r.confidence > 0]
            total_execution_time = time.time() - start_time
            average_confidence = (
                sum(r.confidence for r in successful_results) / len(successful_results)
                if successful_results
                else 0.0
            )

            # Cache hits keep their original token metadata for transparency,
            # but this run made no model request for them — exclude them from
            # the per-run usage/cost totals.
            billed = [r for r in processed_results if not r.metadata.get("cache_hit")]
            prompt_tokens = sum(r.metadata.get("prompt_tokens", 0) for r in billed)
            completion_tokens = sum(
                r.metadata.get("completion_tokens", 0) for r in billed
            )
            return BatchResult(
                results=processed_results,
                total_queries=len(processed_results),
                successful_queries=len(successful_results),
                average_confidence=average_confidence,
                total_execution_time=total_execution_time,
                total_prompt_tokens=prompt_tokens,
                total_completion_tokens=completion_tokens,
                total_tokens=sum(r.metadata.get("tokens_used", 0) for r in billed),
                estimated_cost_usd=_estimate_cost(
                    self.model, prompt_tokens, completion_tokens
                ),
            )

    async def compare(
        self,
        sources: list[str | Path],
        query: str = "Are these layouts consistent?",
        viewport: ViewportType = "desktop",
        context: dict[str, Any] | None = None,
        instructions: Instructions | None = None,
    ) -> ComparisonResult:
        """Compare multiple URLs or screenshots.

        Args:
            sources: List of URLs or screenshot paths to compare.
            query: Natural language question for comparison.
            viewport: Viewport for captures (Viewport.DESKTOP or string).
            context: Additional context for analysis.
            instructions: Rich instructions for expert analysis.

        Returns:
            Comparison analysis with overall assessment.

        Example:
            >>> result = await lens.compare([
            ...     "https://example.com/before",
            ...     "https://example.com/after"
            ... ], "Did the redesign improve the user experience?")
        """
        # Handle enum/string for viewport
        viewport_value = (
            viewport.value if isinstance(viewport, Viewport) else str(viewport)
        )

        start_time = time.time()

        log_function_call(
            "LayoutLens.compare",
            sources=[
                str(s)[:30] + "..." if len(str(s)) > 30 else str(s) for s in sources
            ],
            query=query[:100] + "..." if len(query) > 100 else query,
            viewport=viewport_value,
        )

        self.logger.info(f"Starting comparison of {len(sources)} sources")

        try:
            # Analyze each source individually first
            individual_results = []
            screenshot_paths = []

            for i, source in enumerate(sources):
                self.logger.debug(
                    f"Processing source {i + 1}/{len(sources)}: {str(source)[:50]}..."
                )
                if self._is_url(source):
                    capture_engine = Capture(output_dir=self.output_dir / "screenshots")
                    screenshot_paths_batch = await capture_engine.screenshots(
                        [str(source)], viewport_value
                    )
                    screenshot_path = screenshot_paths_batch[
                        0
                    ]  # Get first (and only) result
                elif self._is_html_file(source):
                    # Render local HTML to a real screenshot; otherwise the raw
                    # HTML bytes would be base64-encoded and sent to the vision
                    # API mislabeled as a PNG (garbage comparative analysis).
                    screenshot_path = await self._serve_html_and_capture(
                        source, viewport_value
                    )
                else:
                    # Existing image file passes through unchanged.
                    screenshot_path = str(source)

                screenshot_paths.append(screenshot_path)

                # Individual analysis on the screenshot we just captured, so
                # each source is rendered exactly once. Restore the original
                # source name afterwards for the caller's benefit.
                individual_result = await self.analyze(
                    screenshot_path,
                    query,
                    viewport_value,
                    context,
                    instructions=instructions,
                )
                individual_result.source = str(source)
                individual_results.append(individual_result)

            # Comparative analysis: every screenshot goes to the model, in
            # order, with a legend mapping "Image N" to its source.
            self.logger.debug("Starting comparative analysis")
            if len(screenshot_paths) >= 2:
                legend = "\n".join(
                    f"Image {i + 1}: {s}" for i, s in enumerate(map(str, sources))
                )
                comparison_query = f"{query}\n\nYou are given {len(screenshot_paths)} images:\n{legend}"
                comparison_response = await self._call_vision_api(
                    image_path=screenshot_paths,
                    query=comparison_query,
                    context=context,
                    instructions=instructions,
                )
                comparison = {
                    "answer": comparison_response["answer"],
                    "confidence": comparison_response["confidence"],
                    "reasoning": comparison_response["reasoning"],
                    "metadata": {
                        **comparison_response["metadata"],
                        "screenshot_count": len(screenshot_paths),
                        "context": context or {},
                    },
                }
            else:
                comparison = {
                    "answer": "Need at least 2 sources for comparison",
                    "confidence": 0.0,
                    "reasoning": "Insufficient sources provided for comparison",
                    "metadata": {"error": "insufficient_sources"},
                }

            execution_time = time.time() - start_time

            confidence = comparison.get("confidence", 0.0)

            # Log performance metrics
            log_performance_metric(
                operation="compare",
                duration=execution_time,
                confidence=confidence,
                source_count=len(sources),
                viewport=viewport_value,
            )

            self.logger.info(
                f"Comparison completed for {len(sources)} sources - confidence: {confidence:.2f}, time: {execution_time:.2f}s"
            )

            return ComparisonResult(
                sources=[str(s) for s in sources],
                query=query,
                answer=comparison["answer"],
                confidence=confidence,
                reasoning=comparison["reasoning"],
                individual_analyses=individual_results,
                screenshot_paths=screenshot_paths,
                execution_time=execution_time,
                metadata=comparison.get("metadata", {}),
            )

        except Exception as e:
            self.logger.error(f"Comparison failed for {len(sources)} sources: {e}")
            execution_time = time.time() - start_time
            return ComparisonResult(
                sources=[str(s) for s in sources],
                query=query,
                answer=f"Error during comparison: {e!s}",
                confidence=0.0,
                reasoning="Comparison failed due to error",
                execution_time=execution_time,
                metadata={"error": str(e)},
            )

    def _is_url(self, source: str | Path) -> bool:
        """Check if source is a URL or file path."""
        if isinstance(source, Path):
            return False

        parsed = urlparse(str(source))
        return bool(parsed.scheme and parsed.netloc)

    def _is_html_file(self, source: str | Path) -> bool:
        """Check if source is an HTML file."""
        if self._is_url(source):
            return False

        path = Path(source)
        return path.suffix.lower() in [".html", ".htm"]

    # Recognized raster/vector image extensions treated as pre-rendered screenshots.
    _IMAGE_SUFFIXES = frozenset(
        {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg"}
    )

    def _is_image_file(self, source: str | Path) -> bool:
        """Check if source is an image file (a pre-rendered screenshot).

        Image sources have no DOM, so the deterministic axe engine cannot audit
        them — accessibility modes must reject or skip them rather than audit a
        garbage document served as HTML.
        """
        if self._is_url(source):
            return False

        return Path(source).suffix.lower() in self._IMAGE_SUFFIXES

    async def _serve_html_and_capture(
        self,
        html_file_path: str | Path,
        viewport: ViewportType = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
    ) -> str:
        """Serve a local HTML file and capture a screenshot.

        Serving is delegated to :func:`layoutlens.browser.open_page` (used by
        the capture engine), which stands up a temporary local HTTP server so
        relative CSS/JS/image references resolve correctly.
        """
        html_file_path = Path(html_file_path).resolve()
        if not html_file_path.exists():
            raise LayoutFileNotFoundError(
                f"HTML file not found: {html_file_path}",
                file_path=str(html_file_path),
            )

        viewport_value = (
            viewport.value if isinstance(viewport, Viewport) else str(viewport)
        )
        capture_engine = Capture(output_dir=self.output_dir / "screenshots")
        screenshot_paths = await capture_engine.screenshots(
            [str(html_file_path)],
            viewport_value,
            wait_for_selector=wait_for_selector,
            wait_time=wait_time,
        )
        screenshot_path = screenshot_paths[0]
        self.logger.info(f"Successfully captured HTML file: {html_file_path.name}")
        return screenshot_path

    # Unified Capture Method

    @overload
    async def capture(
        self,
        source: str | Path,
        viewport: ViewportType = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
        max_concurrent: int = 3,
    ) -> str: ...

    @overload
    async def capture(
        self,
        source: list[str | Path],
        viewport: ViewportType = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
        max_concurrent: int = 3,
    ) -> dict[str, str]: ...

    async def capture(
        self,
        source: str | Path | list[str | Path],
        viewport: ViewportType = "desktop",
        wait_for_selector: str | None = None,
        wait_time: int | None = None,
        max_concurrent: int = 3,
    ) -> str | dict[str, str]:
        """Smart capture method that handles single or multiple sources uniformly.

        Args:
            source: Single URL/path or list of URLs/paths to capture.
            viewport: Viewport for capture (Viewport.DESKTOP, "desktop", etc.).
            wait_for_selector: CSS selector to wait for before capturing.
            wait_time: Additional wait time in milliseconds.
            max_concurrent: Maximum concurrent captures for multiple sources.

        Returns:
            Single source: Returns screenshot path as string.
            Multiple sources: Returns dict mapping source to screenshot path.

        Examples:
            # Single URL
            >>> path = await lens.capture("https://example.com")
            # Returns: "/path/to/screenshot.png"

            # Multiple URLs
            >>> paths = await lens.capture(["https://example.com/page1", "https://site2.com"])
            # Returns: {"https://example.com/page1": "/path1.png", "https://site2.com": "/path2.png"}

            # HTML files
            >>> path = await lens.capture("page.html")
            >>> paths = await lens.capture(["page1.html", "page2.html"])

            # Existing images (validation)
            >>> path = await lens.capture("screenshot.png")
        """
        # Handle enum/string for viewport
        viewport_value = (
            viewport.value if isinstance(viewport, Viewport) else str(viewport)
        )

        # Normalize input to determine return type
        is_single_source = not isinstance(source, list)
        sources = [source] if is_single_source else source

        start_time = time.time()

        log_function_call(
            "LayoutLens.capture",
            source_count=len(sources),
            is_single_source=is_single_source,
            viewport=viewport_value,
            max_concurrent=max_concurrent,
        )

        self.logger.info(f"Starting capture of {len(sources)} source(s)")

        results = {}
        failed_count = 0

        # Separate sources by type for optimal processing
        urls_to_capture = [s for s in sources if self._is_url(s)]
        html_files = [s for s in sources if self._is_html_file(s)]
        existing_files = [
            s for s in sources if not (self._is_url(s) or self._is_html_file(s))
        ]

        # Validate existing files (images)
        for file_path in existing_files:
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                results[str(file_path)] = str(file_path)
                self.logger.debug(f"Using existing file: {file_path}")
            else:
                failed_count += 1
                results[str(file_path)] = f"Error: File not found"
                self.logger.warning(f"File not found: {file_path}")

        # Capture URLs using efficient batch processing
        if urls_to_capture:
            try:
                # Create Capture instance for URL processing
                capture_engine = Capture(output_dir=self.output_dir / "screenshots")
                screenshot_paths = await capture_engine.screenshots(
                    [str(u) for u in urls_to_capture],
                    viewport_value,
                    max_concurrent,
                    wait_for_selector,
                    wait_time,
                )

                # Map results back
                for i, url in enumerate(urls_to_capture):
                    screenshot_path = screenshot_paths[i]
                    if screenshot_path.startswith("Error:"):
                        failed_count += 1
                    results[str(url)] = screenshot_path

                self.logger.info(f"Captured {len(urls_to_capture)} URL screenshots")

            except Exception as e:
                self.logger.error(f"URL capture failed: {e}")
                for url in urls_to_capture:
                    failed_count += 1
                    results[str(url)] = f"Error: {e!s}"

        # Capture HTML files individually (they need special serving)
        if html_files:
            semaphore = asyncio.Semaphore(max_concurrent)

            async def capture_html_file(html_path):
                async with semaphore:
                    try:
                        return await self._serve_html_and_capture(
                            html_path, viewport_value, wait_for_selector, wait_time
                        )
                    except Exception as e:
                        self.logger.warning(f"HTML capture failed for {html_path}: {e}")
                        return f"Error: {e!s}"

            # Process HTML files concurrently
            html_tasks = [capture_html_file(html_path) for html_path in html_files]
            html_results = await asyncio.gather(*html_tasks, return_exceptions=True)

            for i, result in enumerate(html_results):
                html_path = html_files[i]
                if isinstance(result, Exception) or (
                    isinstance(result, str) and result.startswith("Error:")
                ):
                    failed_count += 1
                    results[str(html_path)] = (
                        f"Error: {result!s}"
                        if isinstance(result, Exception)
                        else result
                    )
                else:
                    results[str(html_path)] = result

            self.logger.info(f"Captured {len(html_files)} HTML file screenshots")

        execution_time = time.time() - start_time
        successful_count = len(sources) - failed_count

        # Log performance metrics
        log_performance_metric(
            operation="capture_unified",
            duration=execution_time,
            total_sources=len(sources),
            successful_captures=successful_count,
            failed_captures=failed_count,
            viewport=viewport_value,
            max_concurrent=max_concurrent,
        )

        self.logger.info(
            f"Capture completed: {successful_count}/{len(sources)} successful, time: {execution_time:.2f}s"
        )

        # Return format based on input type
        if is_single_source:
            # Single source: return the path directly
            return results[str(sources[0])]
        else:
            # Multiple sources: return the full mapping
            return results

    # Deterministic accessibility helpers

    @staticmethod
    def _axe_run_only_for_level(compliance_level: str) -> list[str]:
        """Map a WCAG compliance level to the axe tags to run.

        A -> ``["wcag2a"]``, AA -> ``["wcag2a", "wcag2aa"]``,
        AAA -> ``["wcag2a", "wcag2aa", "wcag2aaa"]``.
        """
        tags = ["wcag2a"]
        if compliance_level in ("AA", "AAA"):
            tags.append("wcag2aa")
        if compliance_level == "AAA":
            tags.append("wcag2aaa")
        return tags

    @staticmethod
    def _wcag_level_label(run_only: list[str] | None) -> str:
        """Return the WCAG level label covered by an axe ``run_only`` tag list.

        ``["wcag2a"]`` -> "WCAG A", ``["wcag2a", "wcag2aa"]`` -> "WCAG A/AA",
        adding ``"wcag2aaa"`` -> "WCAG A/AA/AAA".
        """
        tags = set(run_only or [])
        if "wcag2aaa" in tags:
            return "WCAG A/AA/AAA"
        if "wcag2aa" in tags:
            return "WCAG A/AA"
        return "WCAG A"

    @staticmethod
    def _axe_answer(report: A11yReport, level_label: str = "WCAG A/AA") -> str:
        """Phrase a natural-language yes/no answer from an axe report.

        ``level_label`` names the WCAG level(s) actually audited (see
        :meth:`_wcag_level_label`) so the answer never overstates coverage.
        """
        if report.violations:
            rule_ids = ", ".join(sorted({f.rule_id for f in report.violations}))
            return f"No — axe-core found {len(report.violations)} {level_label} violation(s): {rule_ids}"
        return f"Yes — axe-core found no {level_label} violations"

    def _build_axe_result(
        self,
        source: str | Path,
        query: str,
        viewport_value: str,
        report: A11yReport,
        mode: str,
        run_only: list[str] | None = None,
    ) -> AnalysisResult:
        """Build a deterministic AnalysisResult from an axe report (no LLM)."""
        return AnalysisResult(
            source=str(source),
            query=query,
            answer=self._axe_answer(report, self._wcag_level_label(run_only)),
            confidence=1.0,
            reasoning=report.summary(),
            viewport=viewport_value,
            metadata={
                "a11y": asdict(report),
                "mode": mode,
                "engine": f"axe-core {AXE_VERSION}",
                "provider": self.provider,
                "model": self.model,
            },
        )

    def _apply_axe_override(
        self,
        result: AnalysisResult,
        report: A11yReport,
        mode: str,
        run_only: list[str] | None = None,
    ) -> AnalysisResult:
        """Apply the deterministic override to a hybrid LLM result.

        If axe found violations, the final answer is forced to "no" with full
        confidence and reasoning that combines axe findings with the LLM's
        assessment. If axe found none, the LLM's answer/confidence are kept.
        The axe report is always attached under ``metadata["a11y"]``.
        """
        if report.violations:
            result.answer = self._axe_answer(report, self._wcag_level_label(run_only))
            result.confidence = 1.0
            result.reasoning = (
                f"{report.summary()}\n\nLLM assessment:\n{result.reasoning}"
            )
        result.metadata["a11y"] = asdict(report)
        result.metadata["mode"] = mode
        result.metadata["engine"] = f"axe-core {AXE_VERSION}"
        return result

    @staticmethod
    def _inject_axe_context(query: str, report: A11yReport) -> str:
        """Append a deterministic axe-core context block to an LLM query."""
        return (
            f"{query}\n\n"
            f"Deterministic axe-core scan results for this page:\n{report.summary()}\n"
            "Assess additional visual/contextual accessibility issues that automated rules cannot catch."
        )

    async def _run_a11y_check(
        self,
        source: str | Path,
        query: str,
        viewport_value: str,
        run_only: list[str],
        mode: str,
        instructions: Instructions | None = None,
    ) -> AnalysisResult:
        """Shared axe/hybrid execution for the accessibility entry points.

        Handles the image-source guard, the deterministic ``axe`` path, and the
        single-session ``hybrid`` path. ``llm`` mode is handled entirely by the
        callers and never reaches here.

        Raises:
            ValidationError: In ``axe`` mode when ``source`` is an image, which
                has no DOM for axe to audit.
        """
        # Image sources are pre-rendered screenshots with no DOM; axe would
        # otherwise be handed a garbage document served as HTML and report a
        # false "compliant" at full confidence.
        if self._is_image_file(source):
            if mode == "axe":
                raise ValidationError(
                    f"axe mode cannot audit an image source ({source}) — it has no DOM. "
                    "Provide a URL or HTML file, or use mode='llm' for vision-only analysis.",
                    field="source",
                    value=str(source),
                )
            # hybrid: fall back to vision-only and record why axe was skipped.
            self.logger.warning(
                f"Image source {source} has no DOM; falling back to llm-only for hybrid accessibility check."
            )
            result = await self.analyze(
                source, query, viewport=viewport_value, instructions=instructions
            )
            result.metadata["mode"] = "llm"
            result.metadata["a11y_skipped"] = "image source"
            return result

        if mode == "axe":
            report = await AxeAuditor(run_only=run_only).audit(source, viewport_value)
            return self._build_axe_result(
                source, query, viewport_value, report, mode, run_only
            )

        return await self._hybrid_a11y(
            source, query, viewport_value, run_only, mode, instructions
        )

    async def _hybrid_a11y(
        self,
        source: str | Path,
        query: str,
        viewport_value: str,
        run_only: list[str],
        mode: str,
        instructions: Instructions | None = None,
    ) -> AnalysisResult:
        """Run one browser session for the screenshot + axe audit, then the LLM.

        A single :func:`open_page` session yields the exact page the screenshot
        is taken from AND the DOM axe audits, so the pixels the LLM sees and the
        DOM axe scores can never diverge (and only one browser is launched).
        Results are cached under a key that includes the a11y mode so llm-mode
        and hybrid-mode results for the same source never collide. If axe fails,
        the check degrades gracefully to LLM-only with an ``a11y_error`` note.
        """
        cache_key = self.cache.get_analysis_key(
            source=str(source),
            query=query,
            viewport=viewport_value,
            context={"a11y_mode": mode},
            model=self._model_fingerprint(),
            instructions_fingerprint=self._instructions_fingerprint(instructions),
        )
        # ``AnalysisCache.get`` already hands back a defensive deep copy.
        cached = self.cache.get(cache_key)
        if cached and isinstance(cached, AnalysisResult):
            cached.metadata["cache_hit"] = True
            return cached

        start_time = time.time()
        capture_engine = Capture(output_dir=self.output_dir / "screenshots")
        screenshot_path = capture_engine.output_dir / capture_engine._generate_filename(
            str(source), viewport_value
        )

        report: A11yReport | None = None
        axe_error: str | None = None
        async with open_page(source, viewport_value) as page:
            await page.screenshot(path=str(screenshot_path), full_page=True)
            try:
                report = await AxeAuditor(run_only=run_only).audit_page(
                    page, source=str(source), viewport=viewport_value
                )
            except Exception as e:
                axe_error = str(e)
                self.logger.warning(
                    f"axe audit failed in hybrid mode; proceeding LLM-only: {e}"
                )

        llm_query = (
            self._inject_axe_context(query, report) if report is not None else query
        )
        vision_response = await self._call_vision_api(
            image_path=str(screenshot_path), query=llm_query, instructions=instructions
        )

        result = AnalysisResult(
            source=str(source),
            query=query,
            answer=str(vision_response["answer"]),
            confidence=float(vision_response["confidence"]),
            reasoning=str(vision_response["reasoning"]),
            screenshot_path=str(screenshot_path),
            viewport=viewport_value,
            execution_time=time.time() - start_time,
            metadata={
                **vision_response["metadata"],
                "provider": self.provider,
                "model": self.model,
            },
        )

        if report is not None:
            result = self._apply_axe_override(result, report, mode, run_only)
        else:
            result.metadata["mode"] = mode
            result.metadata["a11y_error"] = axe_error

        self.cache.set(cache_key, result)
        return result

    # Faithful judge interface (for external eval harnesses)

    async def judge(
        self,
        image_path: str | Path,
        prompt: str,
        *,
        max_tokens: int | _Auto = AUTO,
        timeout: float = 120.0,
    ) -> JudgeResult:
        """Send ``prompt`` VERBATIM with an image and return a parsed verdict.

        This is the faithful judge interface for external evaluation harnesses
        (e.g. UIJudgeBench). Unlike :meth:`analyze`, LayoutLens adds NOTHING to
        the prompt: no system persona, no scaffolding, no appended JSON-format
        instruction. The caller owns the entire prompt, including any response
        contract. The call always hits the model (no caching) and honors the
        per-model parameter policy (Claude 4.6+/5 omit temperature).

        Args:
            image_path: Path to an existing image file (mime inferred from the
                extension: ``.jpg``/``.jpeg`` -> JPEG, otherwise PNG).
            prompt: The exact text to send as the sole text block.
            max_tokens: Maximum tokens to generate. Defaults to ``AUTO``, which
                resolves to 8000 for reasoning/thinking models (they spend
                thinking tokens inside this budget) and 300 otherwise. Pass an
                explicit integer to override.
            timeout: Per-call timeout in seconds (default 120 — reasoning
                models can take well over 30s on a single judgment).

        Returns:
            JudgeResult with the parsed answer/confidence/rationale, the raw
            text, a refusal flag, per-model usage split, and the parse mode.

        Raises:
            ValidationError: If ``image_path`` does not exist.
            AuthenticationError: If no API key is configured for a mapped provider.
        """
        from .judge import judge as _judge

        return await _judge(
            self, image_path, prompt, max_tokens=max_tokens, timeout=timeout
        )

    async def judge_batch(
        self,
        requests: list[BatchRequest],
        *,
        max_tokens: int | _Auto = AUTO,
        resume: bool = True,
        manifest_path: str | Path | None = None,
        poll_interval: float = 10.0,
        poll_timeout: float = 24 * 3600.0,
    ) -> dict[str, JudgeResult]:
        """Judge many image+prompt requests over a provider batch transport.

        The batched counterpart to :meth:`judge`: each request sends its prompt
        VERBATIM with its image (byte-identical to :meth:`judge`), honors the
        reasoning-aware ``max_tokens`` default and the per-model parameter
        policy, and is parsed into a :class:`JudgeResult`. Batch APIs are ~50%
        cheaper and the right transport for bulk offline evaluation (e.g.
        UIJudgeBench). LayoutLens is thus the reference *batched* judge.

        The backend is chosen from ``self.model``: ``gemini/*`` (AI Studio) uses
        the google-genai inline batch (optional extra ``layoutlens[gemini]``);
        every other model uses the litellm file-based batch (OpenAI, Anthropic,
        Vertex, Bedrock, ...). Both are resumable via a manifest.

        Args:
            requests: The batch items. Each ``id`` keys its result. A request
                whose image is missing yields an ``"unknown"`` result rather
                than aborting the batch.
            max_tokens: Per-request token budget. Defaults to ``AUTO`` (8000 for
                reasoning models, else 300); an explicit integer overrides.
            resume: When True (default), collect any prior jobs from the
                manifest first and submit only uncovered ids.
            manifest_path: Where submitted job ids persist for resume. Defaults
                to a path under ``output_dir/batch`` keyed by the request-id set
                and model.
            poll_interval: Seconds between batch-status polls.
            poll_timeout: Max seconds to wait for a single batch job.

        Returns:
            ``{request_id: JudgeResult}`` for every request.

        Raises:
            AuthenticationError: If no API key is configured for a mapped provider.
            ImportError: If a ``gemini/*`` model is used without ``google-genai``.
        """
        from .batch import judge_batch as _judge_batch

        return await _judge_batch(
            self,
            requests,
            max_tokens=max_tokens,
            resume=resume,
            manifest_path=manifest_path,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
        )

    # Developer convenience methods
    # Expert-Based Analysis Methods

    async def check_accessibility(
        self,
        source: str | Path,
        standards: list[str] | None = None,
        compliance_level: ComplianceLevelType = "AA",
        viewport: ViewportType = "desktop",
        mode: Literal["hybrid", "axe", "llm"] = "hybrid",
    ) -> AnalysisResult:
        """Accessibility audit: deterministic axe-core, LLM vision, or both.

        Args:
            source: URL or file path to analyze
            standards: Accessibility standards to apply (default: WCAG 2.1, Section 508)
            compliance_level: WCAG compliance level (ComplianceLevel.AA or string)
            viewport: Viewport for analysis (Viewport.DESKTOP or string)
            mode: ``"hybrid"`` (default) combines deterministic axe-core checks with
                LLM analysis (axe violations force a "no" verdict). ``"axe"`` runs
                axe-core only (no API key required). ``"llm"`` runs the legacy
                vision-only audit. The axe run honors ``compliance_level``:
                A -> ``wcag2a``, AA -> ``wcag2a``+``wcag2aa``, AAA additionally
                includes ``wcag2aaa``.

        Returns:
            Detailed accessibility assessment with specific WCAG guidance

        Raises:
            ValueError: If compliance_level is not a valid WCAG level
        """
        from ..prompts import Instructions

        # Validate and normalize compliance level
        if isinstance(compliance_level, ComplianceLevel):
            compliance_level_value = compliance_level.value
        else:
            # Handle string input and validate
            compliance_level_upper = compliance_level.upper()
            try:
                compliance_level_enum = ComplianceLevel(compliance_level_upper)
                compliance_level_value = compliance_level_enum.value
            except ValueError:
                valid_levels = [level.value for level in ComplianceLevel]
                raise ValueError(
                    f"compliance_level must be one of {valid_levels}, got: '{compliance_level}'"
                ) from None

        viewport_value = (
            viewport.value if isinstance(viewport, Viewport) else str(viewport)
        )
        instructions = Instructions.for_accessibility_audit(
            standards=standards, compliance_level=compliance_level_value
        )
        query = f"Perform a comprehensive accessibility audit for WCAG {compliance_level_value} compliance"

        if mode == "llm":
            result = await self.analyze(
                source, query, viewport=viewport_value, instructions=instructions
            )
            result.metadata["mode"] = mode
            return result

        run_only = self._axe_run_only_for_level(compliance_level_value)
        return await self._run_a11y_check(
            source, query, viewport_value, run_only, mode, instructions=instructions
        )

    # Deterministic layout checks (geometry/contrast), mirroring the a11y stack

    @staticmethod
    def _layout_answer(report: LayoutReport) -> str:
        """Phrase a natural-language yes/no answer from a layout report."""
        if report.findings:
            classes = ", ".join(sorted({f.defect_class for f in report.findings}))
            return (
                f"No — deterministic layout scan found {len(report.findings)} "
                f"defect(s): {classes}"
            )
        return "Yes — deterministic layout scan found no defects"

    @staticmethod
    def _inject_layout_context(query: str, report: LayoutReport) -> str:
        """Append a deterministic layout-scan context block to an LLM query."""
        return (
            f"{query}\n\n"
            f"Deterministic layout/geometry scan results for this page:\n{report.summary()}\n"
            "Assess additional visual layout issues that geometric rules cannot catch."
        )

    def _apply_layout_override(
        self, result: AnalysisResult, report: LayoutReport, mode: str
    ) -> AnalysisResult:
        """Apply the deterministic override to a hybrid layout result.

        If the scorer measured any defect, the final answer is forced to "no"
        with full confidence — the measurements are receipts, not opinions.
        Otherwise the LLM's own answer/confidence stand. The layout report is
        always attached under ``metadata["layout"]``.
        """
        if report.findings:
            result.answer = self._layout_answer(report)
            result.confidence = 1.0
            result.reasoning = (
                f"{report.summary()}\n\nLLM assessment:\n{result.reasoning}"
            )
        result.metadata["layout"] = asdict(report)
        result.metadata["mode"] = mode
        result.metadata["engine"] = "layoutlens-layout"
        return result

    async def check_layout(
        self,
        source: str | Path,
        viewport: ViewportType = "desktop",
        mode: Literal["hybrid", "deterministic", "llm"] = "hybrid",
        scorer: LayoutScorer | None = None,
    ) -> AnalysisResult:
        """Layout check: deterministic geometry/contrast scan, LLM vision, or both.

        The deterministic scan measures contrast, sibling overlap, clipped
        content, viewport protrusion, page-level horizontal overflow, truncated
        text, WCAG-aware target spacing, complete focus obscuration, and text
        occlusion — directly off the rendered page, with no LLM and no API key.

        Args:
            source: URL or HTML file to check (images have no DOM to measure —
                use ``mode="llm"`` for pre-rendered screenshots).
            viewport: Viewport for the scan/capture.
            mode: ``"hybrid"`` (default) runs the deterministic scan AND LLM
                vision, forcing a "no" verdict when the scan measures any
                defect. ``"deterministic"`` runs the scan only — keyless.
                ``"llm"`` is vision-only.
            scorer: Optional pre-configured :class:`LayoutScorer` (custom
                thresholds).

        Returns:
            AnalysisResult. In deterministic/hybrid modes ``metadata["layout"]``
            holds the full layout report with per-finding measurements.

        Raises:
            ValidationError: In ``deterministic`` mode when ``source`` is an
                image, which has no DOM to measure.
        """
        viewport_value = (
            viewport.value if isinstance(viewport, Viewport) else str(viewport)
        )
        scorer = scorer or LayoutScorer()
        query = (
            "Are there layout defects on this page — overlapping or clipped "
            "content, elements extending past the viewport, truncated or "
            "occluded text, obscured keyboard focus, low-contrast text, or "
            "touch targets that are too small or closely spaced?"
        )

        if self._is_image_file(source):
            if mode == "deterministic":
                raise ValidationError(
                    f"deterministic mode cannot measure an image source ({source}) — "
                    "it has no DOM. Provide a URL or HTML file, or use mode='llm'.",
                    field="source",
                    value=str(source),
                )
            self.logger.warning(
                f"Image source {source} has no DOM; falling back to llm-only for layout check."
            )
            result = await self.analyze(source, query, viewport=viewport_value)
            result.metadata["mode"] = "llm"
            result.metadata["layout_skipped"] = "image source"
            return result

        if mode == "llm":
            result = await self.analyze(source, query, viewport=viewport_value)
            result.metadata["mode"] = mode
            return result

        if mode == "deterministic":
            report = await scorer.scan(source, viewport=viewport_value)
            return AnalysisResult(
                source=str(source),
                query=query,
                answer=self._layout_answer(report),
                confidence=1.0,
                reasoning=report.summary(),
                viewport=viewport_value,
                metadata={
                    "layout": asdict(report),
                    "mode": mode,
                    "engine": "layoutlens-layout",
                    "provider": self.provider,
                    "model": self.model,
                },
            )

        return await self._hybrid_layout(source, query, viewport_value, mode, scorer)

    async def _hybrid_layout(
        self,
        source: str | Path,
        query: str,
        viewport_value: str,
        mode: str,
        scorer: LayoutScorer,
    ) -> AnalysisResult:
        """One browser session for the screenshot + layout scan, then the LLM.

        Mirrors :meth:`_hybrid_a11y`: a single :func:`open_page` session yields
        the exact page the screenshot is taken from AND the DOM the scorer
        measures, so pixels and measurements can never diverge. If the scan
        fails, the check degrades gracefully to LLM-only with a
        ``layout_error`` note.
        """
        cache_key = self.cache.get_analysis_key(
            source=str(source),
            query=query,
            viewport=viewport_value,
            # Scorer thresholds are part of the key: a rerun with a stricter
            # custom scorer must never be served the lenient scorer's verdict.
            context={
                "layout_mode": mode,
                "scorer": {
                    "min_target_px": scorer.min_target_px,
                    "overlap_threshold_px2": scorer.overlap_threshold_px2,
                    "clip_tolerance_px": scorer.clip_tolerance_px,
                    "protrude_tolerance_px": scorer.protrude_tolerance_px,
                    "contrast_threshold": scorer.contrast_threshold,
                },
            },
            model=self._model_fingerprint(),
        )
        cached = self.cache.get(cache_key)
        if cached and isinstance(cached, AnalysisResult):
            cached.metadata["cache_hit"] = True
            return cached

        start_time = time.time()
        capture_engine = Capture(output_dir=self.output_dir / "screenshots")
        screenshot_path = capture_engine.output_dir / capture_engine._generate_filename(
            str(source), viewport_value
        )

        report: LayoutReport | None = None
        layout_error: str | None = None
        async with open_page(source, viewport_value) as page:
            await page.screenshot(path=str(screenshot_path), full_page=True)
            try:
                report = await scorer.scan_page(
                    page, source=str(source), viewport=viewport_value
                )
            except Exception as e:
                layout_error = str(e)
                self.logger.warning(
                    f"layout scan failed in hybrid mode; proceeding LLM-only: {e}"
                )

        llm_query = (
            self._inject_layout_context(query, report) if report is not None else query
        )
        vision_response = await self._call_vision_api(
            image_path=str(screenshot_path), query=llm_query
        )

        result = AnalysisResult(
            source=str(source),
            query=query,
            answer=str(vision_response["answer"]),
            confidence=float(vision_response["confidence"]),
            reasoning=str(vision_response["reasoning"]),
            screenshot_path=str(screenshot_path),
            viewport=viewport_value,
            execution_time=time.time() - start_time,
            metadata={
                **vision_response["metadata"],
                "provider": self.provider,
                "model": self.model,
            },
        )

        if report is not None:
            result = self._apply_layout_override(result, report, mode)
        else:
            result.metadata["mode"] = mode
            result.metadata["layout_error"] = layout_error

        self.cache.set(cache_key, result)
        return result

    async def optimize_conversions(
        self,
        source: str | Path,
        business_goals: list[str] | None = None,
        industry: str | None = None,
        target_audience: str | None = None,
        viewport: ViewportType = "desktop",
    ) -> AnalysisResult:
        """Conversion rate optimization analysis using CRO expert knowledge.

        Args:
            source: URL or file path to analyze
            business_goals: Business objectives (e.g., reduce_cart_abandonment)
            industry: Industry context for specialized recommendations
            target_audience: Target audience for optimization focus
            viewport: Viewport for analysis (Viewport.DESKTOP or string)

        Returns:
            Detailed CRO recommendations with A/B testing suggestions
        """
        from ..prompts import Instructions

        instructions = Instructions.for_conversion_optimization(
            business_goals=business_goals,
            industry=industry,
            target_audience=target_audience,
        )

        query = "Analyze for conversion optimization opportunities with specific recommendations"
        return await self.analyze(
            source, query, viewport=viewport, instructions=instructions
        )

    async def analyze_mobile_ux(
        self,
        source: str | Path,
        device_types: list[str] | None = None,
        performance_focus: bool = True,
    ) -> AnalysisResult:
        """Mobile UX analysis using mobile expert knowledge.

        Args:
            source: URL or file path to analyze
            device_types: Target devices (smartphone, tablet)
            performance_focus: Include performance optimization analysis

        Returns:
            Mobile-specific UX recommendations and optimizations
        """
        from ..prompts import Instructions

        instructions = Instructions.for_mobile_optimization(
            device_types=device_types, performance_focus=performance_focus
        )

        query = (
            "Evaluate mobile user experience and provide optimization recommendations"
        )
        return await self.analyze(
            source, query, viewport="mobile_portrait", instructions=instructions
        )

    async def audit_ecommerce(
        self,
        source: str | Path,
        page_type: str = "product_page",
        business_model: str = "b2c",
        viewport: ViewportType = "desktop",
    ) -> AnalysisResult:
        """E-commerce UX audit using retail expert knowledge.

        Args:
            source: URL or file path to analyze
            page_type: Type of e-commerce page (product_page, checkout, homepage)
            business_model: Business model (b2c, b2b)
            viewport: Viewport for analysis (Viewport.DESKTOP or string)

        Returns:
            E-commerce specific recommendations for conversion improvement
        """
        from ..prompts import Instructions

        instructions = Instructions.for_ecommerce_analysis(
            page_type=page_type, business_model=business_model
        )

        query = f"Audit this {page_type} for e-commerce best practices and conversion optimization"
        return await self.analyze(
            source, query, viewport=viewport, instructions=instructions
        )

    async def analyze_with_expert(
        self,
        source: str | Path,
        query: str,
        expert_persona: ExpertType,
        focus_areas: list[str] | None = None,
        user_context: dict[str, Any] | None = None,
        viewport: ViewportType = "desktop",
    ) -> AnalysisResult:
        """Analyze using a specific domain expert persona.

        Args:
            source: URL or file path to analyze
            query: Question to analyze
            expert_persona: Expert to use (Expert.ACCESSIBILITY or string)
            focus_areas: Specific areas to focus analysis on
            user_context: Rich context about users and requirements
            viewport: Viewport for analysis (Viewport.DESKTOP or string)

        Returns:
            Expert-level analysis with domain-specific recommendations
        """
        from ..prompts import Instructions, UserContext

        # Handle enum/string for expert_persona
        expert_persona_value = (
            expert_persona.value
            if isinstance(expert_persona, Expert)
            else str(expert_persona)
        )

        # Handle enum/string for viewport
        viewport_value = (
            viewport.value if isinstance(viewport, Viewport) else str(viewport)
        )

        # Convert user_context dict to UserContext object if provided
        context_obj = None
        if user_context:
            context_obj = UserContext(**user_context)

        instructions = Instructions(
            expert_persona=expert_persona_value,
            focus_areas=focus_areas or [],
            user_context=context_obj,
        )

        return await self.analyze(
            source, query, viewport=viewport_value, instructions=instructions
        )

    async def compare_with_expert(
        self,
        sources: list[str | Path],
        query: str,
        expert_persona: ExpertType,
        focus_areas: list[str] | None = None,
        viewport: ViewportType = "desktop",
    ) -> ComparisonResult:
        """Compare multiple sources using domain expert knowledge.

        Args:
            sources: List of URLs or file paths to compare
            query: Comparison question
            expert_persona: Expert to use for comparison (Expert.ACCESSIBILITY or string)
            focus_areas: Specific areas to focus comparison on
            viewport: Viewport for analysis (Viewport.DESKTOP or string)

        Returns:
            Expert comparison with domain-specific insights
        """
        from ..prompts import Instructions

        # Handle enum/string for expert_persona
        expert_persona_value = (
            expert_persona.value
            if isinstance(expert_persona, Expert)
            else str(expert_persona)
        )

        # Handle enum/string for viewport
        viewport_value = (
            viewport.value if isinstance(viewport, Viewport) else str(viewport)
        )

        instructions = Instructions(
            expert_persona=expert_persona_value, focus_areas=focus_areas or []
        )

        return await self.compare(
            sources, query, viewport=viewport_value, instructions=instructions
        )

    # Cache management methods
    async def run_test_suite(
        self, suite: UITestSuite, parallel: bool = False, max_workers: int = 4
    ) -> list[UITestResult]:
        """Run a test suite and return one result per test case.

        Args:
            suite: The test suite to run.
            parallel: Run test cases concurrently instead of serially.
            max_workers: Maximum concurrent test cases when ``parallel``.

        Returns:
            List of ``UITestResult`` objects, in suite order.
        """
        from .test_suite import run_suite_case

        if parallel:
            semaphore = asyncio.Semaphore(max_workers)

            async def guarded(tc) -> UITestResult:
                async with semaphore:
                    return await run_suite_case(self, suite, tc)

            return list(await asyncio.gather(*(guarded(tc) for tc in suite.test_cases)))
        return [await run_suite_case(self, suite, tc) for tc in suite.test_cases]

    def create_test_suite(
        self, name: str, description: str, test_cases: list[dict[str, Any]]
    ) -> UITestSuite:
        """Create a test suite from spec dicts (see ``UITestSuite.from_specs``)."""
        from .test_suite import UITestSuite

        return UITestSuite.from_specs(name, description, test_cases)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache performance statistics."""
        return self.cache.stats()

    def clear_cache(self) -> None:
        """Clear all cached analysis results."""
        self.cache.clear()

    def enable_cache(self) -> None:
        """Enable caching."""
        self.cache.enabled = True

    def disable_cache(self) -> None:
        """Disable caching."""
        self.cache.enabled = False
