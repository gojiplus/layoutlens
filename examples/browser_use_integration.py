"""Browser Use integration example: validate an agent's run after the fact.

LayoutLens integrates with browser-use at its stable seam — the
``AgentHistoryList`` returned by ``Agent.run()`` — rather than per-step hooks.
After the agent finishes, every unique URL it visited is re-audited with the
keyless deterministic stack (axe-core WCAG A/AA + geometry/contrast scorers),
and, optionally, each recorded screenshot is judged by the vision LLM.

Requires the extra: ``pip install "layoutlens[browser-use]"``.
"""

import asyncio

from layoutlens import LayoutLens
from layoutlens.integrations.browser_use import (
    ValidationReportGenerator,
    validate_agent_run,
)


async def validate_agent_history():
    """Run a browser-use agent, then validate everything it touched."""
    # Any browser-use agent works; this example assumes you already have one.
    from browser_use import Agent, ChatOpenAI

    agent = Agent(
        task="Find the pricing page and read the plans",
        llm=ChatOpenAI(model="gpt-4o-mini"),
    )
    history = await agent.run()

    lens = LayoutLens()  # keyless is fine for the deterministic checks
    session = await validate_agent_run(
        lens,
        history,
        checks=("a11y", "layout"),
        # Optional LLM pass over the agent's own screenshots (needs an API key):
        queries=["Is any content cut off or overlapping?"],
    )

    print(f"Validated {session.validated_actions} step(s)")
    print(f"Total findings: {session.total_findings}")
    for severity, count in session.findings_by_severity.items():
        print(f"  {severity}: {count}")

    # HTML + JSON reports
    reports = ValidationReportGenerator(output_dir="validation_reports")
    html_path = reports.generate_html_report(session)
    json_path = reports.generate_json_report(session)
    print(f"Reports: {html_path}, {json_path}")


async def validate_screenshot_directory():
    """No live agent? Validate a directory of recorded screenshots instead."""
    lens = LayoutLens()
    session = await validate_agent_run(
        lens,
        screenshot_dir="agent_screenshots/",
        queries=["Does this page look broken or incomplete?"],
    )
    print(f"{session.total_findings} finding(s) across {len(session.steps)} step(s)")


if __name__ == "__main__":
    asyncio.run(validate_agent_history())
