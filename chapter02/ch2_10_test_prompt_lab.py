"""Chapter 2 Project - Test Cases.

Twelve deterministic tests. None touch the network: they assert on rendered
prompt text, parser behaviour, schema decisions and registry rules, rather than
on anything a model generated.

Run:  python ch2_10_test_prompt_lab.py            (no dependencies beyond pydantic)
      python -m pytest ch2_10_test_prompt_lab.py
"""

from __future__ import annotations

import json
import sys

from ch2_00_config import INCIDENT, approx_tokens
from ch2_01_zero_vs_few_shot import build_messages, score
from ch2_02_prompt_templates import SUMMARY, TRIAGE, MissingVariable, PromptTemplate
from ch2_03_structured_output import FAKE_REPLIES, extract, parse
from ch2_04_validate_with_pydantic import IncidentFacts, validate
from ch2_05_document_context import (CONTEXT_BUDGET, QUESTION, RUNBOOK, chunk_document,
                                     select, truncate)
from ch2_07_prompt_versioning import Prompt, Registry, RunRecord, V1, VersionConflict
from ch2_09_prompt_lab import Lab


def test_few_shot_examples_become_completed_turns() -> None:
    zero = build_messages(few_shot=False)
    few = build_messages(few_shot=True)
    assert len(zero) == 1 and zero[0]["role"] == "user"
    assert len(few) == 5, "two example pairs plus the real question"
    assert [m["role"] for m in few] == ["user", "assistant", "user", "assistant", "user"]
    assert few[-1]["content"].endswith(INCIDENT), "the real input must come last"


def test_scorer_separates_shape_from_support() -> None:
    shaped_but_speculative = ("SEVERITY: SEV2\nCOMPONENT: checkout-api\n"
                              "EVIDENCE: The outage was caused by memory pressure.")
    s = score(shaped_but_speculative)
    assert s["exact_shape"] is True, "shape is correct"
    assert s["unsupported"] is True, "and it is still an unsupported claim"


def test_template_refuses_to_render_with_a_missing_variable() -> None:
    try:
        TRIAGE.render(audience="ops")
    except MissingVariable as exc:
        assert "incident" in str(exc)
    else:
        raise AssertionError("a half-filled prompt must never render")


def test_template_refuses_an_undeclared_variable() -> None:
    try:
        SUMMARY.render(audience="ops", sentences="2", incident="x", tone="curt")
    except MissingVariable:
        pass
    else:
        raise AssertionError("a silently ignored variable is a silently wrong prompt")


def test_braces_in_data_are_not_treated_as_placeholders() -> None:
    tricky = '{"level":"error"} and {not_a_placeholder}'
    out = SUMMARY.render(audience="ops", sentences="2", incident=tricky)
    assert "{not_a_placeholder}" in out, "data must survive rendering unchanged"


def test_fenced_json_is_extracted_before_parsing() -> None:
    candidate, how = extract(FAKE_REPLIES[1])
    assert how == "fence"
    assert json.loads(candidate)["component"] == "checkout-api"


def test_prose_only_reply_fails_rather_than_guessing() -> None:
    result = parse(FAKE_REPLIES[3])
    assert result.ok is False and result.data is None


def test_schema_rejects_what_json_accepts() -> None:
    payload = ('{"severity":"critical","component":"checkout-api","start_utc":"09:12",'
               '"end_utc":"09:41","error_rate_pct":4,"restarts":3,'
               '"deployment_in_window":false}')
    json.loads(payload)                       # parses fine
    ok, reason = validate(payload)
    assert ok is False and "severity" in reason


def test_strict_mode_catches_coerced_types() -> None:
    data = json.loads('{"severity":"SEV2","component":"checkout-api","start_utc":"09:12",'
                      '"end_utc":"09:41","error_rate_pct":4,"restarts":3,'
                      '"deployment_in_window":"yes"}')
    IncidentFacts.model_validate(data)        # default coercion accepts "yes"
    try:
        IncidentFacts.model_validate(data, strict=True)
    except Exception:
        pass
    else:
        raise AssertionError("strict mode must reject a string where a bool was required")


def test_selection_keeps_the_answer_within_budget() -> None:
    chunks = chunk_document(RUNBOOK)
    kept, spent = select(chunks, QUESTION, CONTEXT_BUDGET)
    assert spent <= CONTEXT_BUDGET, f"{spent} tokens exceeds the {CONTEXT_BUDGET} budget"
    text = "\n".join(c.text for c in kept)
    assert "Do not scale up first" in text, "the warning must survive selection"
    assert "Do not scale up first" not in truncate(RUNBOOK, CONTEXT_BUDGET), \
        "and truncation at the same budget must lose it"


def test_registry_refuses_to_redefine_a_published_version() -> None:
    reg = Registry()
    reg.register(V1)
    reg.register(Prompt(V1.id, V1.version, V1.text))     # identical text is fine
    try:
        reg.register(Prompt(V1.id, V1.version, V1.text + " Be brief."))
    except VersionConflict:
        pass
    else:
        raise AssertionError("editing a published version in place must be refused")


def test_every_lab_result_carries_a_reproducible_prompt_reference() -> None:
    lab = Lab(live=False)
    results = lab.run()
    assert len(results) == 6
    refs = {r.prompt_ref for r in results}
    assert len(refs) == 1, "one prompt version produced the whole table"
    ref = refs.pop()
    assert "+" in ref and len(ref.split("+")[1]) == 12, "reference must carry a content hash"
    assert sum(r.valid for r in results) == 4, "two replies are rejected, at two gates"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failures = 0
    for test in TESTS:
        name = test.__name__.replace("test_", "").replace("_", " ")
        try:
            test()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {name}: {exc}")
        except Exception as exc:
            failures += 1
            print(f"ERROR {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"pass  {name}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    sys.exit(1 if failures else 0)
