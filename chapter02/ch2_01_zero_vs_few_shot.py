"""Lesson 2.1 / Task 9 - Zero-shot and few-shot versions of one task.

Same task, same model, same budget; the only difference is whether worked
examples are supplied. Format adherence and factual support are scored
separately, because few-shot examples reliably fix *shape* and do nothing for
*truth* - and can actively harm it by leaking example content into the answer.

Run live:     python ch2_01_zero_vs_few_shot.py
Run offline:  python ch2_01_zero_vs_few_shot.py --fake
"""

from __future__ import annotations

import re
import sys
from typing import Any

from ch2_00_config import DEFAULT_MODEL, INCIDENT, build_client

MAX_TOKENS = 300
TRIALS = 3

TASK = (
    "Classify this incident. Reply with exactly three lines:\n"
    "SEVERITY: <SEV1|SEV2|SEV3>\n"
    "COMPONENT: <service name>\n"
    "EVIDENCE: <one sentence quoting only what the note states>"
)

# Worked examples. Their services are deliberately unrelated to the real input,
# so any appearance of them in an answer is example leakage, not analysis.
EXAMPLES = [
    ("Service billing-worker queue depth grew from 10 to 40,000 over 20 minutes. "
     "No errors logged.",
     "SEVERITY: SEV2\nCOMPONENT: billing-worker\nEVIDENCE: Queue depth grew from 10 to "
     "40,000 in 20 minutes with no errors logged."),
    ("Service search-api returned HTTP 500 for 100% of requests for 6 minutes after a "
     "config change.",
     "SEVERITY: SEV1\nCOMPONENT: search-api\nEVIDENCE: All requests returned HTTP 500 for "
     "six minutes following a config change."),
]

REQUIRED_KEYS = ("SEVERITY:", "COMPONENT:", "EVIDENCE:")
LEAKED_TERMS = ("billing-worker", "search-api", "queue depth", "config change")

FAKE = {
    "zero": [
        "This looks like a SEV2 incident affecting checkout-api. The 503 errors and pod "
        "restarts suggest instability, possibly memory pressure.",
        "SEVERITY: SEV2\nCOMPONENT: checkout-api\nEVIDENCE: 4% of requests returned 503 "
        "between 09:12 and 09:41 with 3 pod restarts.",
        "Severity: moderate. The affected component is checkout-api. Evidence: intermittent "
        "503s and restarts.",
    ],
    "few": [
        "SEVERITY: SEV2\nCOMPONENT: checkout-api\nEVIDENCE: 4% of requests returned HTTP 503 "
        "between 09:12 and 09:41 UTC with 3 pod restarts.",
        "SEVERITY: SEV2\nCOMPONENT: checkout-api\nEVIDENCE: checkout-api returned 503 for 4% "
        "of requests over 29 minutes; payments-api latency rose at 09:15.",
        "SEVERITY: SEV2\nCOMPONENT: checkout-api\nEVIDENCE: A config change caused 503s for "
        "4% of requests.",
    ],
}


def score(text: str) -> dict[str, Any]:
    """Shape and support are independent measurements."""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return {
        "keys": sum(1 for k in REQUIRED_KEYS if k in text),
        "exact_shape": len(lines) == 3 and all(
            lines[i].startswith(k) for i, k in enumerate(REQUIRED_KEYS)),
        "leaked": sorted({t for t in LEAKED_TERMS if t in text.lower()}),
        "unsupported": bool(re.search(r"caused by|because|due to|possibly|suggests", text, re.I)),
    }


def build_messages(few_shot: bool) -> list[dict[str, str]]:
    """Few-shot examples go in the message list as completed turns."""
    messages: list[dict[str, str]] = []
    if few_shot:
        for note, answer in EXAMPLES:
            messages.append({"role": "user", "content": f"{TASK}\n\nIncident: {note}"})
            messages.append({"role": "assistant", "content": answer})
    messages.append({"role": "user", "content": f"{TASK}\n\nIncident: {INCIDENT}"})
    return messages


def run(few_shot: bool, trial: int, fake: bool) -> str:
    if fake:
        return FAKE["few" if few_shot else "zero"][trial]
    client = build_client()
    response = client.messages.create(
        model=DEFAULT_MODEL, max_tokens=MAX_TOKENS, messages=build_messages(few_shot)
    )
    return "".join(b.text for b in response.content if b.type == "text")


def main(argv: list[str]) -> int:
    fake = "--fake" in argv
    print(f"model={DEFAULT_MODEL}  max_tokens={MAX_TOKENS}  input=fixed  trials={TRIALS}")
    print(f"mode={'offline fixtures' if fake else 'live requests'}\n")
    print(f"{'variant':<10}{'keys':>6}{'exact shape':>14}{'leaked':>9}{'unsupported':>13}")
    print("-" * 52)

    summary = {}
    for label, few in (("zero-shot", False), ("few-shot", True)):
        rows = [score(run(few, i, fake)) for i in range(TRIALS)]
        summary[label] = rows
        for i, s in enumerate(rows, 1):
            print(f"{label + '/' + str(i):<10}{s['keys']:>6}{str(s['exact_shape']):>14}"
                  f"{len(s['leaked']):>9}{str(s['unsupported']):>13}")

    print("-" * 52)
    for label, rows in summary.items():
        shape = sum(r["exact_shape"] for r in rows)
        leak = sum(len(r["leaked"]) > 0 for r in rows)
        unsup = sum(r["unsupported"] for r in rows)
        print(f"{label:<10} exact shape {shape}/{TRIALS} | leaked examples {leak}/{TRIALS} "
              f"| unsupported claims {unsup}/{TRIALS}")

    leaks = sorted({t for rows in summary.values() for r in rows for t in r["leaked"]})
    print(f"\nLeaked example terms observed: {leaks or 'none'}")
    print("Few-shot buys format, not truth. Score the two separately or you will not see it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
