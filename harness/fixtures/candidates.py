"""Fixture candidates for P3 and P10: each a Python program run as `python -I -c <source>` in the judge's candidate
base image, speaking the judge's JSON-RPC over stdio. `BEHAVIOUR` says what each does at its first step; at
begin_episode and end_episode every one acknowledges."""

from __future__ import annotations

_LOOP = """
import json, os, signal, sys, time

def reply(rid, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}) + "\\n")
    sys.stdout.flush()

for line in sys.stdin:
    msg = json.loads(line)
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
    # Ignores SIGTERM, starts a child that ignores it too, and never replies: only a forced kill ends it (P10).
    "stubborn": ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                 "    if os.fork() == 0:\n"
                 "        os.setsid()\n"
                 "        while True: time.sleep(60)\n"
                 "    while True: time.sleep(60)"),
}


def command(behaviour: str) -> list[str]:
    return ["python", "-I", "-c", _LOOP + "    " + BEHAVIOUR[behaviour] + "\n"]
