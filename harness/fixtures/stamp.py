"""A pin over `stamped.VALUE` whose one mutant is a same-length edit, for P0bp's run through the verdict path."""

from harness.pin import ALWAYS, Mutant, Pin

SAME_LENGTH = Mutant("same_length", "harness/fixtures/edits/stamped_same_length.toml")


def check_stamped() -> bool:
    from harness.fixtures import stamped

    print(f"stamped.VALUE = {stamped.VALUE} ({stamped.__file__})")
    return stamped.VALUE == 4


PINS = [Pin("fixture/stamp", "the stamped value is 4", check_stamped, (SAME_LENGTH,), ALWAYS)]
