"""Lesson 2.6 / Task 14 - Relevant versus irrelevant context.

The instinct when an answer is wrong is to add more context. This lesson runs
the control: the same question with the right section, with the wrong section,
with both, and with none. More context costs tokens in every case and only
helps in one of them.

Run:  python ch2_06_relevance_test.py     (offline; fixtures model the four conditions)
"""

from __future__ import annotations

from dataclasses import dataclass

from ch2_00_config import approx_tokens
from ch2_05_document_context import QUESTION, RUNBOOK, chunk_document

RELEVANT = "4. Intermittent 503 with pod restarts"
IRRELEVANT = "2. Dashboards"

# What the model returns under each condition. The point of the fixtures is the
# failure shape, not the wording: with only the wrong section supplied, a model
# will usually still answer - fluently, and from nowhere.
FAKE = {
    "none": ("Intermittent 503s with restarts are often caused by memory pressure or an "
             "out-of-memory kill. Check the pod memory limits.", False),
    "irrelevant": ("Based on the dashboards, you should look at the error rate and p99 "
                   "latency panels. The restarts are likely a resource issue.", False),
    "relevant": ("The readiness probe times out under load because it shares a thread pool "
                 "with request handling, so Kubernetes restarts the pod and in-flight "
                 "requests return 503. Raise the probe timeout to 3s and give the probe its "
                 "own worker; do not scale up first.", True),
    "both": ("The readiness probe times out under load because it shares a thread pool with "
             "request handling. Raise the probe timeout to 3s and give the probe its own "
             "worker; do not scale up first.", True),
}

GROUNDED_TERMS = ("readiness probe", "thread pool", "probe timeout")
INVENTED_TERMS = ("memory pressure", "out-of-memory", "resource issue", "memory limits")


@dataclass
class Condition:
    name: str
    sections: list[str]


def context_for(sections: list[str]) -> str:
    chunks = {c.heading: c.text for c in chunk_document(RUNBOOK)}
    return "\n\n".join(chunks[s] for s in sections)


def judge(answer: str) -> dict[str, object]:
    lowered = answer.lower()
    return {
        "grounded": sum(t in lowered for t in GROUNDED_TERMS),
        "invented": sum(t in lowered for t in INVENTED_TERMS),
    }


CONDITIONS = [
    Condition("none", []),
    Condition("irrelevant", [IRRELEVANT]),
    Condition("relevant", [RELEVANT]),
    Condition("both", [IRRELEVANT, RELEVANT]),
]


if __name__ == "__main__":
    print(f"question: {QUESTION}\n")
    print(f"{'context supplied':<14}{'~ctx tokens':>12}{'grounded':>10}{'invented':>10}{'usable':>8}")
    print("-" * 54)

    rows = []
    for cond in CONDITIONS:
        ctx = context_for(cond.sections)
        answer, usable = FAKE[cond.name]
        marks = judge(answer)
        rows.append((cond.name, approx_tokens(ctx), marks, usable))
        print(f"{cond.name:<14}{approx_tokens(ctx):>12}{marks['grounded']:>10}"
              f"{marks['invented']:>10}{str(usable):>8}")

    print("-" * 54)
    none_t = next(t for n, t, _, _ in rows if n == "none")
    irr_t = next(t for n, t, _, _ in rows if n == "irrelevant")
    rel_t = next(t for n, t, _, _ in rows if n == "relevant")
    both_t = next(t for n, t, _, _ in rows if n == "both")

    print(f"irrelevant context cost ~{irr_t - none_t} tokens and changed nothing usable.")
    print(f"'both' cost ~{both_t - rel_t} tokens more than 'relevant' for the same answer.")
    print("\nThe failure to watch for is the second row: a confident, fluent answer built on")
    print("context that could not possibly support it. Fluency is not grounding, and adding")
    print("the wrong document does not degrade gracefully - it degrades invisibly.")
