"""Token estimation + USD pricing.

Pre-call enforcement needs a *cheap, conservative* token estimate before the provider
returns. Post-call, real usage from the provider response is reconciled. Prices are
USD per 1K tokens (input/output blended for the estimate path).
"""

from __future__ import annotations

# USD per 1,000 tokens (blended input+output approximation). Tune per provider.
_PRICE_PER_1K: dict[str, float] = {
    "openai": 0.005,
    "xai": 0.004,
    "anthropic": 0.006,
    "stub": 0.0,
}

# Rough chars-per-token for the conservative pre-call estimate.
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


def estimate_request_tokens(*parts: str) -> int:
    return sum(estimate_tokens(p) for p in parts if p)


def usd_for_tokens(provider: str, tokens: int) -> float:
    rate = _PRICE_PER_1K.get(provider.lower(), 0.005)
    return round((tokens / 1000.0) * rate, 6)
