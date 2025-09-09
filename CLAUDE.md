# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LayoutLens is an AI-enabled UI testing system that allows writing visual UI tests using natural language. The system captures screenshots of UI states and uses OpenAI's vision models to validate layouts, positioning, text formatting, and visual consistency.

## Development Commands

### Prerequisites Setup
```bash
pip install playwright openai
playwright install chromium
```

### Running Tests and Benchmarks

Generate screenshots only (no AI model calls):
```bash
python benchmark_runner.py --skip-model
```

Run full benchmark with OpenAI model:
```bash
OPENAI_API_KEY=your_key_here python benchmark_runner.py
```

Run with custom output directory:
```bash
python benchmark_runner.py --out custom_screenshots_dir
```

Run with custom benchmark files:
```bash
python benchmark_runner.py --benchmark custom.csv --pairs custom_pairs.csv
```

## Architecture

### Core Components

- **`framework.py`**: Contains the `LayoutLens` class that wraps OpenAI's vision models for natural language UI queries
- **`screenshot.py`**: Provides `html_to_image()` function using Playwright to render HTML files to screenshots  
- **`benchmark_runner.py`**: Main benchmark execution system that processes CSV test definitions and runs queries
- **`eval.py`**: Legacy evaluation script (uses older OpenAI API patterns)

### Test Data Structure

The system uses CSV files to define tests:

**Single Image Tests (`benchmark.csv`)**:
- `html_path`: Path to HTML file to render
- `dom_id`: DOM element ID to test
- `attribute`: Type of attribute (text, box, etc.)
- `expected_behavior`: Expected behavior (justified, left_aligned, bold, etc.)

**Pairwise Comparison Tests (`benchmark_pairs.csv`)**:
- `html_path_a`, `html_path_b`: Paths to two HTML files to compare
- `query`: Natural language question (typically "Do these two layouts look the same?")
- `expected`: Expected answer (yes/no)

### HTML Test Files

Located in `html/` directory with examples covering:
- Text alignment (justified, left, right)
- Text formatting (bold, italic, underlined, colored)
- Box positioning (left, center, right)
- Layout variations for comparison testing

## Key Implementation Notes

- The `LayoutLens` class expects an OpenAI API key via parameter or `OPENAI_API_KEY` environment variable
- Screenshots are rendered at 800x600 resolution by default
- All HTML files should use absolute paths when passed to `html_to_image()`
- The framework gracefully handles missing dependencies (OpenAI, Playwright) with helpful error messages
- Model calls are wrapped in try-catch blocks to handle API failures gracefully

## Testing Natural Language Queries

When creating new tests, structure queries like:
- "Is the element with id 'main_text' justified?"
- "Do these two layouts look the same?"
- "Is the right box bigger than the left?"
- "Is the menu at the top of the page but below the header?"