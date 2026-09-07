"""Lesson 1.8 / Task 8 - Measure Token Usage and Latency.

One final record per logical request. Timing uses a monotonic clock, units are
named in the field (latency_ms), and missing usage stays null rather than
becoming a misleading zero. Prompt, answer and credential never enter the record.

Run:  python ch1_08_measured_client.py     (two synthetic successes and one failure)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Callable

from ch1_00_config import DEFAULT_MODEL


@dataclass
class Record:
    correlation_id: str
    model: str
    status: str                      # "ok" | "error"
    stop_reason: str | None
    error_category: str | None
    input_tokens: int | None         # null, not 0, when the service returned none
    output_tokens: int | None
    latency_ms: float
    time_to_first_text_ms: float | None
    streaming: bool


def measure(send: Callable[[], Any], *, streaming: bool = False,
            clock=time.perf_counter) -> Record:
    """Wrap one logical request. Returns a record whether it succeeded or not."""
    correlation_id = uuid.uuid4().hex[:12]
    start = clock()
    first_text_at: float | None = None
    try:
        if streaming:
            response, first_text_at = send()          # sender reports its own first-text mark
        else:
            response = send()
    except Exception as exc:
        return Record(
            correlation_id=correlation_id, model=DEFAULT_MODEL, status="error",
            stop_reason=None, error_category=type(exc).__name__,
            input_tokens=None, output_tokens=None,
            latency_ms=round((clock() - start) * 1000, 2),
            time_to_first_text_ms=None, streaming=streaming,
        )

    usage = getattr(response, "usage", None)
    return Record(
        correlation_id=correlation_id,
        model=getattr(response, "model", DEFAULT_MODEL),
        status="ok",
        stop_reason=getattr(response, "stop_reason", None),
        error_category=None,
        # Read the final usage object. Never sum cumulative streaming events.
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        latency_ms=round((clock() - start) * 1000, 2),
        time_to_first_text_ms=round((first_text_at - start) * 1000, 2) if first_text_at else None,
        streaming=streaming,
    )


def emit(record: Record) -> None:
    print(json.dumps(asdict(record)))


# --- offline senders -------------------------------------------------------

class _Usage:
    def __init__(self, i: int, o: int) -> None:
        self.input_tokens, self.output_tokens = i, o


class _Response:
    def __init__(self, i: int, o: int) -> None:
        self.model, self.stop_reason, self.usage = DEFAULT_MODEL, "end_turn", _Usage(i, o)


def fake_success() -> _Response:
    time.sleep(0.05)
    return _Response(21, 64)


def fake_stream() -> tuple[_Response, float]:
    """Returns the final message and the moment the first text fragment appeared."""
    time.sleep(0.02)
    first_text_at = time.perf_counter()   # first non-empty delta reaches the display
    time.sleep(0.04)                      # remaining deltas
    return _Response(21, 58), first_text_at


def fake_failure() -> _Response:
    time.sleep(0.01)
    raise TimeoutError("no response within the per-request timeout")


if __name__ == "__main__":
    records = [
        measure(fake_success),
        measure(fake_stream, streaming=True),
        measure(fake_failure),
    ]
    for r in records:
        emit(r)

    print("\nchecks")
    print(f"  all durations non-negative : {all(r.latency_ms >= 0 for r in records)}")
    print(f"  failure usage is null      : {records[-1].input_tokens is None}")
    print(f"  no prompt/answer/key field : {not (set(asdict(records[0])) & {'prompt', 'answer', 'api_key'})}")
