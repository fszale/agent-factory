from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text)}


@dataclass(slots=True)
class RetrievedSnippet:
    source: str
    excerpt: str


class InMemoryKnowledgeBase:
    def __init__(self, documents: list[RetrievedSnippet]) -> None:
        self._documents = documents

    @classmethod
    def from_paths(cls, base_dir: Path, relative_paths: list[str]) -> "InMemoryKnowledgeBase":
        documents: list[RetrievedSnippet] = []
        for relative_path in relative_paths:
            path = base_dir / relative_path
            content = path.read_text(encoding="utf-8").strip()
            chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", content) if chunk.strip()]
            for chunk in chunks:
                if chunk.startswith("#") and "\n" not in chunk:
                    continue
                documents.append(RetrievedSnippet(source=relative_path, excerpt=chunk))
        return cls(documents)

    def search(self, query: str, top_k: int = 3) -> list[RetrievedSnippet]:
        query_tokens = _tokenize(query)
        scored: list[tuple[int, RetrievedSnippet]] = []

        for document in self._documents:
            score = len(query_tokens & _tokenize(document.excerpt))
            if score > 0:
                scored.append((score, document))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [document for _, document in scored[:top_k]]
