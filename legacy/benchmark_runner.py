"""Execute natural-language layout tests defined in CSV files."""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Dict

from screenshot import html_to_image

try:
    from framework import LayoutLens
except Exception:  # pragma: no cover - if openai not installed
    LayoutLens = None  # type: ignore


# ---------------------------------------------------------------------------
# Benchmark helpers


def run_single(csv_path: str, out_dir: str, skip_model: bool) -> None:
    """Run the basic benchmark defined in ``../benchmarks/benchmark.csv``."""
    rows = list(csv.DictReader(open(csv_path)))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    lens = None
    if not skip_model and LayoutLens is not None:
        try:
            lens = LayoutLens()
        except Exception as exc:
            print(f"Could not initialize model: {exc}")
            skip_model = True
    else:
        skip_model = True

    for row in rows:
        html_path = row["html_path"]
        dom_id = row.get("dom_id")
        behavior = row.get("expected_behavior", "")
        image_path = out / (Path(html_path).stem + ".png")
        try:
            html_to_image(html_path, str(image_path))
        except Exception as exc:
            print(f"Failed to render {html_path}: {exc}")
            continue

        query = f"Is the element with id '{dom_id}' {behavior.replace('_', ' ')}?"
        print(f"Query: {query}")

        if not skip_model and lens:
            try:
                answer = lens.ask([str(image_path)], query)
                print("Model answer:", answer)
            except Exception as exc:
                print(f"Model call failed: {exc}")
        else:
            print("Model skipped; set OPENAI_API_KEY to enable.")


def run_pairs(csv_path: str, out_dir: str, skip_model: bool) -> None:
    """Run pairwise layout comparison benchmark."""
    rows = list(csv.DictReader(open(csv_path)))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    lens = None
    if not skip_model and LayoutLens is not None:
        try:
            lens = LayoutLens()
        except Exception as exc:
            print(f"Could not initialize model: {exc}")
            skip_model = True
    else:
        skip_model = True

    for row in rows:
        html_a = row["html_path_a"]
        html_b = row["html_path_b"]
        query = row.get("query", "Do these two layouts look the same?")
        out_a = out / (Path(html_a).stem + "_a.png")
        out_b = out / (Path(html_b).stem + "_b.png")

        for src, dest in [(html_a, out_a), (html_b, out_b)]:
            try:
                html_to_image(src, str(dest))
            except Exception as exc:
                print(f"Failed to render {src}: {exc}")
                continue

        print(f"Query: {query}")
        if not skip_model and lens:
            try:
                answer = lens.ask([str(out_a), str(out_b)], query)
                print("Model answer:", answer)
            except Exception as exc:
                print(f"Model call failed: {exc}")
        else:
            print("Model skipped; set OPENAI_API_KEY to enable.")


# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-model", action="store_true", help="do not call OpenAI")
    parser.add_argument("--out", default="screenshots", help="output directory for screenshots")
    parser.add_argument("--benchmark", default="../benchmarks/benchmark.csv")
    parser.add_argument("--pairs", default="../benchmarks/benchmark_pairs.csv")
    args = parser.parse_args()

    if Path(args.benchmark).exists():
        print(f"Running single-image benchmark from {args.benchmark}")
        run_single(args.benchmark, args.out, args.skip_model)
    else:
        print(f"Benchmark file {args.benchmark} not found")

    if Path(args.pairs).exists():
        print(f"Running pairwise benchmark from {args.pairs}")
        run_pairs(args.pairs, args.out, args.skip_model)
    else:
        print(f"Pair benchmark file {args.pairs} not found")


if __name__ == "__main__":  # pragma: no cover
    main()
