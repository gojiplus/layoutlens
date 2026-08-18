"""Deterministic visual scorer for geometry and automatable WCAG checks.

:class:`LayoutScorer` opens a page (or runs on one already open) and measures
geometric defects with the browser's own layout engine — bounding-box
intersection for overlapping siblings, ``scrollHeight``/``clientHeight`` for
clipped content, right-edge vs the layout viewport for protrusion, and rendered
size and spacing for undersized interactive targets, focus obscuration, and
text covered by another painted element. It also folds in the contrast scan
(:func:`layoutlens.layout.contrast.check_contrast`). No LLM, no API key.

Foundational geometry math was ported from the UIJudgeBench render-verifier
(``uijudge/engine/verify.py``) and generalized from one claimed selector to a
whole-page scan. Focus, target-exception, and text-occlusion checks are
independent LayoutLens implementations; UIJudgeBench retains separate gold
oracles when it evaluates them.
"""

from __future__ import annotations

from pathlib import Path

from playwright.async_api import Page

from ..browser import open_page
from ..types import Viewport, ViewportType
from .contrast import check_contrast
from .types import (
    CLIPPING,
    FOCUS_OBSCURED,
    OVERLAP,
    PAGE_OVERFLOW,
    PROTRUSION,
    TARGET_SIZE,
    TEXT_OCCLUSION,
    TRUNCATION,
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

# Protrusion: element extends past the horizontal layout viewport, on either
# edge (bench _JS_PROTRUDE, extended to the left edge; vertical overflow is
# normal scrolling and never reported). Only the OUTERMOST protruder is
# reported (skip if the parent already protrudes), so a wide container does not
# flood the report with all its descendants.
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
    const pr = parent && parent !== document.body && parent !== document.documentElement
      ? parent.getBoundingClientRect() : null;
    const parentProtrudes = pr && (pr.right > vw + tol || pr.left < -tol);
    if (parentProtrudes) continue;
    if (r.right > vw + tol) {
      out.push({ selector: cssPath(el), edge: 'right', coord: r.right,
                 viewportWidth: vw, overflow: r.right - vw,
                 bbox: [r.x, r.y, r.width, r.height] });
    } else if (r.left < -tol) {
      out.push({ selector: cssPath(el), edge: 'left', coord: r.left,
                 viewportWidth: vw, overflow: -r.left,
                 bbox: [r.x, r.y, r.width, r.height] });
    }
  }
  return out;
}"""
)

# Page-level horizontal overflow: the classic mobile bug — the document is
# wider than the viewport, so the whole page scrolls sideways. One finding for
# the page, complementing per-element protrusion above.
_JS_PAGE_OVERFLOW = (
    "(tol) => {"
    + """
  const vw = document.documentElement.clientWidth;
  const sw = Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0);
  if (sw > vw + tol) {
    return [{ scrollWidth: sw, viewportWidth: vw, overflow: sw - vw }];
  }
  return [];
}"""
)

# Text truncation: single-line ellipsis actually cutting text off — the element
# declares text-overflow: ellipsis with clipped overflow AND its content is
# wider than its box. Distinct from detect_clipping, which reports any box
# with hidden overflow; this isolates the "…" case designers care about.
_JS_TRUNCATION = (
    "(tol) => {"
    + _JS_HELPERS
    + """
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el)) continue;
    const cs = getComputedStyle(el);
    if (cs.textOverflow !== 'ellipsis') continue;
    const hiddenX = cs.overflowX === 'hidden' || cs.overflowX === 'clip' || cs.overflow === 'hidden';
    if (!hiddenX) continue;
    if (el.scrollWidth > el.clientWidth + tol) {
      const r = el.getBoundingClientRect();
      out.push({ selector: cssPath(el), scrollWidth: el.scrollWidth,
                 clientWidth: el.clientWidth,
                 text: (el.textContent || '').trim().slice(0, 60),
                 bbox: [r.x, r.y, r.width, r.height] });
    }
  }
  return out;
}"""
)

# Target size: WCAG 2.5.8 size plus its machine-measurable spacing and inline
# exceptions. Equivalent-control and essential-presentation exceptions require
# human judgment and are disclosed in each finding rather than guessed.
_JS_TARGETS = (
    "(minPx) => {"
    + _JS_HELPERS
    + """
  const sel = 'a[href], button, input:not([type=hidden]), select, textarea, ' +
              '[role=button], [role=link], [role=checkbox], [role=radio], [onclick]';
  const targets = [...document.querySelectorAll(sel)].filter(visible);
  const out = [];
  function rectDistanceToPoint(r, x, y) {
    const dx = Math.max(r.left - x, 0, x - r.right);
    const dy = Math.max(r.top - y, 0, y - r.bottom);
    return Math.hypot(dx, dy);
  }
  function isInlineException(el) {
    const cs = getComputedStyle(el);
    if (!cs.display.startsWith('inline')) return false;
    const parent = el.parentElement;
    if (!parent) return false;
    const nonTargetText = [...parent.childNodes].some(node =>
      node.nodeType === Node.TEXT_NODE && (node.textContent || '').trim().length > 0
    );
    return nonTargetText && parseFloat(cs.lineHeight) > 0;
  }
  function userAgentSized(el) {
    if (!/^(BUTTON|INPUT|SELECT|TEXTAREA)$/.test(el.tagName)) return false;
    const sizeProperties = new Set([
      'appearance', 'block-size', 'border', 'border-bottom', 'border-left',
      'border-right', 'border-top', 'box-sizing', 'font', 'font-size', 'height',
      'inline-size', 'max-block-size', 'max-height', 'max-inline-size', 'max-width',
      'min-block-size', 'min-height', 'min-inline-size', 'min-width', 'padding',
      'padding-bottom', 'padding-left', 'padding-right', 'padding-top', 'transform',
      'width', 'zoom'
    ]);
    function modifiesSize(style) {
      return [...style].some(name => sizeProperties.has(name));
    }
    if (modifiesSize(el.style)) return false;
    function rulesModify(rules) {
      return [...rules].some(rule => {
        if (rule.selectorText && el.matches(rule.selectorText) && modifiesSize(rule.style)) return true;
        try { return rule.cssRules ? rulesModify(rule.cssRules) : false; }
        catch (_) { return false; }
      });
    }
    return ![...document.styleSheets].some(sheet => {
      try { return rulesModify(sheet.cssRules); }
      catch (_) { return false; }
    });
  }
  for (const el of targets) {
    const r = el.getBoundingClientRect();
    if (r.width < minPx || r.height < minPx) {
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const radius = minPx / 2;
      const conflicts = [];
      for (const other of targets) {
        if (other === el) continue;
        const o = other.getBoundingClientRect();
        const otherSmall = o.width < minPx || o.height < minPx;
        const ocx = o.left + o.width / 2, ocy = o.top + o.height / 2;
        const distance = Math.hypot(cx - ocx, cy - ocy);
        const intersects = otherSmall
          ? distance < minPx
          : rectDistanceToPoint(o, cx, cy) < radius;
        if (intersects) conflicts.push(cssPath(other));
      }
      const inlineException = isInlineException(el);
      const uaException = userAgentSized(el);
      if (conflicts.length === 0 || inlineException || uaException) continue;
      out.push({ selector: cssPath(el), width: r.width, height: r.height,
                 bbox: [r.x, r.y, r.width, r.height],
                 spacingConflicts: conflicts,
                 inlineException, userAgentException: uaException });
    }
  }
  return out;
}"""
)

# Text occlusion: sample rendered text fragments and report when another DOM
# element is topmost over part of a fragment. This catches graph lines or
# overlays painted across labels without treating ordinary nested markup as an
# occluder. It is a visual-quality rule, not a WCAG success criterion.
_JS_TEXT_OCCLUSION = (
    "(samplesPerAxis) => {"
    + _JS_HELPERS
    + """
  const out = [];
  const seen = new Set();
  const oldX = scrollX, oldY = scrollY;
  function paintedElement(el) {
    for (let node = el; node && node !== document.documentElement; node = node.parentElement) {
      const cs = getComputedStyle(node);
      if (parseFloat(cs.opacity) === 0) continue;
      if (/^(IMG|VIDEO|CANVAS)$/.test(node.tagName)) return node;
      const alpha = color => {
        if (!color || color === 'transparent') return 0;
        if (color.startsWith('rgba(')) {
          return parseFloat(color.slice(5, -1).split(',').at(-1));
        }
        if (color.startsWith('rgb(') && color.includes('/')) {
          return parseFloat(color.slice(color.lastIndexOf('/') + 1, -1));
        }
        return 1;
      };
      if (alpha(cs.backgroundColor) > 0 ||
          (parseFloat(cs.borderTopWidth) > 0 && alpha(cs.borderTopColor) > 0) ||
          (parseFloat(cs.borderRightWidth) > 0 && alpha(cs.borderRightColor) > 0) ||
          (parseFloat(cs.borderBottomWidth) > 0 && alpha(cs.borderBottomColor) > 0) ||
          (parseFloat(cs.borderLeftWidth) > 0 && alpha(cs.borderLeftColor) > 0) ||
          (node instanceof SVGElement && (cs.fill !== 'none' || cs.stroke !== 'none'))) return node;
    }
    return null;
  }
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el) || ![...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && (n.textContent || '').trim())) continue;
    const before = el.getBoundingClientRect();
    if (before.bottom <= 0 || before.top >= innerHeight || before.right <= 0 || before.left >= innerWidth) {
      el.scrollIntoView({block: 'center', inline: 'nearest'});
    }
    for (const node of el.childNodes) {
      if (node.nodeType !== Node.TEXT_NODE || !(node.textContent || '').trim()) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      for (const rect of range.getClientRects()) {
        if (rect.width <= 0 || rect.height <= 0) continue;
        const hits = new Map();
        let sampled = 0;
        for (let yi = 0; yi < samplesPerAxis; yi++) {
          for (let xi = 0; xi < samplesPerAxis; xi++) {
            const x = rect.left + rect.width * (xi + 0.5) / samplesPerAxis;
            const y = rect.top + rect.height * (yi + 0.5) / samplesPerAxis;
            if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) continue;
            sampled++;
            const top = document.elementFromPoint(x, y);
            if (top && top !== el && !el.contains(top) && !top.contains(el)) {
              const occluder = paintedElement(top);
              if (occluder) hits.set(occluder, (hits.get(occluder) || 0) + 1);
            }
          }
        }
        if (!hits.size) continue;
        const [occluder, covered] = [...hits.entries()].sort((a, b) => b[1] - a[1])[0];
        const key = cssPath(el) + '|' + cssPath(occluder);
        if (seen.has(key)) continue;
        seen.add(key);
        const er = el.getBoundingClientRect();
        out.push({selector: cssPath(el), occluder: cssPath(occluder),
                  coveredSamples: covered, sampledPoints: sampled,
                  text: (node.textContent || '').trim().slice(0, 80),
                  bbox: [er.x, er.y, er.width, er.height]});
      }
    }
  }
  scrollTo(oldX, oldY);
  return out;
}"""
)

# WCAG 2.4.11: focus each keyboard-operable component, let the browser scroll
# it into view, then determine whether any sampled point remains topmost. The
# AA failure is complete obscuration; partial obscuration is intentionally not
# reported. Scroll position and prior focus are restored after the scan.
_JS_FOCUS_OBSCURED = (
    "(samplesPerAxis) => {"
    + _JS_HELPERS
    + """
  const selector = 'a[href], button, input:not([type=hidden]), select, textarea, summary, ' +
    '[tabindex]:not([tabindex="-1"]), [contenteditable="true"]';
  const targets = [...document.querySelectorAll(selector)].filter(el => visible(el) && !el.disabled);
  const oldX = scrollX, oldY = scrollY, oldFocus = document.activeElement;
  const out = [];
  function fullyOpaque(el) {
    const cs = getComputedStyle(el);
    if (parseFloat(cs.opacity) < 0.999) return false;
    if (/^(IMG|VIDEO|CANVAS|SVG)$/.test(el.tagName)) return true;
    const color = cs.backgroundColor;
    if (!color.startsWith('rgb')) return false;
    const parts = color.slice(color.indexOf('(') + 1, -1).split(',').map(value => parseFloat(value.trim()));
    return parts.length < 4 || parts[3] >= 0.999;
  }
  function opaqueBlocker(el) {
    for (let node = el; node && node !== document.documentElement; node = node.parentElement) {
      if (fullyOpaque(node)) return node;
    }
    return null;
  }
  for (const el of targets) {
    el.focus({preventScroll: false});
    el.scrollIntoView({block: 'nearest', inline: 'nearest', behavior: 'instant'});
    if (document.activeElement !== el) continue;
    const r = el.getBoundingClientRect();
    let sampled = 0, visiblePoints = 0;
    const blockers = new Map();
    for (let yi = 0; yi < samplesPerAxis; yi++) {
      for (let xi = 0; xi < samplesPerAxis; xi++) {
        const x = Math.max(0, Math.min(innerWidth - 1, r.left + r.width * (xi + 0.5) / samplesPerAxis));
        const y = Math.max(0, Math.min(innerHeight - 1, r.top + r.height * (yi + 0.5) / samplesPerAxis));
        if (x < Math.max(0, r.left) || x > Math.min(innerWidth, r.right) ||
            y < Math.max(0, r.top) || y > Math.min(innerHeight, r.bottom)) continue;
        sampled++;
        const top = document.elementFromPoint(x, y);
        if (top && (top === el || el.contains(top))) visiblePoints++;
        else if (top) {
          const blocker = opaqueBlocker(top);
          if (blocker) blockers.set(blocker, (blockers.get(blocker) || 0) + 1);
          else visiblePoints++;
        } else visiblePoints++;
      }
    }
    if (sampled > 0 && visiblePoints === 0 && blockers.size) {
      const [occluder, covered] = [...blockers.entries()].sort((a, b) => b[1] - a[1])[0];
      const o = occluder.getBoundingClientRect();
      out.push({selector: cssPath(el), occluder: cssPath(occluder), sampledPoints: sampled,
                visiblePoints, coveredSamples: covered,
                bbox: [r.x, r.y, r.width, r.height],
                occluderBbox: [o.x, o.y, o.width, o.height]});
    }
  }
  if (oldFocus && oldFocus instanceof HTMLElement) oldFocus.focus({preventScroll: true});
  else if (document.activeElement && document.activeElement instanceof HTMLElement) document.activeElement.blur();
  scrollTo(oldX, oldY);
  return out;
}"""
)


def _round_bbox(bbox: list[float]) -> list[int]:
    """Round a ``[x, y, w, h]`` bbox to integers (determinism vs sub-pixel noise)."""
    return [round(v) for v in bbox]


class LayoutScorer:
    """Deterministic layout/geometry scorer over a rendered page."""

    def __init__(
        self,
        *,
        min_target_px: int = 24,
        overlap_threshold_px2: int = 200,
        clip_tolerance_px: int = 2,
        protrude_tolerance_px: int = 1,
        contrast_threshold: float = 4.5,
        occlusion_samples_per_axis: int = 5,
    ):
        """Initialise the scorer with detector thresholds.

        Args:
            min_target_px: Minimum interactive-target dimension in CSS px.
            overlap_threshold_px2: Minimum sibling intersection area to report.
            clip_tolerance_px: Slack before calling content clipped.
            protrude_tolerance_px: Slack before calling viewport protrusion.
            contrast_threshold: Normal-text contrast ratio to require.
            occlusion_samples_per_axis: Grid resolution for occlusion hit testing.

        Raises:
            ValueError: If ``occlusion_samples_per_axis`` is less than two.
        """
        self.min_target_px = min_target_px
        self.overlap_threshold_px2 = overlap_threshold_px2
        self.clip_tolerance_px = clip_tolerance_px
        self.protrude_tolerance_px = protrude_tolerance_px
        self.contrast_threshold = contrast_threshold
        if occlusion_samples_per_axis < 2:
            raise ValueError("occlusion_samples_per_axis must be at least 2")
        self.occlusion_samples_per_axis = occlusion_samples_per_axis

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
        """Return findings for elements protruding past either horizontal viewport edge."""
        raw = await page.evaluate(_JS_PROTRUDE, self.protrude_tolerance_px)
        findings: list[LayoutFinding] = []
        for m in raw:
            findings.append(
                LayoutFinding(
                    defect_class=PROTRUSION,
                    selector=m["selector"],
                    bbox=_round_bbox(m["bbox"]),
                    measured={
                        "edge": m["edge"],
                        "edge_px": round(m["coord"]),
                        "viewport_width_px": round(m["viewportWidth"]),
                        "overflow_px": round(m["overflow"]),
                    },
                    threshold={"viewport_width_px": round(m["viewportWidth"])},
                    description=(
                        f"extends {round(m['overflow'])}px past the {m['edge']} edge "
                        f"of the {round(m['viewportWidth'])}px viewport"
                    ),
                )
            )
        return findings

    async def detect_page_overflow(self, page: Page) -> list[LayoutFinding]:
        """Return a finding if the whole document scrolls horizontally."""
        raw = await page.evaluate(_JS_PAGE_OVERFLOW, self.protrude_tolerance_px)
        findings: list[LayoutFinding] = []
        for m in raw:
            findings.append(
                LayoutFinding(
                    defect_class=PAGE_OVERFLOW,
                    selector="html",
                    bbox=[0, 0, round(m["scrollWidth"]), 0],
                    measured={
                        "scroll_width_px": round(m["scrollWidth"]),
                        "viewport_width_px": round(m["viewportWidth"]),
                        "overflow_px": round(m["overflow"]),
                    },
                    threshold={"viewport_width_px": round(m["viewportWidth"])},
                    description=(
                        f"page scrolls horizontally: content is {round(m['scrollWidth'])}px "
                        f"wide in a {round(m['viewportWidth'])}px viewport"
                    ),
                )
            )
        return findings

    async def detect_truncation(self, page: Page) -> list[LayoutFinding]:
        """Return findings for single-line text actually cut off by an ellipsis."""
        raw = await page.evaluate(_JS_TRUNCATION, self.clip_tolerance_px)
        findings: list[LayoutFinding] = []
        for m in raw:
            hidden_px = m["scrollWidth"] - m["clientWidth"]
            findings.append(
                LayoutFinding(
                    defect_class=TRUNCATION,
                    selector=m["selector"],
                    bbox=_round_bbox(m["bbox"]),
                    measured={
                        "scroll_width_px": m["scrollWidth"],
                        "client_width_px": m["clientWidth"],
                        "hidden_px": hidden_px,
                        "text_preview": m["text"],
                    },
                    threshold={"tolerance_px": self.clip_tolerance_px},
                    description=f"text truncated by ellipsis, {hidden_px}px hidden",
                )
            )
        return findings

    async def detect_small_targets(self, page: Page) -> list[LayoutFinding]:
        """Return undersized targets that also fail measurable WCAG spacing exceptions.

        The spacing, inline, and unmodified user-agent-control exceptions are
        evaluated automatically. Equivalent-control and essential-presentation
        exceptions are semantic and remain manual-review fields on every finding.
        """
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
                        "spacing_conflicts": m["spacingConflicts"],
                        "inline_exception": m["inlineException"],
                        "user_agent_exception": m["userAgentException"],
                        "manual_review_exceptions": [
                            "equivalent-control",
                            "essential-presentation",
                        ],
                    },
                    threshold={
                        "min_px": self.min_target_px,
                        "spacing_circle_diameter_px": self.min_target_px,
                    },
                    description=(
                        f"target {round(m['width'])}x{round(m['height'])}px is below "
                        f"{self.min_target_px}x{self.min_target_px}px and conflicts with "
                        f"{len(m['spacingConflicts'])} nearby target(s); equivalent-control "
                        "and essential-presentation exceptions require review"
                    ),
                    wcag_refs=["wcag258"],
                )
            )
        return findings

    async def detect_text_occlusion(self, page: Page) -> list[LayoutFinding]:
        """Return rendered text fragments covered by another painted DOM element."""
        raw = await page.evaluate(_JS_TEXT_OCCLUSION, self.occlusion_samples_per_axis)
        return [
            LayoutFinding(
                defect_class=TEXT_OCCLUSION,
                selector=m["selector"],
                bbox=_round_bbox(m["bbox"]),
                measured={
                    "occluder": m["occluder"],
                    "covered_samples": m["coveredSamples"],
                    "sampled_points": m["sampledPoints"],
                    "text_preview": m["text"],
                },
                threshold={"min_covered_samples": 1},
                description=(
                    f"text is covered at {m['coveredSamples']} of {m['sampledPoints']} "
                    f"sampled points by {m['occluder']}"
                ),
            )
            for m in raw
        ]

    async def detect_focus_obscured(self, page: Page) -> list[LayoutFinding]:
        """Return keyboard-focused components entirely hidden by author DOM content.

        This automates the geometric core of WCAG 2.4.11. Whether an occluder
        was user-opened and can be dismissed without advancing focus can require
        interaction history, so each finding discloses those manual exceptions.
        """
        raw = await page.evaluate(_JS_FOCUS_OBSCURED, self.occlusion_samples_per_axis)
        return [
            LayoutFinding(
                defect_class=FOCUS_OBSCURED,
                selector=m["selector"],
                bbox=_round_bbox(m["bbox"]),
                measured={
                    "occluder": m["occluder"],
                    "occluder_bbox": _round_bbox(m["occluderBbox"]),
                    "sampled_points": m["sampledPoints"],
                    "visible_sample_points": m["visiblePoints"],
                    "manual_review_exceptions": [
                        "user-opened-and-revealable-without-focus-advance",
                        "user-repositionable-configurable-interface",
                    ],
                },
                threshold={"visible_sample_points": 1},
                description=(
                    f"focused component is entirely covered at {m['sampledPoints']} "
                    f"sampled points by {m['occluder']}"
                ),
                wcag_refs=["wcag2411"],
            )
            for m in raw
        ]

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
        findings.extend(await self.detect_page_overflow(page))
        findings.extend(await self.detect_truncation(page))
        findings.extend(await self.detect_small_targets(page))
        findings.extend(await self.detect_text_occlusion(page))
        findings.extend(await self.detect_focus_obscured(page))
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
