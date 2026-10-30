# VeriGap: Coding Agents Build Software They Cannot Test

### A repository-scale benchmark for test-suite generation from specifications.

**Track:** Tasks & Benchmarks (Gemma 4 Developer Agent — Paper Track).
**Primary domain:** Specification-driven test generation for real command-line applications across three systems languages (Rust, Go, C/C++).
**Capability isolated:** Self-verification — the ability to turn a natural-language specification into a test suite strong enough to tell a correct implementation from a subtly-broken one, with no access to the implementation.
**Headline finding:** Frontier agents saturate the *easy* half of verification — they write valid tests (88–96% pass the reference) and correct code (86–93% of the reference suite passes) from our specifications. They diverge and then collectively fail at the hard half: no agent's suite kills more than **55% of requirement-targeted mutants**, four of six stay under 40%, and handing the agent the real program moves mutation score by **0.4 points**. The failure is in test *design*, not specification clarity, and it worsens as specifications grow.

## Problem Statement

A system approaching autonomous software engineering needs an accurate model of its own *correctness*. For software that already exists this is trivial: run the existing tests. For **genuinely new software** — the kind an agent is asked to build from a specification — there are no tests yet. The agent must write them, and they must be strong enough to catch its own mistakes. If it cannot, autonomy stops exactly where a human has to step in and write the tests.

This matters most for the setting this competition targets: an offline agent on a single accelerator. Such an agent has no cloud reviewer behind it, so its own verification is the only safety net. And because small models are cheap to run many times, generate-then-verify loops are attractive — but only if the verifier is strong. A weak verifier turns a cheap model's volume into confident wrong answers at scale.

Current evaluations miss this. Code-generation benchmarks have scaled from single issues to whole applications, but they check the *code*. Test-generation benchmarks remain at the level of single issues, single files, or single scenarios — and **every one of them hands the agent the implementation to test**. None asks the question autonomy actually requires: given only a specification, can the agent build the *verifier*? Two obstacles explain the gap. Natural-language specifications are ambiguous, itself a leading cause of testing error. And measuring suite strength requires faults that violate *specific* requirements, which rule-based mutation operators cannot guarantee — they produce equivalent or trivial mutants untethered to any stated behaviour.

VeriGap targets this capability across software's own high-stakes domains — text processing, disk utilities, build tools, a JavaScript engine (QuickJS), databases (SQLite, DuckDB), a typesetter (Typst) — where a missed edge case is a real defect and the boundary between a thorough suite and a plausible-looking one is exactly what needs to be measurable.

## Task and Benchmark Construction

VeriGap comprises **three tasks** over **165 open-source CLI applications**, each isolating a distinct facet of verification. An instance is a tuple **(S, E\*, T\*, M)**: a specification *S*, a reference executable *E\**, a reference test suite *T\**, and a set of **mutants** *M*, each an executable that violates exactly one requirement of *S*. The agent sees only *S*. A test *kills* an executable if it fails on it.

**Task 1. Validity (Specification Understanding).** The fraction of the agent's generated tests that pass on *E\**. This is the control: it certifies that the agent read the specification correctly and can express behaviour as runnable tests. Tests that fail on *E\** are discarded before mutation scoring, so a suite cannot earn credit from tests that are simply wrong.

**Task 2. Mutation Score (Verification Strength).** The headline metric: the fraction of mutants killed by at least one *valid* test. Because the reference suite *T\** kills every mutant, **M = 100% is attainable by construction** — any shortfall is the agent's. Mutants decide what the benchmark measures, so each must break one requirement and nothing else. We build a bipartite graph between specification sections and the reference tests that exercise them, then solve a **min-cost max-flow** assignment (≤6 target tests per section, preferring tests shared by few sections). For each target an agent edits the reference source so that *exactly* that test fails, mutating the requirement's logic rather than keying on literals copied from the test. A refinement pass raises the share of mutants with a **singleton kill set from 32.4% to 73.0%** and cuts collateral kills from 1.45% to 0.17% of the remaining suite.

**Task 3. Reference Pass Rate (Code-Generation Control).** The inverse question: the agent *implements* the program from *S*, and we score the fraction of *T\** its build passes. High R with low M is the signature of the verification gap — the agent understands the specification well enough to *build* the program, but not well enough to *test* it.

The specifications themselves are derived, not scraped: developer documentation is far too thin to test against (§Results). Starting from 200 ProgramBench instances, we drop network-dependent, resource-heavy, and flaky tests and keep 165, then an agent writes a 10–50-section specification from the reference suite, each section a tested behaviour described in enough detail to re-implement. A **refinement loop** then attacks each draft with two agents (one implementing, one testing) and classifies every failure as generation error, underspecification, or contradiction — a contradiction verdict must quote the offending sentence verbatim — iterating until under 5% of generated-test failures are attributable to the specification. The pipeline is agent-driven and repository-agnostic: adding a program needs only a build script and a reference suite.

