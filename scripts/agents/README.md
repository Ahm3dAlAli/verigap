# Agent harnesses

This directory owns implementation and test-suite generation by coding-agent
CLIs. Model selection is separate from the harness: several models can share
one CLI and parser.

## Current mapping

| Run ID in `scripts/eval/run_agents.sh` | Model sent to provider | Agentic harness | Transport |
| --- | --- | --- | --- |
| `claude-opus-5` | `opus` | Claude Code | Anthropic |
| `claude-opus-5.5` | `claude-opus-5-5` | Claude Code | Anthropic |
| `claude-sonnet-5.5` | `claude-sonnet-5-5` | Claude Code | Anthropic |
| `claude-fable` | `fable` | Claude Code | Anthropic |
| `codex-gpt-5.6-sol` | `gpt-5.6-sol` | Codex CLI | OpenAI/ChatGPT |
| `codex-gpt-5.6-luna` | `gpt-5.6-luna` | Codex CLI | OpenAI/ChatGPT |
| `codex-gpt-6-sol` | `gpt-6-sol` | Codex CLI | OpenAI/ChatGPT |
| `codex-gpt-6-luna` | `gpt-6-luna` | Codex CLI | OpenAI/ChatGPT |
| `codex-gpt-6.1-sol` | `gpt-6.1-sol` | Codex CLI | OpenAI/ChatGPT |
| `codex-gpt-6-astra` | `gpt-6-astra` | Codex CLI | OpenAI/ChatGPT |
| `gemini-3.8-flash` | `gemini-3.8-flash` | Gemini CLI | Google |
| `qwen-3.8-flash` | `qwen/qwen3.8-flash` | Qwen Code | OpenRouter |
| `deepseek-v4-flash-0423` | `deepseek/deepseek-v4-flash` | DeepSeek Harness | OpenRouter |
| `deepseek-v4-flash-0731` | `deepseek/deepseek-v4-flash-0731` | DeepSeek Harness | OpenRouter |
| `glm-5.3-flash` | `openrouter/z-ai/glm-5.3-flash` | ZCode | OpenRouter |
| `muse-spark-1.3-contributor` | `meta/muse-spark-1.3-contributor` | Muse Code + local adapter | OpenRouter |
| `gemma-4-31b` | `google/gemma-4-31b-it-qat-w4a16-ct` | Qwen Code (`hf` backend) | HF / OpenAI-compatible |
| `gemma-4-12b` | `google/gemma-4-12b-it-qat-w4a16-ct` | Qwen Code (`hf` backend) | HF / OpenAI-compatible |
| `gemma-4-e4b` | `google/gemma-4-e4b-it-qat-w4a16-ct` | Qwen Code (`hf` backend) | HF / OpenAI-compatible |
| `gemma-4-e2b` | `google/gemma-4-e2b-it-qat-w4a16-ct` | Qwen Code (`hf` backend) | HF / OpenAI-compatible |

Claude has dedicated `solve_claude.py` and `generate_tests_claude.py` drivers.
Codex solving uses `solve_codex.py`; Codex test generation and the Gemini,
Muse, Qwen, HF (Gemma), DeepSeek, and GLM use the registry in `solve_agent.py`
plus `generate_tests_agent.py`. DeepSeek uses `dsh --profile headless`;
GLM uses ZCode's headless `--prompt --json` mode.
The `solve_*.sh` and `generate_tests_*.sh` files are thin stable entrypoints.

For Muse, export `OPENROUTER_API_KEY`. The Muse Code binary remains the agent
harness; a pinned local adapter translates Muse's catalog and streaming protocol
to OpenRouter and sends API traffic through the restricted egress proxy. The
runner does not mount or use a Meta credential.
OpenRouter may require account attestations for the Contributor model; complete
them in OpenRouter account preferences before a run.

For DeepSeek, export `OPENROUTER_API_KEY`. The official DeepSeek Harness uses
its OpenAI-compatible provider adapter to run `deepseek/deepseek-v4-flash-0731`
through OpenRouter. The runner writes an isolated DSH profile patch per run,
including the requested reasoning effort and disabled web tools. The harness
session log supplies trajectory events and token usage. Reasoning output and an
elapsed-time update are shown while the query runs. The two named run IDs write
logs to `<output-root>/logs/deepseek-v4-flash-0423` and
`<output-root>/logs/deepseek-v4-flash-0731`, respectively.

For GLM, export `OPENROUTER_API_KEY`. When no ZCode CLI config is present,
the runner creates a private, temporary OpenRouter provider config for
`openrouter/z-ai/glm-5.3-flash` and mounts it into the container. ZCode remains
the agent harness. An existing `~/.zcode/cli/config.json` (or the file named by
`PROGRAMBENCH_ZCODE_CONFIG`) takes priority and is copied with the requested
model selected; its original contents are unchanged. ZCode's released headless
CLI has no reasoning-effort option, so GLM runs use the model's default `max`
effort. The runner shows model requests and tool activity from ZCode's live log;
its final JSON and trajectory format remain unchanged. On a failed turn,
the runner copies ZCode's structured diagnostic log beside the trajectory.
The pinned ZCode desktop package supplies the official CLI bundle.

For HF / Gemma (the `hf` backend), the Google Gemma 4 QAT checkpoints
(`google/gemma-4-*-it-qat-w4a16-ct`) are served over an OpenAI-compatible
endpoint and driven by the same Qwen Code CLI and cleanroom image as `qwen`;
only the base URL, API host, and key differ. The route is env-driven, so the
same run ID works against any of three serving options:

