"""Chapter 1 Project - Resilient Claude CLI.

Combines tasks 1-8 into one inspectable client:
  secure configuration (1), bounded requests (2), configurable system prompt (3),
  explicit output budget (4), streaming or final-text display (5),
  candidate-and-commit history (6), single-owner retry policy (7),
  and one telemetry record per logical request (8).

Run:  python ch1_09_claude_cli.py [--stream] [--system "..."] [--max-tokens 400]
      python ch1_09_claude_cli.py --fake            (scripted offline transcript)
Commands inside the loop: /reset  /exit  /stream  /history
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any, Callable

from ch1_06_chat_loop import ChatSession
from ch1_00_config import API_KEY_VAR, DEFAULT_MODEL, api_key_present
from ch1_08_measured_client import Record, emit, measure
from ch1_07_resilient_client import PermanentError, TransientError, call_with_retry

DEFAULT_SYSTEM = "You are a concise engineering assistant. State uncertainty plainly."


class Client:
    """Owns model configuration, retries, streaming and telemetry."""

    def __init__(self, model: str, system: str, max_tokens: int,
                 stream: bool, sender: Callable[..., Any] | None = None) -> None:
        self.model, self.system, self.max_tokens = model, system, max_tokens
        self.stream = stream
        self._sender = sender          # injected for tests; None means live SDK
        self.records: list[Record] = []

    # -- transport ---------------------------------------------------------
    def _live_once(self, messages: list[dict[str, str]]) -> tuple[Any, float | None]:
        import anthropic

        client = anthropic.Anthropic(max_retries=0)     # this class owns the policy
        try:
            if self.stream:
                first_at = None
                with client.messages.stream(model=self.model, max_tokens=self.max_tokens,
                                            system=self.system, messages=messages) as s:
                    for delta in s.text_stream:
                        if first_at is None and delta.strip():
                            first_at = time.perf_counter()
                        sys.stdout.write(delta)
                        sys.stdout.flush()
                    sys.stdout.write("\n")
                    return s.get_final_message(), first_at
            response = client.messages.create(model=self.model, max_tokens=self.max_tokens,
                                              system=self.system, messages=messages)
            return response, None
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

    # -- public API --------------------------------------------------------
    def send(self, messages: list[dict[str, str]]) -> str:
        """Retry-wrapped, measured request. Returns assistant text or raises.

        The measurement wraps the whole retry-wrapped operation, so latency_ms is
        end-to-end for one logical request and includes any backoff waiting. The
        per-attempt lines printed by call_with_retry stay separate from it.
        """
        once = self._sender or self._live_once
        state: dict[str, Any] = {"attempts": 0}

        def attempt() -> Any:
            result = once(messages)
            response, first_at = result if isinstance(result, tuple) else (result, None)
            state["response"], state["first_at"] = response, first_at
            return response

        def logical_request() -> Any:
            outcome = call_with_retry(attempt)
            state["attempts"] = outcome.attempts
            if not outcome.ok:
                raise RuntimeError(outcome.error or "request failed")
            return (state["response"], state["first_at"]) if self.stream else state["response"]

        record = measure(logical_request, streaming=self.stream)
        self.records.append(record)
        emit(record)

        if record.status == "error":
            raise RuntimeError(f"request failed after {state['attempts']} attempt(s)")

        response = state["response"]
        text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
        if not text:
            raise RuntimeError("response contained no text block")
        return text


# --- offline scripted sender ----------------------------------------------

class _U:
    def __init__(self) -> None:
        self.input_tokens, self.output_tokens = 24, 37


class _B:
    def __init__(self, text: str) -> None:
        self.type, self.text = "text", text


class _R:
    def __init__(self, text: str) -> None:
        self.model, self.stop_reason = DEFAULT_MODEL, "end_turn"
        self.usage, self.content = _U(), [_B(text)]


def fake_sender(messages: list[dict[str, str]]) -> _R:
    joined = " ".join(m["content"] for m in messages if m["role"] == "user").lower()
    if "what is its name" in joined:
        return _R("Its name is Orion." if "orion" in joined
                  else "No service name appears in this conversation.")
    return _R(f"Acknowledged ({len(messages)} message(s) in payload).")


# --- loop ------------------------------------------------------------------

def run(client: Client, script: list[str] | None = None) -> Client:
    session = ChatSession(send=client.send)
    queue = list(script) if script is not None else None
    print(f"Resilient Claude CLI - model={client.model} stream={client.stream} "
          f"max_tokens={client.max_tokens}")
    print("commands: /reset /exit /stream /history\n")

    while True:
        if queue is not None:
            if not queue:
                break
            user = queue.pop(0)
            print(f"you> {user}")
        else:
            try:
                user = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

        if not user:
            continue
        if user == "/exit":
            print("bye - no request sent")
            break
        if user == "/reset":
            session.reset()
            print("history cleared - no request sent")
            continue
        if user == "/stream":
            client.stream = not client.stream
            print(f"streaming {'on' if client.stream else 'off'} - no request sent")
            continue
        if user == "/history":
            print(f"{len(session.committed)} committed message(s) - no request sent")
            continue

        try:
            reply = session.ask(user)
        except Exception as exc:
            print(f"[error] {exc}")
            print(f"[state] committed history unchanged ({len(session.committed)} messages)")
            continue
        if not client.stream:
            print(f"claude> {reply}")
    return client


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Resilient Claude CLI")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--system", default=DEFAULT_SYSTEM)
    parser.add_argument("--max-tokens", type=int, default=400)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--fake", action="store_true", help="scripted offline transcript")
    args = parser.parse_args(argv)

    if not args.fake and not api_key_present():
        print(f"[fatal] {API_KEY_VAR} is not set. Run ch1_01_setup_check.py first. No request sent.")
        return 1

    client = Client(args.model, args.system, args.max_tokens, args.stream,
                    sender=fake_sender if args.fake else None)
    run(client, script=[
        "My test service is called Orion.", "What is its name?",
        "/reset", "What is its name?", "/exit",
    ] if args.fake else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
