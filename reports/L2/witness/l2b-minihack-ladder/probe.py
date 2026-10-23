"""Run named pins clean and under each of their mutants in scratch copies of the tree at argv[1]."""
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

src = Path(sys.argv[1])
pins = sys.argv[2:]
files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=src, capture_output=True, text=True,
                       check=True).stdout.split()


def copy(edits):
    d = Path(tempfile.mkdtemp(prefix="probe39-"))
    for f in files:
        if (src / f).is_file():
            (d / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / f, d / f)
    for e in edits:
        p = d / e["path"]
        t = p.read_text()
        assert t.count(e["old"]) == 1, (e["path"], e["old"], t.count(e["old"]))
        p.write_text(t.replace(e["old"], e["new"]))
    return d


def run(d, fn):
    s = tempfile.mkdtemp(prefix="probe39-scratch-")
    code = f"import harness.pins as p, harness.context as c, pathlib\nc.scratch = pathlib.Path({s!r})\ntry:\n    print('PASS' if p.{fn}() else 'FAIL')\nexcept Exception as e:\n    print('FAIL', type(e).__name__, str(e)[:400])"
    r = subprocess.run(["uv", "run", "--frozen", "--project", str(src), "python", "-c", code], cwd=d,
                       capture_output=True, text=True)
    return (r.stdout + r.stderr).strip().splitlines()[-6:]


for pin in pins:
    fn = {"P37": "p37_nethack_utility", "P39": "p39_minihack_ladder", "P38": "p38_nethack_manifest"}[pin]
    d = copy([])
    print(pin, "clean:", run(d, fn), flush=True)
    shutil.rmtree(d)
    for m in sorted((src / "harness/edits").glob(f"{pin}_*.toml")):
        d = copy(tomllib.loads(m.read_text())["edit"])
        print(pin, m.stem, ":", run(d, fn), flush=True)
        shutil.rmtree(d)
