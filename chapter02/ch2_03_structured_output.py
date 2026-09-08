"""Lesson 2.3 / Task 11 - Request structured JSON output.

Asking for JSON is not the same as receiving it. Models wrap objects in code
fences, add a sentence of preamble, or emit trailing commas. The parser needs an
explicit extraction boundary and must never fall back to eval().

Run live:     python ch2_03_structured_output.py
Run offline:  python ch2_03_structured_output.py --fake
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from typing import Any

from ch2_00_config import DEFAULT_MODEL, INCIDENT, build_client

MAX_TOKENS = 400

SCHEMA_HINT = {
    "severity": "SEV1 | SEV2 | SEV3",
    "component": "string",
    "start_utc": "HH:MM",
    "end_utc": "HH:MM",
    "error_rate_pct": "number",
    "restarts": "integer",
    "deployment_in_window": "boolean",
}

INSTRUCTION = (
    "Return ONLY a JSON object, no prose and no code fence, with exactly these keys:\n"
    + json.dumps(SCHEMA_HINT, indent=2)
    + "\nUse only values stated in the incident note. Do not infer a cause."
)

FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)

# Four replies that all "look like JSON" to a human. Only one parses cleanly.
FAKE_REPLIES = [
    '{"severity":"SEV2","component":"checkout-api","start_utc":"09:12","end_utc":"09:41",'
    '"error_rate_pct":4,"restarts":3,"deployment_in_window":false}',

    'Here is the structured summary:\n\n```json\n{"severity":"SEV2","component":"checkout-api",'
    '"start_utc":"09:12","end_utc":"09:41","error_rate_pct":4,"restarts":3,'
    '"deployment_in_window":false}\n```',

    '{"severity":"SEV2","component":"checkout-api","start_utc":"09:12","end_utc":"09:41",'
    '"error_rate_pct":4,"restarts":3,"deployment_in_window":false,}',        # trailing comma

    "The incident was a SEV2 affecting checkout-api between 09:12 and 09:41 UTC.",  # no JSON
]


@dataclass
class ParseResult:
    ok: bool
    data: dict[str, Any] | None
    stage: str          # where it succeeded or failed
    detail: str


def extract(text: str) -> tuple[str, str]:
    """Return (candidate, how). Strip a fence, else take the outermost braces."""
    fenced = FENCE.search(text)
    if fenced:
        return fenced.group(1).strip(), "fence"
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1], "braces"
    return text.strip(), "raw"


def parse(text: str) -> ParseResult:
    candidate, how = extract(text)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return ParseResult(False, None, f"json/{how}", f"{exc.msg} at char {exc.pos}")
    if not isinstance(data, dict):
        return ParseResult(False, None, f"type/{how}", f"expected object, got {type(data).__name__}")
    missing = sorted(set(SCHEMA_HINT) - set(data))
    unexpected = sorted(set(data) - set(SCHEMA_HINT))
    if missing or unexpected:
        return ParseResult(False, data, f"keys/{how}",
                           f"missing={missing} unexpected={unexpected}")
    return ParseResult(True, data, f"ok/{how}", "all keys present")


def ask(fake_index: int | None) -> str:
    if fake_index is not None:
        return FAKE_REPLIES[fake_index]
    client = build_client()
    response = client.messages.create(
        model=DEFAULT_MODEL, max_tokens=MAX_TOKENS,
        system=INSTRUCTION,
        messages=[{"role": "user", "content": INCIDENT}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


def main(argv: list[str]) -> int:
    fake = "--fake" in argv
    replies = range(len(FAKE_REPLIES)) if fake else [None]
    print(f"model={DEFAULT_MODEL}  mode={'offline fixtures' if fake else 'live request'}\n")
    print(f"{'reply':<7}{'parsed':>8}{'route':>14}  detail")
    print("-" * 74)

    ok = 0
    for i in replies:
        result = parse(ask(i))
        ok += result.ok
        label = f"#{i + 1}" if i is not None else "live"
        print(f"{label:<7}{str(result.ok):>8}{result.stage:>14}  {result.detail[:40]}")

    print("-" * 74)
    print(f"parsed cleanly: {ok}/{len(list(replies))}")
    print("Reply 2 needed the fence stripped. Reply 3 is valid-looking but not valid JSON.")
    print("Reply 4 contains no object at all - the honest outcome is a failure, not a guess.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
