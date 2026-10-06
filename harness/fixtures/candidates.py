"""Fixture candidates for P3, P7 and P10: each a Python program run as `python -I -c <source>` in the judge's candidate
base image, speaking the judge's JSON-RPC over stdio. `BEHAVIOUR` says what each does at its first step; at
begin_episode and end_episode every one acknowledges, keeping the manifest's `targets` from begin_episode."""

from __future__ import annotations

_LOOP = """
import json, os, signal, sys, time

def reply(rid, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}) + "\\n")
    sys.stdout.flush()

targets = []
for line in sys.stdin:
    msg = json.loads(line)
    if msg["method"] == "begin_episode":
        targets = msg["params"]["manifest"]["targets"]
    if msg["method"] != "step":
        reply(msg["id"], {})
        continue
    p = msg["params"]
"""

# Each behaviour is the body of the step branch, with `msg` the request and `p` its params.
BEHAVIOUR = {
    # Plays the first legal action at every step.
    "polite": 'reply(msg["id"], {"action": p["legal_actions"][0]})',
    # Exits with status 3 at its first step.
    "crash": "sys.exit(3)",
    # Answers its first step with a line that is not JSON.
    "garbled": 'sys.stdout.write("not json\\n"); sys.stdout.flush()',
    # Answers with a well-formed action outside legal_actions.
    "illegal": 'reply(msg["id"], {"action": max(p["legal_actions"]) + 1})',
    # Replies to every step, each after a pause, so that only the episode's deadline can end it early.
    "slow": 'time.sleep(0.5); reply(msg["id"], {"action": p["legal_actions"][0]})',
    # P7: plays the first legal action and predicts every target but the last from its field's current value v:
    # target i puts all mass on v if i % 3 == 0, none on v and the rest uniformly if i % 3 == 1, and is uniform if
    # i % 3 == 2. Unchanged values thus score 0, +inf and ln n; the last target is missing.
    "forecaster": ("pred = {}\n"
                   "    for i, tg in enumerate(targets[:-1]):\n"
                   "        s, v = tg['support'], p['observation'][tg['field']]\n"
                   "        pred[tg['name']] = [[float(x == v) for x in s], [0.0 if x == v else 1 / (len(s) - 1) for x in s],\n"
                   "                            [1 / len(s)] * len(s)][i % 3]\n"
                   "    reply(msg['id'], {'action': p['legal_actions'][0], 'prediction': pred})"),
    # P7: predicts a target the manifest does not declare.
    "undeclared": 'reply(msg["id"], {"action": p["legal_actions"][0], "prediction": {"undeclared": [0.5, 0.5]}})',
    # P7: predicts the first target with one probability fewer than its support, uniformly.
    "short": ('n = len(targets[0]["support"]) - 1\n'
              '    reply(msg["id"], {"action": p["legal_actions"][0], "prediction": {targets[0]["name"]: [1 / n] * n}})'),
    # P7: predicts the first target with all probabilities zero, which sum to zero, not one.
    "zeros": ('n = len(targets[0]["support"])\n'
              '    reply(msg["id"], {"action": p["legal_actions"][0], "prediction": {targets[0]["name"]: [0.0] * n}})'),
    # P7: predicts the first target with NaN probabilities, which Python's json writes and JSON does not admit.
    "nan": ('n = len(targets[0]["support"])\n'
            '    reply(msg["id"], {"action": p["legal_actions"][0], "prediction": {targets[0]["name"]: [float("nan")] * n}})'),
    # Ignores SIGTERM, starts a child that ignores it too, and never replies: only a forced kill ends it (P10).
    "stubborn": ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                 "    if os.fork() == 0:\n"
                 "        os.setsid()\n"
                 "        while True: time.sleep(60)\n"
                 "    while True: time.sleep(60)"),
}


def command(behaviour: str) -> list[str]:
    return ["python", "-I", "-c", _LOOP + "    " + BEHAVIOUR[behaviour] + "\n"]
