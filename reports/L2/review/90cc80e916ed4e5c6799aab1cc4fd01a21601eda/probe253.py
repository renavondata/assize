import sys, tempfile, tomllib, subprocess
from pathlib import Path
sys.path.insert(0, ".")
from harness import pins
from harness import context
context.scratch = Path(tempfile.mkdtemp(prefix="p253-"))
def run():
    import importlib, harness.ledger as L
    importlib.reload(L)
    try: return pins.p0bi_open_count()
    except Exception as e: return f"EXC {type(e).__name__}: {e}"
print("clean", run())
for m in ("resolves_unread","skipped_unnamed","legacy_unnamed"):
    spec = tomllib.loads(Path(f"harness/edits/P0bi_{m}.toml").read_text())
    p = Path("harness/ledger.py"); orig = p.read_text(); s = orig
    for e in spec["edit"]:
        assert e["old"] in s, m
        s = s.replace(e["old"], e["new"], 1)
    p.write_text(s)
    try: r = run()
    finally: p.write_text(orig)
    print(m, r)
