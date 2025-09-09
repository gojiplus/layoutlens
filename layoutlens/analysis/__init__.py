"""DOM analysis and query generation for LayoutLens.

This module provides intelligent query generation from HTML analysis
and DOM structure understanding.
"""

from .query_generator import QueryGenerator, GeneratedQuery, ElementInfo, generate_queries_from_file

__all__ = ["QueryGenerator", "GeneratedQuery", "ElementInfo", "generate_queries_from_file"]