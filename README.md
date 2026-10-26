# 🔎 VeriGap

> Measuring the **verification gap**: can a coding agent write a test suite strong enough to tell a *correct* program from a *subtly broken* one — working only from the specification?

VeriGap is an evaluation harness for **spec-driven test generation and code generation**, built to compare **open models served over HuggingFace** (the Gemma 4 QAT family, via any OpenAI-compatible endpoint) on equal footing with proprietary agents (Claude, GPT). Each task pairs the specification of a real CLI tool with its ground-truth executable and a set of mutants; a generated test suite is scored on how well it closes the gap between the spec and the implementation.

## 🎯 What a suite is scored on

- **Mutation score** — the fraction of mutants (subtly broken variants) the test suite kills.
- **Validity rate** — the fraction of generated test functions that pass against the reference implementation.

## ✨ What VeriGap adds

- **Open models as first-class citizens.** The `hf` backend runs any OpenAI-compatible endpoint — the HF Inference router, an HF dedicated endpoint, or a self-hosted vLLM/SGLang server — so open-weight models can be benchmarked with the exact same tasks, prompts, isolation, and scoring as the closed ones.
- **The Gemma 4 QAT family out of the box:** run IDs `gemma-4-31b`, `gemma-4-12b`, `gemma-4-e4b`, `gemma-4-e2b`.
- **Docker *or* rootless Podman** — set `PROGRAMBENCH_DOCKER_EXECUTABLE` to the compatible CLI.

## ⚙️ Setup

> [!IMPORTANT]
> 🐳 All task images are built for `linux/amd64`. Run construction and evaluation on a Linux x86_64 machine with Docker (or rootless Podman).

```bash
uv sync

# If using Podman instead of Docker:
export PROGRAMBENCH_DOCKER_EXECUTABLE=podman
```

Specifications live in `ground_truth/spec/<instance_id>/spec.md`. Reference tests, mutants, and ground-truth executables are pulled on demand from HuggingFace ([Reference Tests](https://huggingface.co/datasets/eth-sri/tsb-reference_tests), [Mutants](https://huggingface.co/datasets/eth-sri/tsb-mutants), [Ground Truth](https://huggingface.co/datasets/eth-sri/tsb-reference_impl)).

### 🔑 Credentials

Export credentials only for the agents you intend to run.

```bash
export CLAUDE_CODE_OAUTH_TOKEN=...  # Claude Code (or ANTHROPIC_API_KEY)
export OPENAI_API_KEY=...           # Codex / GPT (or `codex login`)
export GEMINI_API_KEY=...           # Gemini CLI
export OPENROUTER_API_KEY=...       # OpenRouter-based open models (Qwen, DeepSeek, GLM)
export HF_TOKEN=...                 # Gemma 4 over HuggingFace / an OpenAI-compatible endpoint
```

| Agent | Credential |
| --- | --- |
| Codex | `~/.codex/auth.json` or `OPENAI_API_KEY`. |
| Claude Code | `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`), `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`, or the `claude` login. |
| Gemini CLI | `GEMINI_API_KEY` or the `gemini` login. |
| OpenRouter-based models | `OPENROUTER_API_KEY`. |
| Gemma 4 (HF / `hf` backend) | `HF_TOKEN` for the HF router or a dedicated endpoint. For a self-hosted vLLM/SGLang server, set `PROGRAMBENCH_HF_BASE_URL` (and `PROGRAMBENCH_HF_API_KEY` if it needs a key). See [scripts/agents/README.md](scripts/agents/README.md#adding-a-model). |

## 📊 Evaluation

`scripts/eval/run_agents.sh` runs one or more model configurations (`--runs`) over a set of tasks, each in an isolated container with network access limited to its provider's API. Run IDs and their harnesses are listed in [scripts/agents/README.md](scripts/agents/README.md).

### 🧬 Test generation

```bash
bash scripts/eval/run_agents.sh --runs "claude-opus-5 codex-gpt-6-sol" \
    --tasks-file ground_truth/valid_task.txt --jobs 2 -- --part test_gen
# Results: output/eval/testgen/<model>_<reasoning>/<instance_id>/
```

### 💻 Code generation

```bash
bash scripts/eval/run_agents.sh --runs "claude-opus-5 codex-gpt-6-sol" \
    --tasks-file ground_truth/valid_task.txt --jobs 2 -- --part exec_gen
# Results: output/eval/codegen/<model>_<reasoning>/<instance_id>/
```

### 🤗 Comparing open Gemma models (HF)

These QAT checkpoints are `compressed-tensors` weights served via vLLM/SGLang (not the public HF router), so serve them on a GPU and point VeriGap at the endpoint:

```bash
# Serve (GPU; 31B-w4a16 ≈ 17 GB VRAM):
uv run vllm serve google/gemma-4-31b-it-qat-w4a16-ct \
  --enable-auto-tool-choice --tool-call-parser hermes --port 8000

export PROGRAMBENCH_HF_BASE_URL=http://<host>:8000/v1
export PROGRAMBENCH_HF_API_KEY=EMPTY   # or HF_TOKEN for the router / a dedicated endpoint

# Open-only, all-Gemma sweep — no Anthropic/OpenAI keys needed:
bash scripts/eval/run_agents.sh \
  --runs "gemma-4-31b gemma-4-12b gemma-4-e4b gemma-4-e2b" \
  --tasks-file ground_truth/valid_task.txt --jobs 2 -- --part all
```

> [!NOTE]
> Agent containers run on an `--internal` egress network reaching only allowlisted hosts through a proxy. For a self-hosted endpoint on a non-allowlisted host, add it to [scripts/docker/egress-squid.conf](scripts/docker/egress-squid.conf), or use `PROGRAMBENCH_EGRESS_NETWORK="" PROGRAMBENCH_ALLOW_OPEN_NETWORK=1`.

Score the generated suites:

```bash
uv run programbench eval-tests \
    output/eval/testgen/<model>_<reasoning> \
    --workers 4 --mutant-workers 8
```

## 🗂️ Repository layout

The pipeline internals are documented in [docs/explore.md](docs/explore.md).

## 📄 License

[MIT LICENSE](LICENSE)
