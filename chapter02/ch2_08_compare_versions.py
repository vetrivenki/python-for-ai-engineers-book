"""Lesson 2.8 / Task 16 - Compare quality, tokens and latency together.

A prompt change is only an improvement if you know what it cost. This lesson
runs two registered prompt versions over the same input and reports all three
axes in one table, then states the trade explicitly rather than declaring a
winner on quality alone.

Run:  python ch2_08_compare_versions.py     (offline fixtures with measured timing)
"""

from __future__ import annotations

import re
import statistics
import time
from dataclasses import dataclass

from ch2_00_config import DEFAULT_MODEL, INCIDENT, approx_tokens
from ch2_07_prompt_versioning import V1, V2, Prompt, Registry, RunRecord

TRIALS = 3

# (output, input_tokens, output_tokens, simulated_seconds) per version per trial.
FAKE = {
    "1.0.0": [
        ("Known facts\n- checkout-api returned 503 for 4% of requests 09:12-09:41 UTC.\n"
         "- 3 pod restarts.\nMissing evidence\n- Probe configuration.", 96, 48, 0.031),
        ("Known facts\n- 4% error rate over 29 minutes; 3 restarts; no deployment.\n"
         "Missing evidence\n- Thread pool metrics.\nThis was likely caused by memory "
         "pressure.", 96, 57, 0.034),
        ("Known facts\n- Intermittent 503s and restarts on checkout-api.\n"
         "Missing evidence\n- Probe timings.", 96, 39, 0.028),
    ],
    "1.1.0": [
        ("Known facts\n- checkout-api returned HTTP 503 for 4% of requests between 09:12 "
         "and 09:41 UTC.\n- 3 pod restarts; no deployment recorded.\n- payments-api latency "
         "rose at 09:15.\nMissing evidence\n- Readiness probe configuration and timings.\n"
         "- Thread pool saturation metrics.\nCause is not established from this note.",
         118, 92, 0.049),
        ("Known facts\n- 4% of requests returned 503 over a 29 minute window.\n- 3 restarts, "
         "no deployment.\nMissing evidence\n- Probe configuration.\n- Downstream dependency "
         "timeline.\nUncertain: the note does not identify a cause.", 118, 78, 0.045),
        ("Known facts\n- Intermittent 503s, 3 restarts, no deployment in window.\n"
         "Missing evidence\n- Probe settings, pool metrics.\nNo root cause is stated in the "
         "supplied note.", 118, 61, 0.041),
    ],
}

REQUIRED_HEADINGS = ("Known facts", "Missing evidence")
# An affirmative cause claim only. The negative lookbehind keeps "no root cause
# is stated" out of the count - the first version of this scorer flagged the
# hedge as the very thing it was hedging against.
CAUSE_CLAIMS = re.compile(r"(?<!no )(?<!not )\b(caused by|root cause is|due to|because of)\b")
UNCERTAINTY = ("not established", "uncertain", "does not identify", "no root cause",
               "cause is not")


@dataclass
class Trial:
    version: str
    quality: int
    headings: bool
    unsupported_cause: bool
    hedged: bool
    input_tokens: int
    output_tokens: int
    latency_ms: float


def grade(text: str) -> tuple[int, bool, bool, bool]:
    lowered = text.lower()
    headings = all(h in text for h in REQUIRED_HEADINGS)
    cause = CAUSE_CLAIMS.search(lowered) is not None
    hedged = any(u in lowered for u in UNCERTAINTY)
    # Quality: structure, plus credit for stating uncertainty, minus an
    # unsupported cause. Deliberately simple and written down.
    score = (2 if headings else 0) + (1 if hedged else 0) - (2 if cause else 0)
    return score, headings, cause, hedged


def run(prompt: Prompt, trial: int) -> Trial:
    text, tin, tout, sleep_for = FAKE[prompt.version][trial]
    start = time.perf_counter()
    time.sleep(sleep_for)                       # stands in for the request
    elapsed = (time.perf_counter() - start) * 1000
    score, headings, cause, hedged = grade(text)
    return Trial(prompt.version, score, headings, cause, hedged, tin, tout, round(elapsed, 1))


if __name__ == "__main__":
    reg = Registry()
    reg.register(V1)
    reg.register(V2)

    print(f"model={DEFAULT_MODEL}  input=fixed (~{approx_tokens(INCIDENT)} tokens)  "
          f"trials={TRIALS} per version\n")
    print(f"{'version':<9}{'trial':>6}{'quality':>9}{'headings':>10}{'cause':>7}"
          f"{'hedged':>8}{'in':>6}{'out':>6}{'ms':>8}")
    print("-" * 69)

    results: dict[str, list[Trial]] = {}
    for prompt in (V1, V2):
        rows = [run(prompt, i) for i in range(TRIALS)]
        results[prompt.version] = rows
        for i, r in enumerate(rows, 1):
            print(f"{r.version:<9}{i:>6}{r.quality:>9}{str(r.headings):>10}"
                  f"{str(r.unsupported_cause):>7}{str(r.hedged):>8}"
                  f"{r.input_tokens:>6}{r.output_tokens:>6}{r.latency_ms:>8.1f}")

    print("-" * 69)
    print(f"{'version':<9}{'quality':>9}{'unsupported':>13}{'avg in':>9}{'avg out':>9}{'avg ms':>9}")
    print("-" * 69)
    for version, rows in results.items():
        print(f"{version:<9}{statistics.mean(r.quality for r in rows):>9.1f}"
              f"{sum(r.unsupported_cause for r in rows):>13}"
              f"{statistics.mean(r.input_tokens for r in rows):>9.0f}"
              f"{statistics.mean(r.output_tokens for r in rows):>9.0f}"
              f"{statistics.mean(r.latency_ms for r in rows):>9.1f}")

    a, b = results["1.0.0"], results["1.1.0"]
    d_in = statistics.mean(r.input_tokens for r in b) - statistics.mean(r.input_tokens for r in a)
    d_out = statistics.mean(r.output_tokens for r in b) - statistics.mean(r.output_tokens for r in a)
    d_ms = statistics.mean(r.latency_ms for r in b) - statistics.mean(r.latency_ms for r in a)
    print("-" * 69)
    print(f"\n1.1.0 vs 1.0.0: unsupported causes {sum(r.unsupported_cause for r in a)} -> "
          f"{sum(r.unsupported_cause for r in b)}, "
          f"+{d_in:.0f} input tokens, +{d_out:.0f} output tokens, +{d_ms:.0f} ms per request.")
    print("That is the trade, stated in full. Whether it is worth paying depends on how")
    print("expensive a confidently wrong root cause is in your system - which is a")
    print("judgement, not a number the table can make for you.")

    record = RunRecord.of(V2, DEFAULT_MODEL, INCIDENT, FAKE["1.1.0"][0][0])
    print(f"\nrecorded against: {record.prompt_ref}")
