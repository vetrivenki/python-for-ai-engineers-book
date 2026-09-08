# Python for AI Engineers — Companion Code

Runnable source for the book **Python for AI Engineers: From LLMs to Production Agentic AI** by Venkatesan Vetrimurasu.

The book explains and measures this code; the code itself lives here rather than being reprinted, so it can be cloned, run and updated without a new edition. **Every file runs offline**, so you can work through a whole chapter — including its test suite — without an API key and without spending anything.

## File naming

Files are numbered in reading order and prefixed with their chapter:

```
ch2_04_validate_with_pydantic.py
└┬┘ └┬┘ └───────────┬──────────┘
 │   │              └─ what it does
 │   └─ serial number within the chapter
 └─ chapter
```

Underscores rather than hyphens, because these files import each other and a hyphen is not valid in a Python module name.

## Chapter 1 — Working with LLMs & Claude API

Tasks 1–8. Build a client whose output, state and failures can be inspected.

| # | File | What it teaches |
|---|---|---|
| 00 | [`ch1_00_config.py`](chapter01/ch1_00_config.py) | Shared model ID and credential lookup |
| 01 | [`ch1_01_setup_check.py`](chapter01/ch1_01_setup_check.py) | Local setup and credential presence, with no API call |
| 02 | [`ch1_02_first_message.py`](chapter01/ch1_02_first_message.py) | Parsing a response as typed content blocks, not a string |
| 03 | [`ch1_03_compare_system_prompts.py`](chapter01/ch1_03_compare_system_prompts.py) | A controlled A/B of system instructions, scored for structure *and* unsupported claims |
| 04 | [`ch1_04_compare_output_settings.py`](chapter01/ch1_04_compare_output_settings.py) | Output budgets vs. actual usage, and detecting truncation two ways |
| 05 | [`ch1_05_stream_response.py`](chapter01/ch1_05_stream_response.py) | Streaming with an honest partial-output state |
| 06 | [`ch1_06_chat_loop.py`](chapter01/ch1_06_chat_loop.py) | Conversation history with candidate-and-commit semantics |
| 07 | [`ch1_07_resilient_client.py`](chapter01/ch1_07_resilient_client.py) | Error classification and a single-owner retry policy |
| 08 | [`ch1_08_measured_client.py`](chapter01/ch1_08_measured_client.py) | Telemetry where missing usage stays `null`, never `0` |
| 09 | [`ch1_09_claude_cli.py`](chapter01/ch1_09_claude_cli.py) | Project — all eight combined into one inspectable CLI |
| 10 | [`ch1_10_test_client.py`](chapter01/ch1_10_test_client.py) | Ten deterministic tests, none touching the network |

## Chapter 2 — Prompt & Context Engineering

Tasks 9–16. Make what you send reproducible, and make the cost of every change visible.

| # | File | What it teaches |
|---|---|---|
| 00 | [`ch2_00_config.py`](chapter02/ch2_00_config.py) | Shared config and the one fixed incident note every comparison uses |
| 01 | [`ch2_01_zero_vs_few_shot.py`](chapter02/ch2_01_zero_vs_few_shot.py) | Few-shot fixes format, not truth — and its examples can leak into answers |
| 02 | [`ch2_02_prompt_templates.py`](chapter02/ch2_02_prompt_templates.py) | Templates that refuse to render half-filled, and survive braces in data |
| 03 | [`ch2_03_structured_output.py`](chapter02/ch2_03_structured_output.py) | Fences, prose and trailing commas: four plausible replies, two survive |
| 04 | [`ch2_04_validate_with_pydantic.py`](chapter02/ch2_04_validate_with_pydantic.py) | `json.loads` accepts 7/7; the schema accepts 2/7 |
| 05 | [`ch2_05_document_context.py`](chapter02/ch2_05_document_context.py) | Chunk-and-select vs truncation at the same budget |
| 06 | [`ch2_06_relevance_test.py`](chapter02/ch2_06_relevance_test.py) | The control run: irrelevant context costs tokens and invents causes |
| 07 | [`ch2_07_prompt_versioning.py`](chapter02/ch2_07_prompt_versioning.py) | Content digests, and a registry that refuses redefinition |
| 08 | [`ch2_08_compare_versions.py`](chapter02/ch2_08_compare_versions.py) | Quality, tokens and latency in one table |
| 09 | [`ch2_09_prompt_lab.py`](chapter02/ch2_09_prompt_lab.py) | Project — one harness, three context conditions, two rejection gates |
| 10 | [`ch2_10_test_prompt_lab.py`](chapter02/ch2_10_test_prompt_lab.py) | Twelve deterministic tests, none touching the network |

## Quick start

Each chapter folder is self-contained.

```bash
cd chapter01                                          # or chapter02
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Chapter 1 depends on the `anthropic` SDK. Chapter 2 adds **Pydantic 2** for schema validation — a local library, no extra service or credential.

Run any lesson offline:

```bash
# chapter01
python ch1_01_setup_check.py
python ch1_02_first_message.py --fake
python ch1_05_stream_response.py --fake --interrupt
python ch1_09_claude_cli.py --fake

# chapter02
python ch2_01_zero_vs_few_shot.py --fake
python ch2_04_validate_with_pydantic.py
python ch2_06_relevance_test.py
python ch2_09_prompt_lab.py
```

Six of Chapter 2's eight lessons make no API call at all, in any mode.

## Tests

```bash
cd chapter01 && python -m pytest      # 10 passed
cd chapter02 && python -m pytest      # 12 passed
```

Each folder ships a `pytest.ini` widening discovery to the `ch<n>_` naming — without it a numbered filename does not match `test_*.py`, and a suite that silently collects zero tests reports success.

## Going live

```bash
cp .env.example .env        # then add your key; .env is git-ignored
export ANTHROPIC_API_KEY="..."
export CLAUDE_MODEL="claude-opus-5"   # verify this ID is enabled for your account

python ch1_09_claude_cli.py --stream
python ch2_09_prompt_lab.py --live
```

Live runs make real requests and may incur charges. Both entry points refuse to start without a credential.

## Design notes

Choices here are teaching points rather than style preferences:

- **`chN_00_config.py` owns the model ID.** One environment variable re-points a whole chapter, so no listing hard-codes an identifier that will age badly.
- **`ChatSession` sends a candidate and commits only on success.** A failed request cannot duplicate a user turn or leave an assistant turn half-written.
- **The SDK client is built with `max_retries=0`.** Two retry layers multiply — three inside three is nine requests — so the policy has exactly one owner.
- **`Record` is a closed dataclass.** Prompts, answers and credentials have nowhere to go, so they cannot leak into telemetry by accident.
- **Templates render into declared slots.** Data containing `{}` survives intact and cannot introduce a placeholder; `str.format` over interpolated data cannot say the same.
- **Prompts are identified by content hash, not version string.** A version number records what someone meant to publish; the digest records what was.
- **Rubrics live in the code.** A reviewer who disagrees with a score can change the rubric and re-run, rather than argue about what "better" meant.

## Requirements

Python 3.10 or later. `anthropic` for live runs; `pydantic` for Chapter 2.

## License

Code in this repository is released under the MIT License. The book's prose and figures are not covered by it.
