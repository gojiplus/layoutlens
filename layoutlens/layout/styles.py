"""Deterministic computed-style / geometry reader for a rendered element.

Thin wrappers over ``getComputedStyle`` and ``getBoundingClientRect`` that read
the *live* rendered value of a CSS property (or an element's geometry) for a
given selector — the primitive the UIJudgeBench referring-question generator
uses (``uijudge/engine/referring.py``) to build computed-style ground truth
(text-align, font-weight, font-size). Exposed here so callers can ask "what is
the rendered ``text-align`` of ``#hero``?" deterministically, no LLM involved.
"""

from __future__ import annotations

from playwright.async_api import Page

_JS_READ_STYLES = """([sel, props]) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const cs = getComputedStyle(el);
  const out = {};
  for (const p of props) out[p] = cs.getPropertyValue(p) || cs[p];
  return out;
}"""

_JS_GEOMETRY = """(sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return [r.x, r.y, r.width, r.height];
}"""


async def read_computed_styles(page: Page, selector: str, props: list[str]) -> dict[str, str] | None:
    """Read computed CSS property values for the first element matching ``selector``.

    Args:
        page: A loaded Playwright page.
        selector: A CSS selector; the first match is read.
        props: CSS property names to read (e.g. ``["text-align", "font-weight"]``).

    Returns:
        A ``{property: computed_value}`` dict, or ``None`` if no element matched.
    """
    return await page.evaluate(_JS_READ_STYLES, [selector, props])


async def element_geometry(page: Page, selector: str) -> list[int] | None:
    """Return the ``[x, y, width, height]`` bounding box of the matched element.

    Args:
        page: A loaded Playwright page.
        selector: A CSS selector; the first match is measured.

    Returns:
        The rounded ``[x, y, width, height]`` in CSS pixels, or ``None`` if no
        element matched.
    """
    raw = await page.evaluate(_JS_GEOMETRY, selector)
    if raw is None:
        return None
    return [round(v) for v in raw]
