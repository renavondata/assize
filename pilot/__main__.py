"""Pilot subcommands (brief 1 section 5; A1 item 3).

`run PRIVATE LEDGERS RUNTIME OUT PILOT_ID`: on the measurement host only (`make measure`). Build the random incumbent's
image offline under RUNTIME, issue its proposer (`[incumbent]` of `config.toml`) a credential and register the image
under it in the judge-private storage PRIVATE, then play the committed pilot through `evaluate()`, the ledger in
LEDGERS, under request ids `pilot-PILOT_ID-<k>`. Each request's records are appended to OUT/records.jsonl as they
arrive, so a pilot killed from outside leaves what it recorded; at the end the ledger is verified and the report is
written to OUT/report.json and OUT/report.md and printed. Exit 0 if and only if the report carries a verdict.
`smoke PRIVATE LEDGERS RUNTIME OUT PILOT_ID N`: the same with N <= 10 episodes (`make smoke`); its report is marked
not evidence, whatever it says."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from judge import evaluate, ledger, registry, runtime, seeds
from pilot import run, timetolearn

ROOT = Path(__file__).resolve().parent.parent
USAGE = ("usage: python -m pilot run PRIVATE LEDGERS RUNTIME OUT PILOT_ID | "
         "smoke PRIVATE LEDGERS RUNTIME OUT PILOT_ID N (N <= 10)")
SMOKE_MAX = 10  # CLAUDE.md: smoke tests of at most 10 episodes per World


def build(rt: runtime.Runtime, context: Path) -> str:
    """Build the image of `context` under `rt` with no network and no pull; return its digest `sha256:<hex>`."""
    with tempfile.TemporaryDirectory() as d:
        iid = Path(d) / "iid"
        subprocess.run([rt.binary, "build", "--network=none", "--pull=false", "-q", f"--iidfile={iid}",
                        "-f", str(context / "Containerfile"), str(context)], check=True, capture_output=True)
        i = iid.read_text().strip()
    return i if i.startswith("sha256:") else f"sha256:{i}"


def pilot(private: Path, ledgers: Path, rt_name: str, out: Path, pilot_id: str, cfg: dict, evidence: bool) -> int:
    world = cfg["pilot"]["world"]
    rt = evaluate._usable(rt_name)
    runtime.pull(rt, runtime.candidate_config()["base_image"])
    image = build(rt, ROOT / cfg["incumbent"]["context"])
    registry.register(private, image, registry.credential(private, cfg["incumbent"]["proposer"]))
    out.mkdir(parents=True, exist_ok=True)
    log = out / "records.jsonl"

    def progress(records) -> None:
        with log.open("a") as f:
            f.writelines(json.dumps(r, sort_keys=True) + "\n" for r in records)

    played = run.play(lambda rid, n: evaluate.evaluate(image, world, n, rid, private=private, ledgers=ledgers,
                                                       runtime_name=rt.name),
                      pilot_id, cfg, refusals=(registry.Refused, seeds.SeedError), progress=progress)
    binding = evaluate._binding(world)
    targets = [t["name"] for t in binding.manifest()["targets"]]
    rep = run.report(played, cfg, targets, list(binding.crafter.constants.achievements), binding.hafner_score,
                     evidence=evidence)
    findings = (ledger.verify(evaluate.ledger_path(ledgers, world), private, played.records[-1]["sha256"])
                if played.records else ["no request returned a record, so no head anchors the ledger's verification"])
    rep = rep | {"pilot_id": pilot_id, "ledger_findings": findings}
    if findings and not rep["verdict"].startswith("STOPPED"):
        rep["verdict"] = f"STOPPED: the ledger fails verification ({len(findings)} findings)"
    (out / "report.json").write_text(json.dumps(rep, sort_keys=True, indent=1) + "\n")
    text = run.render(rep)
    (out / "report.md").write_text(text)
    print(text, end="")
    return 1 if rep["verdict"].startswith("STOPPED") else 0


def main(argv: list[str]) -> int:
    cfg = timetolearn.config()
    if len(argv) == 6 and argv[0] == "run":
        args, evidence = argv[1:], True
    elif len(argv) == 7 and argv[0] == "smoke" and argv[6].isascii() and argv[6].isdigit() \
            and 1 <= int(argv[6]) <= SMOKE_MAX:
        args, evidence = argv[1:6], False
        cfg = cfg | {"pilot": cfg["pilot"] | {"episodes": int(argv[6])}}
    else:
        print(USAGE, file=sys.stderr)
        return 2
    private, ledgers, rt_name, out, pilot_id = args
    try:
        return pilot(Path(private), Path(ledgers), rt_name, Path(out), pilot_id, cfg, evidence)
    except (registry.Refused, seeds.SeedError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
