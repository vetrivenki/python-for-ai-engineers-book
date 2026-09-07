"""Lesson 1.4 / Task 4 - Understand Tokens and Output Budgets.

Holds the prompt fixed and varies only max_tokens across 128 / 256 / 512, twice
each. Separates the configured limit from the usage actually returned, and
detects truncation from both metadata (stop_reason) and content inspection.

These budgets are illustrative experiment settings, not production defaults.

Run live:     python compare_output_settings.py
Run offline:  python compare_output_settings.py --fake
"""

from __future__ import annotations

import re
import sys
from typing import Any

from config import DEFAULT_MODEL, build_client

PROMPT = "In five numbered steps, explain how a chat client maintains conversation history."
BUDGETS = (128, 256, 512)
RUNS_PER_BUDGET = 2

# (text, stop_reason, input_tokens, output_tokens) for the offline matrix.
FAKE_MATRIX = {
    128: [("1. Store messages.\n2. Append the user turn.\n3. Send the whole list.\n4. Receive",
           "max_tokens", 21, 128)] * RUNS_PER_BUDGET,
    256: [("1. Keep an ordered list of messages.\n2. Append the new user turn.\n"
           "3. Send the list as context.\n4. Append the assistant reply.\n"
           "5. Trim whole old exchanges when the list grows.", "end_turn", 21, 71)] * RUNS_PER_BUDGET,
    512: [("1. Keep an ordered list of messages.\n2. Append the new user turn.\n"
           "3. Send the list as context.\n4. Append the assistant reply after success.\n"
           "5. Trim whole old exchanges to stay inside the context window.",
           "end_turn", 21, 79)] * RUNS_PER_BUDGET,
}


def count_steps(text: str) -> int:
    """Number of numbered steps actually present in the answer."""
    return len(re.findall(r"^\s*\d+[.)]", text, flags=re.MULTILINE))


def count_input_tokens(prompt: str) -> int | None:
    """Model-aware input count, measured before the request. None when offline."""
    try:
        client = build_client()
        result = client.messages.count_tokens(
            model=DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return result.input_tokens
    except Exception:
        return None


def run(budget: int, index: int, fake: bool) -> dict[str, Any]:
    if fake:
        text, stop, tin, tout = FAKE_MATRIX[budget][index]
    else:
        client = build_client()
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=budget,
            messages=[{"role": "user", "content": PROMPT}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        stop = response.stop_reason
        tin = response.usage.input_tokens
        tout = response.usage.output_tokens
    return {
        "budget": budget,
        "stop_reason": stop,
        "input_tokens": tin,
        "output_tokens": tout,
        "steps": count_steps(text),
        "complete": stop != "max_tokens" and count_steps(text) >= 5,
    }


def main(argv: list[str]) -> int:
    fake = "--fake" in argv
    pre = 21 if fake else count_input_tokens(PROMPT)
    print(f"model={DEFAULT_MODEL}  prompt=fixed  pre-request input token count={pre}")
    print(f"mode={'offline fake responses' if fake else 'live requests'}\n")
    print(f"{'run':<6}{'max_tokens':>11}{'in':>6}{'out':>6}{'stop_reason':>14}{'steps':>7}{'complete':>10}")
    print("-" * 60)

    rows = []
    for budget in BUDGETS:
        for i in range(RUNS_PER_BUDGET):
            r = run(budget, i, fake)
            rows.append(r)
            print(f"{budget}-{i+1:<4}{r['budget']:>11}{r['input_tokens']:>6}{r['output_tokens']:>6}"
                  f"{r['stop_reason']:>14}{r['steps']:>7}{str(r['complete']):>10}")

    print("-" * 60)
    workable = [r for r in rows if r["complete"]]
    if workable:
        chosen = min(r["budget"] for r in workable)
        print(f"Chosen budget: {chosen} - smallest tested budget that completed all five steps "
              f"in every run.")
    else:
        chosen = max(BUDGETS)
        print(f"No tested budget completed the answer; retry above {chosen}.")
    truncated = [r for r in rows if r["stop_reason"] == "max_tokens"]
    print(f"Truncated runs: {len(truncated)} (stop_reason=max_tokens). "
          f"Configured limit is a constraint; output_tokens is the measurement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
