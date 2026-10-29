# %% [markdown]
# # VeriGap: Reference Pass Rate (R) — code-generation task
# The model implements the program from the spec; we build it in-sandbox and run the
# REFERENCE test suite against it. R = fraction of reference tests that pass.
# NOTE: the build step only succeeds where the sandbox has the toolchain/deps (simple C
# like cmatrix may build; complex Rust/Go/C++ repos generally won't — that's a known limit).

# %%
import os, sys, shutil, subprocess, tempfile, json, tarfile
from pathlib import Path
from dataclasses import dataclass
import xml.etree.ElementTree as ET
try:
    import kaggle_benchmarks as kbench
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "kaggle-benchmarks"]); import kaggle_benchmarks as kbench
subprocess.run(["pip", "install", "-q", "huggingface_hub", "pytest"], capture_output=True)
from huggingface_hub import snapshot_download
WS = Path("/workspace")
if not shutil.which("python"):
    os.symlink(shutil.which("python3"), "/usr/local/bin/python")

# %%
@dataclass
class SrcFile:
    path: str       # e.g. 'main.c' or 'build.sh'
    content: str

@dataclass
class Implementation:
    files: list[SrcFile]

def _field(o, k):
    return getattr(o, k) if hasattr(o, k) else o[k]

IMPL_INSTRUCTIONS = """You are implementing a command-line program from its specification.

## Output
Return a list of files (source files + a build script). Exactly one file must be `build.sh`.
- `build.sh` is run from the directory containing your files. After it runs, a single runnable
  file named exactly `executable` must exist in that directory.
- The program must follow the specification exactly (same CLI, output, and exit codes).
- You may install system packages inside build.sh if needed (e.g. `apt-get -y install ...`).
- Keep it to one self-contained program.
"""

def build_impl(llm, spec):
    last = None
    for _ in range(3):
        try:
            impl = llm.prompt(IMPL_INSTRUCTIONS + "\n\n## Specification\n\n" + spec, schema=Implementation)
            root = Path(tempfile.mkdtemp()) / "impl"; root.mkdir(parents=True)
            for f in _field(impl, "files"):
                p = root / _field(f, "path").lstrip("/")
                p.parent.mkdir(parents=True, exist_ok=True); p.write_text(_field(f, "content"))
                if p.name == "build.sh": p.chmod(0o755)
            bs = root / "build.sh"
            if bs.exists():
                subprocess.run(["bash", "build.sh"], cwd=root, capture_output=True, text=True, timeout=600)
            exe = root / "executable"
            return exe if exe.exists() else None
        except Exception as e:
            last = e
    if last: raise last
    return None

def fetch_reference_suite(task):
    td = Path(snapshot_download("eth-sri/tsb-reference_tests", repo_type="dataset", allow_patterns=f"tests/{task}.tar.gz"))
    ex = Path(tempfile.mkdtemp()) / "refsuite"; ex.mkdir(parents=True)
    with tarfile.open(td / "tests" / f"{task}.tar.gz") as t: t.extractall(ex)
    rs = sorted(ex.rglob("run.sh"))
    return rs[0].parent.parent if rs else ex

def run_against(exe, suite_root):
    if WS.exists(): shutil.rmtree(WS)
    WS.mkdir(parents=True)
    shutil.copy2(exe, WS / "executable"); (WS / "executable").chmod(0o755)
    for item in suite_root.iterdir():
        (shutil.copytree if item.is_dir() else shutil.copy2)(item, WS / item.name)
    try:
        subprocess.run(["bash", "eval/run.sh"], cwd=WS, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        pass
    res = WS / "eval" / "results.xml"; out = {}
    if res.is_file():
        for tc in ET.parse(res).getroot().iter("testcase"):
            name = (tc.get("classname", "") + "::" + tc.get("name", "")).strip(":")
            tags = {c.tag for c in tc}
            out[name] = "skipped" if "skipped" in tags else ("failed" if ({"failure", "error"} & tags) else "passed")
    return out

# %%
@kbench.task(name="verigap-codegen",
             description="Implement the program from the spec; score the fraction of reference tests it passes (R).")
def verigap_codegen(llm, task: str, spec: str) -> float:
    exe = build_impl(llm, spec)
    kbench.assertions.assert_true(exe is not None,
        expectation="the model's implementation must build into a runnable ./executable")
    if exe is None:
        return 0.0
    out = run_against(exe, fetch_reference_suite(task))
    kbench.assertions.assert_true(bool(out), expectation="the reference test suite must run against the built program")
    if not out:
        return 0.0
    passed = sum(1 for s in out.values() if s == "passed")
    return passed / len(out)

# %%
import glob as _glob
def load_spec(task_id):
    cands = [f"/kaggle/input/verigap-specs/{task_id}.md"]
    cands += _glob.glob(f"/kaggle/input/**/{task_id}.md", recursive=True)
    cands += [f"ground_truth/spec/{task_id}/spec.md"]
    for c in cands:
        if Path(c).exists(): return Path(c).read_text()
    listing = os.listdir("/kaggle/input") if os.path.isdir("/kaggle/input") else "NO /kaggle/input"
    raise FileNotFoundError(f"spec {task_id} not found. /kaggle/input contains: {listing}")

task_id = "abishekvashok__cmatrix.5c082c6"
verigap_codegen.run(kbench.llm, task=task_id, spec=load_spec(task_id))
