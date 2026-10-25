"""Probe P0bu (PR #352) in memory with mutants the Builder did not name. Runs on a scratch copy only.

Usage: cd <probe clone> && PYTHONDONTWRITEBYTECODE=1 uv run --frozen python -B probe_p0bu.py <probe clone>
Each case rewrites .github/workflows/release.yml in the copy, calls the pin function directly, and restores the file.
"""
import contextlib
import io
import shutil
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
import harness.pins as pins  # noqa: E402
from harness import context  # noqa: E402

context.scratch = Path(tempfile.mkdtemp(prefix="p0bu-probe-"))
wf = root / ".github" / "workflows" / "release.yml"
orig = wf.read_text()


def reordered(t: str) -> str:
    a = t.index("      - name: Composed digest equals the seal\n")
    b = t.index("      - name: Push by digest\n")
    c = t.index("      - name: Pulled digest equals the seal\n")
    return t[:a] + t[b:c] + t[a:b] + t[c:]


CASES = {
    "control": lambda t: t,
    "push_by_tag": lambda t: t.replace('"docker://$IMAGE@$DIGEST"', '"docker://$IMAGE:latest"'),
    "steps_reordered": reordered,
    "paths_release_dropped": lambda t: t.replace('      - "release/**"\n', ""),
    "paths_judge_dropped": lambda t: t.replace('      - "judge/**"\n', ""),
    "job_permissions_added": lambda t: t.replace(
        "  release:\n    runs-on: ubuntu-latest\n",
        "  release:\n    permissions:\n      actions: write\n    runs-on: ubuntu-latest\n"),
    "compare_exit_zero": lambda t: t.replace(
        'echo "the composed digest is not the seal" >&2; exit 1; }',
        'echo "the composed digest is not the seal" >&2; exit 0; }'),
    "pulled_exit_zero": lambda t: t.replace(
        'echo "the pulled digest is not the seal" >&2; exit 1; }',
        'echo "the pulled digest is not the seal" >&2; exit 0; }'),
    "digest_from_elsewhere": lambda t: t.replace(
        "          DIGEST: ${{ steps.seal.outputs.digest }}\n          CREDS: ${{ github.actor }}:${{ github.token }}\n"
        "        run: skopeo copy",
        "          DIGEST: ${{ vars.DIGEST }}\n          CREDS: ${{ github.actor }}:${{ github.token }}\n"
        "        run: skopeo copy"),
    "if_on_push": lambda t: t.replace("      - name: Push by digest\n", "      - name: Push by digest\n        if: always()\n"),
    "output_written_on_failure": lambda t: t.replace(
        '[ -n "$sealed" ] && [ "$composed" = "$sealed" ] || { echo "the composed digest is not the seal" >&2; exit 1; }\n'
        '          echo "digest=$sealed" >> "$GITHUB_OUTPUT"',
        'echo "digest=$sealed" >> "$GITHUB_OUTPUT"\n'
        '          [ -n "$sealed" ] && [ "$composed" = "$sealed" ] || { echo "the composed digest is not the seal" >&2; exit 1; }'),
    "pulled_compares_to_itself": lambda t: t.replace('[ "$pulled" = "$DIGEST" ] || {', '[ "$pulled" = "$pulled" ] || {'),
    "composed_read_from_image_line": lambda t: t.replace("sed -n 's/^manifest //p' out/seal.txt", "sed -n 's/^image //p' out/seal.txt"),
}

for name, f in CASES.items():
    text = f(orig)
    if name != "control" and text == orig:
        print(f"{name}: EDIT DID NOT APPLY")
        continue
    wf.write_text(text)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            result = pins.p0bu_release_checks_digest()
    except Exception as e:  # noqa: BLE001
        result = f"EXC {e!r}"
    finally:
        wf.write_text(orig)
    fails = [ln.strip() for ln in out.getvalue().splitlines() if "[FAIL]" in ln]
    verdict = "pass" if result is True else ("FAIL" if result is False else result)
    print(f"{name}: {verdict}" + (f"  <- {fails[0][:140]}" if fails else ""))

shutil.rmtree(context.scratch, ignore_errors=True)
