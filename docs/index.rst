LayoutLens Documentation
========================

.. image:: https://img.shields.io/pypi/v/layoutlens
   :target: https://pypi.org/project/layoutlens/
   :alt: PyPI Version

.. image:: https://img.shields.io/github/license/matmulai/layoutlens
   :target: https://github.com/gojiplus/layoutlens/blob/main/LICENSE
   :alt: License

.. image:: https://readthedocs.org/projects/layoutlens/badge/?version=latest
   :target: https://layoutlens.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

LayoutLens is a production-ready AI-powered UI testing framework that enables natural language visual testing. It captures screenshots using Playwright and analyzes them with OpenAI's GPT-4 Vision API to validate layouts, accessibility, responsive design, and visual consistency.

**Key Achievement:** 95.2% accuracy on professional ground truth benchmark suite.

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
* **Comprehensive Benchmarks**: 31 test cases across 9 UI categories
* **95.2% Accuracy**: Validated on professional ground truth suite
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
   api/providers

📊 Performance Metrics
----------------------

* ✅ **95.2% accuracy** on ground truth benchmark suite
* ✅ **31 HTML test files** across 9 specialized categories
* ✅ **~23 seconds** average processing time per test
* ✅ **Multi-viewport testing** with responsive design validation
* ✅ **Production ready** with professional documentation

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
