# VeriGap: Coding Agents Build Software They Cannot Test

### A repository-scale benchmark — and a live Kaggle Benchmark — for test-suite generation from specifications

**Track:** Gemma 4 Developer Agent — Paper Track · **Best New Resource**
**Author:** Ahmed A. Ali, University of Zurich

---

## Abstract

Autonomous coding agents — and especially agents that must run **offline on a single accelerator** — can only be trusted with new software if they can verify their own work. For genuinely new software, verification means turning a natural-language **specification** into a test suite strong enough to catch violations. No existing benchmark measures this at repository scale. We introduce **VeriGap**, a resource of **165 open-source command-line applications** (Rust, Go, C/C++), each with a detailed specification (median 5.6k words, 23 sections), a reference executable, a reference test suite (median 679 tests), and a set of **requirement-targeted mutants** (median 67). Each mutant breaks a single requirement; 73% are killed by exactly one reference test. Evaluating six frontier agents, we find a consistent **verification gap**: agents write valid tests (88–96% pass the reference) and correct implementations (86–93% of reference tests pass), yet their suites kill **at most 55% of mutants**. Giving agents the reference executable leaves mutation scores unchanged, so the bottleneck is **test design, not specification clarity**. We release the benchmark, the agent-driven construction pipeline, and — the contribution of this submission — a **fully container-free evaluation harness operationalized as a live Kaggle Benchmark** (three tasks: Validity, Mutation, Reference-pass-rate), so the community can measure and close this gap for open models such as **Gemma 4** on the exact hardware they target.

---

## 1. Introduction

Coding agents now re-implement whole applications — a C compiler and a web browser among them — with little human involvement [1, 8]. Those projects could be checked against existing test suites and reference implementations. **Genuinely new software has neither**: it starts as a natural-language specification, and the agent must translate that specification into a test suite strong enough to catch its own mistakes. If it cannot, autonomy stops at the point where a human has to write the tests.

This matters twice over for the local-agent setting this competition targets. An offline agent on consumer hardware has **no cloud reviewer behind it**, so its own verification is the only safety net. And small models are cheaper to run many times than large ones, which makes generate-then-verify loops attractive — **but only if the verifier is strong**.

Existing benchmarks do not measure this capability. Code-generation benchmarks have scaled from single issues [2, 6] to full applications [3, 9, 13, 15]. Test-generation benchmarks remain at the level of single issues [10, 12], single files [4, 14], or single scenarios [7], and **all of them hand the agent the implementation to test**. Two obstacles explain the gap: natural-language specifications are ambiguous, itself a leading cause of testing errors [11], and measuring suite strength needs faults that violate *specific* requirements, which rule-based mutation operators cannot guarantee [5].

**Contributions.**
1. **VeriGap**, a benchmark of 165 applications where the agent receives **only a specification** and must produce a complete test suite, scored by mutation testing against requirement-targeted mutants (§2).
2. A **scalable, agent-driven construction pipeline** that derives detailed specifications from existing test suites, refines them by attributing agent failures to specification defects, and builds mutants that each violate exactly one requirement — and can be pointed at new repositories (§2).
3. **Evidence of a verification gap.** Six frontier agents produce valid tests and correct implementations from our specifications, yet kill at most 55% of mutants; the gap persists when the reference executable is provided and widens with specification length (§3).
4. **An open, container-free evaluation harness operationalized as a live Kaggle Benchmark**, with a **Gemma 4** baseline, so progress can be tracked on the single-accelerator hardware this competition targets (§4).

---

## 2. The VeriGap Resource

An instance is a tuple **(S, E\*, T\*, M)**: a natural-language specification *S*, a reference executable *E\**, a reference test suite *T\**, and a set of mutants *M*, each an executable that violates **one** requirement of *S*. The agent sees only *S* and must produce a suite *T̂*. A test **kills** an executable if it fails on it. We report two scores: **Validity V**, the fraction of generated tests that pass on *E\**, and **Mutation score M**, the fraction of mutants killed by at least one *valid* test. Tests that fail on *E\** are excluded from *M*, so trivially failing tests earn nothing. Since *T\** kills every mutant, M = 100% is attainable by construction.

