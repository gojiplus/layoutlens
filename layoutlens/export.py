"""Export functionality for LayoutLens analysis results.

This module provides various export formats including PDF, HTML, JSON, and CSV
for analysis results, batch results, and test suite reports.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import jinja2

    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

from .api.core import AnalysisResult, BatchResult, ComparisonResult
from .exceptions import LayoutLensError


class ExportError(LayoutLensError):
    """Error during export operation."""

    pass


class BaseExporter:
    """Base class for all export formats."""

    def __init__(self, output_dir: str | Path = "layoutlens_exports"):
        """Initialize exporter.

        Args:
            output_dir: Directory to save exported files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _get_timestamp(self) -> str:
        """Get current timestamp for file naming."""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for cross-platform compatibility."""
        return "".join(c for c in name if c.isalnum() or c in "._- ").strip()


class JSONExporter(BaseExporter):
    """Export results to JSON format."""

    def export_result(
        self,
        result: AnalysisResult | BatchResult | ComparisonResult,
        filename: str | None = None,
    ) -> Path:
        """Export single result to JSON.

        Args:
            result: Analysis result to export
            filename: Optional custom filename

        Returns:
            Path to exported file
        """
        if not filename:
            timestamp = self._get_timestamp()
            result_type = type(result).__name__.lower()
            filename = f"layoutlens_{result_type}_{timestamp}.json"

        filepath = self.output_dir / filename

        # Convert result to dictionary
        if hasattr(result, "__dict__"):
            data = self._result_to_dict(result)
        else:
            # This should not happen with our result types, but handle gracefully
            data = {"error": "Unable to convert result to dictionary"}

        # Add metadata
        data["export_info"] = {
            "exported_at": datetime.now().isoformat(),
            "exporter": "LayoutLens JSONExporter",
            "format_version": "1.0",
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

        return filepath

    def export_batch(
        self,
        results: list[AnalysisResult | BatchResult | ComparisonResult],
        filename: str | None = None,
    ) -> Path:
        """Export multiple results to JSON.

        Args:
            results: List of results to export
            filename: Optional custom filename

        Returns:
            Path to exported file
        """
        if not filename:
            timestamp = self._get_timestamp()
            filename = f"layoutlens_batch_{timestamp}.json"

        filepath = self.output_dir / filename

        data = {
            "results": [self._result_to_dict(result) for result in results],
            "summary": {
                "total_results": len(results),
                "export_info": {
                    "exported_at": datetime.now().isoformat(),
                    "exporter": "LayoutLens JSONExporter",
                    "format_version": "1.0",
                },
            },
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

        return filepath

    def _result_to_dict(self, result: Any) -> dict[str, Any]:
        """Convert result object to dictionary."""
        if hasattr(result, "__dataclass_fields__"):
            # Handle dataclass
            return {field.name: getattr(result, field.name) for field in result.__dataclass_fields__.values()}
        elif hasattr(result, "__dict__"):
            return vars(result)
        else:
            return dict(result)


class CSVExporter(BaseExporter):
    """Export results to CSV format."""

    def export_batch(self, results: list[AnalysisResult], filename: str | None = None) -> Path:
        """Export analysis results to CSV.

        Args:
            results: List of AnalysisResult objects
            filename: Optional custom filename

        Returns:
            Path to exported file
        """
        if not filename:
            timestamp = self._get_timestamp()
            filename = f"layoutlens_results_{timestamp}.csv"

        filepath = self.output_dir / filename

        if not results:
            raise ExportError("No results to export")

        # Define CSV columns
        columns = [
            "source",
            "query",
            "answer",
            "confidence",
            "reasoning",
            "screenshot_path",
            "viewport",
            "execution_time",
            "timestamp",
            "provider",
            "model",
            "cache_hit",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()

            for result in results:
                row = {
                    "source": result.source,
                    "query": result.query,
                    "answer": result.answer,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "screenshot_path": result.screenshot_path,
                    "viewport": result.viewport,
                    "execution_time": result.execution_time,
                    "timestamp": result.timestamp,
                    "provider": result.metadata.get("provider", ""),
                    "model": result.metadata.get("model", ""),
                    "cache_hit": result.metadata.get("cache_hit", False),
                }
                writer.writerow(row)

        return filepath


class HTMLExporter(BaseExporter):
    """Export results to HTML format with embedded styling."""

    def __init__(self, output_dir: str | Path = "layoutlens_exports"):
        super().__init__(output_dir)
        self._setup_template()

    def _setup_template(self):
        """Setup Jinja2 template for HTML generation."""
        if not JINJA2_AVAILABLE:
            self.template = None
            return

        template_str = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LayoutLens Analysis Report - {{ report_title }}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                         system-ui, sans-serif;
            line-height: 1.6; color: #333; background: #f8f9fa;
            padding: 20px;
        }
        .container {
            max-width: 1200px; margin: 0 auto; background: white;
            border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 30px; border-radius: 8px 8px 0 0;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header .meta { opacity: 0.9; font-size: 1.1em; }
        .content { padding: 30px; }
        .summary {
            background: #f8f9fa; border-radius: 6px; padding: 20px;
            margin-bottom: 30px; display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        .summary .stat { text-align: center; }
        .summary .stat .value {
            font-size: 2em; font-weight: bold; color: #667eea;
        }
        .summary .stat .label {
            color: #6c757d; text-transform: uppercase;
            font-size: 0.85em; letter-spacing: 0.5px;
        }
        .result-card {
            border: 1px solid #e9ecef; border-radius: 6px;
            margin-bottom: 20px; overflow: hidden;
        }
        .result-header {
            background: #f8f9fa; padding: 15px;
            border-bottom: 1px solid #e9ecef;
        }
        .result-header .source { font-weight: bold; color: #495057; }
        .result-header .query {
            color: #6c757d; font-style: italic; margin-top: 5px;
        }
        .result-body { padding: 20px; }
        .confidence {
            display: inline-block; padding: 4px 12px;
            border-radius: 20px; font-size: 0.85em; font-weight: bold;
        }
        .confidence.high { background: #d4edda; color: #155724; }
        .confidence.medium { background: #fff3cd; color: #856404; }
        .confidence.low { background: #f8d7da; color: #721c24; }
        .answer { font-size: 1.1em; margin: 15px 0; color: #212529; }
        .reasoning { color: #6c757d; line-height: 1.7; }
        .metadata { margin-top: 15px; font-size: 0.9em; color: #6c757d; }
        .metadata span { margin-right: 15px; }
        .footer {
            text-align: center; padding: 20px; color: #6c757d;
            border-top: 1px solid #e9ecef;
        }
        @media (max-width: 768px) {
            body { padding: 10px; }
            .header { padding: 20px; }
            .header h1 { font-size: 2em; }
            .content { padding: 20px; }
            .summary { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 {{ report_title }}</h1>
            <div class="meta">
                Generated on {{ export_date }} | LayoutLens v{{ version }}
            </div>
        </div>

        <div class="content">
            {% if summary %}
            <div class="summary">
                {% for stat in summary %}
                <div class="stat">
                    <div class="value">{{ stat.value }}</div>
                    <div class="label">{{ stat.label }}</div>
                </div>
                {% endfor %}
            </div>
            {% endif %}

            {% for result in results %}
            <div class="result-card">
                <div class="result-header">
                    <div class="source">{{ result.source }}</div>
                    <div class="query">{{ result.query }}</div>
                </div>
                <div class="result-body">
                    <span class="confidence {{ result.confidence_level }}">
                        {{ "%.1f%%" | format(result.confidence * 100) }}
                        confidence
                    </span>
                    <div class="answer">{{ result.answer }}</div>
                    <div class="reasoning">{{ result.reasoning }}</div>
                    <div class="metadata">
                        <span><strong>Provider:</strong>
                            {{ result.metadata.get('provider', 'Unknown') }}
                        </span>
                        <span><strong>Model:</strong>
                            {{ result.metadata.get('model', 'Unknown') }}
                        </span>
                        <span><strong>Time:</strong>
                            {{ "%.2f" | format(result.execution_time) }}s
                        </span>
                        {% if result.screenshot_path %}
                        <span><strong>Screenshot:</strong>
                            {{ result.screenshot_path }}
                        </span>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>

        <div class="footer">
            Generated by <strong>LayoutLens</strong> -
            AI-powered UI testing framework
        </div>
    </div>
</body>
</html>
        """.strip()

        self.template = jinja2.Template(template_str)

    def export_results(
        self,
        results: list[AnalysisResult],
        title: str = "Analysis Report",
        filename: str | None = None,
    ) -> Path:
        """Export analysis results to HTML.

        Args:
            results: List of AnalysisResult objects
            title: Report title
            filename: Optional custom filename

        Returns:
            Path to exported file
        """
        if not JINJA2_AVAILABLE:
            raise ExportError("Jinja2 is required for HTML export. Install with: pip install jinja2")

        if not filename:
            timestamp = self._get_timestamp()
            safe_title = self._sanitize_filename(title)
            filename = f"layoutlens_{safe_title}_{timestamp}.html"

        filepath = self.output_dir / filename

        # Prepare data for template
        from layoutlens import __version__

        # Add confidence level classification - done inline below
        # Note: confidence_level calculated dynamically rather than stored

        # Calculate summary statistics
        if results:
            avg_confidence = sum(r.confidence for r in results) / len(results)
            high_confidence = sum(1 for r in results if r.confidence >= 0.7)
            avg_time = sum(r.execution_time for r in results) / len(results)

            summary = [
                {"value": len(results), "label": "Total Analyses"},
                {"value": f"{avg_confidence:.1%}", "label": "Avg Confidence"},
                {"value": high_confidence, "label": "High Confidence"},
                {"value": f"{avg_time:.2f}s", "label": "Avg Time"},
            ]
        else:
            summary = []

        def get_confidence_level(confidence):
            """Helper function for template to get confidence level"""
            if confidence >= 0.7:
                return "high"
            elif confidence >= 0.5:
                return "medium"
            else:
                return "low"

        html_content = self.template.render(
            report_title=title,
            export_date=datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            version=__version__,
            results=results,
            summary=summary,
            get_confidence_level=get_confidence_level,
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        return filepath


class PDFExporter(BaseExporter):
    """Export results to PDF format."""

    def __init__(self, output_dir: str | Path = "layoutlens_exports"):
        super().__init__(output_dir)
        if not REPORTLAB_AVAILABLE:
            raise ExportError("ReportLab is required for PDF export. Install with: pip install reportlab")

    def export_results(
        self,
        results: list[AnalysisResult],
        title: str = "LayoutLens Analysis Report",
        filename: str | None = None,
    ) -> Path:
        """Export analysis results to PDF.

        Args:
            results: List of AnalysisResult objects
            title: Report title
            filename: Optional custom filename

        Returns:
            Path to exported file
        """
        if not filename:
            timestamp = self._get_timestamp()
            safe_title = self._sanitize_filename(title)
            filename = f"layoutlens_{safe_title}_{timestamp}.pdf"

        filepath = self.output_dir / filename

        # Create PDF document
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )

        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor("#667eea"),
            alignment=1,  # Center
        )

        # Build content
        story = []

        # Title
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))

        # Metadata
        from layoutlens import __version__

        meta_text = f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')} | LayoutLens v{__version__}"
        story.append(Paragraph(meta_text, styles["Normal"]))
        story.append(Spacer(1, 30))

        # Summary statistics
        if results:
            avg_confidence = sum(r.confidence for r in results) / len(results)
            high_confidence = sum(1 for r in results if r.confidence >= 0.7)
            avg_time = sum(r.execution_time for r in results) / len(results)

            summary_data = [
                ["Metric", "Value"],
                ["Total Analyses", str(len(results))],
                ["Average Confidence", f"{avg_confidence:.1%}"],
                ["High Confidence Results", str(high_confidence)],
                ["Average Execution Time", f"{avg_time:.2f}s"],
            ]

            summary_table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
            summary_table.setStyle(
                TableStyle(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, 0),
                            colors.HexColor("#667eea"),
                        ),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )

            story.append(Paragraph("Summary", styles["Heading2"]))
            story.append(summary_table)
            story.append(Spacer(1, 30))

        # Individual results
        story.append(Paragraph("Analysis Results", styles["Heading2"]))
        story.append(Spacer(1, 20))

        for i, result in enumerate(results, 1):
            # Result header
            source_text = f"<b>Source:</b> {result.source}"
            query_text = f"<b>Query:</b> {result.query}"

            story.append(Paragraph(f"Result {i}", styles["Heading3"]))
            story.append(Paragraph(source_text, styles["Normal"]))
            story.append(Paragraph(query_text, styles["Normal"]))
            story.append(Spacer(1, 10))

            # Confidence and answer
            confidence_color = (
                "#28a745" if result.confidence >= 0.7 else "#ffc107" if result.confidence >= 0.5 else "#dc3545"
            )
            confidence_text = f'<font color="{confidence_color}"><b>Confidence: {result.confidence:.1%}</b></font>'
            story.append(Paragraph(confidence_text, styles["Normal"]))

            answer_text = f"<b>Answer:</b> {result.answer}"
            story.append(Paragraph(answer_text, styles["Normal"]))
            story.append(Spacer(1, 10))

            # Reasoning
            reasoning_text = f"<b>Reasoning:</b> {result.reasoning}"
            story.append(Paragraph(reasoning_text, styles["Normal"]))
            story.append(Spacer(1, 10))

            # Metadata
            provider = result.metadata.get("provider", "Unknown")
            model = result.metadata.get("model", "Unknown")
            meta_text = f"Provider: {provider} | Model: {model} | Time: {result.execution_time:.2f}s"
            story.append(Paragraph(meta_text, styles["Normal"]))

            if i < len(results):
                story.append(Spacer(1, 20))

        # Build PDF
        doc.build(story)
        return filepath


