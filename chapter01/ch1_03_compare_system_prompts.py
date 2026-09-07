"""Lesson 1.3 / Task 3 - Compare System Instructions.

Controlled comparison: the user input, model and output budget stay fixed while
one system instruction changes. Three trials per instruction, labelled A1-A3 and
B1-B3, then scored for required structure and for unsupported claims separately.

Run live:     python ch1_03_compare_system_prompts.py
Run offline:  python ch1_03_compare_system_prompts.py --fake
"""

from __future__ import annotations

import sys
from typing import Any

from ch1_00_config import DEFAULT_MODEL, build_client

INCIDENT = ("The example service returns intermittent 503 errors; "
            "no logs or deployment history are available.")

INSTRUCTION_A = ("You explain incidents in plain language to an engineer who is new to "
                 "the system. Use short sentences and no jargon.")

INSTRUCTION_B = ("You write concise incident triage notes. Always use exactly two headings: "
                 "'Known facts' and 'Missing evidence'. Do not speculate about root cause.")

TRIALS = 3
MAX_TOKENS = 300

# Words that signal a cause asserted beyond what the incident note supports.
SPECULATION_MARKERS = ("caused by", "root cause is", "because the", "due to a", "clearly a")

FAKE_OUTPUTS = {
    "A": [
        "The service is failing some of the time. A 503 means the server could not handle "
        "the request. We cannot see logs, so we do not know why yet.",
        "Requests to the service sometimes fail with a 503 error. That is a server-side "
        "failure. There is no log or deploy history available, so the reason is unknown.",
        "The service returns errors now and then. This is probably caused by a bad deploy.",
    ],
    "B": [
        "Known facts\n- Intermittent 503 responses from the example service.\n"
        "Missing evidence\n- Application logs\n- Deployment history",
        "Known facts\n- The service returns 503 errors intermittently.\n"
        "Missing evidence\n- No logs available\n- No deployment history available",
        "Known facts\n- Intermittent HTTP 503.\nMissing evidence\n- Logs, deploy timeline.",
    ],
}


def score(text: str) -> dict[str, Any]:
    lowered = text.lower()
    return {
        "chars": len(text),
        "has_known_facts": "known facts" in lowered,
        "has_missing_evidence": "missing evidence" in lowered,
        "unsupported_claims": sum(1 for m in SPECULATION_MARKERS if m in lowered),
    }


def run_trial(system: str, fake_text: str | None) -> str:
    if fake_text is not None:
        return fake_text
    client = build_client()
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=MAX_TOKENS,
        system=system,                                   # top-level system field
        messages=[{"role": "user", "content": INCIDENT}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


def main(argv: list[str]) -> int:
    fake = "--fake" in argv
    rows = []

    for label, system in (("A", INSTRUCTION_A), ("B", INSTRUCTION_B)):
        for n in range(1, TRIALS + 1):
            text = run_trial(system, FAKE_OUTPUTS[label][n - 1] if fake else None)
            rows.append((f"{label}{n}", text, score(text)))

    print(f"model={DEFAULT_MODEL}  max_tokens={MAX_TOKENS}  input=fixed  trials={TRIALS} per instruction")
    print(f"mode={'offline fake responses' if fake else 'live requests'}\n")
    print(f"{'trial':<7}{'chars':>7}{'Known facts':>14}{'Missing ev.':>13}{'unsupported':>13}")
    print("-" * 54)
    for label, _, s in rows:
        print(f"{label:<7}{s['chars']:>7}{str(s['has_known_facts']):>14}"
              f"{str(s['has_missing_evidence']):>13}{s['unsupported_claims']:>13}")

    a = [s for lbl, _, s in rows if lbl.startswith("A")]
    b = [s for lbl, _, s in rows if lbl.startswith("B")]
    print("-" * 54)
    print(f"A: headings in {sum(x['has_known_facts'] for x in a)}/{TRIALS} trials, "
          f"{sum(x['unsupported_claims'] for x in a)} unsupported claim(s)")
    print(f"B: headings in {sum(x['has_known_facts'] for x in b)}/{TRIALS} trials, "
          f"{sum(x['unsupported_claims'] for x in b)} unsupported claim(s)")
    print("\nEvidence excerpt (A3):", FAKE_OUTPUTS['A'][2][-40:] if fake else rows[2][1][-40:])
    print("Conclusion: observed on 6 trials only; not a benchmark result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
