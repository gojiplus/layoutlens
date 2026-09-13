"""Executable package and consumer contracts, including candidate wheel metadata."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tomllib
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from layoutlens import DiffReport
from layoutlens.sarif import diff_to_sarif

ROOT = Path(__file__).resolve().parents[1]
ACTION = Path(
    os.environ.get("LAYOUTLENS_ACTION_ROOT", ROOT.parent / "layoutlens-action")
)
BENCH = Path(os.environ.get("UIJUDGE_BENCH_ROOT", ROOT.parent / "uijudge-bench"))


def metadata():
    wheel = os.environ.get("LAYOUTLENS_WHEEL")
    if wheel:
        with ZipFile(wheel) as archive:
            names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
            assert len(names) == 1
            info = BytesParser().parsebytes(archive.read(names[0]))
        return (
            info["Version"],
            info["Requires-Python"],
            set(info.get_all("Provides-Extra", [])),
        )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    return (
        project["version"],
        project["requires-python"],
        set(project.get("optional-dependencies", {})),
    )


def test_python_floor_and_candidate_dependencies():
    version, floor, extras = metadata()
    assert Version("3.12") in SpecifierSet(floor)
    assert Version("3.11") not in SpecifierSet(floor)
    if not BENCH.is_dir() or not ACTION.is_dir():
        pytest.skip("consumer checkouts supplied by the release-contract workflow")
    project = tomllib.loads((BENCH / "pyproject.toml").read_text())["project"]
    consumer_floor = SpecifierSet(project["requires-python"])
    assert Version("3.11") not in consumer_floor
    assert Version("3.12") in consumer_floor
    requirements = project["dependencies"] + [
        r for group in project.get("optional-dependencies", {}).values() for r in group
    ]
    for text in requirements:
        requirement = Requirement(text)
        if requirement.name == "layoutlens":
            assert Version(version) in requirement.specifier
            assert requirement.extras <= extras
    action = yaml.safe_load((ACTION / "action.yml").read_text())
    assert action["inputs"]["layoutlens-version"]["default"] == version
    assert Version(action["inputs"]["python-version"]["default"]) in SpecifierSet(floor)


def test_action_consumes_structured_sarif(tmp_path):
    if not ACTION.is_dir():
        pytest.skip("Action checkout supplied by the release-contract workflow")
    spec = importlib.util.spec_from_file_location(
        "action_report_contract", ACTION / "scripts/report.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = DiffReport(before="a", after="b", incomplete_reasons=["font failed"])
    sarif = diff_to_sarif(report)
    (tmp_path / "result.sarif").write_text(json.dumps(sarif))
    merged = module.merge(module.load_runs(tmp_path))
    assert merged["runs"][0]["properties"]["incomplete"] is True
    assert not module.merge([diff_to_sarif(DiffReport(before="a", after="b"))])["runs"][
        0
    ]["properties"]["incomplete"]


def test_benchmark_adapters_use_installed_package(monkeypatch):
    if not BENCH.is_dir():
        pytest.skip("UIJudgeBench checkout supplied by the release-contract workflow")
    monkeypatch.syspath_prepend(str(BENCH))
    from uijudge.harness.judges.layoutlens_batch import LayoutLensBatchJudge
    from uijudge.harness.judges.layoutlens_judge import LayoutLensJudge
    from uijudge.harness.judges.layoutlens_layout import LayoutLensLayoutJudge

    assert LayoutLensLayoutJudge().requires == {"layout"}
    judge = LayoutLensJudge(model="gpt-4o-mini")
    assert callable(judge._get_lens().judge)
    batch = LayoutLensBatchJudge()
    assert callable(batch._get_lens().judge_batch)
    assert sys.version_info >= (3, 12)


@pytest.mark.skipif(os.name != "posix", reason="the composite action runs Bash")
def test_action_shell_preserves_incomplete_status(tmp_path, render_state):
    import shutil
    import subprocess

    if not ACTION.is_dir():
        pytest.skip("Action checkout supplied by the release-contract workflow")
    baseline = render_state.save(tmp_path / "before")
    render_state.coverage_gaps = ["font failed"]
    candidate = render_state.save(tmp_path / "after")
    action = yaml.safe_load((ACTION / "action.yml").read_text())
    env = dict(
        os.environ,
        LL_BASELINE=str(baseline),
        LL_CANDIDATE=str(candidate),
        LL_SOURCES="",
        LL_CHECKS="layout",
        LL_VIEWPORT="desktop",
        LL_FAIL_ON="qualified",
        RUNNER_TEMP=str(tmp_path),
        GITHUB_ACTION_PATH=str(ACTION),
        GITHUB_OUTPUT=str(tmp_path / "outputs"),
        PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
    )
    steps = {step["name"]: step for step in action["runs"]["steps"]}
    bash = shutil.which("bash")
    assert bash
    for name in [
        "Run deterministic checks",
        "Build report (summary, annotations, comment, outputs)",
    ]:
        result = subprocess.run(  # noqa: S603 -- trusted workflow in a fixed test environment
            [bash, "-c", steps[name]["run"]],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
    outputs = dict(
        line.split("=", 1) for line in (tmp_path / "outputs").read_text().splitlines()
    )
    assert outputs["incomplete"] == "true"
    env.update(
        LL_FINDINGS=outputs["findings"],
        LL_BLOCKING=outputs["blocking"],
        LL_REGRESSIONS=outputs["regressions"],
        LL_INCOMPLETE=outputs["incomplete"],
    )
    result = subprocess.run(  # noqa: S603 -- trusted workflow in a fixed test environment
        [bash, "-c", steps["Verdict"]["run"]],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
