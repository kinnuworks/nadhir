"""Check that a replayed ablation names the same faults with the same layers as the committed one."""
import json
import sys


def key(r):
    return {(c["fault"], c["scenario"]): (sorted(c["rules_named"]), len(c["agents_named"])) for c in r["cases"]}


a, b = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
ka, kb = key(a), key(b)
diff = [k for k in set(ka) | set(kb) if ka.get(k) != kb.get(k)]
for k in diff:
    print("DIFFERS", k, ka.get(k), kb.get(k))
print("same outcomes" if not diff else f"{len(diff)} differences")
sys.exit(1 if diff else 0)
