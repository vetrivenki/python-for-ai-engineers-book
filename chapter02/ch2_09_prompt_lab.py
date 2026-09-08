"""Chapter 2 Project - Prompt Lab.

Combines tasks 9-16 into one runnable experiment harness:
  versioned templates (10, 15), zero/few-shot variants (9), structured output
  with schema validation (11, 12), budgeted document context (13), a relevance
  control (14), and one comparison table across quality, tokens and latency (16).

Every result carries the prompt reference that produced it, so the table can be
regenerated months later against the exact prompt bytes.

Run:  python ch2_09_prompt_lab.py               (offline; the default)
      python ch2_09_prompt_lab.py --live        (real requests; needs a key)
      python ch2_09_prompt_lab.py --json        (machine-readable records)
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from ch2_00_config import (API_KEY_VAR, DEFAULT_MODEL, INCIDENT, api_key_present,
                           approx_tokens, build_client)
from ch2_02_prompt_templates import PromptTemplate
from ch2_03_structured_output import parse
from ch2_04_validate_with_pydantic import IncidentFacts, validate
from ch2_05_document_context import CONTEXT_BUDGET, QUESTION, RUNBOOK, chunk_document, select
from ch2_07_prompt_versioning import Prompt, Registry, RunRecord

TRIALS = 2

FACTS_TEMPLATE = PromptTemplate(
    name="incident_facts",
    version="2.0.0",
    text=(
        "Extract facts from the incident note as a JSON object with exactly these keys: "
        "severity, component, start_utc, end_utc, error_rate_pct, restarts, "
        "deployment_in_window.\n"
        "Return only the object. Use only values stated in the note.\n"
        "{context}"
        "<<<INCIDENT\n{incident}\nINCIDENT\n"
    ),
)


@dataclass
class Result:
    variant: str
    prompt_ref: str
    parsed: bool
    valid: bool
    reason: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


@dataclass
class Lab:
    """Owns the registry, the variants and the measurement loop."""

    model: str = DEFAULT_MODEL
    live: bool = False
    registry: Registry = field(default_factory=Registry)
    results: list[Result] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.prompt = self.registry.register(
            Prompt(FACTS_TEMPLATE.name, FACTS_TEMPLATE.version, FACTS_TEMPLATE.text))

    # -- context ----------------------------------------------------------
    def context_block(self, variant: str) -> str:
        if variant == "no-context":
            return ""
        chunks = chunk_document(RUNBOOK)
        if variant == "irrelevant-context":
            picked = [c for c in chunks if c.heading.startswith("2.")]
        else:
            picked, _ = select(chunks, QUESTION, CONTEXT_BUDGET)
        body = "\n\n".join(c.text for c in picked)
        return f"<<<RUNBOOK\n{body}\nRUNBOOK\n"

    # -- transport --------------------------------------------------------
    def _live(self, rendered: str) -> tuple[str, int, int]:
        client = build_client()
        response = client.messages.create(
            model=self.model, max_tokens=500,
            messages=[{"role": "user", "content": rendered}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        return text, response.usage.input_tokens, response.usage.output_tokens

    def _fake(self, rendered: str, variant: str, trial: int) -> tuple[str, int, int]:
        # Deterministic stand-ins, one per (variant, trial). The second no-context
        # reply is the interesting one: fluent, well-formed, and inventing a key.
        replies = {
            ("no-context", 0): '{"severity":"SEV2","component":"checkout-api",'
                '"start_utc":"09:12","end_utc":"09:41","error_rate_pct":4,"restarts":3,'
                '"deployment_in_window":false}',
            ("no-context", 1): 'Here you go:\n```json\n{"severity":"SEV2",'
                '"component":"checkout-api","start_utc":"09:12","end_utc":"09:41",'
                '"error_rate_pct":4,"restarts":3,"deployment_in_window":false,'
                '"probable_cause":"memory pressure"}\n```',
            ("irrelevant-context", 0): '{"severity":"SEV2","component":"checkout-api",'
                '"start_utc":"09:12","end_utc":"09:41","error_rate_pct":4,"restarts":3,'
                '"deployment_in_window":false}',
            ("irrelevant-context", 1): '{"severity":"critical","component":"checkout-api",'
                '"start_utc":"09:12","end_utc":"09:41","error_rate_pct":4,"restarts":3,'
                '"deployment_in_window":false}',
            ("selected-context", 0): '{"severity":"SEV2","component":"checkout-api",'
                '"start_utc":"09:12","end_utc":"09:41","error_rate_pct":4,"restarts":3,'
                '"deployment_in_window":false}',
            ("selected-context", 1): '```json\n{"severity":"SEV2","component":"checkout-api",'
                '"start_utc":"09:12","end_utc":"09:41","error_rate_pct":4,"restarts":3,'
                '"deployment_in_window":false}\n```',
        }
        text = replies[(variant, trial)]
        # Stand in for request time so the latency column measures something.
        # It scales with the payload, which is the only honest thing an offline
        # fixture can claim about timing.
        time.sleep(0.004 + approx_tokens(rendered) / 8000)
        return text, approx_tokens(rendered), approx_tokens(text)

    # -- measurement ------------------------------------------------------
    def run_variant(self, variant: str, trial: int) -> Result:
        rendered = FACTS_TEMPLATE.render(
            context=self.context_block(variant), incident=INCIDENT)

        start = time.perf_counter()
        try:
            text, tin, tout = (self._live(rendered) if self.live
                               else self._fake(rendered, variant, trial))
        except Exception as exc:
            return Result(variant, self.prompt.ref, False, False,
                          f"{type(exc).__name__}", 0, 0,
                          round((time.perf_counter() - start) * 1000, 1))
        latency = round((time.perf_counter() - start) * 1000, 1)

        parsed = parse(text)
        if not parsed.ok:
            return Result(variant, self.prompt.ref, False, False, parsed.detail[:44],
                          tin, tout, latency)
        ok, reason = validate(json.dumps(parsed.data))
        return Result(variant, self.prompt.ref, True, ok, reason[:44], tin, tout, latency)

    def run(self) -> list[Result]:
        for variant in ("no-context", "irrelevant-context", "selected-context"):
            for trial in range(TRIALS):
                self.results.append(self.run_variant(variant, trial))
        return self.results


def report(results: list[Result]) -> None:
    print(f"{'variant':<20}{'trial':>6}{'shape':>7}{'valid':>7}{'in':>7}{'out':>6}"
          f"{'ms':>8}  reason")
    print("shape = parsed as a JSON object carrying exactly the expected keys")
    print("-" * 88)
    by_variant: dict[str, list[Result]] = {}
    for r in results:
        by_variant.setdefault(r.variant, []).append(r)
    for variant, rows in by_variant.items():
        for i, r in enumerate(rows, 1):
            print(f"{variant:<20}{i:>6}{str(r.parsed):>7}{str(r.valid):>7}"
                  f"{r.input_tokens:>7}{r.output_tokens:>6}{r.latency_ms:>8.1f}  {r.reason}")

    print("-" * 88)
    print(f"{'variant':<20}{'valid':>8}{'avg in':>9}{'avg out':>9}{'avg ms':>9}")
    print("-" * 88)
    for variant, rows in by_variant.items():
        print(f"{variant:<20}{sum(r.valid for r in rows)}/{len(rows):<6}"
              f"{statistics.mean(r.input_tokens for r in rows):>9.0f}"
              f"{statistics.mean(r.output_tokens for r in rows):>9.0f}"
              f"{statistics.mean(r.latency_ms for r in rows):>9.1f}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Chapter 2 Prompt Lab")
    parser.add_argument("--live", action="store_true", help="make real API requests")
    parser.add_argument("--json", action="store_true", help="emit records as JSON lines")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)

    if args.live and not api_key_present():
        print(f"[fatal] {API_KEY_VAR} is not set. No request sent.")
        return 1

    lab = Lab(model=args.model, live=args.live)
    print(f"Prompt Lab - model={lab.model} mode={'live' if lab.live else 'offline'} "
          f"prompt={lab.prompt.ref}\n")
    results = lab.run()

    if args.json:
        for r in results:
            print(json.dumps(asdict(r)))
        return 0

    report(results)
    rejected = [r for r in results if not r.valid]
    print(f"\n{len(rejected)} of {len(results)} replies were rejected, at two different gates:")
    for r in rejected:
        gate = "schema" if r.parsed else "shape"
        print(f"  {r.variant:<20} {gate:<7} {r.reason}")
    print("\nEvery row above is reproducible: the prompt reference carries a content hash,")
    print("so a future run can prove it used the same prompt bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
