"""Deterministic accessibility auditing via a vendored axe-core bundle.

:class:`AxeAuditor` injects the bundled axe-core JavaScript into a Playwright
page, runs ``axe.run``, and maps the resulting JSON into typed
:class:`~layoutlens.a11y.types.A11yReport` objects. The axe-core assets are
vendored under ``layoutlens/a11y/assets`` and loaded at runtime via
:mod:`importlib.resources`, so they are available from an installed wheel.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from playwright.async_api import Page

from ..browser import open_page
from ..exceptions import AnalysisError
from ..logger import get_logger
from ..types import Viewport, ViewportType
from .types import A11yFinding, A11yReport

logger = get_logger("a11y.axe")

# Exact version of the vendored axe-core bundle (see assets/axe.min.js header).
AXE_VERSION = "4.10.3"

# Maximum length for a node's HTML snippet before truncation.
MAX_HTML_LEN = 200

# axe tag prefixes that correspond to standards references worth keeping.
_STANDARD_TAG_PREFIXES = ("wcag", "section508")


@lru_cache(maxsize=1)
def _load_axe_source() -> str:
    """Load and cache the vendored axe-core JavaScript source."""
    asset = resources.files("layoutlens.a11y") / "assets" / "axe.min.js"
    return asset.read_text(encoding="utf-8")


def _truncate_html(html: str) -> str:
    """Truncate an HTML snippet to a sane length for reporting."""
    if len(html) <= MAX_HTML_LEN:
        return html
    return html[:MAX_HTML_LEN] + "..."


def _filter_wcag_refs(tags: list[str]) -> list[str]:
    """Keep only standards tags (wcag*, section508), dropping category tags."""
    return [tag for tag in tags if tag.startswith(_STANDARD_TAG_PREFIXES)]


def _finding_from_rule(rule: dict[str, Any]) -> A11yFinding:
    """Map a single axe rule result (violation/incomplete) to an A11yFinding."""
    nodes = [
        {
            "target": node.get("target", []),
            "html": _truncate_html(node.get("html", "")),
        }
        for node in rule.get("nodes", [])
    ]
    return A11yFinding(
        rule_id=rule.get("id", ""),
        impact=rule.get("impact") or "",
        wcag_refs=_filter_wcag_refs(rule.get("tags", [])),
        description=rule.get("description", ""),
        help_url=rule.get("helpUrl", ""),
        nodes=nodes,
    )


class AxeAuditor:
    """Runs axe-core against a Playwright page and returns structured findings.

    Args:
        run_only: Optional list of axe tags to restrict the run to (e.g.
            ``["wcag2a", "wcag2aa"]``). Maps to axe's
            ``runOnly: {type: "tag", values: [...]}``. ``None`` uses axe defaults.
        disabled_rules: Optional list of rule ids to disable. Maps to axe's
            ``rules: {<id>: {enabled: false}}``.
    """

    def __init__(
        self,
        run_only: list[str] | None = None,
        disabled_rules: list[str] | None = None,
    ):
        """Initialize the auditor with optional tag and rule filters."""
        self.run_only = run_only
        self.disabled_rules = disabled_rules or []

    def _axe_options(self) -> dict[str, Any]:
        """Build the options dict passed to ``axe.run``."""
        options: dict[str, Any] = {}
        if self.run_only:
            options["runOnly"] = {"type": "tag", "values": self.run_only}
        if self.disabled_rules:
            options["rules"] = {rule_id: {"enabled": False} for rule_id in self.disabled_rules}
        return options

    @staticmethod
    def _build_report(results: dict[str, Any], source: str, viewport: str) -> A11yReport:
        """Map a raw ``axe.run`` results dict into an :class:`A11yReport`."""
        violations = [_finding_from_rule(rule) for rule in results.get("violations", [])]
        incomplete = [_finding_from_rule(rule) for rule in results.get("incomplete", [])]
        passes_count = len(results.get("passes", []))
        engine_version = results.get("testEngine", {}).get("version") or AXE_VERSION

        return A11yReport(
            source=source,
            viewport=viewport,
            engine_version=engine_version,
            violations=violations,
            incomplete=incomplete,
            passes_count=passes_count,
        )

    async def audit_page(self, page: Page, source: str | None = None, viewport: str = "desktop") -> A11yReport:
        """Inject axe-core into an already-loaded page and run the audit.

        Args:
            page: A loaded Playwright page.
            source: Optional source label recorded in the report; defaults to
                the page URL.
            viewport: Viewport name recorded in the report.

        Returns:
            The structured accessibility report.

        Raises:
            AnalysisError: If axe injection or execution fails.
        """
        source_label = source if source is not None else page.url
        try:
            await page.add_script_tag(content=_load_axe_source())
            results = await page.evaluate(
                "(opts) => axe.run(document, opts)",
                self._axe_options(),
            )
        except Exception as exc:  # noqa: BLE001 - re-wrapped into a domain error
            raise AnalysisError(
                f"axe-core execution failed: {exc}",
                source=source_label,
            ) from exc

        return self._build_report(results, source_label, viewport)

    async def audit(self, source: str | Path, viewport: ViewportType = "desktop") -> A11yReport:
        """Audit a URL or local HTML file, owning the browser lifecycle.

        Args:
            source: A URL or path to a local HTML file.
            viewport: Viewport name or :class:`~layoutlens.types.Viewport` enum member.

        Returns:
            The structured accessibility report.

        Raises:
            AnalysisError: If axe injection or execution fails.
        """
        viewport_name = viewport.value if isinstance(viewport, Viewport) else str(viewport)
        async with open_page(source, viewport) as page:
            return await self.audit_page(page, source=str(source), viewport=viewport_name)
