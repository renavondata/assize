"""Reviewer probe (PR #22 @ 2817eb7): can a party who can write the ledger and heads.jsonl, but does not hold the key,
remove the last request undetected? Drop request b's ledger bytes and its head line; run `python -m judge verify`."""
import json, subprocess, sys, tempfile
from pathlib import Path
from judge import ledger
w = Path(tempfile.mkdtemp(prefix="rev22-probe-"))
led, priv = w / "ledger.jsonl", w / "private"
ledger.append(led, priv, "req-a", [{"episode": 0, "utility": 3}, {"episode": 1, "utility": 0}])
size_a = led.stat().st_size
ledger.append(led, priv, "req-b", [{"episode": 0, "utility": 5}])
def run(tag):
    r = subprocess.run([sys.executable, "-m", "judge", "verify", str(led), str(priv)], capture_output=True, text=True)
    print(f"{tag}: exit {r.returncode}: {r.stdout.strip()}")
run("as written")
heads = (priv / "heads.jsonl").read_text().splitlines(keepends=True)
(priv / "heads.jsonl").write_text("".join(heads[:-1]))
led.write_bytes(led.read_bytes()[:size_a])
run("last request and its head removed, no key used")
(priv / "heads.jsonl").unlink(); led.unlink()
run("ledger and heads.jsonl both deleted")
import shutil; shutil.rmtree(w); print("probe dir removed:", not w.exists())
