# %%
import os, sys, shutil, subprocess, tempfile, gzip, hashlib, json, stat, tarfile, time
from pathlib import Path
from dataclasses import dataclass
import xml.etree.ElementTree as ET
try:
    import kaggle_benchmarks as kbench
except ImportError:
    subprocess.run([sys.executable,"-m","pip","install","-q","kaggle-benchmarks"]); import kaggle_benchmarks as kbench
subprocess.run(["pip","install","-q","huggingface_hub","pytest"], capture_output=True)
from huggingface_hub import snapshot_download
WS = Path("/workspace")
if not shutil.which("python"): os.symlink(shutil.which("python3"), "/usr/local/bin/python")

@dataclass
class TestFile:
    path: str
    content: str
@dataclass
class GeneratedSuite:
    files: list[TestFile]
@dataclass
class SrcFile:
    path: str
    content: str
@dataclass
class Implementation:
    files: list[SrcFile]
def _f(o,k): return getattr(o,k) if hasattr(o,k) else o[k]

TEST_INSTR = ("You are creating a test suite under eval/ whose tests invoke /workspace/executable. "
  "Return files incl. eval/run.sh that writes JUnit XML to /workspace/eval/results.xml and runs the whole suite "
  "even after failures (cd /workspace/eval && pytest --junitxml=/workspace/eval/results.xml).")
IMPL_INSTR = ("Implement the CLI program from its specification. Return source files + exactly one build.sh that, "
  "run from the files dir, produces a runnable file named exactly `executable`. Install packages in build.sh. Follow the spec.")

def specs(limit):
    return sorted(p for p in Path("/kaggle/input").rglob("*.md") if "__" in p.stem)[:limit]
def fetch_ref(task):
    d=Path(snapshot_download("eth-sri/tsb-reference_impl",repo_type="dataset",allow_patterns=f"executable/{task}/**"))
    e=d/"executable"/task/"executable"; e.chmod(0o755); return e
def fetch_manifest(task):
    r=Path(snapshot_download("eth-sri/tsb-mutants",repo_type="dataset",allow_patterns=f"{task}/mutants.json"))/task
    m=json.loads((r/"mutants.json").read_text()); return r,(m["mutants"] if isinstance(m,dict) else m)
def fetch_one(task,m):
    w=(m.get("artifact") or {}).get("path") or m["payload"]
    snapshot_download("eth-sri/tsb-mutants",repo_type="dataset",allow_patterns=f"{task}/{w}")
def materialize(root,m):
    p=root/m["payload"]
    if p.is_file(): return p,False
    a=m["artifact"]; fd,n=tempfile.mkstemp(prefix="mut-"); os.close(fd); t=Path(n)
    with gzip.open(root/a["path"],"rb") as c,open(t,"wb") as o: shutil.copyfileobj(c,o,length=1<<20)
    assert hashlib.sha256(t.read_bytes()).hexdigest()==a["sha256"]; t.chmod(t.stat().st_mode|stat.S_IXUSR); return t,True
def ref_suite(task):
    td=Path(snapshot_download("eth-sri/tsb-reference_tests",repo_type="dataset",allow_patterns=f"tests/{task}.tar.gz"))
    ex=Path(tempfile.mkdtemp())/"rs"; ex.mkdir(parents=True)
    with tarfile.open(td/"tests"/f"{task}.tar.gz") as t: t.extractall(ex)
    rs=sorted(ex.rglob("run.sh")); return rs[0].parent.parent if rs else ex
def gen_suite(llm,spec):
    last=None
    for _ in range(3):
        try:
            s=llm.prompt(TEST_INSTR+"\n\n## Specification\n\n"+spec, schema=GeneratedSuite)
            root=Path(tempfile.mkdtemp())/"s"; root.mkdir(parents=True)
            for f in _f(s,"files"):
                p=root/_f(f,"path").lstrip("/"); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(_f(f,"content"))
                if p.name=="run.sh": p.chmod(0o755)
            return root
        except Exception as e: last=e
    raise last
def build_impl(llm,spec):
    last=None
    for _ in range(2):
        try:
            im=llm.prompt(IMPL_INSTR+"\n\n## Specification\n\n"+spec, schema=Implementation)
            root=Path(tempfile.mkdtemp())/"i"; root.mkdir(parents=True)
            for f in _f(im,"files"):
                p=root/_f(f,"path").lstrip("/"); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(_f(f,"content"))
                if p.name=="build.sh": p.chmod(0o755)
            if (root/"build.sh").exists():
                try: subprocess.run(["bash","build.sh"],cwd=root,capture_output=True,text=True,timeout=180)
                except subprocess.TimeoutExpired: pass
            e=root/"executable"; return e if e.exists() else None
        except Exception as ex: last=ex
    return None
def run_against(exe,suite_root,timeout=45):
    if WS.exists(): shutil.rmtree(WS)
    WS.mkdir(parents=True); shutil.copy2(exe,WS/"executable"); (WS/"executable").chmod(0o755)
    for it in suite_root.iterdir():
        (shutil.copytree if it.is_dir() else shutil.copy2)(it,WS/it.name)
    try: subprocess.run(["bash","eval/run.sh"],cwd=WS,capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired: pass
    res=WS/"eval"/"results.xml"; out={}
    if res.is_file():
        for tc in ET.parse(res).getroot().iter("testcase"):
            tags={c.tag for c in tc}; nm=(tc.get("classname","")+"::"+tc.get("name","")).strip(":")
            out[nm]="skipped" if "skipped" in tags else ("failed" if ({"failure","error"} & tags) else "passed")
    return out

# %%
BUDGET=18000
@kbench.task(name='verigap-mutation-50', description='Mean mutation score over up to 50 VeriGap tasks (12-mutant sample each).')
def verigap_mutation_50(llm) -> float:
    ms=[]; t0=time.time()
    for q in specs(50):
        if time.time()-t0>BUDGET: break
        try:
            root=gen_suite(llm,q.read_text()); gt={n for n,s in run_against(fetch_ref(q.stem),root).items() if s=="passed"}
            if not gt: ms.append(0.0)
            else:
                mr,muts=fetch_manifest(q.stem); muts=muts[:12]; k=0
                for m in muts:
                    try: fetch_one(q.stem,m); me,tmp=materialize(mr,m)
                    except Exception: continue
                    try:
                        o=run_against(me,root)
                        if any(o.get(n)!="passed" for n in gt): k+=1
                    finally:
                        if tmp: Path(me).unlink(missing_ok=True)
                ms.append(k/len(muts) if muts else 0.0)
        except Exception: pass
        print(f"{len(ms)} {q.stem} elapsed={round(time.time()-t0)}s", flush=True)
    print(f"COVERAGE {len(ms)} scored, elapsed {round(time.time()-t0)}s")
    kbench.assertions.assert_true(bool(ms), expectation=f"scored {len(ms)} tasks in budget")
    return (sum(ms)/len(ms)) if ms else 0.0

# %%
verigap_mutation_50.run(kbench.llm)
