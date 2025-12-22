Vision Providers
================

The providers module contains AI vision provider implementations for
different vision models and services.

Base Provider
-------------

.. autoclass:: layoutlens.providers.VisionProvider
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: layoutlens.providers.VisionProviderConfig
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: layoutlens.providers.VisionAnalysisRequest
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: layoutlens.providers.VisionAnalysisResponse
   :members:
   :undoc-members:
   :show-inheritance:

LiteLLM Provider (Unified Interface)
------------------------------------

.. autoclass:: layoutlens.providers.LiteLLMProvider
   :members:
   :undoc-members:
   :show-inheritance:

Provider Factory
----------------

.. autofunction:: layoutlens.providers.create_provider

.. autofunction:: layoutlens.providers.get_available_providers

.. autofunction:: layoutlens.providers.get_provider_info
