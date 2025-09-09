from __future__ import annotations
"""Framework utilities for natural language UI testing.

This module wraps OpenAI's vision-enabled models so that testers can
ask questions about one or more screenshots using natural language.
"""

from dataclasses import dataclass
from typing import Iterable, List, Optional
import os

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - the library might not be installed
    OpenAI = None  # type: ignore


@dataclass
class LayoutLens:
    """Small helper around the OpenAI responses API.

    Parameters
    ----------
    api_key:
        Optional API key. If not provided the ``OPENAI_API_KEY``
        environment variable is used.
    model:
        Name of the OpenAI model to use. Models such as
        ``gpt-4o-mini`` or ``gpt-4o`` support image inputs.
    """

    api_key: Optional[str] = None
    model: str = "gpt-4o-mini"

    def __post_init__(self) -> None:
        key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OpenAI API key is required")
        if OpenAI is None:  # pragma: no cover
            raise ImportError("openai package is required to use LayoutLens")
        self.client = OpenAI(api_key=key)

    # public API ---------------------------------------------------------
    def ask(self, images: Iterable[str], query: str) -> str:
        """Ask a question about one or more images.

        Parameters
        ----------
        images:
            Iterable of paths to image files.
        query:
            Natural language question about the images.
        Returns
        -------
        str
            Raw text response from the model.
        """

        content: List[dict] = [{"type": "input_text", "text": query}]
        for path in images:
            with open(path, "rb") as fh:
                content.append({"type": "input_image", "image": fh.read()})

        response = self.client.responses.create(
            model=self.model,
            input=[{"role": "user", "content": content}],
        )
        # ``output_text`` conveniently returns the concatenated text outputs.
        return getattr(response, "output_text", "").strip()

    def compare_layouts(self, image_a: str, image_b: str) -> str:
        """Convenience wrapper to ask if two layouts are the same."""
        question = "Do these two layouts look the same?"
        return self.ask([image_a, image_b], question)
