import hashlib
import logging
import math
from collections.abc import Iterable

import openai
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

logger = logging.getLogger(__name__)


class CompatOpenAIEmbedder(OpenAIEmbedder):
    """OpenAI embedder with deterministic local fallback when /embeddings is unavailable."""

    _warned_fallback = False

    def __init__(self, config: OpenAIEmbedderConfig | None = None):
        super().__init__(config=config)

    @staticmethod
    def _stable_embedding(text: str, dim: int) -> list[float]:
        values: list[float] = []
        counter = 0
        seed = text or "__empty__"

        while len(values) < dim:
            digest = hashlib.sha256(f"{seed}:{counter}".encode("utf-8")).digest()
            counter += 1
            for idx in range(0, len(digest), 4):
                chunk = digest[idx : idx + 4]
                if len(chunk) < 4:
                    continue
                number = int.from_bytes(chunk, "big", signed=False)
                values.append((number / 0xFFFFFFFF) * 2 - 1)
                if len(values) >= dim:
                    break

        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values[:dim]]

    def _fallback(self, input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]]) -> list[float]:
        if not self._warned_fallback:
            logger.warning(
                "Embedding endpoint unavailable; falling back to deterministic local embeddings. "
                "Graph build will continue, but retrieval quality may be reduced."
            )
            self.__class__._warned_fallback = True

        if isinstance(input_data, str):
            text = input_data
        elif isinstance(input_data, list) and input_data and isinstance(input_data[0], str):
            text = input_data[0]
        else:
            text = str(list(input_data))
        return self._stable_embedding(text, self.config.embedding_dim)

    async def create(
        self, input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]]
    ) -> list[float]:
        try:
            return await super().create(input_data)
        except (openai.NotFoundError, openai.BadRequestError):
            return self._fallback(input_data)

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        try:
            return await super().create_batch(input_data_list)
        except (openai.NotFoundError, openai.BadRequestError):
            return [self._stable_embedding(text, self.config.embedding_dim) for text in input_data_list]
