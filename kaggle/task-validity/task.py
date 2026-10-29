# %% [markdown]
# # VeriGap Validity — VeriGap task (`kbench`)
# 
# Spec-driven test generation scored by validity rate (does the suite pass a correct implementation?).
# 
# Independent task — publish it, then **Add to Benchmark** to pool with the other VeriGap tasks. Reads specs from the attached `verigap-specs` dataset; reference binary / mutants pulled from public HF at runtime. Serves all models via `kbench` (use **Add Models**).

# %%
import os, sys, shutil, subprocess, tempfile, gzip, hashlib, json, stat, base64
from pathlib import Path
from dataclasses import dataclass
import xml.etree.ElementTree as ET
try:
    import kaggle_benchmarks as kbench
except ImportError:
    subprocess.run([sys.executable,'-m','pip','install','-q','kaggle-benchmarks']); import kaggle_benchmarks as kbench
subprocess.run(['pip','install','-q','huggingface_hub','pytest'], capture_output=True)
from huggingface_hub import snapshot_download
WS = Path('/workspace')
if not shutil.which('python'): os.symlink(shutil.which('python3'), '/usr/local/bin/python')

# %%
def fetch_reference(task):
    impl = Path(snapshot_download('eth-sri/tsb-reference_impl', repo_type='dataset', allow_patterns=f'executable/{task}/**'))
    ref = impl/'executable'/task/'executable'; ref.chmod(0o755); return ref

def fetch_manifest(task):
    root = Path(snapshot_download('eth-sri/tsb-mutants', repo_type='dataset', allow_patterns=f'{task}/mutants.json'))/task
    man = json.loads((root/'mutants.json').read_text())
    return root, (man['mutants'] if isinstance(man, dict) else man)

def fetch_one_mutant(task, m):
    want = (m.get('artifact') or {}).get('path') or m['payload']
    snapshot_download('eth-sri/tsb-mutants', repo_type='dataset', allow_patterns=f'{task}/{want}')

def materialize_mutant(root, m):
    p = root/m['payload']
    if p.is_file(): return p, False
    art = m.get('artifact');
    if not art: raise FileNotFoundError(p)
    fd, name = tempfile.mkstemp(prefix='mut-'); os.close(fd); tmp = Path(name)
    with gzip.open(root/art['path'],'rb') as c, open(tmp,'wb') as o: shutil.copyfileobj(c,o,length=1<<20)
    assert hashlib.sha256(tmp.read_bytes()).hexdigest()==art['sha256'], 'hash mismatch'
    tmp.chmod(tmp.stat().st_mode|stat.S_IXUSR); return tmp, True

def run_against(exe, suite_root):
    if WS.exists(): shutil.rmtree(WS)
    WS.mkdir(parents=True)
    shutil.copy2(exe, WS/'executable'); (WS/'executable').chmod(0o755)
    for item in suite_root.iterdir():
        (shutil.copytree if item.is_dir() else shutil.copy2)(item, WS/item.name)
    try: subprocess.run(['bash','eval/run.sh'], cwd=WS, capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired: pass
    res = WS/'eval'/'results.xml'; out = {}
    if res.is_file():
        for tc in ET.parse(res).getroot().iter('testcase'):
            name = (tc.get('classname','')+'::'+tc.get('name','')).strip(':'); tags={c.tag for c in tc}
            out[name] = 'skipped' if 'skipped' in tags else ('failed' if ({'failure','error'} & tags) else 'passed')
    return out

@dataclass
class TestFile:
    path: str   # e.g. 'eval/run.sh' or 'eval/test_spec1.py'
    content: str

@dataclass
class GeneratedSuite:
    files: list[TestFile]

def _field(obj, key):
    return getattr(obj, key) if hasattr(obj, key) else obj[key]

def generate_suite(llm, spec):
    prompt = INSTRUCTIONS + '\n\n## Specification\n\n' + spec
    last = None
    for _ in range(3):   # structured-output generation can fail stochastically; retry
        try:
            suite = llm.prompt(prompt, schema=GeneratedSuite)
            files = _field(suite, 'files')
            root = Path(tempfile.mkdtemp())/'suite'; root.mkdir(parents=True)
            for f in files:
                rel = _field(f, 'path').lstrip('/'); p = root/rel
                p.parent.mkdir(parents=True, exist_ok=True); p.write_text(_field(f, 'content'))
                if p.name == 'run.sh': p.chmod(0o755)
            return root
        except Exception as e:
            last = e
    raise last

INSTRUCTIONS = 'You are creating a test suite.\n\n## Task\n\nCreate a comprehensive test suite under `eval/`.\n\n## Evaluation Design\n\n- The suite is evaluated against fresh workspaces containing the program under test at `/workspace/executable`.\n- The specification is available only now, while authoring the suite.\n- Tests must invoke `/workspace/executable` (absolute path).\n\n## Rules\n\n- Cover documented functional behavior thoroughly. The suite must kill mutants that violate the spec, while passing any implementation that follows the spec.\n- Cover each explicitly numbered/sectioned requirement with at least one focused test. Prefer many small tests over one huge test.\n\n## Output\n\nReturn a list of files. Exactly one must be `eval/run.sh` (executable), plus any test files it needs.\n- `eval/run.sh` must always write valid JUnit XML to `/workspace/eval/results.xml`.\n- It must run the whole suite even after individual failures.\n- Root `<testsuites>` (or a single `<testsuite>`), one named `<testcase>` per test; non-pass outcomes use nested `<failure>`/`<error>`/`<skipped>`.\n- For pytest: `cd /workspace/eval && pytest --junitxml=/workspace/eval/results.xml`.\n'

# %%
@kbench.task(name='verigap_validity',
    description='Spec-driven test generation scored by validity rate on the reference implementation.')
def verigap_validity(llm, task: str, spec: str) -> float:
    root = generate_suite(llm, spec)
    ref = fetch_reference(task)
    out = run_against(ref, root)
    kbench.assertions.assert_true(bool(out), expectation='suite must produce runnable tests')
    if not out: return 0.0
    passed = sum(1 for s in out.values() if s=='passed')
    return passed/len(out)

# %%
# Spec loads from the attached verigap-specs dataset (wherever Kaggle mounts it),
# or the local repo when validating with `python task.py` from the repo root.
import glob as _glob
def load_spec(task_id):
    cands = [f'/kaggle/input/verigap-specs/{task_id}.md']
    cands += _glob.glob(f'/kaggle/input/**/{task_id}.md', recursive=True)
    cands += [f'ground_truth/spec/{task_id}/spec.md']
    for c in cands:
        if Path(c).exists(): return Path(c).read_text()
    listing = os.listdir('/kaggle/input') if os.path.isdir('/kaggle/input') else 'NO /kaggle/input'
    raise FileNotFoundError(f'spec {task_id} not found. /kaggle/input contains: {listing}')

task_id = 'abishekvashok__cmatrix.5c082c6'
verigap_validity.run(kbench.llm, task=task_id, spec=load_spec(task_id))

# Full 165-task sweep across models (uncomment once the single run works):
# import pandas as pd
# SPEC_DIR = Path('/kaggle/input/verigap-specs')
# df = pd.DataFrame([{'task': p.stem, 'spec': p.read_text()} for p in sorted(SPEC_DIR.glob('*.md'))])
# print(verigap_validity.evaluate(llm=[kbench.llm], evaluation_data=df).as_dataframe())
