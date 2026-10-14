"""What makes a directory judge-private storage (L1 obligation 6, review 02a71436d9ff F3).

The directory is the judge's own and has no group or other bits, and so is every entry in it: a 0644 file inside a
0700 directory is readable by anyone who can reach the directory by another path (a bind mount, a descriptor, a
backup). The signing key, the credentials, the registrations and the seed store share this rule, one place.
"""
import os
import stat
from pathlib import Path


def findings(path: Path) -> list[str]:
    """Every way `path`, or an entry under it, is not the judge's own with no group or other bits; empty if none.
    Entries are examined without following links, so a link is reported, not trusted."""
    def bad(p: Path, st: os.stat_result) -> str | None:
        mode = stat.S_IMODE(st.st_mode)
        if st.st_uid != os.getuid() or mode & 0o077 or stat.S_ISLNK(st.st_mode):
            return f"{p} is mode {mode:o}, owner {st.st_uid}{', a link' if stat.S_ISLNK(st.st_mode) else ''}"
        return None

    entries = [path, *sorted(path.rglob("*"))]
    return [f for p in entries if (f := bad(p, p.lstat()))]
