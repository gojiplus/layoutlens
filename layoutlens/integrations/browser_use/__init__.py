"""
Browser Use integration for LayoutLens.

Provides hooks and utilities for validating browser agent actions
using LayoutLens visual analysis.

Examples:
    >>> from layoutlens.integrations.browser_use import AgentValidator, ValidationPolicy
    >>> validator = AgentValidator(
    ...     experts=["accessibility_expert", "mobile_expert"],
    ...     policy=ValidationPolicy(capture_on_click=True)
    ... )
    >>> hooks = validator.get_hooks()
    >>> await agent.run(**hooks)
    >>> session = validator.get_session()
    >>> print(f"Found {session.total_findings} issues")
"""

from .reports import ValidationReportGenerator
from .session import SessionRecorder, SessionReplayer
from .types import (
    SessionComparison,
    SessionRecording,
    SessionState,
    ValidationFinding,
    ValidationPolicy,
    ValidationSession,
    ValidationSeverity,
    ValidationStepResult,
    ValidationTrigger,
)
from .validator import AgentValidator

__all__ = [
    "AgentValidator",
    "SessionRecorder",
    "SessionReplayer",
    "ValidationReportGenerator",
    "ValidationPolicy",
    "ValidationSession",
    "ValidationStepResult",
    "ValidationFinding",
    "ValidationTrigger",
    "ValidationSeverity",
    "SessionState",
    "SessionRecording",
    "SessionComparison",
]
