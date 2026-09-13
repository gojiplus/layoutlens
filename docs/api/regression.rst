Render states and regression
============================

.. autofunction:: layoutlens.capture_state

.. autofunction:: layoutlens.capture_page

.. autofunction:: layoutlens.diff

.. autoclass:: layoutlens.RenderState
   :members: save, load, diff, fingerprint

.. autoclass:: layoutlens.DiffReport
   :members: gate_status, to_json, summary

.. autoclass:: layoutlens.VisualDelta

.. autoclass:: layoutlens.Qualification
   :members: precision_interval, qualifies

.. autoclass:: layoutlens.Verification
   :members: supports
