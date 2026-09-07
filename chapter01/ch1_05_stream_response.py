"""Lesson 1.5 / Task 5 - Stream a Response Reliably.

Displays deltas as they arrive while accumulating a buffer, then compares that
buffer with the final message. An interrupted stream is labelled partial and is
never committed as a completed answer.

Run live:          python ch1_05_stream_response.py
Offline success:   python ch1_05_stream_response.py --fake
Offline failure:   python ch1_05_stream_response.py --fake --interrupt
Buffered output:   python ch1_05_stream_response.py --fake --buffered
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Iterator

from ch1_00_config import DEFAULT_MODEL, build_client

PROMPT = "Explain a context window in two sentences."
MAX_TOKENS = 200

FAKE_DELTAS = ["A context window is ", "the amount of text a model ", "can consider at once, ",
               "measured in tokens. ", "Everything you send and everything ",
               "the model generates must fit inside it."]


class StreamInterrupted(RuntimeError):
    """Raised when the transport fails after some text was already displayed."""


@dataclass
class StreamResult:
    text: str
    complete: bool
    matched_final: bool | None  # None when the stream never completed


def fake_stream(interrupt_after: int | None = None) -> Iterator[str]:
    for i, delta in enumerate(FAKE_DELTAS):
        if interrupt_after is not None and i == interrupt_after:
            raise StreamInterrupted("connection reset by peer")
        yield delta


def consume(deltas: Iterator[str], display: bool = True,
            buffer: list[str] | None = None) -> str:
    """Accumulate every delta. Display is a separate concern from accumulation.

    Pass `buffer` to keep whatever arrived before an exception; the caller owns
    it, so a failure mid-stream still leaves the partial text inspectable.
    """
    buffer = buffer if buffer is not None else []
    for delta in deltas:
        buffer.append(delta)
        if display:
            sys.stdout.write(delta)
            sys.stdout.flush()   # without a flush the whole answer appears at once
    if display:
        sys.stdout.write("\n")
    return "".join(buffer)


def stream_live(display: bool) -> StreamResult:
    client = build_client()
    with client.messages.stream(
        model=DEFAULT_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": PROMPT}],
    ) as stream:
        accumulated = consume(iter(stream.text_stream), display=display)
        final = stream.get_final_message()
    final_text = "".join(b.text for b in final.content if b.type == "text")
    return StreamResult(accumulated, True, accumulated == final_text)


def main(argv: list[str]) -> int:
    fake = "--fake" in argv
    interrupt = "--interrupt" in argv
    buffered = "--buffered" in argv          # accessible batch mode
    display = not buffered

    print(f"model={DEFAULT_MODEL}  mode={'fake' if fake else 'live'}"
          f"{'  (interrupt injected)' if interrupt else ''}"
          f"{'  (buffered display)' if buffered else ''}\n")

    partial: list[str] = []
    try:
        if fake:
            deltas = fake_stream(interrupt_after=3 if interrupt else None)
            text = consume(deltas, display=display, buffer=partial)
            final_text = "".join(FAKE_DELTAS)
            result = StreamResult(text, True, text == final_text)
        else:
            result = stream_live(display=display)
    except StreamInterrupted as exc:
        # Show what arrived, mark it, and stop. Do not silently retry into the buffer.
        arrived = "".join(partial)
        if not display:
            print(arrived)
        print(f"\n[PARTIAL] stream interrupted after {len(arrived)} chars: {exc}")
        print("[PARTIAL] not committed to history; no automatic replay")
        return 1

    if buffered:
        print(result.text)

    print(f"\n[COMPLETE] accumulated {len(result.text)} chars; "
          f"matches final message: {result.matched_final}")
    return 0 if result.matched_final else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