The three tasks bundle into a single **VeriGap** benchmark.

## Dataset

**Size.** 165 instances. Medians: specification **5,635 words / 23 sections**; implementation **7,008 LOC**; reference suite **679 tests**; **67 mutants** per instance. Languages: Rust 59%, Go 25%, C/C++ 16%.

**Provenance.** Reference executables and test suites are inherited from ProgramBench (agent-built, human-audited). Specifications are agent-derived from those suites and refined by failure attribution. Mutants are agent-generated and requirement-linked through min-cost-flow targeting and singleton-kill-set filtering. Two classes of artefact were hand-fixed: 20 specifications that leaked crash locations (which trivially identify mutants) and 14 that described network-dependent behaviour.

**Schema.** Each instance ships a specification, a compiled reference executable, compiled mutant executables (content-addressed, gzip-compressed), and the reference suite as a directory whose `eval/run.sh` emits JUnit XML. The agent-facing contract is minimal — tests invoke the program under test at `/workspace/executable`:

```
instance/
  spec.md                    # the only artefact the agent sees
  executable                 # reference E*   (compiled, linux/amd64)
  mutants/mutants.json       # per mutant: id, target_spec, target_test, payload/artifact
  tests/eval/run.sh          # reference T*   -> /workspace/eval/results.xml (JUnit)
```

The resource is released as two Kaggle datasets — **`verigap-specs`** (165 specifications) and **`verigap-data`** (ground-truth and task definitions) — with reference binaries and mutants streamed from the public `eth-sri/tsb-*` sources.

## Technical Details

Each task is implemented in Python on the **`kaggle-benchmarks` SDK** as a `@kbench.task` returning a numeric score, so the platform's *Add Models* control fans every task across the model catalogue with no code change. The engineering contribution here is a **fully container-free scorer**: the original research harness runs each instance in Docker, but Kaggle's runtime is `linux/amd64`, so the precompiled reference and mutant binaries **run natively**. Scoring needs no image builds — place a binary at `/workspace/executable`, run the suite's `eval/run.sh`, parse `results.xml`. Because the model is served by the platform, the same tasks run on open models on a single accelerator with identical prompts and scoring; we report a Gemma 4 baseline alongside frontier agents.

Scoring recap:

- **Validity (V):** `(# generated tests passing on E*) / (# generated tests)`.
- **Mutation score (M):** `(# mutants killed by ≥1 reference-passing test) / (# mutants)`; a mutant is killed iff some test that passed on *E\** fails on it.
- **Reference pass rate (R):** `(# reference tests passing on the agent's build) / (# reference tests)`.

To keep per-run cost and wall-clock inside a notebook sandbox, the Kaggle tasks report a **time-budgeted aggregate** — the mean metric over as many of the 165 instances as fit a fixed budget — which yields a low-variance score rather than the high-variance single-instance number. Two metrics (V, M) only *run* precompiled binaries and port cleanly; R additionally requires *building* the agent's implementation, which succeeds only where the sandbox has the toolchain (simple C such as `cmatrix`; most Rust/Go/C++ repositories do not), so the full-fidelity R uses the Dockerized harness retained in the repository.

## Results

Six frontier agents were evaluated in their vendors' default harnesses: one attempt per instance, 6-hour limit, 2 CPUs, no network. Scores are percentages; higher is better.

| Model | M (mutation) | V (validity) | R (ref-pass) | $/instance |
|---|---|---|---|---|
| Claude Opus 5 | **55.5** | 96.1 | 91.8 | 10.56 |
| GPT-6 Astra | 50.1 | 94.3 | 92.7 | 2.18 |
| Gemini 3.8 Flash | 37.9 | 88.2 | 86.2 | 1.63 |
| GPT-5.6 Sol | 37.7 | 94.4 | 86.9 | 0.89 |
| DeepSeek V4 Flash | 28.6 | 78.1 | 66.8 | 0.14 |
| GPT-5.6 Luna | 19.3 | 74.1 | 65.4 | 0.03 |

Four findings stand out.

**1. Valid tests, correct code, weak suites.** The four strongest agents pass 88–96% of their tests on the reference and build implementations passing 86–93% of the reference suite — the control condition confirms the specification is clear enough to work from. Yet no suite kills more than 55.5% of mutants, and four of six stay under 40%. A suite can be entirely valid — the appearance of thoroughly-tested software — and still miss nearly half of the single-requirement violations it was written to catch. The gap between V and M is the benchmark's central result.

**2. Cost buys little.** Mutation score grows roughly *logarithmically* with spend — about 14–15 points per 10× cost; raising one agent's reasoning effort from low to xhigh moved M from 31.3% to 46.5% at 5× the cost. For a compute-bounded local setting, scaling inference alone will not close the gap.

