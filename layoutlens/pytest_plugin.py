"""pytest plugin: UI assertions backed by LayoutLens.

Registered automatically via the ``pytest11`` entry point when layoutlens is
installed. The deterministic assertions (``assert_a11y``, ``assert_layout``)
run keyless — no API key, no LLM, fully reproducible — so they can gate CI on
any fork with no secrets. The LLM assertion (``assert_ui``) *skips* rather
than fails when no API key is configured, so the same suite runs everywhere.

Usage::

    def test_landing_page(layoutlens):
        layoutlens.assert_a11y("landing.html")                    # axe, keyless
        layoutlens.assert_layout("landing.html", viewport="mobile")  # keyless
        layoutlens.assert_ui("landing.html", "Is the CTA above the fold?")

Options: ``--layoutlens-model`` (default gpt-4o-mini), ``--layoutlens-no-llm``
(make ``assert_ui`` skip unconditionally — a fast, free, deterministic-only
CI lane).
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from .api.core import AnalysisResult


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register layoutlens command-line options."""
    group = parser.getgroup("layoutlens")
    group.addoption(
        "--layoutlens-model",
        default="gpt-4o-mini",
        help="Model for LLM-backed assert_ui checks (default: gpt-4o-mini)",
    )
    group.addoption(
        "--layoutlens-provider",
        default="openai",
        help="Provider for assert_ui checks: openai, anthropic, google, "
        "gemini, or litellm (default: openai). Determines which credential "
        "env var is checked before running LLM assertions.",
    )
    group.addoption(
        "--layoutlens-no-llm",
        action="store_true",
        help="Skip assert_ui checks entirely; run only the keyless "
        "deterministic assertions",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register layoutlens markers."""
    config.addinivalue_line(
        "markers", "layoutlens: tests using layoutlens UI assertions"
    )


def _run(coro):
    """Run a coroutine from sync test code."""
    return asyncio.run(coro)


class LayoutLensFixture:
    """Sync assertion helpers over a shared :class:`LayoutLens` client."""

    def __init__(self, config: pytest.Config):
        """Build the helper from pytest configuration options."""
        from .api.core import LayoutLens

        self._no_llm = bool(config.getoption("--layoutlens-no-llm"))
        model = config.getoption("--layoutlens-model") or "gpt-4o-mini"
        provider = str(config.getoption("--layoutlens-provider") or "openai")
        self.lens = LayoutLens(model=str(model), provider=provider)

    # -- keyless deterministic assertions ---------------------------------

    def assert_a11y(
        self,
        source: str,
        compliance_level: str = "AA",
        viewport: str = "desktop",
    ) -> AnalysisResult:
        """Assert the page has no axe-core WCAG violations (keyless).

        Raises:
            pytest.fail.Exception: Listing each violated rule, its impact, and
                the first affected selectors.
        """
        result = _run(
            self.lens.check_accessibility(
                source,
                compliance_level=compliance_level,
                viewport=viewport,
                mode="axe",
            )
        )
        violations = result.metadata["a11y"]["violations"]
        if violations:
            lines = [f"Accessibility violations on {source} (WCAG {compliance_level}):"]
            for v in violations:
                targets = ", ".join(
                    ",".join(n.get("target", [])) for n in v["nodes"][:3]
                )
                lines.append(
                    f"  - {v['rule_id']} [{v['impact']}]: {v['description']}"
                    f" (at: {targets})"
                )
            lines.append(f"  screenshot/context: {result.metadata.get('engine')}")
            pytest.fail("\n".join(lines), pytrace=False)
        return result

    def assert_layout(self, source: str, viewport: str = "desktop") -> AnalysisResult:
        """Assert the deterministic layout scan measures no defects (keyless).

        Raises:
            pytest.fail.Exception: Listing each measured defect with its
                selector, measured values, and violated threshold.
        """
        result = _run(
            self.lens.check_layout(source, viewport=viewport, mode="deterministic")
        )
        findings = result.metadata["layout"]["findings"]
        if findings:
            lines = [f"Layout defects on {source} [{viewport}]:"]
            for f in findings:
                lines.append(
                    f"  - {f['defect_class']} at {f['selector']}: "
                    f"{f['description']} (measured: {f['measured']})"
                )
            pytest.fail("\n".join(lines), pytrace=False)
        return result

    # -- LLM-backed assertion (skips without a key) ------------------------

    def assert_ui(
        self,
        source: str,
        question: str,
        min_confidence: float = 0.0,
        viewport: str = "desktop",
    ) -> AnalysisResult:
        """Assert the vision model answers ``question`` with a leading "yes".

        Skips (never fails) when ``--layoutlens-no-llm`` is set or no API key
        is configured, so keyless environments still run the rest of the suite.

        Raises:
            pytest.fail.Exception: When the model answers "no" (or an
                unparseable answer), with the model's reasoning attached.
        """
        if self._no_llm:
            pytest.skip("assert_ui disabled via --layoutlens-no-llm")
        if not self._llm_available():
            pytest.skip("assert_ui needs an API key; deterministic checks ran")

        result = _run(self.lens.analyze(source, question, viewport=viewport))
        answer = (result.answer or "").strip().lower()
        if not answer.startswith("yes"):
            pytest.fail(
                f"UI check failed on {source}\n"
                f"  question:   {question}\n"
                f"  answer:     {result.answer}\n"
                f"  confidence: {result.confidence:.2f}\n"
                f"  reasoning:  {result.reasoning}\n"
                f"  screenshot: {result.screenshot_path}",
                pytrace=False,
            )
        if result.confidence < min_confidence:
            pytest.fail(
                f"UI check confidence {result.confidence:.2f} below required "
                f"{min_confidence:.2f} on {source} for: {question}",
                pytrace=False,
            )
        return result

    def _llm_available(self) -> bool:
        """True when credentials for the configured provider are resolvable.

        Checks the provider's own env var (ANTHROPIC_API_KEY for anthropic,
        GEMINI_API_KEY for google/gemini, ...), not just OPENAI_API_KEY. The
        "litellm" passthrough provider has no single canonical var, so it is
        treated as available and errors surface from the call itself.
        """
        if self.lens.api_key:
            return True
        from .api.core import PROVIDER_API_KEY_ENV_VARS

        env_var = PROVIDER_API_KEY_ENV_VARS.get(self.lens.provider, "OPENAI_API_KEY")
        if env_var is None:  # litellm passthrough
            return True
        return bool(os.getenv(env_var))

    # -- raw access --------------------------------------------------------

    def scan_layout(self, source: str, viewport: str = "desktop") -> dict[str, Any]:
        """Return the raw deterministic layout report dict (no assertion)."""
        result = _run(
            self.lens.check_layout(source, viewport=viewport, mode="deterministic")
        )
        return result.metadata["layout"]

    def audit_a11y(self, source: str, viewport: str = "desktop") -> dict[str, Any]:
        """Return the raw axe report dict (no assertion)."""
        result = _run(
            self.lens.check_accessibility(source, viewport=viewport, mode="axe")
        )
        return result.metadata["a11y"]


@pytest.fixture(scope="session")
def layoutlens(pytestconfig: pytest.Config) -> LayoutLensFixture:
    """Session-scoped LayoutLens assertion helper."""
    return LayoutLensFixture(pytestconfig)
