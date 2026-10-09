# assize — layer verdicts (append-only index)

One line per layer verdict. Lines are appended, never edited.

- L0 — verdict pending the `pins.yml` witness on its PR; criteria 1, 2a, 3 met in the cloud session — [reports/L0/REPORT.md](reports/L0/REPORT.md)
- L0 — **PASSED** (cloud session and `pins.yml` on PR #2; host `measure.yml` run not witnessed, Guy to confirm) — [reports/L0/REPORT.md](reports/L0/REPORT.md#a1--2026-10-04-pinsyml-witness-verdict)
- L0 — **PASSED under brief 0 A2** (one mutation mechanism, causal twins; dev-box session and `pins.yml` at `477d477`; A1's causality claim for P0b and P0c withdrawn; host `measure.yml` run not witnessed) — [reports/L0/REPORT.md](reports/L0/REPORT.md#a2--2026-10-05-one-mutation-mechanism-brief-0-amendment-a2-verdict)
- L0 — **PASSED under brief 0 A2, with P0h** (8/8 clean, 9/9 KILLED with passing twins; brief 1 A2 inserted before A3; parent-owned scratch roots; dev-box session and `pins.yml` at `735f357`; host `measure.yml` run not witnessed) — [reports/L0/REPORT.md](reports/L0/REPORT.md#a3--2026-10-05-pre-merge-items-brief-1-a2-ordering-p0h-witness-hygiene-verdict)
- L0 — **PASSED under brief 0 A2 and A3** (F1 disposed: LEAKED verdict, fixture.escapee, P0h narrowed; 8/8 clean, 10/10 KILLED with passing twins, 0 leaked; `pins.yml` green at `f07330a`; L1 obligation recorded; host `measure.yml` run not witnessed) — [reports/L0/REPORT.md](reports/L0/REPORT.md#a4--2026-10-05-review-finding-f1-disposed-brief-0-amendment-a3-verdict)
- L1 — **SEALED; Crafter FIT; interface PROVISIONAL** (brief 1 with A1–A9; δ = 0.5 detected at 33 episodes per arm, 92 s of an 86400 s budget, host measure run 37831165785; judge_sha256 28710725…; pins CI run 37829367792 on cab0ca0, the pilot's code; pins CI run 37836660872 on af3a8ea, master's tree; P0b's added mutant witnessed in this PR) — [reports/L1/REPORT.md](reports/L1/REPORT.md)
