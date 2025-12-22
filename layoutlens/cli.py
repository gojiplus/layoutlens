#!/usr/bin/env python3
"""LayoutLens CLI - Simple and powerful."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .api.core import LayoutLens
from .exceptions import LayoutLensError


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="layoutlens",
        description="AI-powered UI testing and analysis",
        epilog="""
Examples:
  layoutlens https://example.com "Is it accessible?"
  layoutlens page1.html page2.html --compare
  layoutlens screenshot.png "What issues do you see?"
  layoutlens *.html "Is the design consistent?" --viewport mobile
        """,
    )

    # Main arguments
    parser.add_argument("sources", nargs="*", help="URLs, HTML files, or screenshots to analyze")
    parser.add_argument("--query", "-q", help="Question to ask about the UI")
    parser.add_argument("--compare", "-c", action="store_true", help="Compare sources instead of analyzing separately")

    # Options
    parser.add_argument(
        "--viewport",
        "-v",
        default="desktop",
        choices=["desktop", "mobile", "tablet"],
        help="Viewport size (default: desktop)",
    )
    parser.add_argument(
        "--output", "-o", default="text", choices=["text", "json"], help="Output format (default: text)"
    )
    parser.add_argument("--api-key", help="API key (or set OPENAI_API_KEY env)")
    parser.add_argument("--model", "-m", default="gpt-4o-mini", help="AI model to use")

    args = parser.parse_args()

    # Handle no arguments
    if not args.sources:
        parser.print_help()
        return 0

    # Extract query from sources if mixed
    sources = []
    query = args.query

    for item in args.sources:
        # If it's a URL or file, it's a source
        if item.startswith(("http://", "https://")) or Path(item).exists():
            sources.append(item)
        # Otherwise treat as query (if no explicit query given)
        elif not query:
            query = item
        else:
            sources.append(item)

    if not sources:
        print("Error: No valid sources provided", file=sys.stderr)
        return 1

    # Default query
    if not query:
        query = "Analyze this UI for accessibility, usability, and design quality."

    # Initialize LayoutLens
    try:
        lens = LayoutLens(api_key=args.api_key or os.getenv("OPENAI_API_KEY"), model=args.model)
    except Exception as e:
        print(f"Error initializing LayoutLens: {e}", file=sys.stderr)
        return 1

    # Execute analysis
    try:
        if args.compare and len(sources) >= 2:
            # Compare mode
            result = await lens.compare(
                sources=sources[:2],  # Compare first two
                query=query,
                viewport=args.viewport,
            )
        else:
            # Regular analysis (smart method handles single/multiple)
            source = sources[0] if len(sources) == 1 else sources
            result = await lens.analyze(source=source, query=query, viewport=args.viewport)

        # Output results
        if args.output == "json":
            print(result.to_json())
        else:
            # Human-readable output
            print()
            if hasattr(result, "results"):  # BatchResult
                for r in result.results:
                    print(f"📍 {r.source}")
                    print(f"❓ {r.query}")
                    print(f"✅ {r.answer}")
                    print(f"📊 Confidence: {r.confidence:.0%}\n")
            else:  # Single result or ComparisonResult
                if hasattr(result, "sources"):  # ComparisonResult
                    print(f"📍 Comparing: {' vs '.join(result.sources)}")
                else:
                    print(f"📍 {result.source}")
                print(f"❓ {query}")
                print(f"✅ {result.answer}")
                print(f"📊 Confidence: {result.confidence:.0%}")
                if result.reasoning and len(result.reasoning) < 200:
                    print(f"💭 {result.reasoning}")
            print()

        return 0

    except LayoutLensError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def cli():
    """Entry point for the CLI."""
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    cli()
