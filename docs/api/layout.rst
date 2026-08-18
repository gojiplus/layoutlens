Layout Scorers API
==================

Deterministic geometry/contrast defect detection measured directly off the
rendered page — no LLM, no API key. Detects contrast failures, sibling
overlap, clipped content, viewport protrusion (both edges), page-level
horizontal overflow, ellipsis text truncation, WCAG-aware target spacing,
complete focus obscuration, and rendered text occlusion.
Target-size findings apply machine-measurable WCAG 2.5.8 exceptions. The scanner also
exercises focusable controls for complete focus obscuration (WCAG 2.4.11) and detects
painted DOM elements crossing rendered text, including graph labels. Semantic exceptions
remain explicit manual-review fields; the report is not a site-wide conformance claim.

LayoutScorer
------------

.. autoclass:: layoutlens.LayoutScorer
   :members:
   :undoc-members:
   :show-inheritance:

Report Types
------------

.. autoclass:: layoutlens.LayoutReport
   :members: ok, by_class, summary, to_json
   :no-undoc-members:
   :show-inheritance:

.. autoclass:: layoutlens.LayoutFinding
   :no-undoc-members:
   :no-members:
   :show-inheritance:

Contrast Math
-------------

.. autofunction:: layoutlens.contrast_ratio

.. autofunction:: layoutlens.check_contrast
