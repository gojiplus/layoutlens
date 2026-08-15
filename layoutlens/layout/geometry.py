"""Deterministic layout/geometry scorer: overlap, clipping, protrusion, target size.

:class:`LayoutScorer` opens a page (or runs on one already open) and measures
geometric defects with the browser's own layout engine — bounding-box
intersection for overlapping siblings, ``scrollHeight``/``clientHeight`` for
clipped content, right-edge vs the layout viewport for protrusion, and rendered
size for undersized interactive targets. It also folds in the contrast scan
(:func:`layoutlens.layout.contrast.check_contrast`). No LLM, no API key.

The measurement math is ported from the UIJudgeBench render-verifier
(``uijudge/engine/verify.py``) — the same detectors the benchmark used to build
its layout ground truth — generalised from verifying one claimed selector to
scanning the whole page for every instance.
"""

from __future__ import annotations

from pathlib import Path

from playwright.async_api import Page

from ..browser import open_page
from ..types import Viewport, ViewportType
from .contrast import check_contrast
from .types import (
    CLIPPING,
    OVERLAP,
    PROTRUSION,
    TARGET_SIZE,
    LayoutFinding,
    LayoutReport,
)

# Shared JS helpers injected into every detector snippet.
_JS_HELPERS = """
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
"""

# Overlap: pairwise bbox intersection among visible siblings (bench _JS_INTERSECT,
# scanned per parent so it is O(children^2) per container, not O(n^2) over the page).
_JS_OVERLAP = (
    "(minArea) => {"
    + _JS_HELPERS
    + """
  const out = [];
  for (const parent of document.querySelectorAll('*')) {
    const kids = [...parent.children].filter(visible);
    for (let i = 0; i < kids.length; i++) {
      for (let j = i + 1; j < kids.length; j++) {
        const ra = kids[i].getBoundingClientRect(), rb = kids[j].getBoundingClientRect();
        const ix = Math.max(0, Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left));
        const iy = Math.max(0, Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top));
        const area = ix * iy;
        if (area > minArea) {
          out.push({ a: cssPath(kids[i]), b: cssPath(kids[j]), intersection: area,
                     bbox_a: [ra.x, ra.y, ra.width, ra.height],
                     bbox_b: [rb.x, rb.y, rb.width, rb.height] });
        }
      }
    }
  }
  return out;
}"""
)

# Clipping: content taller/wider than its box AND overflow hidden/clip so it is
# actually cut off (the overflow condition is added over the bench check, which
# knew the mutation set overflow:hidden and so did not need to re-test it).
_JS_CLIP = (
    "(tol) => {"
    + _JS_HELPERS
    + """
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el)) continue;
    const cs = getComputedStyle(el);
    const hiddenY = cs.overflowY === 'hidden' || cs.overflowY === 'clip';
    const hiddenX = cs.overflowX === 'hidden' || cs.overflowX === 'clip';
    const clippedY = hiddenY && el.scrollHeight > el.clientHeight + tol;
    const clippedX = hiddenX && el.scrollWidth > el.clientWidth + tol;
    if (clippedY || clippedX) {
      const r = el.getBoundingClientRect();
      out.push({ selector: cssPath(el), clippedY, clippedX,
                 scrollHeight: el.scrollHeight, clientHeight: el.clientHeight,
                 scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
                 bbox: [r.x, r.y, r.width, r.height] });
    }
  }
  return out;
}"""
)

