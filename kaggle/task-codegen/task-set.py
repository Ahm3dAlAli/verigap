# %%
import os, sys, shutil, subprocess, tempfile, tarfile, time
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
if not shutil.which("python"): os.symlink(shutil.which("python3"), "/usr/local/bin/python")

# %%
@dataclass
class SrcFile:
    path: str
    content: str
@dataclass
class Implementation:
    files: list[SrcFile]
def _field(o,k): return getattr(o,k) if hasattr(o,k) else o[k]
IMPL = ("You are implementing a command-line program from its specification.\n"
        "Return source files + exactly one `build.sh` that, run from the files' directory, produces a runnable "
        "file named exactly `executable`. Install needed packages inside build.sh. Follow the spec exactly.")
def build_impl(llm, spec):
    last=None
    for _ in range(2):
        try:
            impl=llm.prompt(IMPL+"\n\n## Specification\n\n"+spec, schema=Implementation)
            root=Path(tempfile.mkdtemp())/"impl"; root.mkdir(parents=True)
            for f in _field(impl,"files"):
                p=root/_field(f,"path").lstrip("/"); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(_field(f,"content"))
                if p.name=="build.sh": p.chmod(0o755)
            if (root/"build.sh").exists():
                try: subprocess.run(["bash","build.sh"], cwd=root, capture_output=True, text=True, timeout=180)
                except subprocess.TimeoutExpired: pass
            e=root/"executable"; return e if e.exists() else None
        except Exception as ex: last=ex
    return None
def fetch_reference_suite(task):
    td=Path(snapshot_download("eth-sri/tsb-reference_tests", repo_type="dataset", allow_patterns=f"tests/{task}.tar.gz"))
    ex=Path(tempfile.mkdtemp())/"rs"; ex.mkdir(parents=True)
    with tarfile.open(td/"tests"/f"{task}.tar.gz") as t: t.extractall(ex)
    rs=sorted(ex.rglob("run.sh")); return rs[0].parent.parent if rs else ex
def run_against(exe, suite_root):
    if WS.exists(): shutil.rmtree(WS)
    WS.mkdir(parents=True); shutil.copy2(exe, WS/"executable"); (WS/"executable").chmod(0o755)
    for it in suite_root.iterdir():
        (shutil.copytree if it.is_dir() else shutil.copy2)(it, WS/it.name)
    try: subprocess.run(["bash","eval/run.sh"], cwd=WS, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired: pass
    res=WS/"eval"/"results.xml"; out={}
    if res.is_file():
        for tc in ET.parse(res).getroot().iter("testcase"):
            tags={c.tag for c in tc}; name=(tc.get("classname","")+"::"+tc.get("name","")).strip(":")
            out[name]="skipped" if "skipped" in tags else ("failed" if ({"failure","error"} & tags) else "passed")
    return out

# %%
BUDGET=2400; LIMIT=21
@kbench.task(name="verigap-codegen-set",
             description="Reference pass rate R: implement the program from spec, build in-sandbox, run the reference suite. Averaged over up to 21 tasks (builds only succeed where the toolchain is present).")
def verigap_codegen_set(llm) -> float:
    specs=sorted(p for p in Path("/kaggle/input").rglob("*.md") if "__" in p.stem)[:LIMIT]
    rs=[]; built=0; t0=time.time()
    for q in specs:
        if time.time()-t0>BUDGET: break
        try:
            exe=build_impl(llm, q.read_text())
            if exe is None:
                rs.append(0.0); print(f"{q.stem} build=FAIL R=0.0"); continue
            built+=1; out=run_against(exe, fetch_reference_suite(q.stem))
            r=(sum(1 for s in out.values() if s=="passed")/len(out)) if out else 0.0
            rs.append(r); print(f"{q.stem} build=OK R={round(r,3)}")
        except Exception as ex:
            rs.append(0.0); print(f"{q.stem} ERROR {ex}")
    print(f"COVERAGE {len(rs)} tasks, {built} built, elapsed {round(time.time()-t0)}s")
    kbench.assertions.assert_true(bool(rs), expectation=f"scored {len(rs)} tasks ({built} built) within budget")
    return (sum(rs)/len(rs)) if rs else 0.0

# %%
verigap_codegen_set.run(kbench.llm)
