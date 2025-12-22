#!/usr/bin/env python3
"""
LayoutLens Benchmark Runner

Runs LayoutLens API against benchmark test data and generates results for evaluation.
This script demonstrates the async API and proper JSON output handling.

Usage:
    python benchmarks/run_benchmark.py --api-key YOUR_KEY
    python benchmarks/run_benchmark.py --help
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from layoutlens import LayoutLens

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class BenchmarkRunner:
    """Runs LayoutLens against benchmark test data."""

    def __init__(self, api_key: str, output_dir: str = "layoutlens_output"):
        """Initialize benchmark runner."""
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Initialize LayoutLens with performance settings
        self.lens = LayoutLens(
            api_key=api_key,
            model="gpt-4o-mini",  # Cost-effective for benchmarks
            output_dir=str(self.output_dir / "screenshots"),
            cache_enabled=True,
            cache_type="file",
        )

        print(f"⚙️  Benchmark Settings:")
        print(f"   Model: gpt-4o-mini")
        print(f"   Cache: Enabled (file-based)")
        print(f"   Output: {self.output_dir}")

        # Base paths
        self.base_path = Path(__file__).parent
        self.test_data_path = self.base_path / "test_data"
        self.answer_keys_path = self.base_path / "answer_keys"

    def load_answer_keys(self) -> dict[str, Any]:
        """Load answer keys with queries for each test file."""
        answer_keys = {}

        for answer_file in self.answer_keys_path.glob("*.json"):
            with open(answer_file) as f:
                data = json.load(f)
                answer_keys.update(data.get("test_cases", {}))

        return answer_keys

    async def run_single_test(self, html_file: Path, query: str) -> dict[str, Any]:
        """Run a single test and return structured result."""
        try:
            result = await self.lens.analyze(source=str(html_file), query=query, viewport="desktop")

            return {
                "html_file": html_file.name,
                "query": query,
                "answer": result.answer,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "success": True,
                "error": None,
                "metadata": result.metadata,
            }

        except Exception as e:
            return {
                "html_file": html_file.name,
                "query": query,
                "answer": f"Error: {str(e)}",
                "confidence": 0.0,
                "reasoning": f"Test failed due to: {type(e).__name__}",
                "success": False,
                "error": str(e),
                "metadata": {"error_type": type(e).__name__},
            }

    async def run_batch_test(self, html_files: list[Path], queries: list[str]) -> list[dict[str, Any]]:
        """Run batch analysis for multiple files and queries."""
        try:
            # Convert paths to strings for LayoutLens
            sources = [str(f) for f in html_files]

            # Use LayoutLens batch processing
            batch_result = await self.lens.analyze(
                source=sources,
                query=queries,
                viewport="desktop",
                max_concurrent=3,  # Limit concurrent requests
            )

            # Convert batch result to structured format
            results = []
            for result in batch_result.results:
                results.append(
                    {
                        "html_file": Path(result.source).name,
                        "query": result.query,
                        "answer": result.answer,
                        "confidence": result.confidence,
                        "reasoning": result.reasoning,
                        "success": True,
                        "error": None,
                        "metadata": result.metadata,
                    }
                )

            return results

        except Exception as e:
            # Return error results for all combinations
            error_results = []
            for html_file in html_files:
                for query in queries:
                    error_results.append(
                        {
                            "html_file": html_file.name,
                            "query": query,
                            "answer": f"Batch error: {str(e)}",
                            "confidence": 0.0,
                            "reasoning": f"Batch test failed: {type(e).__name__}",
                            "success": False,
                            "error": str(e),
                            "metadata": {"error_type": type(e).__name__},
                        }
                    )

            return error_results

    async def run_benchmark(self, use_batch: bool = True) -> dict[str, Any]:
        """Run complete benchmark suite."""
        print("🚀 Starting LayoutLens Benchmark")
        print(f"   Output directory: {self.output_dir}")
        print(f"   Batch processing: {use_batch}")
        print()

        # Load answer keys
        answer_keys = self.load_answer_keys()
        print(f"📋 Loaded {len(answer_keys)} test cases from answer keys")

        # Collect all test cases
        test_cases = []
        for html_filename, test_data in answer_keys.items():
            html_path = None

            # Find the HTML file in test_data directory
            for category_dir in self.test_data_path.iterdir():
                if category_dir.is_dir():
                    candidate_path = category_dir / html_filename
                    if candidate_path.exists():
                        html_path = candidate_path
                        break

            if html_path is None:
                print(f"⚠️  HTML file not found: {html_filename}")
                continue

            # Extract queries from answer key
            queries = list(test_data.get("queries", {}).keys())
            if not queries:
                print(f"⚠️  No queries found for: {html_filename}")
                continue

            test_cases.append((html_path, queries))

        print(f"✅ Found {len(test_cases)} valid test cases")
        print()

        # Run tests
        all_results = []

        if use_batch:
            # Group by similar files for batch processing
            print("🔄 Running batch analysis...")

            # Process all files and queries together for efficiency
            all_files = [tc[0] for tc in test_cases]
            all_queries = []
            for _, queries in test_cases:
                all_queries.extend(queries)

            # Remove duplicates while preserving order
            unique_queries = list(dict.fromkeys(all_queries))

            batch_results = await self.run_batch_test(all_files, unique_queries)
            all_results.extend(batch_results)

        else:
            # Run individual tests
            print("🔄 Running individual tests...")

            for i, (html_file, queries) in enumerate(test_cases, 1):
                print(f"   {i}/{len(test_cases)}: {html_file.name}")

                for query in queries:
                    result = await self.run_single_test(html_file, query)
                    all_results.append(result)

        # Generate summary
        successful_tests = [r for r in all_results if r["success"]]
        failed_tests = [r for r in all_results if not r["success"]]

        summary = {
            "benchmark_info": {
                "total_tests": len(all_results),
                "successful_tests": len(successful_tests),
                "failed_tests": len(failed_tests),
                "success_rate": len(successful_tests) / len(all_results) if all_results else 0,
                "batch_processing_used": use_batch,
                "model_used": "gpt-4o-mini",
            },
            "results": all_results,
        }

        print(f"✅ Benchmark completed!")
        print(f"   Total tests: {len(all_results)}")
        print(f"   Successful: {len(successful_tests)}")
        print(f"   Failed: {len(failed_tests)}")
        print(f"   Success rate: {summary['benchmark_info']['success_rate']:.1%}")

        return summary

    def save_results(self, results: dict[str, Any], filename: str = "benchmark_results.json") -> Path:
        """Save benchmark results to JSON file."""
        output_file = self.output_dir / filename

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"💾 Results saved to: {output_file}")
        return output_file


async def main():
    """Main benchmark runner entry point."""
    parser = argparse.ArgumentParser(
        description="Run LayoutLens benchmark against test data",
        epilog="""
