"""
Report generation for Browser Use validation results.

Provides HTML and JSON report generation for validation sessions.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ...logger import get_logger
from .types import (
    SessionComparison,
    ValidationSession,
    ValidationSeverity,
    ValidationStepResult,
)


class ValidationReportGenerator:
    """Generates HTML and JSON reports from validation sessions.

    Creates human-readable reports with embedded screenshots, timeline
    visualization, and CI/CD-compatible JSON output.

    Attributes:
        output_dir: Directory for storing generated reports.

    Examples:
        >>> generator = ValidationReportGenerator(output_dir="reports")
        >>> generator.generate_html_report(session, "validation_report.html")
        >>> generator.generate_json_report(session, "validation_report.json")
    """

    def __init__(self, output_dir: str | Path = "reports"):
        """Initialize the report generator.

        Args:
            output_dir: Directory for storing generated reports.
        """
        self.logger = get_logger("integrations.browser_use.reports")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"ValidationReportGenerator initialized - output_dir: {self.output_dir}")

    def generate_html_report(
        self,
        session: ValidationSession,
        output_path: str | Path | None = None,
        include_screenshots: bool = True,
        embed_images: bool = False,
    ) -> Path:
        """Generate an HTML report from a validation session.

        Args:
            session: ValidationSession to generate report for.
            output_path: Output path for the HTML file.
            include_screenshots: Whether to include screenshot references.
            embed_images: Whether to embed images as base64 (larger file).

        Returns:
            Path to the generated HTML report.
        """
        if output_path is None:
            output_path = self.output_dir / f"report_{session.session_id}.html"
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        html_content = self._generate_html_content(
            session,
            include_screenshots,
            embed_images,
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        self.logger.info(f"Generated HTML report: {output_path}")
        return output_path

    def generate_json_report(
        self,
        session: ValidationSession,
        output_path: str | Path | None = None,
    ) -> Path:
        """Generate a JSON report from a validation session.

        Args:
            session: ValidationSession to generate report for.
            output_path: Output path for the JSON file.

        Returns:
            Path to the generated JSON report.
        """
        if output_path is None:
            output_path = self.output_dir / f"report_{session.session_id}.json"
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        report_data = self._session_to_dict(session)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, default=str)

        self.logger.info(f"Generated JSON report: {output_path}")
        return output_path

    def generate_comparison_report(
        self,
        comparison: SessionComparison,
        output_path: str | Path | None = None,
    ) -> Path:
        """Generate an HTML report comparing two sessions.

        Args:
            comparison: SessionComparison to generate report for.
            output_path: Output path for the HTML file.

        Returns:
            Path to the generated HTML report.
        """
        if output_path is None:
            output_path = self.output_dir / f"comparison_{comparison.baseline_id}_vs_{comparison.current_id}.html"
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        html_content = self._generate_comparison_html(comparison)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        self.logger.info(f"Generated comparison report: {output_path}")
        return output_path

    def _session_to_dict(self, session: ValidationSession) -> dict[str, Any]:
        """Convert session to JSON-serializable dictionary."""
        return {
            "session_id": session.session_id,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "state": session.state.value,
            "start_url": session.start_url,
            "agent_task": session.agent_task,
            "total_actions": session.total_actions,
            "validated_actions": session.validated_actions,
            "duration_seconds": session.duration_seconds,
            "total_findings": session.total_findings,
            "findings_by_severity": session.findings_by_severity,
            "average_confidence": session.average_confidence,
            "policy": {
                "capture_on_click": session.policy.capture_on_click,
                "capture_on_navigation": session.policy.capture_on_navigation,
                "capture_on_form_submit": session.policy.capture_on_form_submit,
                "capture_on_error": session.policy.capture_on_error,
                "experts": session.policy.experts,
                "viewport": session.policy.viewport,
                "confidence_threshold": session.policy.confidence_threshold,
            },
            "steps": [self._step_to_dict(step) for step in session.steps],
            "metadata": session.metadata,
        }

    def _step_to_dict(self, step: ValidationStepResult) -> dict[str, Any]:
        """Convert step to JSON-serializable dictionary."""
        return {
            "step_number": step.step_number,
            "trigger": step.trigger.value,
            "timestamp": step.timestamp,
            "url": step.url,
            "screenshot_path": step.screenshot_path,
            "answer": step.answer,
            "confidence": step.confidence,
            "reasoning": step.reasoning,
            "execution_time": step.execution_time,
            "findings": [
                {
                    "issue": f.issue,
                    "severity": f.severity.value,
                    "expert": f.expert,
                    "confidence": f.confidence,
                    "location": f.location,
                    "recommendation": f.recommendation,
                    "wcag_reference": f.wcag_reference,
                }
                for f in step.findings
            ],
            "finding_count_by_severity": step.finding_count_by_severity,
            "has_critical_findings": step.has_critical_findings,
            "action_context": step.action_context,
            "metadata": step.metadata,
        }

    def _generate_html_content(
        self,
        session: ValidationSession,
        include_screenshots: bool,
        embed_images: bool,
    ) -> str:
        """Generate HTML content for the report."""
        severity_colors = {
            "critical": "#dc3545",
            "high": "#fd7e14",
            "medium": "#ffc107",
            "low": "#17a2b8",
            "info": "#6c757d",
        }

        steps_html = ""
        for step in session.steps:
            screenshot_html = ""
            if include_screenshots and step.screenshot_path:
                if embed_images:
                    import base64

                    try:
                        with open(step.screenshot_path, "rb") as f:
                            img_data = base64.b64encode(f.read()).decode()
                        screenshot_html = f'<img src="data:image/png;base64,{img_data}" class="screenshot" />'
                    except Exception:
                        screenshot_html = f'<p class="error">Screenshot not available: {step.screenshot_path}</p>'
                else:
                    screenshot_html = f'<img src="{step.screenshot_path}" class="screenshot" />'

            findings_html = ""
            for finding in step.findings:
                color = severity_colors.get(finding.severity.value, "#6c757d")
                findings_html += f"""
                <div class="finding" style="border-left: 4px solid {color};">
                    <span class="severity" style="background-color: {color};">{finding.severity.value.upper()}</span>
                    <span class="expert">[{finding.expert}]</span>
                    <p class="issue">{finding.issue[:300]}...</p>
                    {f'<p class="recommendation">Recommendation: {finding.recommendation}</p>' if finding.recommendation else ""}
                    {f'<p class="wcag">WCAG: {finding.wcag_reference}</p>' if finding.wcag_reference else ""}
                    <p class="confidence">Confidence: {finding.confidence:.0%}</p>
                </div>
                """

            steps_html += f"""
            <div class="step">
                <div class="step-header">
                    <h3>Step {step.step_number}: {step.trigger.value}</h3>
                    <span class="timestamp">{step.timestamp}</span>
                </div>
                <p class="url">{step.url}</p>
                {screenshot_html}
                <div class="step-details">
                    <p><strong>Confidence:</strong> {step.confidence:.0%}</p>
                    <p><strong>Execution Time:</strong> {step.execution_time:.2f}s</p>
                    <p><strong>Findings:</strong> {len(step.findings)}</p>
                </div>
                <div class="findings">
                    {findings_html if findings_html else '<p class="no-findings">No issues found</p>'}
                </div>
                <details class="reasoning">
                    <summary>Detailed Reasoning</summary>
                    <pre>{step.reasoning}</pre>
                </details>
            </div>
            """

        findings_summary = session.findings_by_severity
        summary_html = "".join(
            f'<span class="summary-item" style="background-color: {severity_colors.get(sev, "#6c757d")};">'
            f"{sev.upper()}: {count}</span>"
            for sev, count in findings_summary.items()
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LayoutLens Validation Report - {session.session_id}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{ margin: 0 0 10px 0; }}
        .header p {{ margin: 5px 0; opacity: 0.9; }}
        .summary {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary h2 {{ margin-top: 0; }}
        .summary-item {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            color: white;
            margin: 5px;
            font-weight: bold;
        }}
        .step {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .step-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
            margin-bottom: 10px;
        }}
        .step-header h3 {{ margin: 0; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
        .url {{ color: #0066cc; word-break: break-all; }}
        .screenshot {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .step-details {{
            display: flex;
            gap: 20px;
            margin: 10px 0;
            padding: 10px;
            background: #f9f9f9;
            border-radius: 5px;
        }}
        .step-details p {{ margin: 0; }}
        .findings {{ margin-top: 15px; }}
        .finding {{
            padding: 15px;
            margin: 10px 0;
            background: #f9f9f9;
            border-radius: 5px;
        }}
        .severity {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            color: white;
            font-size: 0.8em;
            font-weight: bold;
        }}
        .expert {{ color: #666; margin-left: 10px; }}
        .issue {{ margin: 10px 0; }}
        .recommendation {{ color: #28a745; font-style: italic; }}
        .wcag {{ color: #6610f2; }}
        .confidence {{ color: #666; font-size: 0.9em; }}
        .no-findings {{ color: #28a745; font-style: italic; }}
        .reasoning {{
            margin-top: 15px;
            padding: 10px;
            background: #f0f0f0;
            border-radius: 5px;
        }}
        .reasoning summary {{
            cursor: pointer;
            font-weight: bold;
        }}
        .reasoning pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
            font-size: 0.9em;
            margin: 10px 0 0 0;
        }}
        .error {{ color: #dc3545; }}
        .footer {{
            text-align: center;
            color: #666;
            padding: 20px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>LayoutLens Validation Report</h1>
        <p><strong>Session ID:</strong> {session.session_id}</p>
        <p><strong>Task:</strong> {session.agent_task or "N/A"}</p>
        <p><strong>Start URL:</strong> {session.start_url or "N/A"}</p>
        <p><strong>Duration:</strong> {session.duration_seconds:.1f}s</p>
    </div>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Steps:</strong> {len(session.steps)}</p>
        <p><strong>Total Actions:</strong> {session.total_actions}</p>
        <p><strong>Validated Actions:</strong> {session.validated_actions}</p>
        <p><strong>Total Findings:</strong> {session.total_findings}</p>
        <p><strong>Average Confidence:</strong> {session.average_confidence:.0%}</p>
        <div class="severity-summary">
            {summary_html}
        </div>
    </div>

    <h2>Validation Steps</h2>
    {steps_html}

    <div class="footer">
        <p>Generated by LayoutLens Browser Use Integration</p>
        <p>Report generated at {time.strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
</body>
</html>"""

        return html

    def _generate_comparison_html(self, comparison: SessionComparison) -> str:
        """Generate HTML content for comparison report."""
        severity_colors = {
            "critical": "#dc3545",
            "high": "#fd7e14",
            "medium": "#ffc107",
            "low": "#17a2b8",
            "info": "#6c757d",
        }

        def render_findings(findings: list, section_class: str) -> str:
            if not findings:
                return '<p class="no-findings">None</p>'
            html = ""
            for f in findings:
                color = severity_colors.get(f.severity.value, "#6c757d")
                html += f"""
                <div class="finding {section_class}" style="border-left: 4px solid {color};">
                    <span class="severity" style="background-color: {color};">{f.severity.value.upper()}</span>
                    <span class="expert">[{f.expert}]</span>
                    <p class="issue">{f.issue[:300]}...</p>
                </div>
                """
            return html

        regression_color = (
            "#dc3545"
            if comparison.regression_score > 0
            else "#28a745"
            if comparison.regression_score < 0
            else "#6c757d"
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LayoutLens Session Comparison</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{ margin: 0 0 10px 0; }}
        .summary {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary h2 {{ margin-top: 0; }}
        .score {{
            font-size: 2em;
            font-weight: bold;
            color: {regression_color};
        }}
        .section {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{ margin-top: 0; }}
        .new {{ border-left: 4px solid #dc3545; }}
        .resolved {{ border-left: 4px solid #28a745; }}
        .persistent {{ border-left: 4px solid #ffc107; }}
        .finding {{
            padding: 15px;
            margin: 10px 0;
            background: #f9f9f9;
            border-radius: 5px;
        }}
        .severity {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            color: white;
            font-size: 0.8em;
            font-weight: bold;
        }}
        .expert {{ color: #666; margin-left: 10px; }}
        .issue {{ margin: 10px 0; }}
        .no-findings {{ color: #28a745; font-style: italic; }}
        .footer {{
            text-align: center;
            color: #666;
            padding: 20px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Session Comparison Report</h1>
        <p><strong>Baseline:</strong> {comparison.baseline_id}</p>
        <p><strong>Current:</strong> {comparison.current_id}</p>
    </div>

    <div class="summary">
        <h2>Summary</h2>
        <p class="score">{comparison.summary}</p>
        <p><strong>Regression Score:</strong> {comparison.regression_score:+.1f}</p>
        <p><strong>New Issues:</strong> {len(comparison.new_findings)}</p>
        <p><strong>Resolved Issues:</strong> {len(comparison.resolved_findings)}</p>
        <p><strong>Persistent Issues:</strong> {len(comparison.persistent_findings)}</p>
    </div>

    <div class="section">
        <h2 style="color: #dc3545;">New Issues ({len(comparison.new_findings)})</h2>
        {render_findings(comparison.new_findings, "new")}
    </div>

    <div class="section">
        <h2 style="color: #28a745;">Resolved Issues ({len(comparison.resolved_findings)})</h2>
        {render_findings(comparison.resolved_findings, "resolved")}
    </div>

    <div class="section">
        <h2 style="color: #ffc107;">Persistent Issues ({len(comparison.persistent_findings)})</h2>
        {render_findings(comparison.persistent_findings, "persistent")}
    </div>

    <div class="footer">
        <p>Generated by LayoutLens Browser Use Integration</p>
        <p>Report generated at {time.strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
</body>
</html>"""

        return html

    def generate_timeline_data(self, session: ValidationSession) -> dict[str, Any]:
        """Generate timeline visualization data for the session.

        Args:
            session: ValidationSession to generate timeline for.

        Returns:
            Dictionary with timeline data suitable for visualization.
        """
        timeline_data = {
            "session_id": session.session_id,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "events": [],
        }

        for step in session.steps:
            event = {
                "step": step.step_number,
                "timestamp": step.timestamp,
                "trigger": step.trigger.value,
                "url": step.url,
                "confidence": step.confidence,
                "finding_count": len(step.findings),
                "critical_count": sum(1 for f in step.findings if f.severity == ValidationSeverity.CRITICAL),
                "execution_time": step.execution_time,
            }
            timeline_data["events"].append(event)

        return timeline_data


__all__ = ["ValidationReportGenerator"]
