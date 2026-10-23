"""Session witness: run a pin's check in a scratch copy of the tree, clean and under each of its mutants' edits."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1])
PINS = sys.argv[2:]
CHECK = """
import sys
from pathlib import Path
from harness import context, pins
context.scratch = Path(sys.argv[2])
print("RESULT", getattr(pins, sys.argv[1])())
"""


def run(tree: Path, fn: str) -> str:
    scratch = Path(tempfile.mkdtemp(prefix="wit-"))
    out = subprocess.run([str(ROOT / ".venv/bin/python"), "-B", "-c", CHECK, fn, str(scratch)], cwd=tree,
                         capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "HOME": str(scratch)})
    fails = [l for l in out.stdout.splitlines() if "[FAIL]" in l]
    last = (out.stdout.strip().splitlines() or [out.stderr.strip()[-300:]])[-1]
    return f"{last} {fails[:2]}" if out.returncode == 0 else f"ERROR rc={out.returncode} {out.stderr.strip()[-300:]}"


sys.path.insert(0, str(ROOT))
from harness import edits, pins  # noqa: E402

for p in pins.REGISTRY if hasattr(pins, "REGISTRY") else []:
    pass
registry = next(v for k, v in vars(pins).items() if isinstance(v, list) and v and type(v[0]).__name__ == "Pin")
for pin in (p for p in registry if p.name in PINS):
    fn = pin.check.__name__
    with tempfile.TemporaryDirectory() as d:
        tree = Path(d) / "t"
        shutil.copytree(ROOT, tree, ignore=shutil.ignore_patterns(".venv", "out", ".git", "__pycache__"))
        print(pin.name, "clean:", run(tree, fn), flush=True)
    for m in pin.mutants:
        with tempfile.TemporaryDirectory() as d:
            tree = Path(d) / "t"
            shutil.copytree(ROOT, tree, ignore=shutil.ignore_patterns(".venv", "out", ".git", "__pycache__"))
            edits.apply(tree, edits.load(m.edits) if isinstance(m.edits, str) else m.edits)
            print(pin.name, m.name, "mutant:", run(tree, fn), flush=True)
