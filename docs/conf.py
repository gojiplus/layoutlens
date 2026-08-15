"""Sphinx configuration — fleet standard via py-canon."""

from py_canon.sphinx import configure

configure(
    globals(),
    # Docstring `>>>` examples are illustrative (placeholder API keys, async
    # calls shown without a running loop), not executable doctests. Only
    # explicit `.. doctest::` directives are tested.
    doctest_test_doctest_blocks="",
    intersphinx_mapping={
        "python": ("https://docs.python.org/3/", None),
    },
)
