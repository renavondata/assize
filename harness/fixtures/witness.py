"""fixture.witness (instruction #108 item 5): three toy pins witnessing `src/a/**`, everything, and `docs/**`."""

from harness.fixtures.toy import OFF_BY_ONE, check_toy
from harness.pin import ALWAYS, Pin

PINS = [Pin("fixture/a", "toy addition, witnessing src/a/", check_toy, (OFF_BY_ONE,), ("src/a/**",)),
        Pin("fixture/all", "toy addition, witnessing every path", check_toy, (OFF_BY_ONE,), ALWAYS),
        Pin("fixture/docs", "toy addition, witnessing docs/", check_toy, (OFF_BY_ONE,), ("docs/**",))]
