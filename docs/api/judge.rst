Judge API
=========

The faithful judge interface for external evaluation harnesses: the prompt is
sent VERBATIM (no persona, no scaffolding), nothing is cached, and every
result carries its model id and prompt hash for auditability.

.. automethod:: layoutlens.LayoutLens.judge
   :no-index:

.. autoclass:: layoutlens.JudgeResult
   :no-undoc-members:
   :no-members:
   :show-inheritance:

Batch Judging
-------------

.. automethod:: layoutlens.LayoutLens.judge_batch
   :no-index:

.. autoclass:: layoutlens.BatchRequest
   :no-undoc-members:
   :no-members:
   :show-inheritance:

.. autofunction:: layoutlens.batch_usage_summary
