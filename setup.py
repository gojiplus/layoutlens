"""Setup script for LayoutLens framework."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README.md for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding='utf-8') if readme_path.exists() else ""

setup(
    name="layoutlens",
    version="1.0.0",
    description="AI-Enabled UI Test System for natural language visual testing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="LayoutLens Team",
    author_email="team@layoutlens.ai",
    url="https://github.com/layoutlens/layoutlens",
    packages=find_packages(),
    package_data={
        "layoutlens": ["*.yaml"],
        "examples": ["*.yaml", "*.html"],
        "scripts": ["**/*.py"]
    },
    include_package_data=True,
    install_requires=[
        "openai>=1.0.0",
        "playwright>=1.40.0",
        "beautifulsoup4>=4.12.0",
        "pyyaml>=6.0",
        "Pillow>=10.0.0"
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0"
        ],
        "docs": [
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0"
        ]
    },
    entry_points={
        "console_scripts": [
            "layoutlens=layoutlens.cli:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Testing",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Multimedia :: Graphics :: Capture :: Screen Capture"
    ],
    keywords="ui testing, visual regression, ai, computer vision, web testing, layout testing",
    project_urls={
        "Bug Reports": "https://github.com/layoutlens/layoutlens/issues",
        "Documentation": "https://layoutlens.readthedocs.io/",
        "Source": "https://github.com/layoutlens/layoutlens",
    }
)