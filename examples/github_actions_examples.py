#!/usr/bin/env python3
"""
GitHub Actions integration examples for LayoutLens.

This file demonstrates how to use LayoutLens in GitHub Actions workflows
for automated UI testing in CI/CD pipelines.
"""

import os

from layoutlens import LayoutLens


def github_actions_ui_test():
    """Example function for GitHub Actions UI testing."""

    # Get environment variables (typically set by GitHub Actions)
    api_key = os.getenv("OPENAI_API_KEY")
    preview_url = os.getenv("PREVIEW_URL", "https://example.com")

    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set")
        return False

    try:
        # Initialize LayoutLens
        lens = LayoutLens(api_key=api_key)

        # Test the preview URL
        result = lens.analyze(
            source=preview_url,
            query="Is this page professional and user-friendly?",
            viewport="desktop",
        )

        print(f"✅ Analysis Result: {result.answer}")
        print(f"📊 Confidence: {result.confidence:.1%}")

        # Return success if confidence is high enough
        return result.confidence >= 0.7

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return False


def accessibility_check():
    """GitHub Actions accessibility validation."""

    preview_url = os.getenv("PREVIEW_URL", "https://example.com")

    try:
        lens = LayoutLens()

        # Run accessibility check
        result = lens.check_accessibility(preview_url)

        print(f"♿ Accessibility: {result.answer}")
        print(f"📊 Confidence: {result.confidence:.1%}")

        return result.confidence >= 0.8

    except Exception as e:
        print(f"❌ Accessibility check failed: {e}")
        return False


def mobile_friendly_check():
    """GitHub Actions mobile-friendly validation."""

    preview_url = os.getenv("PREVIEW_URL", "https://example.com")

    try:
        lens = LayoutLens()

        # Run mobile-friendly check
        result = lens.check_mobile_friendly(preview_url)

        print(f"📱 Mobile-friendly: {result.answer}")
        print(f"📊 Confidence: {result.confidence:.1%}")

        return result.confidence >= 0.7

    except Exception as e:
        print(f"❌ Mobile-friendly check failed: {e}")
        return False


def main():
    """Main function for GitHub Actions execution."""

    print("🚀 LayoutLens GitHub Actions UI Testing")
    print("=" * 50)

    # Check required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable is required")
        print("Please add your OpenAI API key to GitHub repository secrets")
        exit(1)

    # Run all checks
    checks = [
        ("UI Quality", github_actions_ui_test),
        ("Accessibility", accessibility_check),
        ("Mobile-Friendly", mobile_friendly_check),
    ]

    results = []
    for check_name, check_func in checks:
        print(f"\n🔍 Running {check_name} check...")
        success = check_func()
        results.append((check_name, success))

        if success:
            print(f"✅ {check_name}: PASSED")
        else:
            print(f"❌ {check_name}: FAILED")

    # Summary
    passed = sum(1 for _, success in results if success)
    total = len(results)

    print(f"\n📊 Summary: {passed}/{total} checks passed")

    if passed == total:
        print("🎉 All UI checks passed!")
        exit(0)
    else:
        print("❌ Some UI checks failed")
        exit(1)


if __name__ == "__main__":
    main()