# Protrusion: element right edge past the layout viewport width (bench _JS_PROTRUDE).
# Only the OUTERMOST protruder is reported (skip if the parent already protrudes),
# so a wide container does not flood the report with all its descendants.
_JS_PROTRUDE = (
    "(tol) => {"
    + _JS_HELPERS
    + """
  const out = [];
  const vw = document.documentElement.clientWidth;
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    const parent = el.parentElement;
    // body/html stretch to fit overflowing content, so they are not counted as
    // protruding ancestors — otherwise they would suppress the real offender.
    const parentProtrudes = parent && parent !== document.body &&
      parent !== document.documentElement && parent.getBoundingClientRect().right > vw + tol;
    if (r.right > vw + tol && !parentProtrudes) {
      out.push({ selector: cssPath(el), right: r.right, viewportWidth: vw,
                 overflow: r.right - vw, bbox: [r.x, r.y, r.width, r.height] });
    }
  }
  return out;
}"""
)

# Target size: interactive/clickable elements rendered smaller than the minimum
# (bench _JS_BBOX + the <24x24 rule; WCAG 2.5.8 Target Size (Minimum)).
_JS_TARGETS = (
    "(minPx) => {"
    + _JS_HELPERS
    + """
  const sel = 'a[href], button, input:not([type=hidden]), select, textarea, ' +
              '[role=button], [role=link], [role=checkbox], [role=radio], [onclick]';
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < minPx || r.height < minPx) {
      out.push({ selector: cssPath(el), width: r.width, height: r.height,
                 bbox: [r.x, r.y, r.width, r.height] });
    }
  }
  return out;
}"""
)


def _round_bbox(bbox: list[float]) -> list[int]:
    """Round a ``[x, y, w, h]`` bbox to integers (determinism vs sub-pixel noise)."""
    return [round(v) for v in bbox]


