"""
CrossEncoder reranker — rescores vector-search candidates by query relevance.

Lazily loads the model on first call to avoid startup overhead.
Model is multilingual (supports Chinese + English mixed content).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .config import RERANK_FINAL_K, RERANKER_MODEL

logger = logging.getLogger(__name__)


class Reranker:
    """Lazy-loaded CrossEncoder for reranking retrieval candidates."""

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        self._model_name = model_name
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import CrossEncoder
        logger.info("Loading reranker model: %s", self._model_name)
        self._model = CrossEncoder(self._model_name)
        logger.info("Reranker ready.")

    def rerank(
        self,
        query: str,
        docs: list[dict],
        top_k: int = RERANK_FINAL_K,
    ) -> list[dict]:
        """Score each doc against query, return top_k sorted by relevance.

        Adds 'rerank_score' field to each returned dict.
        Content is truncated to 512 chars for the cross-encoder to stay within limits.
        """
        if not docs:
            return []

        self._ensure_loaded()

        pairs = [(query, d.get("content", "")[:512]) for d in docs]
        scores = self._model.predict(pairs)

        ranked = sorted(
            zip(docs, scores),
            key=lambda x: float(x[1]),
            reverse=True,
        )
        return [
            {**d, "rerank_score": round(float(s), 4)}
            for d, s in ranked[:top_k]
        ]