Examples:
  python benchmarks/run_benchmark.py --api-key sk-your-key
  python benchmarks/run_benchmark.py --api-key sk-your-key --no-batch --output custom_results
        """,
    )

    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument(
        "--output",
        default="benchmarks/layoutlens_output",
        help="Output directory for results (default: benchmarks/layoutlens_output)",
    )
    parser.add_argument("--no-batch", action="store_true", help="Disable batch processing (run tests individually)")
    parser.add_argument(
        "--filename", default="benchmark_results.json", help="Output filename (default: benchmark_results.json)"
    )

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: API key required")
        print("   Use --api-key YOUR_KEY or set OPENAI_API_KEY environment variable")
        return 1

    try:
        # Run benchmark
        runner = BenchmarkRunner(api_key, args.output)
        results = await runner.run_benchmark(use_batch=not args.no_batch)

        # Save results
        output_file = runner.save_results(results, args.filename)

        print()
        print("🎯 Next steps:")
        print(f"   1. Review results: {output_file}")
        print(f"   2. Run evaluation: python benchmarks/evaluation/evaluator.py \\")
        print(f"        --answer-keys benchmarks/answer_keys \\")
        print(f"        --results {args.output} \\")
        print(f"        --output benchmark_evaluation.json")

        return 0

    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
