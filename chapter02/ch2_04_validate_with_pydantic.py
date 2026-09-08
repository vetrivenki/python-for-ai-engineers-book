"""Lesson 2.4 / Task 12 - Validate responses with Pydantic.

json.loads() answers "is this JSON?". It does not answer "is this the object my
application requires?". A payload can parse perfectly and still carry a severity
of "critical", an error rate of "4%" as a string, or a restart count of -1.

Run:  python ch2_04_validate_with_pydantic.py
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from ch2_03_structured_output import parse


class IncidentFacts(BaseModel):
    """The contract the application actually depends on."""

    model_config = {"extra": "forbid"}      # unexpected keys are an error, not a shrug

    severity: Literal["SEV1", "SEV2", "SEV3"]
    component: str = Field(min_length=1, max_length=64)
    start_utc: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_utc: str = Field(pattern=r"^\d{2}:\d{2}$")
    error_rate_pct: float = Field(ge=0, le=100)
    restarts: int = Field(ge=0)
    deployment_in_window: bool

    @field_validator("end_utc")
    @classmethod
    def _ends_after_start(cls, v: str, info) -> str:
        start = info.data.get("start_utc")
        if start and v <= start:
            raise ValueError(f"end_utc {v} is not after start_utc {start}")
        return v


# Every payload below is syntactically valid JSON. Only the first is usable.
PAYLOADS = {
    "valid": '{"severity":"SEV2","component":"checkout-api","start_utc":"09:12",'
             '"end_utc":"09:41","error_rate_pct":4,"restarts":3,"deployment_in_window":false}',
    "severity not in enum": '{"severity":"critical","component":"checkout-api",'
             '"start_utc":"09:12","end_utc":"09:41","error_rate_pct":4,"restarts":3,'
             '"deployment_in_window":false}',
    "rate as string with %": '{"severity":"SEV2","component":"checkout-api",'
             '"start_utc":"09:12","end_utc":"09:41","error_rate_pct":"4%","restarts":3,'
             '"deployment_in_window":false}',
    "negative restarts": '{"severity":"SEV2","component":"checkout-api","start_utc":"09:12",'
             '"end_utc":"09:41","error_rate_pct":4,"restarts":-1,"deployment_in_window":false}',
    "window runs backwards": '{"severity":"SEV2","component":"checkout-api",'
             '"start_utc":"09:41","end_utc":"09:12","error_rate_pct":4,"restarts":3,'
             '"deployment_in_window":false}',
    "extra invented key": '{"severity":"SEV2","component":"checkout-api","start_utc":"09:12",'
             '"end_utc":"09:41","error_rate_pct":4,"restarts":3,"deployment_in_window":false,'
             '"root_cause":"memory leak"}',
    "boolean as yes": '{"severity":"SEV2","component":"checkout-api","start_utc":"09:12",'
             '"end_utc":"09:41","error_rate_pct":4,"restarts":3,"deployment_in_window":"yes"}',
}


def validate(raw: str) -> tuple[bool, str]:
    """json.loads first, then the schema. Report which gate rejected it."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return False, f"json: {exc.msg}"
    try:
        IncidentFacts.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "(root)"
        return False, f"schema: {loc} - {first['msg']}"
    return True, "valid"


if __name__ == "__main__":
    print("Every payload below is well-formed JSON.\n")
    print(f"{'payload':<24}{'json.loads':>12}{'schema':>9}  reason")
    print("-" * 78)
    passed = 0
    for label, raw in PAYLOADS.items():
        loads_ok = True
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            loads_ok = False
        ok, reason = validate(raw)
        passed += ok
        print(f"{label:<24}{str(loads_ok):>12}{str(ok):>9}  {reason[:38]}")

    print("-" * 78)
    print(f"json.loads accepted {len(PAYLOADS)}/{len(PAYLOADS)}; the schema accepted "
          f"{passed}/{len(PAYLOADS)}.")

    # "yes" passed above. Pydantic coerces by default, which is usually what you
    # want from an API boundary and is emphatically not what you want when you
    # are measuring whether a model returned the type it was asked for.
    print("\ncoercion is on by default - strict mode measures what was actually returned")
    for label in ("boolean as yes", "rate as string with %"):
        data = json.loads(PAYLOADS[label])
        lax = strict = "ok"
        try:
            IncidentFacts.model_validate(data)
        except ValidationError:
            lax = "rejected"
        try:
            IncidentFacts.model_validate(data, strict=True)
        except ValidationError:
            strict = "rejected"
        print(f"  {label:<24} default={lax:<9} strict={strict}")

    print("\nvalidated object (typed, not a dict of strings)")
    facts = IncidentFacts.model_validate_json(PAYLOADS["valid"])
    print(f"  {facts.component} {facts.severity} {facts.start_utc}-{facts.end_utc} "
          f"rate={facts.error_rate_pct} restarts={facts.restarts} "
          f"deploy={facts.deployment_in_window}")
    print(f"  error_rate_pct is a {type(facts.error_rate_pct).__name__}, "
          f"deployment_in_window is a {type(facts.deployment_in_window).__name__}")

    print("\nend to end: extract -> parse -> validate")
    from ch2_03_structured_output import FAKE_REPLIES
    for i, reply in enumerate(FAKE_REPLIES, 1):
        result = parse(reply)
        ok, reason = validate(json.dumps(result.data)) if result.ok else (False, result.detail)
        print(f"  reply #{i}: parsed={result.ok!s:<5} valid={ok!s:<5} {reason[:44]}")
