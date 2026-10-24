"""One NetHack 3.6.6 episode (NLE v0.7.3's NetHackChallenge), driven over stdin and stdout, one JSON object per line.

Runs inside the image `Containerfile` builds, under Python 3.9, with no network. The first line read is
`{"core": <int>, "disp": <int>}`, the game's two RNG seeds; NLE v0.7.3 has no level-generator stream. The episode is
reset and its observation written. Each further line is `{"action": <int>}`: the action is played and the
observation written, with `done` and `end_status`, until the episode ends. Every observation carries each key of `KEYS`
as nested lists.

NetHackChallenge locks its game's seeds on the instance; this deletes the three instance attributes, restoring the
package's own methods, and seeds through `nle.env.base.NLE.seed` with NetHack's anti-automation reseeding off, as
`worlds/nethack/binding.py` does for 3.6.7. The game's clock is frozen by `faketime`, the image's entrypoint, at the
instant the caller names, so moon phase, Friday the 13th and night do not come from the day it is played on."""

import json
import sys

from nle.env.base import NLE
from nle.env.tasks import NetHackChallenge

# Every observation key NLE v0.7.3 emits but the colour arrays.
KEYS = ("glyphs", "chars", "message", "blstats", "inv_glyphs", "inv_letters", "inv_oclasses", "inv_strs", "misc",
        "specials", "tty_chars", "tty_cursor")
LOCKS = ("set_initial_seeds", "set_current_seeds", "get_current_seeds")


def write(record):
    sys.stdout.write(json.dumps(record, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main():
    seeds = json.loads(sys.stdin.readline())
    env = NetHackChallenge(observation_keys=KEYS)
    for lock in LOCKS:
        delattr(env.env, lock)
    NLE.seed(env, seeds["core"], seeds["disp"], False)
    obs = env.reset()
    write({"observation": {k: obs[k].tolist() for k in KEYS}, "done": False, "end_status": 0})
    for line in sys.stdin:
        obs, _, done, info = env.step(int(json.loads(line)["action"]))
        write({"observation": {k: obs[k].tolist() for k in KEYS}, "done": bool(done),
               "end_status": int(info["end_status"])})
        if done:
            break
    env.close()


if __name__ == "__main__":
    main()
