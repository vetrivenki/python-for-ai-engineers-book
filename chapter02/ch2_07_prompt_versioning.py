"""Lesson 2.7 / Task 15 - Prompt versioning.

A prompt edited in place destroys the record of what produced yesterday's
output. Treat prompts as immutable versioned artifacts: an id, a semantic
version, a content hash, and a registry that refuses to redefine a version whose
text has changed.

Run:  python ch2_07_prompt_versioning.py     (registry only, no API call)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


class VersionConflict(ValueError):
    """A published version was re-registered with different text."""


@dataclass(frozen=True)
class Prompt:
    id: str
    version: str
    text: str
    note: str = ""

    @property
    def digest(self) -> str:
        """Content hash. Two prompts are the same only if their bytes are."""
        return hashlib.sha256(self.text.encode()).hexdigest()[:12]

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}+{self.digest}"


class Registry:
    def __init__(self) -> None:
        self._by_ref: dict[tuple[str, str], Prompt] = {}

    def register(self, prompt: Prompt) -> Prompt:
        key = (prompt.id, prompt.version)
        existing = self._by_ref.get(key)
        if existing and existing.digest != prompt.digest:
            raise VersionConflict(
                f"{prompt.id}@{prompt.version} already published as {existing.digest}; "
                f"new text hashes to {prompt.digest}. Publish a new version instead.")
        self._by_ref[key] = prompt
        return prompt

    def get(self, id: str, version: str) -> Prompt:
        return self._by_ref[(id, version)]

    def versions(self, id: str) -> list[str]:
        return sorted(v for (i, v) in self._by_ref if i == id)


@dataclass
class RunRecord:
    """What a result must carry to stay reproducible."""
    prompt_ref: str
    model: str
    input_digest: str
    output_digest: str

    @classmethod
    def of(cls, prompt: Prompt, model: str, user_input: str, output: str) -> "RunRecord":
        h = lambda s: hashlib.sha256(s.encode()).hexdigest()[:12]
        return cls(prompt.ref, model, h(user_input), h(output))


V1 = Prompt("incident_triage", "1.0.0",
            "Summarise the incident using the headings Known facts and Missing evidence.")
V2 = Prompt("incident_triage", "1.1.0",
            "Summarise the incident using the headings Known facts and Missing evidence.\n"
            "State uncertainty explicitly. Do not name a root cause.",
            note="added the no-root-cause rule after a false attribution in review")


if __name__ == "__main__":
    reg = Registry()
    reg.register(V1)
    reg.register(V2)

    print("registry")
    for v in reg.versions("incident_triage"):
        p = reg.get("incident_triage", v)
        print(f"  {p.ref}  {p.note or '-'}")

    print("\nre-registering the same version with the same text is a no-op")
    reg.register(Prompt("incident_triage", "1.0.0", V1.text))
    print("  ok")

    print("\nediting a published version in place is refused")
    try:
        reg.register(Prompt("incident_triage", "1.0.0", V1.text + " Be brief."))
    except VersionConflict as exc:
        print(f"  VersionConflict: {exc}")

    print("\nrun records tie an output to the exact prompt bytes that produced it")
    record = RunRecord.of(V2, "claude-opus-5", "checkout-api 503s",
                          "Known facts...\nMissing evidence...")
    print("  " + json.dumps(asdict(record)))

    print("\nsix months later you can answer: which prompt produced this?")
    ref_id, rest = record.prompt_ref.split("@")
    version, digest = rest.split("+")
    found = reg.get(ref_id, version)
    print(f"  looked up {ref_id}@{version} -> digest {found.digest} "
          f"({'matches' if found.digest == digest else 'DOES NOT MATCH'})")
    print(f"  text: {found.text.splitlines()[0]!r}...")
    print("\nWithout the digest, a version number only tells you what the prompt was called.")
