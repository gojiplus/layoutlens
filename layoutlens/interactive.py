"""Interactive CLI mode with real-time feedback and progress indicators."""

import asyncio
import sys
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

try:
    import rich
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text
    from rich.tree import Tree

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .api.core import AnalysisResult, BatchResult, LayoutLens
from .exceptions import LayoutLensError


class InteractiveSession:
    """Interactive session manager with real-time feedback."""

    def __init__(self, lens: LayoutLens, use_rich: bool = None):
        """Initialize interactive session.

        Args:
            lens: LayoutLens instance
            use_rich: Whether to use Rich formatting (auto-detect if None)
        """
        self.lens = lens
        self.use_rich = use_rich if use_rich is not None else RICH_AVAILABLE

        if self.use_rich:
            self.console = Console()
        else:
            self.console = None

        self.session_start = datetime.now()
        self.total_analyses = 0
        self.successful_analyses = 0
        self.total_time = 0.0

    def print(self, *args, **kwargs):
        """Print with Rich if available, fallback to print."""
        if self.use_rich and self.console:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def show_welcome(self):
        """Show welcome message and session info."""
        if self.use_rich:
            welcome_panel = Panel.fit(
                f"[bold blue]LayoutLens Interactive Mode[/bold blue]\n"
                f"Provider: {self.lens.provider}\n"
                f"Model: {self.lens.model}\n"
                f"Session started: {self.session_start.strftime('%H:%M:%S')}",
                title="🔍 Welcome",
                border_style="blue",
            )
            self.print(welcome_panel)
        else:
            print("=" * 50)
            print("🔍 LayoutLens Interactive Mode")
            print(f"Provider: {self.lens.provider}")
            print(f"Model: {self.lens.model}")
            print(f"Session started: {self.session_start.strftime('%H:%M:%S')}")
            print("=" * 50)

    def show_session_stats(self):
        """Show current session statistics."""
        if self.use_rich:
            stats_table = Table(title="Session Statistics")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="magenta")

            stats_table.add_row("Total Analyses", str(self.total_analyses))
            stats_table.add_row("Successful", str(self.successful_analyses))
            stats_table.add_row(
                "Success Rate",
                f"{self.successful_analyses / max(1, self.total_analyses):.1%}",
            )
            stats_table.add_row("Total Time", f"{self.total_time:.2f}s")

            if self.total_analyses > 0:
                avg_time = self.total_time / self.total_analyses
                stats_table.add_row("Avg Time/Analysis", f"{avg_time:.2f}s")

            self.print(stats_table)
        else:
            print("\nSession Statistics:")
            print(f"  Total Analyses: {self.total_analyses}")
            print(f"  Successful: {self.successful_analyses}")
            print(f"  Success Rate: {self.successful_analyses / max(1, self.total_analyses):.1%}")
            print(f"  Total Time: {self.total_time:.2f}s")
            if self.total_analyses > 0:
                avg_time = self.total_time / self.total_analyses
                print(f"  Avg Time/Analysis: {avg_time:.2f}s")

    def analyze_with_progress(
        self,
        source: str,
        query: str,
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
    ) -> AnalysisResult:
        """Analyze with real-time progress feedback."""
        start_time = time.time()

        if self.use_rich:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=self.console,
                transient=True,
            ) as progress:
                # Add analysis task
                task = progress.add_task(f"Analyzing {source[:50]}...", total=None)

                try:
                    # Update progress for different stages
                    progress.update(task, description="📸 Capturing screenshot...")

                    # Simulate progress updates (actual analysis happens internally)
                    time.sleep(0.1)  # Brief pause for visual feedback
                    progress.update(task, description="🤖 Analyzing with AI...")

                    result = self.lens.analyze(source, query, viewport, context)

                    progress.update(task, description="✅ Analysis complete")

                    # Update session stats
                    execution_time = time.time() - start_time
                    self.total_analyses += 1
                    self.successful_analyses += 1
                    self.total_time += execution_time

                    # Show result
                    self._show_result(result)

                    return result

                except Exception as e:
                    progress.update(task, description="❌ Analysis failed")
                    execution_time = time.time() - start_time
                    self.total_analyses += 1
                    self.total_time += execution_time

                    self._show_error(e, source, query)
                    raise
        else:
            # Fallback without Rich
            print(f"Analyzing: {source}")
            print("📸 Capturing screenshot...")

            try:
                result = self.lens.analyze(source, query, viewport, context)

                execution_time = time.time() - start_time
                self.total_analyses += 1
                self.successful_analyses += 1
                self.total_time += execution_time

                print("✅ Analysis complete")
                self._show_result(result)

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                self.total_analyses += 1
                self.total_time += execution_time

                print("❌ Analysis failed")
                self._show_error(e, source, query)
                raise

    async def analyze_batch_with_progress(
        self,
        sources: list[str],
        queries: list[str],
        viewport: str = "desktop",
        context: dict[str, Any] | None = None,
        max_concurrent: int = 3,
    ) -> BatchResult:
        """Analyze batch with real-time progress tracking."""
        start_time = time.time()
        total_tasks = len(sources) * len(queries)

        if self.use_rich:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=self.console,
            ) as progress:
                batch_task = progress.add_task("Batch Analysis", total=total_tasks)

                try:
                    # Create task tracking for concurrent execution
                    completed_count = 0

                    # Custom callback to update progress
                    def update_progress():
                        nonlocal completed_count
                        completed_count += 1
                        progress.update(batch_task, completed=completed_count)

                    # Run batch analysis with progress updates
                    result = await self._run_batch_with_callback(
                        sources,
                        queries,
                        viewport,
                        context,
                        max_concurrent,
                        update_progress,
                    )

                    # Update session stats
                    execution_time = time.time() - start_time
                    self.total_analyses += total_tasks
                    self.successful_analyses += result.successful_queries
                    self.total_time += execution_time

                    # Show batch results
                    self._show_batch_result(result)

                    return result

                except Exception as e:
                    execution_time = time.time() - start_time
                    self.total_analyses += total_tasks
                    self.total_time += execution_time

                    self.print(f"[red]❌ Batch analysis failed: {e}[/red]")
                    raise
        else:
            # Fallback without Rich
            print(f"Running batch analysis: {total_tasks} total tasks")

            try:
                result = await self.lens.analyze_batch_async(
                    [str(s) for s in sources], queries, viewport, context, max_concurrent
                )

                execution_time = time.time() - start_time
                self.total_analyses += total_tasks
                self.successful_analyses += result.successful_queries
                self.total_time += execution_time

                self._show_batch_result(result)
                return result

            except Exception as e:
                execution_time = time.time() - start_time
                self.total_analyses += total_tasks
                self.total_time += execution_time

                print(f"❌ Batch analysis failed: {e}")
                raise

    async def _run_batch_with_callback(
        self,
        sources: list[str],
        queries: list[str],
        viewport: str,
        context: dict[str, Any] | None,
        max_concurrent: int,
        progress_callback: Callable[[], None],
    ) -> BatchResult:
        """Run batch analysis with progress callback."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_single(source: str, query: str) -> AnalysisResult:
            async with semaphore:
                try:
                    result = await self.lens.analyze_async(source, query, viewport, context)
                    progress_callback()
                    return result
                except Exception as e:
                    progress_callback()
                    # Create error result
                    return AnalysisResult(
                        source=source,
                        query=query,
                        answer=f"Error: {str(e)}",
                        confidence=0.0,
                        reasoning=f"Analysis failed: {str(e)}",
                        metadata={"error": True},
                    )

        # Create all tasks
        tasks = []
        for source in sources:
            for query in queries:
                tasks.append(analyze_single(source, query))

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)

        # Calculate batch metrics
        successful_results = [r for r in results if r.confidence > 0]

        return BatchResult(
            results=results,
            total_queries=len(results),
            successful_queries=len(successful_results),
            average_confidence=(
                sum(r.confidence for r in successful_results) / len(successful_results) if successful_results else 0.0
            ),
            total_execution_time=sum(r.execution_time for r in results),
        )

    def _show_result(self, result: AnalysisResult):
        """Display analysis result."""
        if self.use_rich:
            # Create result panel
            result_content = f"""[bold]Query:[/bold] {result.query}
