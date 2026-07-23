#!/usr/bin/env python3
"""
Browser Use Integration Example

This example demonstrates how to use LayoutLens as the "intelligent eyes"
for browser automation agents. It shows:

1. Setting up validation hooks for Browser Use agents
2. Recording and replaying sessions
3. Generating validation reports
4. Comparing sessions for regression detection

Requirements:
    pip install layoutlens[browser-use]
    playwright install chromium
"""

import asyncio
from pathlib import Path

from layoutlens.integrations.browser_use import (
    AgentValidator,
    SessionRecorder,
    ValidationPolicy,
    ValidationReportGenerator,
)


async def example_1_basic_validation():
    """Example 1: Basic page validation with AgentValidator."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Page Validation")
    print("=" * 60)

    validator = AgentValidator(
        experts=["accessibility_expert"],
        policy=ValidationPolicy(
            capture_on_navigation=True,
            viewport="desktop",
            confidence_threshold=0.5,
        ),
        output_dir="validation_output",
    )

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        validator.start_session(
            start_url="https://example.com",
            agent_task="Basic accessibility check",
        )

        await page.goto("https://example.com")

        result = await validator.validate_state(page)

        print(f"\nValidation Result:")
        print(f"  URL: {result.url}")
        print(f"  Confidence: {result.confidence:.0%}")
        print(f"  Findings: {len(result.findings)}")

        for finding in result.findings:
            print(f"\n  [{finding.severity.value.upper()}] {finding.issue[:100]}...")

        await validator.end_session()
        await browser.close()

    session = validator.get_session()
    print(f"\nSession completed: {session.total_findings} total findings")


async def example_2_multi_expert_validation():
    """Example 2: Validation with multiple expert personas."""
    print("\n" + "=" * 60)
    print("Example 2: Multi-Expert Validation")
    print("=" * 60)

    validator = AgentValidator(
        experts=["accessibility_expert", "mobile_expert", "conversion_expert"],
        policy=ValidationPolicy(
            viewport="mobile_portrait",
            confidence_threshold=0.4,
        ),
        output_dir="validation_output",
    )

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 375, "height": 667},
            is_mobile=True,
        )
        page = await context.new_page()

        validator.start_session(
            start_url="https://example.com",
            agent_task="Mobile experience audit",
        )

        await page.goto("https://example.com")

        result = await validator.validate_state(page)

        print(f"\nMulti-Expert Validation:")
        print(f"  Combined Confidence: {result.confidence:.0%}")
        print(f"  Total Findings: {len(result.findings)}")

        findings_by_expert: dict[str, list] = {}
        for finding in result.findings:
            if finding.expert not in findings_by_expert:
                findings_by_expert[finding.expert] = []
            findings_by_expert[finding.expert].append(finding)

        for expert, findings in findings_by_expert.items():
            print(f"\n  {expert}:")
            for f in findings[:2]:
                print(f"    - {f.issue[:80]}...")

        await validator.end_session()
        await browser.close()


async def example_3_session_recording():
    """Example 3: Recording a session for later replay."""
    print("\n" + "=" * 60)
    print("Example 3: Session Recording")
    print("=" * 60)

    output_dir = Path("validation_output")
    output_dir.mkdir(exist_ok=True)

    recorder = SessionRecorder(
        output_dir=output_dir / "recordings",
        policy=ValidationPolicy(
            experts=["accessibility_expert"],
            viewport="desktop",
        ),
    )

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        async with recorder.record(page, "Navigation flow test") as recording:
            await page.goto("https://example.com")
            await recorder.capture_step(page, "Initial page load")

            links = await page.locator("a").all()
            if links:
                first_link = links[0]
                link_text = await first_link.inner_text()
                try:
                    await first_link.click(timeout=5000)
                    await recorder.capture_step(page, f"Clicked: {link_text}")
                except Exception as e:
                    print(f"  Could not click link: {e}")

        print(f"\nRecording saved:")
        print(f"  Recording ID: {recording.recording_id}")
        print(f"  Screenshots: {len(recording.screenshots)}")
        print(f"  Actions: {len(recording.action_log)}")

        recording_path = output_dir / "recordings" / f"{recording.recording_id}.json"
        recording.save(recording_path)
        print(f"  Saved to: {recording_path}")

        await browser.close()


async def example_4_generate_reports():
    """Example 4: Generate HTML and JSON reports."""
    print("\n" + "=" * 60)
    print("Example 4: Report Generation")
    print("=" * 60)

    validator = AgentValidator(
        experts=["accessibility_expert"],
        output_dir="validation_output",
    )

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        validator.start_session("https://example.com", "Report demo")
        await page.goto("https://example.com")
        await validator.validate_state(page)
        await validator.end_session()
        await browser.close()

    session = validator.get_session()

    generator = ValidationReportGenerator(output_dir="validation_output/reports")

    html_report = generator.generate_html_report(
        session,
        include_screenshots=True,
        embed_images=False,
    )
    print(f"\nHTML Report: {html_report}")

    json_report = generator.generate_json_report(session)
    print(f"JSON Report: {json_report}")

    timeline = generator.generate_timeline_data(session)
    print(f"Timeline events: {len(timeline['events'])}")


async def example_5_audit_flow():
    """Example 5: Audit a specific user flow."""
    print("\n" + "=" * 60)
    print("Example 5: Flow Audit")
    print("=" * 60)

    validator = AgentValidator(
        experts=["accessibility_expert", "conversion_expert"],
        output_dir="validation_output",
    )

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("https://example.com")
        validator.start_session("https://example.com", "User flow audit")

        async def step_1(p):
            await p.wait_for_load_state("networkidle")

        async def step_2(p):
            header = p.locator("h1")
            if await header.count() > 0:
                await header.scroll_into_view_if_needed()

        results = await validator.audit_flow(page, [step_1, step_2])

        print(f"\nFlow Audit Results:")
        for i, result in enumerate(results):
            print(f"\n  Step {i + 1}:")
            print(f"    Confidence: {result.confidence:.0%}")
            print(f"    Findings: {len(result.findings)}")

        await validator.end_session()
        await browser.close()


async def main():
    """Run all examples."""
    print("LayoutLens Browser Use Integration Examples")
    print("=" * 60)

    try:
        await example_1_basic_validation()
    except Exception as e:
        print(f"Example 1 failed: {e}")

    try:
        await example_2_multi_expert_validation()
    except Exception as e:
        print(f"Example 2 failed: {e}")

    try:
        await example_3_session_recording()
    except Exception as e:
        print(f"Example 3 failed: {e}")

    try:
        await example_4_generate_reports()
    except Exception as e:
        print(f"Example 4 failed: {e}")

    try:
        await example_5_audit_flow()
    except Exception as e:
        print(f"Example 5 failed: {e}")

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("Check validation_output/ for generated reports and screenshots.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
