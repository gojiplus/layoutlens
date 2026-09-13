"""Evidence-backed CSS locations and revision-verified local git context."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

if TYPE_CHECKING:
    from .models import RenderState, VisualDelta


def _git(repository: Path, *arguments: str) -> str:
    executable = shutil.which("git")
    if not executable:
        raise ValueError("git is not installed")
    return subprocess.run(  # noqa: S603 -- fixed executable and argument vector; no shell
        [executable, "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout


def _renamed_from(repository: Path, before: str, after: str, path: str) -> str | None:
    tokens = _git(
        repository,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--name-status",
        "--find-renames",
        "-z",
        before,
        after,
    ).split("\0")
    index = 0
    while index < len(tokens) - 1:
        status = tokens[index]
        if status.startswith(("R", "C")):
            if tokens[index + 2] == path:
                return tokens[index + 1]
            index += 3
        else:
            index += 2
    return None


def _related_patch(patch: str, line: int) -> str:
    headers, selected, current = [], [], []
    include = False
    for text in patch.splitlines(keepends=True):
        match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", text)
        if match:
            if include:
                selected.extend(current)
            start, count = int(match[1]), int(match[2] or 1)
            include = start <= line < start + count
            current = [text]
        elif current:
            current.append(text)
        else:
            headers.append(text)
    if include:
        selected.extend(current)
    return "".join(headers + selected) if selected else ""


def _file(url: str, source: str, repository: Path) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme == "file":
        candidate = Path(unquote(parsed.path)).resolve()
    elif (
        parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        and not urlparse(source).scheme
        and Path(source).is_file()
    ):
        candidate = (
            (Path(source).resolve().parent / unquote(parsed.path).lstrip("/")).resolve()
            if parsed.path not in ("", "/")
            else Path(source).resolve()
        )
    else:
        return None
    return candidate if candidate.is_relative_to(repository) else None


def attribute(
    delta: VisualDelta,
    before: RenderState,
    after: RenderState,
    repository: str | Path | None,
) -> list[dict]:
    """Link property changes to candidate declarations without asserting causality."""
    old = {n.key: n for n in before.graph.nodes}
    new = {n.key: n for n in after.graph.nodes}
    a, b = old.get(delta.before_element or ""), new.get(delta.after_element or "")
    if b is None:
        return []
    candidates = []
    while b:
        previous = a.styles if a else {}
        changed = {
            prop for prop, value in b.styles.items() if previous.get(prop) != value
        }
        for declaration in b.declarations:
            prop = declaration["property"]
            if prop not in changed and not prop.startswith("--"):
                continue
            if a and declaration in a.declarations:
                continue
            candidate = {
                **declaration,
                "element": b.selector,
                "evidence_level": "candidate-declaration",
                "computed_before": previous.get(prop),
                "computed_after": b.styles.get(prop),
                "missing_links": [],
            }
            location = declaration.get("range")
            if location and declaration.get("origin") != "inline":
                candidate["line"] = (
                    location["startLine"]
                    + declaration.get("stylesheet_start_line", 0)
                    + 1
                )
                candidate["column"] = (
                    location["startColumn"]
                    + (
                        declaration.get("stylesheet_start_column", 0)
                        if location["startLine"] == 0
                        else 0
                    )
                    + 1
                )
            else:
                candidate["missing_links"].append("source line unavailable")
            if declaration.get("original_source"):
                candidate.update(declaration["original_source"])
                candidate["evidence_level"] = "source-mapped-location"
            elif declaration.get("source_map_url"):
                candidate["missing_links"].append(
                    declaration.get(
                        "source_map_error", "original source mapping unavailable"
                    )
                )
            if repository and before.revision and after.revision:
                root = Path(repository).resolve()
                file = _file(candidate.get("url", ""), after.source, root)
                if file is not None and candidate.get("line"):
                    try:
                        old_revision = _git(
                            root,
                            "rev-parse",
                            "--verify",
                            "--end-of-options",
                            before.revision + "^{commit}",
                        ).strip()
                        new_revision = _git(
                            root,
                            "rev-parse",
                            "--verify",
                            "--end-of-options",
                            after.revision + "^{commit}",
                        ).strip()
                        path = file.relative_to(root).as_posix()
                        content = _git(root, "show", f"{new_revision}:{path}")
                        line = content.splitlines()[candidate["line"] - 1]
                        original_content = candidate.get("source_content")
                        if original_content is not None:
                            if original_content != content:
                                raise ValueError(
                                    "source map content does not match revision"
                                )
                        elif prop not in line or declaration["value"] not in line:
                            raise ValueError(
                                "captured declaration does not match revision line"
                            )
                        renamed_from = _renamed_from(
                            root, old_revision, new_revision, path
                        )
                        paths = [path, renamed_from] if renamed_from else [path]
                        if renamed_from:
                            candidate["renamed_from"] = renamed_from
                        patch = _git(
                            root,
                            "diff",
                            "--no-ext-diff",
                            "--no-textconv",
                            "--find-renames",
                            "--unified=3",
                            old_revision,
                            new_revision,
                            "--",
                            *paths,
                        )
                        candidate.update(
                            file=path,
                            revision=new_revision,
                            evidence_level="revision-verified-location",
                        )
                        patch = _related_patch(patch, candidate["line"])
                        if patch:
                            candidate["git_diff"] = patch
                            candidate["git_evidence"] = (
                                "related source hunk; causality unverified"
                            )
                        else:
                            candidate["missing_links"].append(
                                "no edit to this file between revisions"
                            )
                    except (
                        ValueError,
                        IndexError,
                        subprocess.SubprocessError,
                        OSError,
                    ) as error:
                        candidate["missing_links"].append(str(error))
                else:
                    candidate["missing_links"].append(
                        "repository path mapping unavailable"
                    )
            else:
                candidate["missing_links"].append(
                    "repository and both revisions required for git attribution"
                )
            candidates.append(candidate)
        if not delta.defect_class:
            break
        b = new.get(b.parent or "")
        a = old.get(a.parent or "") if a else None
    return candidates