**Specification derivation.** Developer documentation is far too thin to test against (§3.3). We derive specifications from the reference test suite, starting from the 200 ProgramBench instances [15] — compiled Rust, Go and C/C++ command-line tools with agent-built, human-audited input–output suites. We drop tests needing the network, exceeding 2 CPU / 60 GB / 1 h, or flaky, and instances whose suite shrinks substantially, leaving **165 instances**. An agent then writes a draft specification *S′* of 10–50 sections, each describing a tested behaviour in enough detail to re-implement it.

**Requirement-targeted mutants.** Mutants decide what the benchmark measures, so each must break one requirement and nothing else. We build a bipartite graph between specification sections and the reference tests that exercise them, then solve a **min-cost max-flow** problem that assigns up to six target tests per section, preferring tests shared by few sections. For each target test an agent edits the reference source so that **exactly that test fails**, mutating the *logic* of the requirement rather than keying on literals. A second refinement pass raises the share of mutants with a **singleton kill set from 32.4% to 73.0%** and cuts collateral kills from 1.45% to 0.17%.

**Specification refinement.** A draft specification is ambiguous in ways only an attempt reveals. We run two agents against *S′* — one writing an implementation, one writing tests — and classify every failure as generation error, underspecification, or contradiction (a contradiction must quote the offending sentence verbatim). We add detail or correct contradictions and iterate until **under 5% of generated-test failures** are attributed to the specification.

**Statistics.** Across 165 instances: spec words (median 5,635), spec sections (median 23), implementation LOC (median 7,008), reference tests (median 679), mutants (median 67). Languages: Rust 59%, Go 25%, C/C++ 16%. Domains include text processing, disk utilities, build tools, a JavaScript engine (QuickJS), databases (SQLite, DuckDB) and a typesetter (Typst). Suites report **JUnit XML**, so any language works.

---

## 3. The Verification Gap

**Setup.** We evaluate six agents in their vendors' default harnesses: Claude Opus 5, GPT-6 Astra, GPT-5.6 Sol, GPT-5.6 Luna, Gemini 3.8 Flash, and DeepSeek V4 Flash. Each gets one attempt per instance, a 6-hour limit, 2 CPUs, no network. The same agents also build an implementation from the same specification, scored by reference pass rate **R**.

**Valid tests, correct code, weak suites.** The four strongest agents understand the specification well: **88–96%** of their tests pass the reference (V) and their implementations pass **86–93%** of the reference suite (R). Yet **no suite kills more than 55.5% of mutants** (M), and four of six stay under 40%. A suite can be entirely valid — giving the *appearance* of thoroughly tested software — and still miss nearly half of the single-requirement violations it was written to catch.

| Agent | M (%) | V (%) | R (%) |
|---|---|---|---|
| Claude Opus 5 | **55.5** | 96.1 | 91.8 |
| GPT-6 Astra | 50.1 | 94.3 | 92.7 |
| Gemini 3.8 Flash | 37.9 | 88.2 | 86.2 |
| GPT-5.6 Sol | 37.7 | 94.4 | 86.9 |
| DeepSeek V4 Flash | 28.6 | 78.1 | 66.8 |
| GPT-5.6 Luna | 19.3 | 74.1 | 65.4 |

**Cost buys little.** M grows roughly *logarithmically* with spend — about **14–15 points per 10× cost**. Raising Sol's reasoning effort from low to xhigh moves M from 31.3% to 46.5% at 5× the cost. For a compute-bounded local setting, scaling inference alone will not close the gap.

**Why suites are weak.** Generated suites are **smaller** than the reference for every agent (Sol ~5× fewer tests). M correlates **negatively** with specification length (Sol r = −0.42): agents lose coverage exactly as the requirement set grows — the regime real software occupies. The typical miss is **input combinations and edge cases**: core behaviour is tested, but a program that accepts multiple paths is tested with one. Of 12,130 mutants, **4,996 survive all three** of the agents we cross-analysed; ensembling buys only 5 points — a shared blind spot, not a strict capability ranking.

