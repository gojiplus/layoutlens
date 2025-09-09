#!/usr/bin/env python3
"""
Documentation build script for LayoutLens.

This script provides utilities for building and testing documentation locally.
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and return success status."""
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, check=True, 
                              capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False

def install_deps():
    """Install documentation dependencies."""
    print("Installing documentation dependencies...")
    return run_command("pip install -e .[docs]")

def build_docs():
    """Build documentation."""
    print("Building documentation...")
    docs_dir = Path(__file__).parent.parent / "docs"
    return run_command("sphinx-build -b html . _build/html", cwd=docs_dir)

def clean_docs():
    """Clean documentation build."""
    print("Cleaning documentation build...")
    docs_dir = Path(__file__).parent.parent / "docs"
    return run_command("rm -rf _build", cwd=docs_dir)

def check_links():
    """Check for broken links in documentation."""
    print("Checking for broken links...")
    docs_dir = Path(__file__).parent.parent / "docs"
    return run_command("sphinx-build -b linkcheck . _build/linkcheck", cwd=docs_dir)

def serve_docs():
    """Serve documentation locally."""
    print("Serving documentation locally...")
    docs_dir = Path(__file__).parent.parent / "docs"
    html_dir = docs_dir / "_build" / "html"
    
    if not html_dir.exists():
        print("Documentation not built. Building first...")
        if not build_docs():
            return False
    
    print(f"Documentation available at: http://localhost:8000")
    return run_command("python -m http.server 8000", cwd=html_dir)

def main():
    """Main script entry point."""
    if len(sys.argv) < 2:
        print("Usage: python build_docs.py [install|build|clean|check|serve]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "install":
        success = install_deps()
    elif command == "build":
        success = build_docs()
    elif command == "clean":
        success = clean_docs()
    elif command == "check":
        success = check_links()
    elif command == "serve":
        success = serve_docs()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: install, build, clean, check, serve")
        sys.exit(1)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()