Layout Scorers API
==================

Deterministic geometry/contrast defect detection measured directly off the
rendered page — no LLM, no API key. Detects contrast failures, sibling
overlap, clipped content, viewport protrusion (both edges), page-level
horizontal overflow, ellipsis text truncation, and undersized tap targets.

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
