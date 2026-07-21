#!/usr/bin/env python3
"""Generate axe-core ground truth for the accessibility benchmark fixtures.

Runs the deterministic :class:`~layoutlens.a11y.AxeAuditor` (WCAG 2.0 A + AA)
over each accessibility fixture, prints a reconciliation report comparing what
axe actually finds against the claims baked into
``benchmarks/answer_keys/accessibility.json``, and writes a machine-traceable
``axe_ground_truth`` block into each fixture's answer-key entry.

This is an **offline** tool: it drives a headless chromium via Playwright and
never calls an LLM. It is idempotent — re-running it reproduces the same
``axe_ground_truth`` blocks (the answer key is only rewritten when its content
actually changes).

Usage::

    uv run python benchmarks/generators/generate_a11y_ground_truth.py
    uv run python benchmarks/generators/generate_a11y_ground_truth.py --check
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Make the project root importable when run as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from layoutlens.a11y import AXE_VERSION, AxeAuditor  # noqa: E402

FIXTURE_DIR = PROJECT_ROOT / "benchmarks" / "test_data" / "accessibility"
ANSWER_KEY = PROJECT_ROOT / "benchmarks" / "answer_keys" / "accessibility.json"
RUN_ONLY = ["wcag2a", "wcag2aa"]


async def _audit_fixtures(filenames: list[str]) -> dict[str, dict]:
    """Audit each fixture and return a serializable axe_ground_truth block."""
    auditor = AxeAuditor(run_only=RUN_ONLY)
    ground_truth: dict[str, dict] = {}
    for filename in filenames:
        report = await auditor.audit(str(FIXTURE_DIR / filename))
        ground_truth[filename] = {
            "engine": "axe-core",
            "engine_version": report.engine_version,
            "run_only": RUN_ONLY,
            "violations": [
                {
                    "rule_id": f.rule_id,
                    "impact": f.impact,
                    "wcag_refs": f.wcag_refs,
                    "node_count": len(f.nodes),
                }
                for f in report.violations
            ],
            "incomplete_rule_ids": sorted({f.rule_id for f in report.incomplete}),
            "passes_count": report.passes_count,
            "ok": report.ok,
        }
    return ground_truth


def _claimed_violation_rules(entry: dict) -> list[str]:
    """Extract the human-readable violation claims from an answer-key entry."""
    return list(entry.get("metadata", {}).get("violations", []))


def _print_reconciliation(ground_truth: dict[str, dict], answer_key: dict) -> None:
    """Print a per-fixture reconciliation of axe findings vs answer-key claims."""
    print("=" * 72)
    print(f"AXE GROUND TRUTH RECONCILIATION (axe-core {AXE_VERSION}, {RUN_ONLY})")
    print("=" * 72)
    test_cases = answer_key["test_cases"]
    for filename, gt in ground_truth.items():
        entry = test_cases[filename]
        example_type = entry.get("metadata", {}).get("example_type", "?")
        axe_rules = [v["rule_id"] for v in gt["violations"]]
        print(f"\n{filename}  (answer-key example_type={example_type})")
        print(f"  axe violations : {axe_rules or 'none'}  -> ok={gt['ok']}")
        if gt["violations"]:
            for v in gt["violations"]:
                print(f"      - {v['rule_id']} [{v['impact']}] {v['wcag_refs']} x{v['node_count']}")
        claims = _claimed_violation_rules(entry)
        if claims:
            print(f"  answer-key metadata.violations claims: {claims}")
            print("  note: answer-key 'violations' are prose labels, not axe rule ids;")
            print("        the axe_ground_truth block above is the machine-traceable record.")
    print("\n" + "=" * 72)


def _apply_ground_truth(answer_key: dict, ground_truth: dict[str, dict]) -> bool:
    """Insert axe_ground_truth blocks into the answer key. Returns True if changed."""
    changed = False
    for filename, gt in ground_truth.items():
        entry = answer_key["test_cases"][filename]
        if entry.get("axe_ground_truth") != gt:
            entry["axe_ground_truth"] = gt
            changed = True
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit non-zero if the answer key would change or the "
        "compliant fixture still has axe violations.",
    )
    args = parser.parse_args()

    with open(ANSWER_KEY) as f:
        answer_key = json.load(f)

    filenames = list(answer_key["test_cases"].keys())
    missing = [f for f in filenames if not (FIXTURE_DIR / f).exists()]
    if missing:
        print(f"ERROR: missing fixtures: {missing}")
        return 2

    ground_truth = asyncio.run(_audit_fixtures(filenames))
    _print_reconciliation(ground_truth, answer_key)

    # Sanity gate: the "compliant" fixture must be genuinely clean under axe.
    compliant = ground_truth.get("wcag_compliant.html")
    if compliant is not None and not compliant["ok"]:
        print("\nERROR: wcag_compliant.html still has axe violations:")
        for v in compliant["violations"]:
            print(f"  - {v['rule_id']} [{v['impact']}] {v['wcag_refs']}")
        return 1
    print("\nOK: wcag_compliant.html is clean under axe (0 violations).")

    would_change = _apply_ground_truth(answer_key, ground_truth)

    if args.check:
        if would_change:
            print("\n--check: answer key axe_ground_truth blocks are stale (would change).")
            return 1
        print("\n--check: answer key axe_ground_truth blocks are up to date.")
        return 0

    if would_change:
        with open(ANSWER_KEY, "w") as f:
            json.dump(answer_key, f, indent=2)
            f.write("\n")
        print(f"\nWrote axe_ground_truth blocks to {ANSWER_KEY}")
    else:
        print("\nAnswer key already up to date; nothing to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
