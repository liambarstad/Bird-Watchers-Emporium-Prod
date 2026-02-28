from __future__ import annotations

from typing import Iterable

import requests


class EmbeddingClient:
    def __init__(self, base_url: str, timeout_s: float = 30.0) -> None:
        self._base_url = base_url.rstrip('/')
        self._timeout_s = timeout_s

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        payload = {'texts': list(texts)}
        response = requests.post(
            f'{self._base_url}/embed/text',
            json=payload,
            timeout=self._timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get('embeddings', [])
        return embeddings

