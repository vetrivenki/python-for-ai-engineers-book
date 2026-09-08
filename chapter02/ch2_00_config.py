"""Shared configuration for Chapter 2.

Same contract as Chapter 1: one place owns the model ID and the credential
lookup, so the whole chapter can be re-pointed with one environment variable.
Chapter 2 adds a fixed incident note used as the common input across lessons,
because a controlled comparison needs one input that never changes.
"""

from __future__ import annotations

import os

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
API_KEY_VAR = "ANTHROPIC_API_KEY"

# The shared, fabricated input for every comparison in this chapter.
INCIDENT = (
    "Service checkout-api returned HTTP 503 for 4% of requests between 09:12 and "
    "09:41 UTC. Pod restarts: 3. No deployment was recorded in the window. "
    "Downstream payments-api reported elevated latency at 09:15."
)


def api_key_present() -> bool:
    """True when a non-empty credential is visible to this process."""
    return bool(os.environ.get(API_KEY_VAR, "").strip())


def build_client():
    """Return an Anthropic client. Imported lazily so offline lessons still run."""
    from anthropic import Anthropic

    return Anthropic()


def approx_tokens(text: str) -> int:
    """A rough offline stand-in for a token count.

    This is deliberately crude. Real counts come from the provider
    (client.messages.count_tokens, or the usage on a completed response); this
    only exists so the offline lessons can show relative sizes without a
    network call. Never report this number as a real token count.
    """
    return max(1, round(len(text) / 4))
