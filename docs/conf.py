"""Sphinx configuration — fleet standard via py-canon."""

from py_canon.sphinx import configure

configure(
    globals(),
    doctest_test_doctest_blocks="",
    intersphinx_mapping={
        "python": ("https://docs.python.org/3/", None),
    },
)
