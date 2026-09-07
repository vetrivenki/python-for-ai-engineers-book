"""Shared configuration for Chapter 1.

Keeps the model ID and credential lookup in one place so every lesson can be
re-pointed at a different model without editing lesson code.
"""

from __future__ import annotations

import os

# Default model for the examples in this chapter. Override with CLAUDE_MODEL.
# Verify the ID against the model list for your own account before running.
DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")

API_KEY_VAR = "ANTHROPIC_API_KEY"


def api_key_present() -> bool:
    """True when a non-empty credential is visible to this process."""
    return bool(os.environ.get(API_KEY_VAR, "").strip())


def redact(value: str | None, keep: int = 4) -> str:
    """Render a secret as a length-preserving mask. Never print the raw value."""
    if not value:
        return "<absent>"
    return f"<redacted:{len(value)} chars, ends {value[-keep:]}>" if len(value) > keep else "<redacted>"


def build_client():
    """Return an Anthropic client. Import is local so offline lessons still run."""
    from anthropic import Anthropic  # imported lazily on purpose

    return Anthropic()
