#!/usr/bin/env python3
"""merge.py — merge alive.json results from multiple runs into one."""
import json
import sys
from pathlib import Path

out = {}
for d in sys.argv[1:]:
    f = Path(d) / "alive.json"
    if not f.exists():
        print(f"[!] {f} missing")
        continue
    for r in json.loads(f.read_text()):
        key = (r["protocol"], r["ip"], r["port"])
        # keep the one with lower latency
        if key not in out or r["latency_ms"] < out[key]["latency_ms"]:
            out[key] = r

merged = sorted(out.values(), key=lambda r: r["latency_ms"])
print(f"[*] merged alive: {len(merged)}")

Path("proxylist").mkdir(exist_ok=True)
(Path("proxylist") / "alive.json").write_text(json.dumps(merged, indent=2))
(Path("proxylist") / "alive.txt").write_text(
    "\n".join(f"{r['ip']}:{r['port']}" for r in merged) + "\n"
)
from collections import defaultdict
by_proto = defaultdict(list)
by_cc = defaultdict(list)
for r in merged:
    by_proto[r["protocol"]].append(f"{r['ip']}:{r['port']}")
    by_cc[r["cc"]].append(f"{r['ip']}:{r['port']}")
for proto, lines in by_proto.items():
    (Path("proxylist") / f"{proto}.txt").write_text("\n".join(lines) + "\n")
ccdir = Path("proxylist") / "by-country"
ccdir.mkdir(exist_ok=True)
for cc, lines in by_cc.items():
    (ccdir / f"{cc}.txt").write_text("\n".join(lines) + "\n")
print("[*] saved to proxylist/")
