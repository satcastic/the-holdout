"""Embedding back ends behind one interface.

- `PineconeIntegratedEmbedder`: Pinecone hosted inference. The index embeds text itself on
  upsert and search, so `embed()` is never called; the store sends raw text.
- `HashingEmbedder`: deterministic offline bag-of-words vectors, for tests and offline dev.

To swap in another provider, implement `Embedder` with `integrated = False` and a real
`embed()`; `MemoryStore` (or a vector-mode Pinecone index) will use the vectors directly.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Literal, Protocol

Kind = Literal["passage", "query"]


class Embedder(Protocol):
    name: str
    integrated: bool

    def embed(self, texts: list[str], kind: Kind) -> list[list[float]]: ...


class PineconeIntegratedEmbedder:
    """Marker for Pinecone integrated embeddings (e.g. llama-text-embed-v2)."""

    integrated = True

    def __init__(self, model: str) -> None:
        self.name = model

    def embed(self, texts: list[str], kind: Kind) -> list[list[float]]:
        raise NotImplementedError("Integrated embeddings are computed inside Pinecone")


_STOP = set(
    ["a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "for", "from", "had", "has", "have", "he", "her", "his", "i", "in", "is", "it", "its", "me", "my", "of", "on", "or", "she", "that", "the", "their", "them", "they", "this", "to", "was", "were", "what", "when", "where", "which", "who", "why", "with", "you", "your", "about", "after", "before", "any", "anything", "know", "tell", "show", "me", "us"]
)


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    out = []
    for w in words:
        if w in _STOP:
            continue
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


class HashingEmbedder:
    """Unigram + bigram feature hashing with sublinear tf, L2-normalised."""

    integrated = False

    def __init__(self, dim: int = 2048) -> None:
        self.dim = dim
        self.name = f"hashing-{dim}"

    def _bucket(self, feat: str) -> tuple[int, float]:
        h = int.from_bytes(hashlib.blake2b(feat.encode(), digest_size=8).digest(), "big")
        return h % self.dim, (1.0 if (h >> 63) & 1 else -1.0)

    def embed(self, texts: list[str], kind: Kind) -> list[list[float]]:
        vecs = []
        for text in texts:
            toks = _tokens(text)
            feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:], strict=False)]
            counts: dict[str, int] = {}
            for f in feats:
                counts[f] = counts.get(f, 0) + 1
            v = [0.0] * self.dim
            for f, c in counts.items():
                i, sign = self._bucket(f)
                v[i] += sign * (1.0 + math.log(c))
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            vecs.append([x / norm for x in v])
        return vecs
