from harness import context
from harness.fixtures.toy import OFF_BY_ONE, add
from harness.pin import ALWAYS, ROOT, Pin


def check_outside() -> bool:
    """Fails whenever it runs outside the tree its orchestrator was invoked from (seeded defect)."""
    return context.invocation_root == ROOT and add(2, 2) == 4


PINS = [Pin("fixture/outside", "fails outside the invocation tree", check_outside, (OFF_BY_ONE,), ALWAYS)]