class LayoutScorer:
    """Deterministic layout/geometry scorer over a rendered page.

    Args:
        min_target_px: Minimum interactive-target dimension in CSS px (WCAG 2.5.8
            minimum is 24).
        overlap_threshold_px2: Minimum sibling intersection area (px²) to report
            as an overlap; filters sub-pixel touching.
        clip_tolerance_px: Slack added to ``clientHeight``/``clientWidth`` before
            calling content clipped.
        protrude_tolerance_px: Slack added to the viewport width before calling an
            element protruding.
        contrast_threshold: AA normal-text contrast ratio to require in the folded
            contrast scan.
    """

    def __init__(
        self,
        *,
        min_target_px: int = 24,
        overlap_threshold_px2: int = 200,
        clip_tolerance_px: int = 2,
        protrude_tolerance_px: int = 1,
        contrast_threshold: float = 4.5,
    ):
        """Initialise the scorer with detector thresholds."""
        self.min_target_px = min_target_px
        self.overlap_threshold_px2 = overlap_threshold_px2
        self.clip_tolerance_px = clip_tolerance_px
        self.protrude_tolerance_px = protrude_tolerance_px
        self.contrast_threshold = contrast_threshold

    async def detect_overlaps(self, page: Page) -> list[LayoutFinding]:
        """Return findings for visible siblings whose bounding boxes overlap."""
        raw = await page.evaluate(_JS_OVERLAP, self.overlap_threshold_px2)
        findings: list[LayoutFinding] = []
        for m in raw:
            findings.append(
                LayoutFinding(
                    defect_class=OVERLAP,
                    selector=m["a"],
                    bbox=_round_bbox(m["bbox_a"]),
                    measured={
                        "partner": m["b"],
                        "intersection_px2": round(m["intersection"]),
                        "bbox_partner": _round_bbox(m["bbox_b"]),
                    },
                    threshold={"min_intersection_px2": self.overlap_threshold_px2},
                    description=f"overlaps {m['b']} by {round(m['intersection'])}px²",
                )
            )
        return findings

    async def detect_clipping(self, page: Page) -> list[LayoutFinding]:
        """Return findings for elements whose content is clipped by hidden overflow."""
        raw = await page.evaluate(_JS_CLIP, self.clip_tolerance_px)
        findings: list[LayoutFinding] = []
        for m in raw:
            axis = "vertically" if m["clippedY"] else "horizontally"
            clipped_px = (
                m["scrollHeight"] - m["clientHeight"]
                if m["clippedY"]
                else m["scrollWidth"] - m["clientWidth"]
            )
            findings.append(
                LayoutFinding(
                    defect_class=CLIPPING,
                    selector=m["selector"],
                    bbox=_round_bbox(m["bbox"]),
                    measured={
                        "clipped_axis": "y" if m["clippedY"] else "x",
                        "clipped_px": clipped_px,
                        "scroll_height_px": m["scrollHeight"],
                        "client_height_px": m["clientHeight"],
                        "scroll_width_px": m["scrollWidth"],
                        "client_width_px": m["clientWidth"],
                    },
                    threshold={"tolerance_px": self.clip_tolerance_px},
                    description=f"content clipped {axis} by {clipped_px}px",
                )
            )
        return findings

    async def detect_protrusion(self, page: Page) -> list[LayoutFinding]:
        """Return findings for elements protruding past the layout viewport width."""
        raw = await page.evaluate(_JS_PROTRUDE, self.protrude_tolerance_px)
        findings: list[LayoutFinding] = []
        for m in raw:
            findings.append(
                LayoutFinding(
                    defect_class=PROTRUSION,
                    selector=m["selector"],
                    bbox=_round_bbox(m["bbox"]),
                    measured={
                        "right_px": round(m["right"]),
                        "viewport_width_px": round(m["viewportWidth"]),
                        "overflow_px": round(m["overflow"]),
                    },
                    threshold={"viewport_width_px": round(m["viewportWidth"])},
                    description=f"extends {round(m['overflow'])}px past the {round(m['viewportWidth'])}px viewport",
                )
            )
        return findings

    async def detect_small_targets(self, page: Page) -> list[LayoutFinding]:
        """Return findings for interactive targets smaller than ``min_target_px``."""
        raw = await page.evaluate(_JS_TARGETS, self.min_target_px)
        findings: list[LayoutFinding] = []
        for m in raw:
            findings.append(
                LayoutFinding(
                    defect_class=TARGET_SIZE,
                    selector=m["selector"],
                    bbox=_round_bbox(m["bbox"]),
                    measured={
                        "width_px": round(m["width"], 1),
                        "height_px": round(m["height"], 1),
                    },
                    threshold={"min_px": self.min_target_px},
                    description=(
                        f"target {round(m['width'])}x{round(m['height'])}px is below "
                        f"{self.min_target_px}x{self.min_target_px}px"
                    ),
                    wcag_refs=["wcag258"],
                )
            )
        return findings

    async def scan_page(
        self, page: Page, source: str | None = None, viewport: str = "desktop"
    ) -> LayoutReport:
        """Run every detector on an already-loaded page and return a report.

        Args:
            page: A loaded Playwright page.
            source: Optional source label recorded in the report; defaults to the
                page URL.
            viewport: Viewport name recorded in the report.

        Returns:
            The structured layout report.
        """
        findings: list[LayoutFinding] = []
        findings.extend(await check_contrast(page, threshold=self.contrast_threshold))
        findings.extend(await self.detect_overlaps(page))
        findings.extend(await self.detect_clipping(page))
        findings.extend(await self.detect_protrusion(page))
        findings.extend(await self.detect_small_targets(page))
        return LayoutReport(
            source=source if source is not None else page.url,
            viewport=viewport,
            findings=findings,
        )

    async def scan(
        self, source: str | Path, viewport: ViewportType = "desktop"
    ) -> LayoutReport:
        """Scan a URL or local HTML file, owning the browser lifecycle.

        Args:
            source: A URL or path to a local HTML file.
            viewport: Viewport name or :class:`~layoutlens.types.Viewport` member.

        Returns:
            The structured layout report.
        """
        viewport_name = (
            viewport.value if isinstance(viewport, Viewport) else str(viewport)
        )
        async with open_page(source, viewport) as page:
            return await self.scan_page(
                page, source=str(source), viewport=viewport_name
            )
