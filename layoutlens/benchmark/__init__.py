"""
LayoutLens Benchmark System

Modern benchmark infrastructure for AI-powered UI testing with:
- Live website harvesting from multiple sources
- Multi-environment visual capture
- Systematic issue injection
- Query diversity generation
- Performance validation
"""

from .harvester import WebsiteHarvester, Website
from .capture import ModernVisualCapture, VisualTestResult
from .injection import IssueInjectionEngine, IssueVariation
from .queries import QueryDiversityEngine, ContextualQuery
from .validation import BenchmarkValidator, ValidationResults

__all__ = [
    "WebsiteHarvester", "Website",
    "ModernVisualCapture", "VisualTestResult", 
    "IssueInjectionEngine", "IssueVariation",
    "QueryDiversityEngine", "ContextualQuery",
    "BenchmarkValidator", "ValidationResults"
]