"""
GitHub integration utilities for LayoutLens.

This module provides helper functions and classes for integrating
LayoutLens with GitHub Actions and other GitHub workflows.
"""

import json
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

from ..api.core import LayoutLens, AnalysisResult


class GitHubIntegration:
    """Helper class for GitHub Actions integration."""
    
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        """Initialize GitHub integration."""
        self.lens = LayoutLens(api_key=api_key, model=model)
    
    def analyze_pr_preview(
        self,
        preview_url: str,
        queries: list[str] | None = None,
        viewports: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Analyze a pull request preview URL.
        
        Parameters
        ----------
        preview_url : str
            URL of the preview deployment
        queries : list[str], optional
            Custom queries, defaults to common PR checks
        viewports : list[str], optional
            Viewports to test, defaults to ["desktop", "mobile"]
            
        Returns
        -------
        dict
            Analysis results formatted for GitHub Actions
        """
        if queries is None:
            queries = [
                "Does this change improve the user experience?",
                "Are there any obvious visual regressions?",
                "Is the layout responsive and mobile-friendly?",
                "Are there any accessibility issues introduced?"
            ]
        
        if viewports is None:
            viewports = ["desktop", "mobile"]
        
        all_results = []
        
        for viewport in viewports:
            for query in queries:
                result = self.lens.analyze(preview_url, query, viewport)
                all_results.append(result)
        
        # Calculate metrics
        successful_results = [r for r in all_results if r.confidence > 0]
        overall_score = sum(r.confidence for r in successful_results) / len(successful_results) if successful_results else 0.0
        
        return {
            "overall_score": overall_score,
            "passed": overall_score >= 0.7,
            "results": all_results,
            "summary": self._generate_summary(all_results, overall_score)
        }
    
    def compare_before_after(
        self,
        before_url: str,
        after_url: str,
        viewport: str = "desktop"
    ) -> dict[str, Any]:
        """
        Compare before/after URLs for a deployment.
        
        Parameters
        ----------
        before_url : str
            URL of the previous version
        after_url : str  
            URL of the new version
        viewport : str, default "desktop"
            Viewport for comparison
            
        Returns
        -------
        dict
            Comparison results
        """
        result = self.lens.compare(
            [before_url, after_url],
            "What are the main differences between these versions? Are there any regressions?",
            viewport
        )
        
        return {
            "comparison": result,
            "recommendation": self._generate_deployment_recommendation(result)
        }
    
    def generate_pr_comment(self, analysis_results: dict[str, Any]) -> str:
        """
        Generate a formatted PR comment from analysis results.
        
        Parameters
        ----------
        analysis_results : dict
            Results from analyze_pr_preview
            
        Returns
        -------
        str
            Markdown-formatted comment for GitHub PR
        """
        overall_score = analysis_results["overall_score"]
        passed = analysis_results["passed"]
        results = analysis_results["results"]
        
        # Header with status
        status_emoji = "✅" if passed else "⚠️" if overall_score >= 0.5 else "❌"
        status_text = "PASS" if passed else "REVIEW NEEDED"
        
        comment = f"""## LayoutLens UI Analysis {status_emoji}

**Status:** {status_text}  
**Overall Score:** {overall_score:.1%}

### Analysis Results

"""
        
        # Group by viewport
        viewport_results = {}
        for result in results:
            viewport = result.viewport
            if viewport not in viewport_results:
                viewport_results[viewport] = []
            viewport_results[viewport].append(result)
        
        for viewport, viewport_results_list in viewport_results.items():
            comment += f"#### {viewport.title()} Viewport\n\n"
            
            for result in viewport_results_list:
                confidence_emoji = "✅" if result.confidence >= 0.8 else "⚠️" if result.confidence >= 0.6 else "❌"
                comment += f"- **{result.query}** {confidence_emoji} `{result.confidence:.1%}`\n"
                comment += f"  {result.answer}\n\n"
        
        comment += """
---
*Powered by [LayoutLens](https://github.com/your-org/layoutlens) - AI-powered UI testing*
"""
        
        return comment
    
    def _generate_summary(self, results: list[AnalysisResult], overall_score: float) -> str:
        """Generate a summary of analysis results."""
        high_confidence = len([r for r in results if r.confidence >= 0.8])
        total = len(results)
        
        if overall_score >= 0.8:
            return f"Excellent UI quality - {high_confidence}/{total} checks passed with high confidence"
        elif overall_score >= 0.7:
            return f"Good UI quality - {high_confidence}/{total} checks passed with high confidence"
        elif overall_score >= 0.5:
            return f"UI quality needs attention - only {high_confidence}/{total} checks passed with high confidence"
        else:
            return f"Significant UI issues detected - {high_confidence}/{total} checks passed with high confidence"
    
    def _generate_deployment_recommendation(self, comparison_result) -> str:
        """Generate deployment recommendation based on comparison."""
        confidence = comparison_result.confidence
        answer = comparison_result.answer.lower()
        
        if confidence >= 0.8 and "improve" in answer:
            return "✅ DEPLOY - Changes improve the user experience"
        elif confidence >= 0.7 and "regression" not in answer:
            return "✅ DEPLOY - Changes look good with no major issues"
        elif "regression" in answer or "worse" in answer:
            return "❌ DO NOT DEPLOY - Potential regressions detected"
        else:
            return "⚠️ REVIEW - Manual review recommended before deployment"


def create_workflow_template() -> str:
    """Create a complete GitHub workflow template."""
    
    return """name: LayoutLens UI Quality Check

on:
  pull_request:
    types: [opened, synchronize, reopened]
  deployment_status:

jobs:
  ui-analysis:
    runs-on: ubuntu-latest
    if: github.event.deployment_status.state == 'success' || github.event_name == 'pull_request'
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Get Preview URL
        id: preview_url
        run: |
          # For Vercel deployments
          if [ "${{ github.event_name }}" == "deployment_status" ]; then
            echo "url=${{ github.event.deployment_status.target_url }}" >> $GITHUB_OUTPUT
          else
            # For PR previews, adjust this based on your deployment system
            echo "url=https://pr-${{ github.event.number }}.your-domain.com" >> $GITHUB_OUTPUT
          fi
      
      - name: LayoutLens Analysis
        id: layoutlens
        uses: ./layoutlens/.github/actions/layoutlens
        with:
          url: ${{ steps.preview_url.outputs.url }}
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          queries: |
            - "Is the navigation clear and accessible?"
            - "Does the layout work well on mobile devices?"
            - "Are there any obvious usability issues?"
            - "Does this change improve the user experience?"
          viewports: 'desktop,mobile,tablet'
          fail_threshold: '0.7'
      
      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const markdown = fs.readFileSync('layoutlens_output/results/analysis_results.md', 'utf8');
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: markdown
            });
      
      - name: Fail if quality threshold not met
        if: steps.layoutlens.outputs.passed == 'false'
        run: |
          echo "UI quality check failed with score: ${{ steps.layoutlens.outputs.overall_score }}"
          exit 1

"""


def create_simple_workflow_template() -> str:
    """Create a simple workflow template for basic usage."""
    
    return """name: Simple UI Check

on:
  pull_request:

jobs:
  check-ui:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Check UI Quality
        uses: ./layoutlens/.github/actions/layoutlens
        with:
          url: 'https://your-preview-url.com'
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          queries: 'Is the layout professional and user-friendly?'
"""