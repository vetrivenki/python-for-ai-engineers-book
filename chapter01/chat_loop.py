"""Lesson 1.6 / Task 6 - Maintain Conversation History.

Candidate-and-commit: the new user message is sent as part of a candidate list
but only joins committed history once the request succeeds. A failed call
therefore cannot duplicate input or leave a dangling user turn.

Run live:     python chat_loop.py
Run offline:  python chat_loop.py --fake     (scripted transcript, no API calls)
"""

from __future__ import annotations

import sys
from typing import Callable

from config import DEFAULT_MODEL, build_client

MAX_TOKENS = 300
MAX_TURNS = 6          # retention limit, counted in complete exchanges

Message = dict[str, str]
Sender = Callable[[list[Message]], str]


class ChatSession:
    def __init__(self, send: Sender, max_turns: int = MAX_TURNS) -> None:
        self._send = send
        self._max_turns = max_turns
        self.committed: list[Message] = []
        self.dropped_turns = 0

    def candidate(self, user_text: str) -> list[Message]:
        """History plus the new input, without touching committed state."""
        return [*self.committed, {"role": "user", "content": user_text}]

    def ask(self, user_text: str) -> str:
        candidate = self.candidate(user_text)
        reply = self._send(candidate)                 # may raise; nothing committed yet
        self.committed = candidate + [{"role": "assistant", "content": reply}]
        self._trim()
        return reply

    def _trim(self) -> None:
        """Remove whole oldest exchanges so a question never outlives its answer."""
        while len(self.committed) > self._max_turns * 2:
            del self.committed[0:2]
            self.dropped_turns += 1

    def reset(self) -> None:
        self.committed = []
        self.dropped_turns = 0


def live_sender(messages: list[Message]) -> str:
    client = build_client()
    response = client.messages.create(
        model=DEFAULT_MODEL, max_tokens=MAX_TOKENS, messages=messages
    )
    return "".join(b.text for b in response.content if b.type == "text")


def fake_sender(messages: list[Message]) -> str:
    """Answers only from what is present in the payload, so history is observable."""
    text = " ".join(m["content"] for m in messages if m["role"] == "user").lower()
    if "what is its name" in text:
        return "Its name is Orion." if "orion" in text else "I do not have a name in this conversation."
    if "orion" in text and "called" in text:
        return "Understood - the test service is called Orion."
    return f"Acknowledged ({len(messages)} message(s) in payload)."


def chat_loop(send: Sender = live_sender, script: list[str] | None = None) -> ChatSession:
    session = ChatSession(send)
    queue = list(script) if script is not None else None

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
        if user == "/exit":                      # handled before any request
            print("bye - no request sent")
            break
        if user == "/reset":
            session.reset()
            print("history cleared - no request sent")
            continue

        payload_size = len(session.candidate(user))
        try:
            reply = session.ask(user)
        except Exception as exc:                 # committed history is untouched
            print(f"[error] {type(exc).__name__}: {exc}")
            print(f"[state] committed history unchanged ({len(session.committed)} messages)")
            continue

        print(f"claude> {reply}")
        print(f"        [payload {payload_size} msg | committed {len(session.committed)} msg"
              + (f" | dropped {session.dropped_turns} old turn(s)]" if session.dropped_turns else "]"))
    return session


if __name__ == "__main__":
    if "--fake" in sys.argv:
        chat_loop(send=fake_sender, script=[
            "My test service is called Orion.",
            "What is its name?",
            "/reset",
            "What is its name?",
            "/exit",
        ])
    else:
        chat_loop()
