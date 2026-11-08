"""Check that a replayed bench gives the same gate outcomes as the committed results."""
import json
import sys


def key(r):
    out = {}
    for i in r["incidents"]:
        out[i["id"]] = (i["as_sent"]["decision"], sorted(i["as_sent"]["failed"]), i["match"],
                        [(x["final_decision"], sorted(x["ungoverned_violations"])) for x in (i["ai"] or {}).get("runs", [])])
    for s in r["scenarios"]:
        out[s["id"]] = [(x["final_decision"], sorted(x["ungoverned_violations"])) for x in s["runs"]]
    return out


a, b = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
ka, kb = key(a), key(b)
diff = [k for k in set(ka) | set(kb) if ka.get(k) != kb.get(k)]
for k in diff:
    print("DIFFERS", k, ka.get(k), kb.get(k))
print("same outcomes" if not diff else f"{len(diff)} differences")
sys.exit(1 if diff else 0)
