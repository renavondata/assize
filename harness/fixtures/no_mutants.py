from harness.fixtures.toy import OFF_BY_ONE, check_toy, toy_pin
from harness.pin import Pin

PINS = [toy_pin(OFF_BY_ONE), Pin("fixture/bare", "declares no mutants (seeded defect)", check_toy, ())]
