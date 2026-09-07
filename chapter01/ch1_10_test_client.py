"""Chapter 1 Project - Test Cases.

Ten deterministic tests covering the acceptance criteria. None of them touch the
network: they inspect the request payload and the client's own state instead of
asking a model to report what it remembers.

Run:  python ch1_10_test_client.py            (no dependencies)
      python -m pytest ch1_10_test_client.py  (if pytest is installed)
"""

from __future__ import annotations

import os
import random
import sys

import ch1_09_claude_cli as claude_cli
from ch1_06_chat_loop import ChatSession, fake_sender
from ch1_00_config import API_KEY_VAR
from ch1_08_measured_client import fake_failure, fake_success, measure
from ch1_07_resilient_client import (MAX_ATTEMPTS, PermanentError, TransientError,
                              call_with_retry, make_fake)
from ch1_05_stream_response import StreamInterrupted, consume, fake_stream


def test_missing_key_makes_no_request() -> None:
    saved = os.environ.pop(API_KEY_VAR, None)
    try:
        assert claude_cli.main([]) == 1, "must exit non-zero without a credential"
    finally:
        if saved is not None:
            os.environ[API_KEY_VAR] = saved


def test_first_message_parses_non_text_block() -> None:
    from ch1_02_first_message import FakeResponse, describe, extract_text

    response = FakeResponse()
    texts = extract_text(response)
    assert len(texts) == 1, "the thinking block must not be read as text"
    assert describe(response)["stop_reason"] == "end_turn"


def test_history_second_payload_contains_first_exchange() -> None:
    session = ChatSession(send=fake_sender)
    session.ask("My test service is called Orion.")
    candidate = session.candidate("What is its name?")
    assert len(candidate) == 3, "payload must carry the prior user+assistant pair"
    assert "Orion" in candidate[0]["content"]
    assert session.ask("What is its name?") == "Its name is Orion."


def test_reset_clears_history_without_a_request() -> None:
    session = ChatSession(send=fake_sender)
    session.ask("My test service is called Orion.")
    session.reset()
    assert session.committed == []
    assert session.ask("What is its name?") == "I do not have a name in this conversation."


def test_transient_recovery_takes_two_attempts() -> None:
    outcome = call_with_retry(make_fake(fail_times=1, error=TransientError("503")),
                              sleep=lambda _: None, rng=random.Random(1))
    assert outcome.ok and outcome.attempts == 2, outcome


def test_exhaustion_stops_at_the_policy_limit() -> None:
    outcome = call_with_retry(make_fake(fail_times=99, error=TransientError("503")),
                              sleep=lambda _: None, rng=random.Random(1))
    assert not outcome.ok and outcome.attempts == MAX_ATTEMPTS == 3, outcome


def test_authentication_failure_takes_one_attempt() -> None:
    outcome = call_with_retry(make_fake(fail_times=99, error=PermanentError("401")),
                              sleep=lambda _: None, rng=random.Random(1))
    assert not outcome.ok and outcome.attempts == 1, outcome


def test_stream_interruption_is_not_committed() -> None:
    session = ChatSession(send=fake_sender)
    session.ask("My test service is called Orion.")
    before = list(session.committed)

    def interrupted(_: list[dict[str, str]]) -> str:
        consume(fake_stream(interrupt_after=3), display=False)
        return "unreachable"

    session._send = interrupted
    try:
        session.ask("Explain a context window.")
    except StreamInterrupted:
        pass
    else:
        raise AssertionError("the interruption must propagate")
    assert session.committed == before, "partial text must not enter history"


def test_failure_usage_is_unknown_not_zero() -> None:
    record = measure(fake_failure)
    assert record.status == "error"
    assert record.input_tokens is None and record.output_tokens is None
    assert record.latency_ms >= 0
    ok = measure(fake_success)
    assert ok.input_tokens == 21 and ok.output_tokens == 64


def test_exit_command_sends_no_request() -> None:
    calls = {"n": 0}

    def counting(messages: list[dict[str, str]]) -> str:
        calls["n"] += 1
        return "should not happen"

    client = claude_cli.Client("test-model", "sys", 100, False, sender=counting)
    claude_cli.run(client, script=["/exit"])
    assert calls["n"] == 0, "no request may be sent for /exit"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failures = 0
    for test in TESTS:
        name = test.__name__.replace("test_", "").replace("_", " ")
        try:
            test()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {name}: {exc}")
        except Exception as exc:
            failures += 1
            print(f"ERROR {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"pass  {name}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    sys.exit(1 if failures else 0)
