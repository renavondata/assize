"""A pin over `stamped.VALUE` whose clean run alone meets stale bytecode, for P0bp's single-defence case.

P0bp arms this tree with a cache of the unedited module, then edits the module itself to 5. The clean run is made in the
tree, not in a disposable copy, so the copy's cache exclusion does not stand between the cache and the verdict: only the
child's cache prefix does."""

from harness.pin import ALWAYS, Mutant, Pin

HEAD_MUTANT = Mutant("head_value", "harness/fixtures/edits/stamped_head_mutant.toml")


def check_stamped_head() -> bool:
    from harness.fixtures import stamped

    print(f"stamped.VALUE = {stamped.VALUE} ({stamped.__file__})")
    return stamped.VALUE == 5


PINS = [Pin("fixture/stamp_head", "the stamped value in the tree is 5", check_stamped_head, (HEAD_MUTANT,), ALWAYS)]
