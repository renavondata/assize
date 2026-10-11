import sys, pathlib
sys.path.insert(0, sys.argv[1]); sys.dont_write_bytecode = True
from harness import pins
text = (pathlib.Path(sys.argv[1]) / ".github/workflows/review.yml").read_text()
cond = pins._review_condition(text)
print("condition:", cond)
cases = [
 ("reviewer labels PR needs-review", "assize-reviewer", "pull_request", "labeled", "needs-review", None, True),
 ("reviewer labels PR awaits-guy", "assize-reviewer", "pull_request", "labeled", "awaits-guy", None, False),
 ("reviewer labels PR blocked", "assize-reviewer", "pull_request", "labeled", "blocked", None, False),
 ("reviewer labels issue wish", "assize-reviewer", "issues", "labeled", "wish", None, False),
 ("reviewer labels issue needs-review", "assize-reviewer", "issues", "labeled", "needs-review", None, False),
 ("reviewer assigns issue to gfrmin", "assize-reviewer", "issues", "assigned", None, "gfrmin", False),
 ("reviewer-armed automerge push to master", "assize-reviewer", "push", None, None, None, False),
 ("builder labels PR needs-review", "assize-builder", "pull_request", "labeled", "needs-review", None, True),
 ("builder labels PR awaits-guy", "assize-builder", "pull_request", "labeled", "awaits-guy", None, True),
 ("gfrmin labels issue wish", "gfrmin", "issues", "labeled", "wish", None, True),
]
bad = 0
for what, s, e, a, l, asg, want in cases:
    ctx = {"github.event.sender.login": s, "github.event_name": e, "github.event.action": a, "github.event.label.name": l, "github.event.assignee.login": asg}
    got = pins._github_condition(cond, ctx)
    bad += got is not want
    print(f"{'ok ' if got is want else 'BAD'} {what}: starts={got} expected={want}")
print("mismatches:", bad)