**3. It is not the specification.** Two ablations rule out the obvious explanation. Giving the agent the real program raises validity 94.4→98.4% but moves M only 37.7→**38.1%**. Conversely, replacing our rich specification with developer documentation collapses M from 25.5% to **4.0%**. Rich specifications are necessary but not sufficient; the bottleneck is test design.

**4. The miss is input combinations, and agents share the blind spot.** Generated suites are smaller than the reference for every agent, and M correlates *negatively* with specification length (one agent r = −0.42) — agents lose coverage exactly as the requirement set grows, the regime real software occupies. Of 12,130 mutants, **4,996 survive all three** cross-analysed agents; ensembling buys only 5 points. One correlational but actionable signal: agents that *self-verify* — build a throwaway implementation, even their own mutants, while writing tests — score highest, suggesting self-mutation before testing as a concrete method for small models.

**Live Kaggle / Gemma companion.** The three tasks run end-to-end on the container-free harness on a single accelerator. The budgeted-aggregate validity task returns V = 0.73 over a 21-instance stratified subset, and the per-instance pipeline yields V, M, and R for Gemma 4 — the first measurement of the verification gap for an open, single-accelerator model, on the hardware it is meant to run on.

## Insights and Conclusions

Treating "can it verify its own work" as a single scalar obscures the structure. VeriGap decomposes it into three axes that behave differently:

- **Validity (V)** — a near-saturated dimension: the four strongest agents score 88–96%. The model understands the spec; this no longer discriminates at the top.
- **Mutation score (M)** — the unsolved, decisive dimension: no agent exceeds 55%, and it is where models separate and the composite story lives.
- **Reference pass rate (R)** — a control that proves the specification is buildable (86–93%), isolating *test design* as the point of failure rather than comprehension.

The practical implication is that suite strength is a distinct, targetable capability: not reducible to accuracy, not reducible to calibration-style validity, and not emergent from scale. A model can write code that works and tests that pass, and still ship software whose defects its own tests would never find.

Three milestones for tracking progress:

- V ≥ 90% across languages. (The four strongest agents clear this.)
- **M ≥ 60%.** (No current agent clears this.)
- R − M gap below 20 points. (No current agent clears this.)

For local agents this is the capability to measure first, because an offline model's own tests are its only reviewer. VeriGap produces a full gradient of mutation score (19% to 55%) with no agent near the ceiling, cleanly separates models adjacent on traditional code-generation benchmarks, and surfaces a failure mode — confident, valid, yet weak test suites — that standard evaluations miss entirely. We release the benchmark, the agent-driven construction pipeline (pointable at new repositories), the container-free Kaggle harness, a main explainer notebook, and three task notebooks, so progress on open models such as Gemma 4 can be tracked on the hardware those models are meant to run on.

## Organizational Affiliations

University of Zurich. Reference artefacts are inherited from ProgramBench; the specification-derivation and mutant-targeting pipeline, the container-free harness, and the Kaggle benchmark are contributions of this work.

## References

Carlini, N. Building a C compiler with a team of parallel Claudes. Anthropic Engineering, 2026.
Deng, X., et al. SWE-Bench Pro: Can AI agents solve long-horizon software engineering tasks? arXiv:2509.16941, 2025.
Ding, J., et al. NL2Repo-Bench: Towards long-horizon repository generation evaluation of coding agents. arXiv:2512.12730, 2025.
Jain, K., Synnaeve, G., Rozière, B. TestGenEval: A real world unit test generation and test completion benchmark. ICLR, 2025.
Jia, Y., Harman, M. An analysis and survey of the development of mutation testing. IEEE TSE 37(5), 2011.
Jimenez, C. E., et al. SWE-bench: Can language models resolve real-world GitHub issues? ICLR, 2024.
Kogler, L., et al. RESTestBench: Evaluating LLM-generated REST API test cases from NL requirements. arXiv:2604.25862, 2026.
Mündler, N., et al. SWT-Bench: Testing and validating real-world bug-fixes with code agents. NeurIPS, 2024.
Mustafa, A., et al. Automated test case generation from requirements: a systematic literature review. CMC 67(2), 2021.
Sun, Y., et al. SWE-Mutation: Can LLMs generate reliable test suites in software engineering? Findings of ACL, 2026.
Vero, M., et al. BaxBench: Can LLMs generate correct and secure backends? arXiv:2502.11844, 2025.
Wang, Y., et al. MultiFileTest: A multi-file-level LLM unit test generation benchmark. Findings of ACL, 2026.
Yang, J., et al. ProgramBench: Can language models rebuild programs from scratch? arXiv:2605.03546, 2026.
