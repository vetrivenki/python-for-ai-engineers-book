# Python for AI Engineers — Companion Code

Runnable source for the book **Python for AI Engineers: From LLMs to Production Agentic AI** by Venkatesan Vetrimurasu.

Every listing in the book appears here in full. **Every file runs offline**, so you can work through a whole chapter — including its test suite — without an API key and without spending anything.

## Chapter 1 — Working with LLMs & Claude API

| Task | File | What it teaches |
|---|---|---|
| 1 | [`chapter01/setup_check.py`](chapter01/setup_check.py) | Local setup and credential presence, with no API call |
| 2 | [`chapter01/first_message.py`](chapter01/first_message.py) | Parsing a response as typed content blocks, not a string |
| 3 | [`chapter01/compare_system_prompts.py`](chapter01/compare_system_prompts.py) | A controlled A/B of system instructions, scored for structure *and* unsupported claims |
| 4 | [`chapter01/compare_output_settings.py`](chapter01/compare_output_settings.py) | Output budgets vs. actual usage, and detecting truncation two ways |
| 5 | [`chapter01/stream_response.py`](chapter01/stream_response.py) | Streaming with an honest partial-output state |
| 6 | [`chapter01/chat_loop.py`](chapter01/chat_loop.py) | Conversation history with candidate-and-commit semantics |
| 7 | [`chapter01/resilient_client.py`](chapter01/resilient_client.py) | Error classification and a single-owner retry policy |
| 8 | [`chapter01/measured_client.py`](chapter01/measured_client.py) | Telemetry where missing usage stays `null`, never `0` |
| Project | [`chapter01/claude_cli.py`](chapter01/claude_cli.py) | All eight combined into one inspectable CLI |
| Tests | [`chapter01/test_client.py`](chapter01/test_client.py) | Ten deterministic tests, none touching the network |

## Quick start

```bash
cd chapter01
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python setup_check.py
```

Run any lesson offline:

```bash
python first_message.py --fake
python compare_system_prompts.py --fake
python stream_response.py --fake --interrupt
python chat_loop.py --fake
python resilient_client.py
python measured_client.py
python claude_cli.py --fake
```

Run the project test suite:

```bash
python test_client.py
```

```
10/10 passed
```

## Going live

```bash
cp .env.example .env        # then add your key; .env is git-ignored
export ANTHROPIC_API_KEY="..."
export CLAUDE_MODEL="claude-opus-5"   # verify this ID is enabled for your account
python claude_cli.py --stream
```

Live runs make real requests and may incur charges. `setup_check.py` exits non-zero when configuration is missing, so it can gate a later step in a script or CI job.

## Design notes

A few choices in this code are deliberate teaching points rather than style preferences:

- **`config.py` owns the model ID.** One environment variable re-points every lesson, so no listing hard-codes a model identifier that will age badly.
- **`ChatSession` sends a candidate and commits only on success.** A failed request cannot duplicate a user turn or leave an assistant turn half-written.
- **`call_with_retry` takes `sleep`, `clock` and `rng` as parameters.** That is what makes the retry tests instant and reproducible.
- **The SDK client is built with `max_retries=0`.** Two retry layers multiply — three inside three is nine requests — so the policy has exactly one owner.
- **`Record` is a closed dataclass.** Prompts, answers and credentials have nowhere to go, so they cannot leak into telemetry by accident.

## Requirements

Python 3.10 or later, and the `anthropic` SDK for live runs only.

## License

Code in this repository is released under the MIT License. The book's prose and figures are not covered by it.
