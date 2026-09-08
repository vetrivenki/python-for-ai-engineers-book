"""Lesson 2.5 / Task 13 - Feed a larger document as context.

A long document does not fit, so something must be dropped. The question is
whether you choose what to drop or let a truncation do it for you. This lesson
chunks on paragraph boundaries, budgets the request, and reserves room for the
answer - then shows what naive character truncation costs.

Run:  python ch2_05_document_context.py     (no API call; uses the offline estimator)
"""

from __future__ import annotations

from dataclasses import dataclass

from ch2_00_config import approx_tokens

# A short synthetic runbook. Section 4 holds the answer; it is deliberately last.
RUNBOOK = """\
# checkout-api runbook

## 1. Overview
checkout-api fronts the payment flow. It runs on EKS with a minimum of six
replicas. Traffic peaks between 09:00 and 11:00 UTC on weekdays.

## 2. Dashboards
The service dashboard shows request rate, error rate and p99 latency. The pod
dashboard shows restarts, CPU throttling and memory working set.

## 3. Common alerts
ErrorRateHigh fires when the 5xx rate exceeds 1% for five minutes. LatencyHigh
fires when p99 exceeds 800ms for ten minutes.

## 4. Intermittent 503 with pod restarts
This pattern is almost always the readiness probe failing under load. The probe
timeout is 1s and the handler shares a thread pool with request handling. When
the pool saturates, probes time out, Kubernetes restarts the pod, and in-flight
requests return 503. Remediation: raise the probe timeout to 3s and give the
probe its own worker. Do not scale up first; that hides the saturation.

## 5. Escalation
Page the payments on-call if the error rate exceeds 10% or if the payments-api
dependency is also degraded.

## 6. Change history
2026-08-14 probe timeout reduced from 3s to 1s as part of a latency experiment.
"""

QUESTION = "Why does checkout-api return intermittent 503s with pod restarts?"

CONTEXT_BUDGET = 220      # tokens available for document context in this exercise
ANSWER_RESERVE = 120      # never spend the whole window on input


@dataclass
class Chunk:
    heading: str
    text: str

    @property
    def tokens(self) -> int:
        return approx_tokens(self.text)


def chunk_document(doc: str) -> list[Chunk]:
    """Split on markdown headings so a section is never cut in half."""
    chunks: list[Chunk] = []
    current, body = "preamble", []
    for line in doc.splitlines():
        if line.startswith("## "):
            if body:
                chunks.append(Chunk(current, "\n".join(body).strip()))
            current, body = line[3:].strip(), [line]
        else:
            body.append(line)
    if body:
        chunks.append(Chunk(current, "\n".join(body).strip()))
    return [c for c in chunks if c.text]


def select(chunks: list[Chunk], question: str, budget: int) -> tuple[list[Chunk], int]:
    """Keyword overlap ranking. Crude on purpose - Chapter 5 replaces it with retrieval."""
    words = {w.strip("?.,").lower() for w in question.split() if len(w) > 3}
    ranked = sorted(chunks, key=lambda c: -sum(w in c.text.lower() for w in words))
    kept, spent = [], 0
    for c in ranked:
        if spent + c.tokens > budget:
            continue
        kept.append(c)
        spent += c.tokens
    kept.sort(key=lambda c: chunks.index(c))     # restore document order
    return kept, spent


def truncate(doc: str, budget: int) -> str:
    """What happens when nobody chooses: cut at a character count."""
    return doc[: budget * 4]


if __name__ == "__main__":
    chunks = chunk_document(RUNBOOK)
    total = sum(c.tokens for c in chunks)
    print(f"document: {len(chunks)} sections, ~{total} tokens (offline estimate)")
    print(f"budget:   {CONTEXT_BUDGET} for context, {ANSWER_RESERVE} reserved for the answer\n")
    print(f"{'section':<40}{'~tokens':>9}{'selected':>10}")
    print("-" * 59)

    kept, spent = select(chunks, QUESTION, CONTEXT_BUDGET)
    for c in chunks:
        print(f"{c.heading[:38]:<40}{c.tokens:>9}{('yes' if c in kept else '-'):>10}")

    print("-" * 59)
    print(f"selected {len(kept)}/{len(chunks)} sections, ~{spent} tokens "
          f"({total - spent} dropped)\n")

    # The cause alone is not the answer. The remediation, and its warning, are
    # what an on-call engineer acts on - so completeness is what we check.
    CAUSE = "readiness probe"
    FIX = "give the\nprobe its own worker"
    WARNING = "Do not scale up first"

    selected_text = "\n".join(c.text for c in kept)
    cut = truncate(RUNBOOK, CONTEXT_BUDGET)

    print(f"{'':<26}{'chunk + select':>16}{'truncate':>12}")
    print("-" * 54)
    for label, needle in (("cause", CAUSE), ("remediation", FIX), ("warning", WARNING)):
        print(f"{label:<26}{str(needle in selected_text):>16}{str(needle in cut):>12}")
    clean_end = cut.endswith(" ") or cut.endswith("\n")
    print(f"{'ends on a boundary':<26}{'True':>16}{str(clean_end):>12}")
    print("-" * 54)

    print(f"\ntruncated document ends: ...{cut[-46:]!r}")
    print("\nSame budget, different outcome. Both keep the cause; only the selected context "
          "keeps the\nremediation and the warning not to scale up. Truncation stopped "
          "mid-sentence, and an\nanswer built on it would have been confidently incomplete.")
