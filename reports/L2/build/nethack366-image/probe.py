"""Determinism probe for the 3.6.6 game image: play one action stream from one seed pair under one frozen clock,
in a fresh container, and print the SHA-256 over every line the server wrote, with the step count and end."""
import hashlib
import json
import random
import subprocess
import sys

image, core, disp, clock, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], int(sys.argv[5])
rng = random.Random(f"{core}:{disp}:actions")
p = subprocess.Popen(["podman", "run", "--rm", "-i", "--network=none", "--read-only", image, clock, "python",
                      "/server.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
h = hashlib.sha256()
p.stdin.write(json.dumps({"core": core, "disp": disp}) + "\n"); p.stdin.flush()
line = p.stdout.readline(); h.update(line.encode()); rec = json.loads(line)
first_msg = bytes(rec["observation"]["message"]).rstrip(b"\0").decode()
t = 0
while not rec["done"] and t < n:
    p.stdin.write(json.dumps({"action": rng.randrange(113)}) + "\n"); p.stdin.flush()
    line = p.stdout.readline()
    if not line:
        break
    h.update(line.encode()); rec = json.loads(line); t += 1
p.stdin.close(); p.wait()
print(json.dumps({"core": core, "disp": disp, "clock": clock, "steps": t, "done": rec["done"],
                  "end_status": rec["end_status"], "sha256": h.hexdigest(), "first_message": first_msg,
                  "exit": p.returncode}))
