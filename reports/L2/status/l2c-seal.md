# STATUS — L2 — 2026-10-22 — 1a0520c — PR #310
VERDICT: SESSION DONE: L2c in part: the judge's image is composed by digest (`sha256:c7856fe2…918259c`), recorded and held by P21; CODEOWNERS entry blocked on an admission; host verdict pending
LAYER BOUNDARY: no (per A1.3's definition: records no layer verdict in the root REPORT.md; adds or opens no brief)
pins CI run 39716530703 on 1a0520c: success (reports/L2/ci/39716530703.json)
pins: clean 97/97; mutants 319/319 KILLED; twins 319/319 (none non-causal); leaked 0; stale 0; inconclusive 0; non-causal 0; exit 0 (CI run 39716530703; local P21 only: reports/L2/build/l2c-seal/p21-local-2.txt)
changed: harness/seal.py, harness/pins.py (P21), harness/edits/P21_*.toml (4), release/seal.toml, reports/L2/REPORT.md (§L2c, appended), harness/proposer.d/l2c-seal.toml, reports/L2/{forecasts/2c0eb055-….jsonl,build/l2c-seal/,ci/39710710128.json,ci/39716530703.json,status/l2c-seal.md}
did: no signed open instruction; A3 item 1 (zero-diff pin) is held by open PR #301 (`claims next` did not detect the hold, its STATUS names the PR, not the item), so I took A3 item 2, L2c; no switchback seed, first free candidate
did: `harness.seal` composes the OCI image as bytes (judge/ of L2a baseline bcc9ac6, tree 113d9ff, one ustar layer, canonical JSON); its digest re-derives on this host's podman 6.1.2 and on ubuntu-latest's (P21 clean in CI)
did: P21 = composed digest == release/seal.toml; REPORT.md at the invocation tree records it (fixture-tested); verify in the loaded image; P0b scan of its layer. Mutants digest_misrecorded, report_unchecked, verify_omitted, image_imports_mutants, each killed by its own expectation
did: first CI run 39710710128 failed: the three mutants were STALE because copies carry no reports/. Fixed by release/seal.toml (1a0520c)
did: rule breaches by me: I appended REPORT.md §L2c with `printf >>` and changed pins.py imports with `sed -i`, both against instruction #110 (Edit/Write only); content as committed in 59fc1c5; pre-push hook not installed here, I ran `claims trailers` by hand (0 findings)
decided (not asked): started L2c while #301 is open, since A3 item 1's pin is built and only awaits merge, and L2c changes nothing under judge/ or worlds/spec/ — p(stands on review)=0.65
decided (not asked): "released" means content-addressed and re-derivable offline; a registry push needs uncompressed layers to keep the digest (skopeo copy oci:…) and Guy's credential — p=0.5
decided (not asked): CODEOWNERS left unchanged: P0bm admits a CODEOWNERS line only under an `Audit findings at <sha>` heading (harness/trusted.py:29) and none admits /judge/ or /worlds/spec/; citing 8aae43c8c792 would be false — p=0.7
decided (not asked): P21 runs under podman only (the host's runtime, CLAUDE.md); docker builds stay P31's — p=0.7
decided (not asked): `measure` label added after this STATUS push, so the host run measures this head — p=0.6
forecasts: made 4 (pins_green #310 p=0.75, review_accept #310 p=0.5, host_verdict L2 FIT p=0.35, session_minutes 90 p=0.45); resolved 0 this session; builder record (`ledger proposer builder`): 358 resolved, log-loss 191.43; base-rate loss not computed here
price: guy-items 2; guy-latency median 0.7h max 1.3h; sessions 1; runner-min 112 (`ledger price --since 3234bd5`)
obligations added: L2: A3 item 2's CODEOWNERS lines need an audit-dated admission before this PR merges; L3: P21 composes the image itself; a pulled release is not yet checked against the digest
NEEDS YOU (at most 1): sign an instruction (or dispatch an audit) that admits `/judge/ @gfrmin` and `/worlds/spec/ @gfrmin` into harness/trusted_base.toml, so this seal PR can add them to CODEOWNERS (CLAUDE.md A1.1, brief 2 A4 item 8)
next: on #310: add the CODEOWNERS lines once admitted, then record the `measure` run's Crafter verdict in reports/L2/REPORT.md §L2c
