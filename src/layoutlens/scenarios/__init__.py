"""Stateful, keyless browser scenarios with portable checkpoint evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

from ..browser import BrowserConfig, resolve_viewport
from .models import (
    Event,
    InteractionFinding,
    ScenarioDiff,
    ScenarioReport,
    Step,
    StepResult,
)
from .runner import run_scenario

if TYPE_CHECKING:
    from ..regression.policy import GatePolicy
    from ..types import ViewportType

__all__ = [
    "Event",
    "InteractionFinding",
    "Scenario",
    "ScenarioDiff",
    "ScenarioReport",
    "Step",
    "StepResult",
]


class Scenario:
    """A sequence whose chained methods return new scenarios."""

    def __init__(
        self,
        source: str | Path,
        *,
        base_url: str | None = None,
        steps: tuple[Step, ...] = (),
    ):
        """Declare the starting page and an optional origin for relative routes."""
        self.source = urljoin(base_url, str(source)) if base_url else str(source)
        self.steps = steps

    def _append(
        self, action: str, target: str | None = None, value: Any = None
    ) -> Scenario:
        if target is not None and not target:
            raise ValueError("target must be nonempty")
        step = Step.model_validate({"action": action, "target": target, "value": value})
        if (
            action == "checkpoint"
            and target
            and (
                target.startswith("__failure_")
                or any(
                    s.action == "checkpoint" and s.target == target for s in self.steps
                )
            )
        ):
            raise ValueError("checkpoint names must be unique and not reserved")
        return Scenario(
            self.source,
            steps=(*self.steps, step),
        )

    def tab(self, *, backwards: bool = False) -> Scenario:
        """Press Tab or Shift+Tab and record the actual focus transition."""
        return self._append("tab", value=backwards)

    def press(self, key: str) -> Scenario:
        """Press a Playwright keyboard key or chord, such as Escape or Shift+Tab."""
        return self._append("press", value=key)

    def type(self, text: str) -> Scenario:
        """Type into the focused editable element, emitting keyboard and input events."""
        return self._append("type", value=text)

    def fill(self, target: str, text: str) -> Scenario:
        """Fill a named or explicitly selected editable element."""
        return self._append("fill", target, text)

    def click(self, target: str) -> Scenario:
        """Click an actionable target; obscured or missing targets interrupt the run."""
        return self._append("click", target)

    def hover(self, target: str) -> Scenario:
        """Move the pointer over a target to reveal hover-dependent content."""
        return self._append("hover", target)

    def drag(self, source: str, target: str) -> Scenario:
        """Drag between actionable elements using Playwright's pointer sequence."""
        return self._append("drag", source, target)

    def navigate(self, url: str) -> Scenario:
        """Navigate in the existing browser context, retaining cookies and storage."""
        return self._append("navigate", value=url)

    def resize(self, width: int, height: int) -> Scenario:
        """Resize the current page to test responsive state transitions."""
        resolve_viewport((width, height))
        return self._append("resize", value=[width, height])

    def pointer_move(self, x: float, y: float) -> Scenario:
        """Move the pointer to viewport CSS coordinates."""
        return self._append("pointer_move", value=[x, y])

    def pointer_down(self, button: str = "left") -> Scenario:
        """Press a pointer button without releasing it."""
        return self._append("pointer_down", value=button)

    def pointer_up(self, button: str = "left") -> Scenario:
        """Release a pointer button."""
        return self._append("pointer_up", value=button)

    def checkpoint(self, name: str) -> Scenario:
        """Capture the current rendered state without resetting focus or media settings."""
        return self._append("checkpoint", name)

    def expect_focus(self, target: str) -> Scenario:
        """Require the named element to receive focus, including inside open shadow DOM."""
        return self._append("expect_focus", target)

    def expect_visible(self, target: str) -> Scenario:
        """Require a target to become visible within the action timeout."""
        return self._append("expect_visible", target)

    def expect_hidden(self, target: str) -> Scenario:
        """Require a target to become hidden or detached, for example after dismissal."""
        return self._append("expect_hidden", target)

    def expect_url(self, url: str) -> Scenario:
        """Require an exact URL, or a route path with its optional query string."""
        return self._append("expect_url", value=url)

    def expect_text(self, target: str, text: str) -> Scenario:
        """Require the target's rendered text to match an explicit content contract."""
        return self._append("expect_text", target, text)

    def expect_count(self, target: str, count: int) -> Scenario:
        """Require a locator count, for example one modal instead of stacked dialogs."""
        if type(count) is not int or count < 0:
            raise ValueError("count must be a nonnegative integer")
        return self._append("expect_count", target, count)

    def expect_style(self, target: str, property_name: str, value: str) -> Scenario:
        """Require a computed CSS property, such as the expected focus-ring outline."""
        return self._append(
            "expect_style", target, {"property": property_name, "value": value}
        )

    def expect_clickable(self, target: str) -> Scenario:
        """Require Playwright's click actionability checks to pass without clicking."""
        return self._append("expect_clickable", target)

    def expect_tab_reaches(self, target: str, *, max_tabs: int = 20) -> Scenario:
        """Require a target to be reachable within a bounded forward keyboard sequence."""
        if type(max_tabs) is not int or not 1 <= max_tabs <= 1000:
            raise ValueError("max_tabs must be between 1 and 1000")
        return self._append("expect_tab_reaches", target, max_tabs)

    def to_dict(self) -> dict[str, Any]:
        """Export the executable definition; values supplied to type and fill are included."""
        return {
            "source": self.source,
            "steps": [step.model_dump(mode="json") for step in self.steps],
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *, base_url: str | None = None
    ) -> Scenario:
        """Load a declarative scenario; arbitrary script execution is unsupported."""
        if (
            not isinstance(data, dict)
            or set(data) != {"source", "steps"}
            or not isinstance(data["source"], str)
            or not isinstance(data["steps"], list)
        ):
            raise ValueError("scenario requires exactly source and steps")
        scenario = cls(data["source"], base_url=base_url)
        for item in data["steps"]:
            step = Step.model_validate(item)
            scenario = scenario._append(step.action, step.target, step.value)
        return scenario

    @classmethod
    def load(cls, path: str | Path, *, base_url: str | None = None) -> Scenario:
        """Read a JSON scenario definition."""
        return cls.from_dict(
            json.loads(Path(path).read_text(encoding="utf-8")), base_url=base_url
        )

    async def run(
        self,
        *,
        browser: str = "chromium",
        viewport: ViewportType | tuple[int, int] = "desktop",
        color_scheme: str = "light",
        reduced_motion: str = "reduce",
        locale: str = "en-US",
        timezone_id: str = "UTC",
        device_scale_factor: float | None = None,
        timeout: int = 30000,
        policy: GatePolicy = "qualified",
    ) -> ScenarioReport:
        """Run locally without an API key and return ordered receipts and checkpoints."""
        if not self.steps:
            raise ValueError("scenario requires at least one step")
        if type(timeout) is not int or timeout <= 0:
            raise ValueError("timeout must be a positive integer")
        config = BrowserConfig(
            browser,
            color_scheme,
            reduced_motion,
            locale,
            timezone_id,
            device_scale_factor,
        )
        resolve_viewport(viewport)
        return await run_scenario(
            self.source,
            self.steps,
            config=config,
            viewport=viewport,
            timeout=timeout,
            policy=policy,
        )
