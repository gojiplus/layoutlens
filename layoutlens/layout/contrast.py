"""WCAG relative-luminance / contrast-ratio math and a page-wide contrast scan.

The arithmetic (:func:`relative_luminance`, :func:`contrast_ratio`,
:func:`parse_css_color`) is pure and browser-free, so it unit-tests against
published WCAG example pairs. :func:`check_contrast` walks a rendered page,
reads each text element's computed foreground and effective opaque background,
and flags any whose ratio falls below the WCAG AA threshold (4.5:1 normal,
3.0:1 large text) — a standalone, inspectable complement to axe's
``color-contrast`` rule.

The math and the effective-background walk are ported verbatim from the
UIJudgeBench render-verifier (``uijudge/engine/wcag.py`` and the ``_JS_CONTRAST``
snippet in ``uijudge/engine/verify.py``), the same detector the benchmark used
to build its contrast ground truth.
"""

from __future__ import annotations

import re

from playwright.async_api import Page

from .types import CONTRAST, LayoutFinding

RGB = tuple[int, int, int]

# WCAG AA contrast thresholds (SC 1.4.3): normal text and large text.
AA_NORMAL_TEXT = 4.5
AA_LARGE_TEXT = 3.0


def _linearize_channel(c8: int) -> float:
    """Linearise one 8-bit sRGB channel to its 0..1 linear-light value."""
    c = c8 / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: RGB) -> float:
    """Return the WCAG relative luminance (0..1) of an sRGB color."""
    r, g, b = (_linearize_channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(rgb1: RGB, rgb2: RGB) -> float:
    """Return the WCAG contrast ratio (1..21) between two sRGB colors (symmetric)."""
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


_HEX3 = re.compile(r"^#([0-9a-fA-F]{3})$")
_HEX6 = re.compile(r"^#([0-9a-fA-F]{6})$")
_RGB = re.compile(r"^rgba?\(\s*([0-9.]+)[,\s]+([0-9.]+)[,\s]+([0-9.]+)")


def parse_css_color(value: str) -> RGB:
    """Parse a CSS color string into an ``(r, g, b)`` tuple.

    Supports ``#rgb``, ``#rrggbb``, ``rgb(...)`` and ``rgba(...)`` (comma- or
    space-separated). Alpha is ignored — the effective opaque background is
    resolved separately by walking the ancestor chain.

    Args:
        value: A CSS color string.

    Returns:
        The ``(r, g, b)`` channels as integers 0..255.

    Raises:
        ValueError: If ``value`` is not a recognised color form.
    """
    s = value.strip()
    m = _HEX6.match(s)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    m = _HEX3.match(s)
    if m:
        h = m.group(1)
        return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))
    m = _RGB.match(s)
    if m:
        return (
            round(float(m.group(1))),
            round(float(m.group(2))),
            round(float(m.group(3))),
        )
    raise ValueError(f"unrecognized CSS color: {value!r}")


def is_large_text(font_size_px: float, font_weight: str) -> bool:
    """WCAG 'large text': >= 24px, or >= 18.66px and bold (>= 700)."""
    try:
        bold = int(font_weight) >= 700
    except (TypeError, ValueError):
        bold = font_weight in ("bold", "bolder")
    return font_size_px >= 24 or (font_size_px >= 18.66 and bold)


# Enumerate every element with direct visible text, returning its computed
# foreground color, effective opaque background (walking ancestors), font
# metrics, and bbox. The effective-background walk is the ``_JS_CONTRAST`` logic
# from the bench verifier, generalized from one selector to the whole page.
_JS_CONTRAST_SCAN = """() => {
  const transparent = c => !c || c === 'transparent' || c === 'rgba(0, 0, 0, 0)';
  function visible(el) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function cssPath(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && node !== document.documentElement) {
      if (node.id) { parts.unshift('#' + CSS.escape(node.id)); break; }
      let sel = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (parent) {
        const sibs = [...parent.children].filter(c => c.tagName === node.tagName);
        if (sibs.length > 1) sel += ':nth-of-type(' + (sibs.indexOf(node) + 1) + ')';
      }
      parts.unshift(sel);
      node = node.parentElement;
    }
    return parts.join(' > ');
  }
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    let hasText = false;
    for (const n of el.childNodes) {
      if (n.nodeType === 3 && n.textContent.trim()) { hasText = true; break; }
    }
    if (!hasText || !visible(el)) continue;
    const cs = getComputedStyle(el);
    let node = el;
    while (node && transparent(getComputedStyle(node).backgroundColor)) node = node.parentElement;
    const bg = node ? getComputedStyle(node).backgroundColor : 'rgb(255, 255, 255)';
    const r = el.getBoundingClientRect();
    out.push({ selector: cssPath(el), fg: cs.color, bg,
               fontSize: parseFloat(cs.fontSize), fontWeight: cs.fontWeight,
               bbox: [r.x, r.y, r.width, r.height] });
  }
  return out;
}"""


async def check_contrast(
    page: Page, *, threshold: float = AA_NORMAL_TEXT
) -> list[LayoutFinding]:
    """Scan ``page`` for text below the WCAG AA contrast threshold.

    Reads every visible text element's computed foreground and effective opaque
    background, computes the WCAG contrast ratio, and returns a finding for each
    element under threshold (3.0 for large text, ``threshold`` otherwise).

    Args:
        page: A loaded Playwright page.
        threshold: The AA normal-text ratio to require (default 4.5).

    Returns:
        One :class:`LayoutFinding` per low-contrast text element.
    """
    elements = await page.evaluate(_JS_CONTRAST_SCAN)
    findings: list[LayoutFinding] = []
    for el in elements:
        try:
            ratio = contrast_ratio(parse_css_color(el["fg"]), parse_css_color(el["bg"]))
        except ValueError:
            continue  # unparseable computed color (e.g. background image) — skip
        limit = (
            AA_LARGE_TEXT
            if is_large_text(el["fontSize"], el["fontWeight"])
            else threshold
        )
        if ratio >= limit:
            continue
        findings.append(
            LayoutFinding(
                defect_class=CONTRAST,
                selector=el["selector"],
                bbox=[round(v) for v in el["bbox"]],
                measured={
                    "contrast_ratio": round(ratio, 2),
                    "fg": el["fg"],
                    "bg": el["bg"],
                    "font_size_px": round(el["fontSize"], 1),
                },
                threshold={"min_ratio": limit},
                description=f"text contrast {ratio:.2f}:1 is below {limit}:1",
                wcag_refs=["wcag143"],
            )
        )
    return findings