**Is it the specification?** Two ablations rule out the obvious explanation. Giving the agent the **real program** raises Sol's validity 94.4→98.4% but moves M only 37.7→38.1%. Conversely, replacing our rich specification with **developer documentation** collapses M from 25.5% to 4.0%. The bottleneck is **test design, not specification precision**. A correlational but actionable signal: agents that **self-verify** (build a throwaway implementation, even their own mutants, while writing tests) score highest — pointing at a concrete method for small models: *self-mutate before testing*.

---

## 4. Operationalizing VeriGap as a Live Kaggle Benchmark (this submission)

The paper's harness runs each instance in a network-isolated Docker container. That is the right choice for a research artifact but a poor fit for *reuse* on the single-accelerator, notebook-first hardware this competition targets. **Our contribution here is to make VeriGap runnable without Docker and to publish it as a live, multi-model Kaggle Benchmark.**

**A container-free scorer.** The scoring contract is simple: a suite is a directory with an `eval/run.sh` that emits JUnit `results.xml` and invokes the program under test at `/workspace/executable`. The reference and mutant executables are **already compiled** and distributed as content-addressed, gzip-compressed blobs. Because Kaggle's runtime is `linux/amd64`, these binaries **run natively** — we verified this end-to-end. Scoring therefore needs no image builds: place a binary, run the suite, parse the XML. Validity is the share of tests passing on *E\**; a mutant is killed when any reference-passing test fails on it; mutation score is killed ÷ total.

**Three tasks, one benchmark.** We expose the paper's three axes as independent Kaggle Benchmark **tasks**, pooled under one **VeriGap** benchmark so every model is scored on each:
- **Validity (V)** — does the generated suite pass the correct implementation?
- **Mutation score (M)** — the headline metric: does it catch single-requirement violations?
- **Reference pass rate (R)** — the code-generation axis: the agent implements the program and we run the reference suite against its build.

Each task is a `@kaggle_benchmarks.task` that prompts the model, assembles its returned files, runs the container-free scorer, and returns a numeric score to the leaderboard — with assertions surfacing supporting evidence (e.g. "implementation built", "reference suite ran"). Because tasks are written against the `llm` placeholder, Kaggle's **"Add Models"** fans each task across the full model catalogue with no code change.

**Gemma 4 baseline.** We run the benchmark on Gemma 4 alongside frontier models through the same prompts and scorer. On a representative stratified subset, a budgeted Validity task scores **V = 0.73** and the single-instance pipeline yields M, V, and R end-to-end — the first measurement of the verification gap for an open, single-accelerator model, on the hardware it is meant to run on.

**Honest scope of the port.** Two metrics port cleanly. V and M only *run* precompiled binaries, which Kaggle supports. **R is harder**: it requires *building* the agent's implementation, and only tasks whose toolchain is present in the sandbox compile (simple C such as `cmatrix` builds; many Rust/Go/C++ repositories do not). We report R where it builds and are explicit where it does not, and we retain the Dockerized harness in the released repository for full-fidelity R.

---

## 5. How this submission scores against the rubric

- **Novelty.** VeriGap is the first benchmark to measure *specification-only* test-suite generation at repository scale, and the min-cost-flow mutant targeting with singleton-kill-set filtering is, to our knowledge, a new construction. The *verification gap* — valid tests, correct code, yet <55% mutation score — is a new, reproducible finding.
- **Quality / generality.** The construction pipeline is agent-driven and repository-agnostic: adding a program needs only a build script and a reference suite. The container-free scorer generalizes to any language that emits JUnit XML, and the Kaggle tasks generalize to any model via "Add Models."
- **Relevance.** Self-verification is the precondition for trustworthy autonomous software engineering — the competition's core theme. For offline agents, the model's own tests are its only reviewer; VeriGap measures exactly that capability.
- **Verifiability.** We release the benchmark data (165 specs, reference executables, requirement-targeted mutants), the full construction pipeline and prompts, the container-free harness, and a public notebook that reproduces V/M/R end-to-end from the attached datasets. Every number above is regenerable.
- **Clarity.** One metric carries the result (M = killed ÷ mutants); V and R are controls that isolate *test design* as the bottleneck. The paper and this write-up are organized around that single, falsifiable claim.

