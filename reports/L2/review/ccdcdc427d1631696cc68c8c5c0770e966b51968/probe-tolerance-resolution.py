"""Review probe for PR #197 (P27): how finely does P27 pin the sum tolerance?

For each candidate `tolerance(n)` body, copy the reviewed tree (no .git, .venv, out) to a scratch directory, replace the
tolerance line of judge/scoring.py exactly as the harness's edit files do, and run `harness.pins.p27_sum_tolerance` in a
subprocess with PYTHONPATH at the scratch copy. Prints pass/fail per variant; a variant other than the clean one that
passes is a tolerance P27 cannot tell from the derived bound. Also prints, per declared support size, the largest
deviation from one (in epsilons) that a naive-sum softmax reaches over more seeded trials than the pin uses.

Usage: python probe-tolerance-resolution.py <reviewed tree> <scratch parent>
"""
import math
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OLD = "    return n * sys.float_info.epsilon\n"
VARIANTS = {
    "clean (n*eps)": OLD,
    "1.5*n*eps": "    return 1.5 * n * sys.float_info.epsilon\n",
    "(n+1)*eps": "    return (n + 1) * sys.float_info.epsilon\n",
    "2*n*eps": "    return 2 * n * sys.float_info.epsilon\n",
    "0.5 (tolerance_loose)": "    return 0.5\n",
    "0 (tolerance_zero)": "    return 0\n",
}
RUNNER = "import sys\nfrom harness.pins import p27_sum_tolerance\nsys.exit(0 if p27_sum_tolerance() else 1)\n"


def scratch_copy(tree: Path, parent: Path) -> Path:
    dst = Path(tempfile.mkdtemp(prefix="review197-probe-", dir=parent))
    shutil.copytree(tree, dst / "tree", ignore=shutil.ignore_patterns(".git", ".venv", "out", "__pycache__"))
    return dst


def run_variant(tree: Path, parent: Path, body: str) -> tuple[int, str]:
    d = scratch_copy(tree, parent)
    try:
        f = d / "tree" / "judge" / "scoring.py"
        text = f.read_text()
        assert text.count(OLD) == 1, "tolerance line not found exactly once"
        f.write_text(text.replace(OLD, body))
        r = subprocess.run([sys.executable, "-c", RUNNER], cwd=d / "tree", capture_output=True, text=True,
                           env={"PYTHONPATH": str(d / "tree"), "PATH": "/usr/bin:/bin", "HOME": str(d)}, timeout=300)
        return r.returncode, r.stdout + r.stderr
    finally:
        shutil.rmtree(d)


def worst_naive_softmax(n: int, trials: int, seed: int, logit: float) -> float:
    rng = random.Random(seed)
    eps = sys.float_info.epsilon
    worst = 0.0
    for _ in range(trials):
        e = [math.exp(rng.uniform(-logit, logit)) for _ in range(n)]
        for order in (sorted(e), sorted(e, reverse=True), e):
            s = 0.0
            for v in order:
                s += v
            p = [v / s for v in e]
            worst = max(worst, abs(math.fsum(p) - 1) / eps)
    return worst


def main() -> None:
    tree, parent = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    print(f"tree {tree}\nscratch parent {parent}\n")
    for name, body in VARIANTS.items():
        code, out = run_variant(tree, parent, body)
        fails = [l for l in out.splitlines() if "[FAIL]" in l]
        print(f"variant {name:>24}: P27 {'PASS' if code == 0 else 'FAIL'}" + (f"; {len(fails)} FAIL lines" if fails else ""))
        for l in fails:
            print("   ", l.strip())
    print()
    for n in (2, 3, 5, 10, 20, 50, 100):
        for logit in (30.0, 300.0):
            print(f"n={n:>3} logit±{logit:>5}: worst naive softmax deviation {worst_naive_softmax(n, 2000, 10, logit):.1f}·ε "
                  f"(bound n·ε = {n}·ε)")


if __name__ == "__main__":
    main()
