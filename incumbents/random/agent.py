"""The random incumbent (brief 1 section 4): a candidate speaking the judge's JSON-RPC 2.0 over stdio, one message per
line. At every step it plays an action drawn uniformly from `legal_actions` by the operating system's CSPRNG, so it
holds no seed and repeats nothing across containers. Its prediction is the predictive floor: for each declared target,
the add-one unigram frequencies of that target's field over its own observations of the episode so far, the current
one included, so no value of the declared support has zero mass. It reads nothing but its input and the manifest
`begin_episode` carries, and keeps nothing across episodes. Standard library only."""

import json
import random
import sys

CHOOSE = random.SystemRandom().choice


def floor(targets, seen):
    """Each target's add-one unigram frequencies over the observations `seen`, aligned with its declared support."""
    return {tg["name"]: [(1 + sum(o[tg["field"]] == x for o in seen)) / (len(tg["support"]) + len(seen))
                         for x in tg["support"]]
            for tg in targets}


def reply(rid, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}) + "\n")
    sys.stdout.flush()


def main():
    targets, seen = [], []
    for line in sys.stdin:
        msg = json.loads(line)
        if msg["method"] == "begin_episode":
            targets, seen = msg["params"]["manifest"]["targets"], []
        if msg["method"] != "step":
            reply(msg["id"], {})
            continue
        p = msg["params"]
        seen.append(p["observation"])
        reply(msg["id"], {"action": CHOOSE(p["legal_actions"]), "prediction": floor(targets, seen)})


if __name__ == "__main__":
    main()