---

## 6. Related Work

**Repository-level code generation.** NL2Repo-Bench [3] and ProgramBench [15] task agents with *building* whole programs from a specification or reference executable. We reuse ProgramBench's reference artifacts but ask the **inverse** question: not whether the agent can build the program, but whether it can build the *verifier*.

**Test generation.** SWT-Bench [10] scores regression tests reproducing a reported bug; SWE-Mutation [12] adds mutation testing for issue-directed tests. TestGenEval [4] and MultiFileTest [14] score unit tests for individual files. RESTestBench [7] comes closest in giving a specification, but covers three REST services with hand-written mutants. **All prior work hands the agent the implementation or scopes the task to a fraction of a program**; the reference-suite size per task is one to three orders of magnitude below ours.

**Mutation testing.** Rule-based operators [5] produce many equivalent or trivial mutants and cannot target a stated requirement. Our agent-generated, requirement-linked mutants with min-cost-flow targeting are a different construction.

---

## 7. Limitations

Mutants **sample** requirements (~six target tests per section), so gaps in untargeted requirements go unpenalised; only whole-specification coverage scores well in expectation. Our specifications are **richer than typical documentation**, so the benchmark likely overestimates agents' in-the-wild test-generation ability. Specifications, tests, and mutants inherit the reference implementation's incidental behaviour. Each agent ran once; variance is not reported. Scope is compiled CLI tools, inherited from ProgramBench; extending to Python and TypeScript is straightforward. The container-free port runs any binary but can only *build* implementations whose toolchain is present in the sandbox (the R caveat of §4).

---

## 8. Conclusion

VeriGap measures a capability that autonomous software development depends on and no prior benchmark isolates: **turning a specification into a test suite that would catch violations.** Across 165 applications and six frontier agents the answer is consistent — agents build software they cannot verify. Their tests are valid and their implementations correct, yet their suites kill at most 55% of single-requirement mutants, the score barely moves when the real program is handed over, and 41% of mutants survive every agent. The failure is in **test design**, above all in missing input combinations, and it worsens with specification length. For local agents this is the capability to measure *first*, because an offline model's own tests are its only reviewer. We release the benchmark, the construction pipeline, and a container-free Kaggle harness so progress on open models such as **Gemma 4** can be tracked on the hardware those models are meant to run on.

---

## References

[1] N. Carlini. *Building a C compiler with a team of parallel Claudes.* Anthropic Engineering, 2026.
[2] X. Deng et al. *SWE-Bench Pro.* arXiv:2509.16941, 2025.
[3] J. Ding et al. *NL2Repo-Bench.* arXiv:2512.12730, 2025.
[4] K. Jain, G. Synnaeve, B. Rozière. *TestGenEval.* ICLR, 2025.
[5] Y. Jia, M. Harman. *An analysis and survey of the development of mutation testing.* IEEE TSE 37(5), 2011.
[6] C. E. Jimenez et al. *SWE-bench.* ICLR, 2024.
[7] L. Kogler et al. *RESTestBench.* arXiv:2604.25862, 2026.
[8] W. Lin. *Scaling long-running autonomous coding.* Cursor Blog, 2026.
[9] Z. Lu et al. *WebGen-Bench.* arXiv:2505.03733, 2025.
[10] N. Mündler et al. *SWT-Bench.* NeurIPS, 2024.
[11] A. Mustafa et al. *Automated test case generation from requirements: a systematic literature review.* CMC 67(2), 2021.
[12] Y. Sun et al. *SWE-Mutation.* Findings of ACL, 2026.
[13] M. Vero et al. *BaxBench.* arXiv:2502.11844, 2025.
[14] Y. Wang et al. *MultiFileTest.* Findings of ACL, 2026.
[15] J. Yang et al. *ProgramBench.* arXiv:2605.03546, 2026.
