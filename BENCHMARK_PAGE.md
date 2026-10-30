# VeriGap — benchmark page content (paste into the Sections / Metadata fields)

## SECTION 1 — Overview

**Can a coding agent build the verifier, not just the program?** VeriGap gives an agent only a natural-language **specification** of a real command-line tool and asks it to produce a **test suite** strong enough to tell a correct implementation from a subtly-broken one. For an offline agent on a single accelerator, its own tests are its only reviewer — so this is the capability to measure first.

**Headline finding.** Frontier agents write *valid* tests (88–96% pass the reference) and *correct* code (86–93% of the reference suite passes), yet their suites kill **at most 55% of requirement-targeted mutants** — and handing the agent the real program barely moves the score. The failure is in test *design*, not specification clarity, and it worsens as specifications grow.

165 applications across Rust (59%), Go (25%), and C/C++ (16%) — text tools, disk utilities, build tools, a JavaScript engine (QuickJS), databases (SQLite, DuckDB), and a typesetter (Typst).

## SECTION 2 — The three tasks

- **Validity (V)** — the fraction of the agent's generated tests that pass the reference implementation. A control: does the agent *understand* the spec? (Near-saturated for strong agents.)
- **Mutation score (M)** — *the headline metric.* The fraction of requirement-targeted mutants killed by a valid test. A mutant is killed when a reference-passing test fails on it. Each mutant breaks exactly one requirement; 73% are killed by a single reference test. (Unsolved: no agent exceeds 55%.)
- **Reference pass rate (R)** — the inverse control: the agent *implements* the program from the spec, scored on the fraction of reference tests it passes. High R with low M is the verification gap.

## SECTION 3 — How to read the leaderboard

Each model gets a per-task score and a composite. Scores are **low-variance aggregates over a stratified subset** of the 165 tasks (not single instances), computed by a **container-free harness**: the precompiled reference/mutant binaries run natively and the generated suite's `run.sh` emits JUnit XML. Validity and Mutation port exactly; **Reference-pass-rate (R) only builds where the sandbox has the toolchain** (simple C such as `cmatrix`), so codegen scores low here by construction — full-fidelity R uses the Dockerized harness in the repository. Milestones: V ≥ 90% (strong agents clear it), **M ≥ 60% (none clear it)**, R−M gap < 20 points (none clear it).

---

## METADATA

**Provenance → Sources** (add each as a source link):
- GitHub — https://github.com/Ahm3dAlAli/verigap
- Dataset — `archie40004/verigap-specs` (165 specifications)
- Dataset — `archie40004/verigap-data` (ground-truth + task definitions)
- Built on ProgramBench reference artifacts (arXiv:2605.03546)

**Provenance → Citations / associated papers:**
- VeriGap: Coding Agents Build Software They Cannot Test (this submission's writeup)
- ProgramBench: Can language models rebuild programs from scratch? (arXiv:2605.03546)
- SWT-Bench (NeurIPS 2024); TestGenEval (ICLR 2025); SWE-Mutation (ACL Findings 2026)

**Citation (BibTeX)** — keep Kaggle's auto-generated one, or use:
```bibtex
@misc{alali2026verigap,
  title  = {VeriGap: Coding Agents Build Software They Cannot Test},
  author = {Ahmed A. Ali},
  year   = {2026},
  note   = {A repository-scale benchmark for test-suite generation from specifications},
  url    = {https://www.kaggle.com/benchmarks/archie40004/verigap}
}
```

**Collaborators:** (owner only — leave as is unless adding teammates.)