- **HF Inference Providers router (default):** export `HF_TOKEN`. Base URL
  defaults to `https://router.huggingface.co/v1`. Note: these QAT checkpoints
  are not always deployed on the public router; they are `compressed-tensors`
  weights intended for vLLM/SGLang, so self-hosting is the common path.
- **HF dedicated Inference Endpoint:** export `HF_TOKEN` and
  `PROGRAMBENCH_HF_BASE_URL=https://<id>.endpoints.huggingface.cloud/v1`.
- **Self-hosted vLLM/SGLang (or a Kaggle-provided endpoint):** download the
  weights from HF, serve with `--served-model-name google/gemma-4-31b-it-qat-w4a16-ct`,
  and set `PROGRAMBENCH_HF_BASE_URL=http://<host>:<port>/v1`. If the server
  requires a key, set `PROGRAMBENCH_HF_API_KEY`; vLLM accepts any value by
  default. Add the serving host to `scripts/docker/egress-squid.conf` (the HF
  routers `.huggingface.co` and `.endpoints.huggingface.cloud` are already
  allowlisted), or run with the documented open-network escape hatch
  (`PROGRAMBENCH_EGRESS_NETWORK="" PROGRAMBENCH_ALLOW_OPEN_NETWORK=1`) when the
  endpoint is on a non-allowlisted host.

Gemma QAT served this way exposes no OpenAI `reasoning.effort` control, so the
`--hf-reasoning` value is recorded in the label and trajectory but no effort
field is sent to the server. The Qwen Code harness drives tool-calling over the
OpenAI protocol; a self-hosted vLLM server needs a Gemma-compatible
`--tool-call-parser` (and `--enable-auto-tool-choice`) for the agent to issue
file edits.

The existing OpenRouter pricing file describes historical Qwen-harness runs.
Use the OpenRouter model price for new DeepSeek runs and the configured
provider price for ZCode cost summaries.

## Adding a model

When an existing harness can serve the model, do not create a new agent
implementation. Add a unique run ID to the `model`, `backend`, and `reasoning`
maps in `scripts/eval/run_agents.sh`. For an additional OpenRouter model without a dedicated harness, use Qwen Code.
DeepSeek and GLM use their own official CLIs and provider credentials.

Use the following checklist only when adding a genuinely new CLI harness:

1. Add its pinned CLI installation to `scripts/docker/programbench_image.Dockerfile`,
   its installer selection to `install_agent_cleanroom.sh`, and its freshness
   probe to `programbench_image_probe.sh`. Keep all non-CLI packages outside the
   `AGENT` case so generation and grading retain the same runtime.
2. Prefer an `Agent` entry in `solve_agent.py`. Add dedicated Python drivers only
   when the CLI's execution or event format cannot fit that registry. Provide
   thin `solve_<agent>.sh` and `generate_tests_<agent>.sh` entrypoints.
3. Disable every provider-side web-search and web-fetch tool in the command or
   settings. Run `agent_network_preflight()` before image setup. Add only the
   provider API hosts that are strictly required to `scripts/docker/egress-squid.conf`;
   never grant ordinary bridge networking. Evaluation remains `--network none`.
4. Define credentials without copying them into artifacts, pass the exact model
   ID and reasoning setting, and ensure both implementation and test generation
   receive `--docker-cpus` from the eval script.
5. Normalize the CLI stream into `traj.json`: preserve complete raw events,
   stdout/stderr, normalized messages and tool calls, model/reasoning, exit
   status, timestamps/duration, token categories, and model-call count. Keep raw
   files when conversion fails. Update `summarize_agent_runs.py` for any new
   usage schema.
6. Add `<agent>_eval.sh` with the same phases and resource/evaluation flags as
   the existing scripts, then register a unique model run ID in
   `run_agents.sh`. A backend name identifies the harness; it must not be used as
   the model identity.
7. Extend the parity, network, runner, trajectory, and TSV tests. At minimum run:

   ```bash
   bash -n scripts/agents/*.sh scripts/eval/*.sh
   uv run pytest -q \
       tests/test_eval_runtime_parity.py \
       tests/test_agent_network.py \
       tests/test_run_agents_script.py \
       tests/test_summarize_agent_runs.py
   ```

For test generation with the final specification and the reference executable,
use `scripts/eval/run_agents_with_code.sh` with the same `--runs`, `--task` or
`--tasks-file`, and `--jobs` options as `run_agents.sh`. It runs only `test_gen`,
selects the existing spec-and-binary prompt, and writes to
`output/eval_with_code/` by default. For example:

```bash
bash scripts/eval/run_agents_with_code.sh --runs "claude-opus-5 codex-gpt-5.6-sol" \
  --tasks-file ground_truth/valid_task.txt --jobs 2
```

## Required invariants

- All variants build from `scripts/docker/programbench_image.Dockerfile`; `AGENT=none`
  is the evaluator and contains no agent CLI.
- Generation has API-only egress through the internal proxy. Evaluations and
  fresh-build verification have no network.
- The agent's own web tools are disabled even though its provider API is
  reachable.
- Every phase retains an artifact and a complete trajectory or, on conversion
  failure, raw stdout/stderr sufficient to recover it.
- `run_agents.sh` supplies identical task inputs, CPU limits, evaluator flags,
  and directory layout to every configured harness.
