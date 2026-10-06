from harness.fixtures.toy import OFF_BY_ONE, add, toy_pin
from harness.pin import Pin

PINS = [
    toy_pin(OFF_BY_ONE),
    Pin("fixture/broken", "a clean check that fails (seeded defect)",
        lambda: add(2, 2) == 5, (OFF_BY_ONE,)),
]
