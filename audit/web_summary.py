"""Build web/results/audit.json from audit/results.json and audit/gate-on-real.json."""
import json
from pathlib import Path

d = json.loads(Path("audit/results.json").read_text(encoding="utf-8"))
g = json.loads(Path("audit/gate-on-real.json").read_text(encoding="utf-8"))
rows = []
for s in d["sources"]:
    live = s["groups"]["live"]
    if live["alerts"]:
        rows.append({"source": s.get("label") or s.get("source_id"), "alerts": live["alerts"],
                     "ai": live["ai_marker"], "approver": live["approver_marker"], "signed": live["with_signature"]})
total = sum(r["alerts"] for r in rows)
ai = sum(r["ai"] for r in rows)
out = {
    "headline": (f"{total:,} real public alerts from {len(rows)} feeds (snapshot {d['snapshot']}): {ai} record that AI or "
                 "machine translation was involved, and none records who approved them. The only approver-like fields "
                 "are one vendor's login names (UserName), in 17 US alerts."),
    "rows": rows,
    "gate_on_real": {"alerts": g["alerts"], "held": g["blocked_on_content_rules"], "by_rule": g["by_rule"]},
    "note": (f"The gate was also run over the {g['alerts']} US alerts using the rules that need no issuer context "
             f"(R0, R2, R6, R10): it would hold {g['blocked_on_content_rules']} ("
             + ", ".join(f"{k}: {v}" for k, v in g["by_rule"].items())
             + "). Scheduled US EAS tests sent as status Actual are exempt; that exemption was added after a first run "
               "flagged them. UAE: no CAP feed is listed on the WMO Register of Alerting Authorities (record dated 2013)."),
}
Path("web/results").mkdir(parents=True, exist_ok=True)
Path("web/results/audit.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print(out["headline"]); print(out["note"]); print(rows)