class ExportManager:
    """Main export manager that coordinates different export formats."""

    def __init__(self, output_dir: str | Path = "layoutlens_exports"):
        """Initialize export manager.

        Args:
            output_dir: Directory to save exported files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Initialize exporters
        self.json_exporter = JSONExporter(output_dir)
        self.csv_exporter = CSVExporter(output_dir)
        self.html_exporter = HTMLExporter(output_dir)

        if REPORTLAB_AVAILABLE:
            self.pdf_exporter: PDFExporter | None = PDFExporter(output_dir)
        else:
            self.pdf_exporter = None

    def export(
        self,
        results: AnalysisResult | list[AnalysisResult] | BatchResult,
        formats: list[str] = None,
        title: str = "LayoutLens Analysis Report",
        filename_base: str | None = None,
    ) -> dict[str, Path]:
        """Export results in multiple formats.

        Args:
            results: Analysis results to export
            formats: List of formats to export ("json", "csv", "html", "pdf")
            title: Report title for formatted exports
            filename_base: Base filename (without extension)

        Returns:
            Dictionary mapping format to exported file path
        """
        # Normalize results to a list
        if formats is None:
            formats = ["json"]
        normalized_results: list[AnalysisResult | BatchResult | ComparisonResult] = []

        if isinstance(results, list):
            normalized_results = list(results)  # Create a new list to satisfy mypy
        elif isinstance(results, AnalysisResult | BatchResult | ComparisonResult):
            normalized_results = [results]
        else:
            raise ExportError(f"Unsupported result type: {type(results)}")

        if not normalized_results:
            raise ExportError("No results to export")

        # Ensure we're working with AnalysisResult objects for certain formats
        analysis_results: list[AnalysisResult] = []
        for result in normalized_results:
            if isinstance(result, AnalysisResult):
                analysis_results.append(result)
            elif isinstance(result, BatchResult) and result.results:
                # BatchResult case
                analysis_results.extend(result.results)

        exported_files = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for fmt in formats:
            try:
                match fmt.lower():
                    case "json":
                        json_name = f"{filename_base}_{timestamp}.json"
                        filename = json_name if filename_base else None
                        if len(normalized_results) == 1:
                            filepath = self.json_exporter.export_result(normalized_results[0], filename)
                        else:
                            filepath = self.json_exporter.export_batch(normalized_results, filename)
                        exported_files["json"] = filepath

                    case "csv" if analysis_results:
                        csv_name = f"{filename_base}_{timestamp}.csv"
                        filename = csv_name if filename_base else None
                        filepath = self.csv_exporter.export_batch(analysis_results, filename)
                        exported_files["csv"] = filepath

                    case "html" if analysis_results:
                        html_name = f"{filename_base}_{timestamp}.html"
                        filename = html_name if filename_base else None
                        filepath = self.html_exporter.export_results(analysis_results, title, filename)
                        exported_files["html"] = filepath

                    case "pdf" if analysis_results:
                        if not self.pdf_exporter:
                            msg = "PDF export requires ReportLab: pip install reportlab"
                            raise ExportError(msg)
                        pdf_name = f"{filename_base}_{timestamp}.pdf"
                        filename = pdf_name if filename_base else None
                        filepath = self.pdf_exporter.export_results(analysis_results, title, filename)
                        exported_files["pdf"] = filepath

                    case _:
                        raise ExportError(f"Unsupported export format: {fmt}")

            except Exception as e:
                raise ExportError(f"Failed to export as {fmt}: {str(e)}") from e

        return exported_files

    def get_supported_formats(self) -> list[str]:
        """Get list of supported export formats.

        Returns:
            List of supported format names
        """
        formats = ["json", "csv"]

        if JINJA2_AVAILABLE:
            formats.append("html")

        if REPORTLAB_AVAILABLE:
            formats.append("pdf")

        return formats
