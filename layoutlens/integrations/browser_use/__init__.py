"""Browser Use integration for LayoutLens.

Post-run validation of browser-use agent sessions at the stable seam — the
``AgentHistoryList`` returned by ``Agent.run()`` — plus report generation.

Examples:
    >>> from layoutlens import LayoutLens
    >>> from layoutlens.integrations.browser_use import validate_agent_run
    >>> history = await agent.run()
    >>> session = await validate_agent_run(LayoutLens(), history)
    >>> print(f"Found {session.total_findings} issues")
"""

from .reports import ValidationReportGenerator
from .types import (
    SessionState,
    ValidationFinding,
    ValidationPolicy,
    ValidationSession,
    ValidationSeverity,
    ValidationStepResult,
    ValidationTrigger,
)
from .validator import validate_agent_run

__all__ = [
    "SessionState",
    "ValidationFinding",
    "ValidationPolicy",
    "ValidationReportGenerator",
    "ValidationSession",
    "ValidationSeverity",
    "ValidationStepResult",
    "ValidationTrigger",
    "validate_agent_run",
]
