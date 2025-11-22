# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Dynamic version import
try:
    import importlib.metadata

    release = importlib.metadata.version("layoutlens")
    version = ".".join(release.split(".")[:2])  # Major.minor
except importlib.metadata.PackageNotFoundError:
    release = "1.1.0-dev"
    version = "1.1"

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "LayoutLens"
copyright = "2024, LayoutLens Team"
author = "LayoutLens Team"

# Version is set dynamically above from package metadata

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Add the project root to Python path for autodoc
sys.path.insert(0, os.path.abspath(".."))

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "myst_parser",
]

# MyST Markdown support
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "dollarmath",
    "html_admonition",
    "html_image",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]

# Furo theme options
html_theme_options = {
    "source_repository": "https://github.com/gojiplus/layoutlens/",
    "source_branch": "main",
    "source_directory": "docs/",
    "edit_page": True,
    "light_css_variables": {
        "color-brand-primary": "#2980B9",
        "color-brand-content": "#2980B9",
    },
    "dark_css_variables": {
        "color-brand-primary": "#79aeda",
        "color-brand-content": "#79aeda",
    },
}

# -- Options for autodoc ----------------------------------------------------
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# -- Options for intersphinx extension ---------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "playwright": ("https://playwright.dev/python/", None),
}

# -- Autosummary settings ----------------------------------------------------
autosummary_generate = True
autosummary_imported_members = True

# -- HTML output options -----------------------------------------------------
html_title = f"{project} v{version}"
html_short_title = project
html_logo = None
html_favicon = None

# Custom CSS
html_css_files: list[str] = []

# GitHub integration
html_context = {
    "display_github": True,
    "github_user": "gojiplus",
    "github_repo": "layoutlens",
    "github_version": "main",
    "conf_py_path": "/docs/",
}
