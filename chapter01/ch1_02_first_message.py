"""Lesson 1.2 / Task 2 - Send and Inspect Your First Message.

Treats the response as structured data: iterate content blocks by type, then
record model, stop reason and usage separately from the visible text.

Run live:     python ch1_02_first_message.py
Run offline:  python ch1_02_first_message.py --fake
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

from ch1_00_config import DEFAULT_MODEL, build_client

PROMPT = "Explain a context window in two sentences."
MAX_TOKENS = 200


@dataclass
class FakeBlock:
    type: str
    text: str = ""


@dataclass
class FakeUsage:
    input_tokens: int = 18
    output_tokens: int = 44


@dataclass
class FakeResponse:
    """Stands in for a Messages API response so the parser can be tested offline."""
    model: str = DEFAULT_MODEL
    stop_reason: str = "end_turn"
    usage: FakeUsage = field(default_factory=FakeUsage)
    content: list[Any] = field(default_factory=lambda: [
        FakeBlock("thinking"),  # a non-text block the parser must survive
        FakeBlock("text", "A context window is the amount of text a model can consider at "
                          "once, measured in tokens. Everything you send and everything the "
                          "model generates has to fit inside it."),
    ])


def extract_text(response: Any) -> list[str]:
    """Return the text of every text block. Non-text blocks are skipped, not crashed on."""
    return [block.text for block in response.content if getattr(block, "type", None) == "text"]


def describe(response: Any) -> dict[str, Any]:
    """Control information, kept apart from the generated content."""
    usage = getattr(response, "usage", None)
    return {
        "model": getattr(response, "model", "unknown"),
        "stop_reason": getattr(response, "stop_reason", "unknown"),
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "block_types": [getattr(b, "type", "?") for b in response.content],
    }


def send(fake: bool = False) -> Any:
    if fake:
        return FakeResponse()
    client = build_client()
    return client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": PROMPT}],
    )


def main(argv: list[str]) -> int:
    fake = "--fake" in argv
    response = send(fake=fake)

    texts = extract_text(response)
    meta = describe(response)

    print(f"prompt: {PROMPT}")
    print(f"mode:   {'offline fake response' if fake else 'live request'}\n")

    if not texts:
        print("[no text returned] the response carried no text block")
    for i, text in enumerate(texts, 1):
        print(f"--- text block {i} ---\n{text}")

    print("\n--- response metadata ---")
    for key, value in meta.items():
        print(f"{key:>15}: {value}")

    complete = meta["stop_reason"] == "end_turn"
    print(f"\nPASS/FAIL: {'PASS' if texts and complete else 'REVIEW'} "
          f"- parsed {len(texts)} text block(s), stop_reason={meta['stop_reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