[bold]Answer:[/bold] {result.answer}
[bold]Confidence:[/bold] {result.confidence:.1%}

[bold]Reasoning:[/bold]
{result.reasoning}

[dim]Execution Time: {result.execution_time:.2f}s | Provider: {result.metadata.get("provider", "unknown")} | Model: {result.metadata.get("model", "unknown")}[/dim]"""

            panel = Panel(
                result_content,
                title=f"🔍 Analysis Result",
                border_style="green" if result.confidence > 0.7 else "yellow",
            )
            self.print(panel)
        else:
            print("\n" + "=" * 50)
            print(f"Query: {result.query}")
            print(f"Answer: {result.answer}")
            print(f"Confidence: {result.confidence:.1%}")
            print(f"Reasoning: {result.reasoning}")
            print(f"Time: {result.execution_time:.2f}s")
            print("=" * 50)

    def _show_batch_result(self, result: BatchResult):
        """Display batch analysis result."""
        if self.use_rich:
            # Create summary table
            summary_table = Table(title="Batch Analysis Summary")
            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Value", style="magenta")

            summary_table.add_row("Total Queries", str(result.total_queries))
            summary_table.add_row("Successful", str(result.successful_queries))
            summary_table.add_row("Success Rate", f"{result.successful_queries / result.total_queries:.1%}")
            summary_table.add_row("Average Confidence", f"{result.average_confidence:.1%}")
            summary_table.add_row("Total Time", f"{result.total_execution_time:.2f}s")

            self.print(summary_table)

            # Show individual results in a tree
            if len(result.results) <= 10:  # Only show details for small batches
                tree = Tree("📊 Individual Results")
                for _i, res in enumerate(result.results):
                    status_icon = "✅" if res.confidence > 0.5 else "❌"
                    tree.add(f"{status_icon} {res.source[:30]}... | {res.confidence:.1%}")

                self.print(tree)
        else:
            print("\nBatch Analysis Summary:")
            print(f"  Total Queries: {result.total_queries}")
            print(f"  Successful: {result.successful_queries}")
            print(f"  Success Rate: {result.successful_queries / result.total_queries:.1%}")
            print(f"  Average Confidence: {result.average_confidence:.1%}")
            print(f"  Total Time: {result.total_execution_time:.2f}s")

    def _show_error(self, error: Exception, source: str, query: str):
        """Display error information."""
        if self.use_rich:
            error_panel = Panel(
                f"[bold red]Error Type:[/bold red] {type(error).__name__}\n"
                f"[bold red]Message:[/bold red] {str(error)}\n"
                f"[bold]Source:[/bold] {source}\n"
                f"[bold]Query:[/bold] {query}",
                title="❌ Analysis Error",
                border_style="red",
            )
            self.print(error_panel)
        else:
            print(f"\n❌ Error: {type(error).__name__}")
            print(f"Message: {str(error)}")
            print(f"Source: {source}")
            print(f"Query: {query}")


def run_interactive_session(lens: LayoutLens):
    """Run an interactive LayoutLens session."""
    session = InteractiveSession(lens)
    session.show_welcome()

    if session.use_rich:
        session.print("\n[dim]Available commands: analyze, batch, stats, help, quit[/dim]")
        session.print('[dim]Example: analyze https://example.com "Is this accessible?"[/dim]\n')
    else:
        print("\nAvailable commands: analyze, batch, stats, help, quit")
        print('Example: analyze https://example.com "Is this accessible?"\n')

    while True:
        try:
            if session.use_rich:
                command = session.console.input("[bold cyan]layoutlens>[/bold cyan] ")
            else:
                command = input("layoutlens> ")

            if not command.strip():
                continue

            parts = command.strip().split()
            cmd = parts[0].lower()

            if cmd == "quit" or cmd == "exit":
                session.show_session_stats()
                if session.use_rich:
                    session.print("[bold green]👋 Goodbye![/bold green]")
                else:
                    print("👋 Goodbye!")
                break

            elif cmd == "help":
                _show_help(session)

            elif cmd == "stats":
                session.show_session_stats()

            elif cmd == "analyze":
                if len(parts) < 3:
                    session.print("❌ Usage: analyze <source> <query>")
                    continue

                source = parts[1]
                query = " ".join(parts[2:]).strip("\"'")

                try:
                    session.analyze_with_progress(source, query)
                except LayoutLensError as e:
                    session.print(f"❌ Analysis failed: {e}")
                except Exception as e:
                    session.print(f"❌ Unexpected error: {e}")

            elif cmd == "batch":
                session.print("❌ Batch mode not yet implemented in interactive session")

            else:
                session.print(f"❌ Unknown command: {cmd}. Type 'help' for available commands.")

        except KeyboardInterrupt:
            session.print("\n👋 Goodbye!")
            break
        except EOFError:
            session.print("\n👋 Goodbye!")
            break


def _show_help(session: InteractiveSession):
    """Show help information."""
    if session.use_rich:
        help_table = Table(title="Available Commands")
        help_table.add_column("Command", style="cyan")
        help_table.add_column("Description", style="white")
        help_table.add_column("Example", style="dim")

        help_table.add_row(
            "analyze <source> <query>",
            "Analyze a single source with a query",
            'analyze https://example.com "Is this accessible?"',
        )
        help_table.add_row("stats", "Show session statistics", "stats")
        help_table.add_row("help", "Show this help message", "help")
        help_table.add_row("quit/exit", "Exit interactive session", "quit")

        session.print(help_table)
    else:
        print("Available Commands:")
        print("  analyze <source> <query> - Analyze a single source")
        print('    Example: analyze https://example.com "Is this accessible?"')
        print("  stats                    - Show session statistics")
        print("  help                     - Show this help message")
        print("  quit/exit               - Exit interactive session")
