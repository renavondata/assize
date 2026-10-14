"""Review of PR #195: a seed store written before the PR (records without `key_version`, as master's `admit` writes
them) under the same interpreter is refused by the head's `admit`; the keys it holds are the ones this interpreter
computes."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from judge import seeds
from worlds.crafter import binding

print("KEY_VERSION", seeds.KEY_VERSION, "| sys.version", sys.version.split()[0])
work = Path(tempfile.mkdtemp(prefix="review-195-"))
try:
    world, key = "crafter", binding.world_seed
    root = work / "legacy"
    seeds.issue(root, world, key, 3, "pre-pr-request")
    path = root / f"{world}.seeds.jsonl"
    recs = [json.loads(line) for line in path.read_text().splitlines()]
    legacy = [{k: v for k, v in r.items() if k != "key_version"} for r in recs]
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in legacy))
    print("legacy store: records", len(legacy), "| any key_version", any("key_version" in r for r in legacy))
    print("stored keys equal this interpreter's keys:", all(key(r["seed"]) == r["key"] for r in legacy))
    before = path.read_bytes()
    for attempt in ("post-pr-request-1", "post-pr-request-2"):
        try:
            got = seeds.issue(root, world, key, 1, attempt)
        except seeds.SeedError as e:
            got = f"SeedError {e.code}: {e}"
        print(attempt, "->", got, "| store unchanged:", path.read_bytes() == before)
finally:
    shutil.rmtree(work, ignore_errors=True)
print("scratch removed:", not work.exists())
