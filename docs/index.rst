LayoutLens Documentation
========================

.. image:: https://img.shields.io/pypi/v/layoutlens.svg
   :target: https://pypi.org/project/layoutlens/
   :alt: PyPI Version

.. image:: https://img.shields.io/badge/python-3.11+-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python 3.11+

.. image:: https://img.shields.io/badge/docs-github.io-blue
   :target: https://gojiplus.github.io/layoutlens/
   :alt: Documentation

LayoutLens is a production-ready AI-powered UI testing framework that enables natural language visual testing. It captures screenshots using Playwright and analyzes them with OpenAI's GPT-4 Vision API to validate layouts, accessibility, responsive design, and visual consistency.

**Measured benchmark:** 81.1% accuracy (60/74 labeled queries, ``gpt-4o-mini``, 2026-07-21) on the bundled ground-truth suite (18 fixtures / 74 queries / 4 categories). See ``benchmarks/results/2026-07-21_gpt-4o-mini.json``.

🚀 Quick Start
--------------

.. code-block:: bash

   pip install layoutlens
   playwright install chromium
   export OPENAI_API_KEY="your-key"

.. code-block:: python

   from layoutlens import LayoutLens

   lens = LayoutLens()
   result = lens.analyze("page.html", "Is the layout responsive?")
   print(f"Answer: {result.answer}")
   print(f"Confidence: {result.confidence:.1%}")

✨ Key Features
---------------

* **Natural Language Testing**: Ask questions like "Is the button properly aligned?"
* **Multi-Viewport Support**: Test across mobile, tablet, and desktop
* **Comprehensive Benchmarks**: 18 fixtures / 74 queries / 4 categories
* **81.1% Accuracy**: Measured on the bundled ground-truth suite (gpt-4o-mini, 2026-07-21)
* **CI/CD Ready**: GitHub Actions and Jenkins integration

📖 Documentation
-----------------

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/core
   api/config
   api/analysis
   api/capture

📊 Performance Metrics
----------------------

* ✅ **81.1% measured accuracy** on the ground-truth benchmark suite (gpt-4o-mini, 2026-07-21)
* ✅ **18 HTML fixtures** across 4 categories (74 labeled yes/no queries)
* ✅ **~23 seconds** average processing time per test
* ✅ **Multi-viewport testing** with responsive design validation
* ✅ **Production ready** with professional documentation

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
