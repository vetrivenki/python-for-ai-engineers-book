"""Lesson 1.7 / Task 7 - Handle Failures and Rate Limits.

One retry owner: the SDK's own retries are disabled (max_retries=0) and this
module owns the whole policy. At most three total attempts for eligible
transient failures, inside an overall deadline that includes backoff time.

Run:  python resilient_client.py       (runs the three fake-failure scenarios)
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable

MAX_ATTEMPTS = 3          # total attempts, not retries
DEADLINE_SECONDS = 10.0   # covers request time and waiting time together
BASE_DELAY = 0.2
MAX_DELAY = 2.0


class PermanentError(RuntimeError):
    """Authentication, permission or malformed input. Retrying changes nothing."""


class TransientError(RuntimeError):
    """May clear without changing the request. Carries an optional server delay."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class Outcome:
    ok: bool
    attempts: int
    value: str | None
    error: str | None
    elapsed: float


def backoff(attempt: int, retry_after: float | None, rng: random.Random) -> float:
    """Server delay wins when present; otherwise capped exponential with jitter."""
    if retry_after is not None:
        return retry_after
    return min(MAX_DELAY, BASE_DELAY * (2 ** (attempt - 1))) * (0.5 + rng.random() / 2)


def call_with_retry(send: Callable[[], str], *, sleep=time.sleep,
                    clock=time.monotonic, rng: random.Random | None = None) -> Outcome:
    rng = rng or random.Random(7)
    started = clock()
    attempt = 0
    last = "unknown"

    while attempt < MAX_ATTEMPTS:
        attempt += 1
        try:
            value = send()
        except PermanentError as exc:
            # Fail fast. Retrying a 401 only spends the budget.
            print(f"  attempt {attempt}: permanent ({type(exc).__name__}) - stopping")
            return Outcome(False, attempt, None, str(exc), clock() - started)
        except TransientError as exc:
            last = str(exc)
            print(f"  attempt {attempt}: transient - {last}")
            if attempt >= MAX_ATTEMPTS:
                break
            delay = backoff(attempt, exc.retry_after, rng)
            if clock() - started + delay > DEADLINE_SECONDS:
                print(f"  deadline would be exceeded by a {delay:.2f}s wait - stopping")
                break
            sleep(delay)
        else:
            print(f"  attempt {attempt}: success")
            return Outcome(True, attempt, value, None, clock() - started)

    return Outcome(False, attempt, None, f"exhausted after {attempt} attempts: {last}",
                   clock() - started)


def build_live_sender(messages: list[dict[str, str]]) -> Callable[[], str]:
    """Live sender with SDK retries switched off so this module owns the policy."""
    def send() -> str:
        import anthropic
        from config import DEFAULT_MODEL

        client = anthropic.Anthropic(max_retries=0)
        try:
            response = client.messages.create(
                model=DEFAULT_MODEL, max_tokens=300, messages=messages
            )
        except anthropic.AuthenticationError as exc:
            raise PermanentError("credential rejected") from exc
        except anthropic.PermissionDeniedError as exc:
            raise PermanentError("not authorized for this model") from exc
        except anthropic.BadRequestError as exc:
            raise PermanentError("malformed request") from exc
        except anthropic.RateLimitError as exc:
            after = exc.response.headers.get("retry-after") if exc.response else None
            raise TransientError("rate limited", float(after) if after else None) from exc
        except (anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
            raise TransientError("service unavailable") from exc
        return "".join(b.text for b in response.content if b.type == "text")
    return send


def make_fake(*, fail_times: int, error: Exception) -> Callable[[], str]:
    state = {"n": 0}

    def send() -> str:
        state["n"] += 1
        if state["n"] <= fail_times:
            raise error
        return "ok"
    return send


SCENARIOS = {
    "transient then success": make_fake(fail_times=1, error=TransientError("503 from upstream")),
    "always transient": make_fake(fail_times=99, error=TransientError("503 from upstream")),
    "authentication failure": make_fake(fail_times=99, error=PermanentError("401 invalid key")),
}


if __name__ == "__main__":
    print(f"policy: max {MAX_ATTEMPTS} total attempts, {DEADLINE_SECONDS:.0f}s deadline, "
          f"SDK retries disabled\n")
    for name, sender in SCENARIOS.items():
        print(f"{name}:")
        outcome = call_with_retry(sender)
        print(f"  -> ok={outcome.ok} attempts={outcome.attempts} "
              f"elapsed={outcome.elapsed:.2f}s error={outcome.error}\n")
