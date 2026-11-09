const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const cls = (s) => (s === "n/a" ? "na" : s);

const DEFAULT_INPUTS = [
  {
    "text": "ABU DHABI, 4th March, 2026 (WAM) -- The National Centre of Meteorology (NCM) has warned of active northwesterly winds affecting various areas across the UAE, expected to be fresh to strong at times, causing blowing dust and sand and reducing horizontal visibility to less than 2,000 metres in some coastal and inland areas. The centre stated that the expected weather conditions began at 14:55 and continue until 19:00 this evening. It urged members of the public to exercise caution, especially while driving on open roads, due to the possibility of reduced horizontal visibility caused by blowing dust.",
    "verified": true,
    "source": "NCM via WAM, 4 Mar 2026"
  },
  {
    "text": "Social media post: a dam near Al Ain has burst, everyone leave the area now",
    "verified": false,
    "source": "illustrative rumour (not real)"
  }
];

function inputRow(item) {
  const div = document.createElement("div");
  div.className = "row";
  div.innerHTML = `<textarea class="in-text">${esc(item.text)}</textarea>
    <label style="flex:0 1 220px"><input type="checkbox" class="in-ver" style="width:auto" ${item.verified ? "checked" : ""}> verified source<br>
    <input class="in-src" value="${esc(item.source)}"></label>`;
  return div;
}
DEFAULT_INPUTS.forEach((i) => $("inputs").appendChild(inputRow(i)));
$("add").onclick = () => $("inputs").appendChild(inputRow({ text: "", verified: true, source: "" }));

async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return r.json();
}

function verdictTable(vs) {
  return `<table><tr><th>Rule</th><th>Result</th><th>Why</th><th>Source</th></tr>${vs.map((v) => `
    <tr><td>${esc(v.rule)} ${esc(v.title)}</td><td class="${cls(v.status)}">${esc(v.status)}</td><td>${esc(v.detail)}</td>
    <td>${v.sources.map((s) => s.url ? `<details><summary>${esc(s.id)}</summary><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title || s.id)}</a>${s.quote ? `<br>“${esc(s.quote)}”` : ""} <span class="muted">(${esc(s.status)})</span></details>` : esc(s.id)).join("")}</td></tr>`).join("")}</table>`;
}

const POSITION = { agree: "agrees", object: "objects", escalate: "escalates to a person" };

function evidence(e) {
  if (e.kind === "clause") {
    return `<li>“${esc(e.quote)}” <span class="muted">(${e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title || e.ref)}</a>` : esc(e.title || e.ref)}, ${esc(e.locator || "")}; clause ${esc(e.ref)})</span></li>`;
  }
  return `<li>“${esc(e.quote)}” <span class="muted">(from the ${esc(e.ref)} it was shown)</span></li>`;
}

function reviewsBlock(inst) {
  if (!inst || !inst.rounds || !inst.rounds.length) return "";
  const rounds = inst.rounds.map((rd) => `<h4>Round ${rd.round}${rd.round > 1 ? " (after the redraft)" : ""}</h4>
    <table><tr><th>Reviewer (sees only)</th><th>Position</th><th>Objections, each with a quote checked word for word</th><th>Searched the knowledge base for</th></tr>
    ${rd.reviews.map((r) => `<tr><td><strong>${esc(r.name)}</strong><br><span class="muted">stands in for ${esc(r.stands_for)}</span></td>
      <td class="${r.position === "agree" ? "pass" : "pending"}">${esc(POSITION[r.position] || r.position)}</td>
      <td>${r.objections.length ? r.objections.map((o) => `<p><strong>${esc(o.issue)}</strong> <span class="muted">[${esc(o.field)}${o.blocking ? ", blocking" : ""}]</span><br>Fix: ${esc(o.fix)}</p><ul>${o.evidence.map(evidence).join("")}</ul>
        <p class="muted">UAE text on this: ${o.uae_basis && o.uae_basis.status === "cites_uae" ? `“${esc(o.uae_basis.quote)}” (${esc(o.uae_basis.title || o.uae_basis.ref)})` : "none found in the UAE texts searched"}</p>`).join("") : `<span class="muted">${esc(r.summary)}</span>`}
        ${r.dropped.length ? `<p class="muted">${r.dropped.length} objection(s) dropped: no quote matched word for word.</p>` : ""}
        ${r.no_basis.length ? `<p class="muted">No clause found to back: ${r.no_basis.map((n) => esc(n.concern)).join("; ")}</p>` : ""}</td>
      <td><span class="muted">${r.queries.map(esc).join("<br>")}</span><details><summary>${r.clauses.length} clauses read</summary>${r.clauses.map((c) => `<div class="muted">${esc(c.id)} · ${esc(c.title)} ${esc(c.locator || "")} · score ${c.score}</div>`).join("")}</details></td></tr>`).join("")}</table>`).join("");
  return `<h3>Institution reviewers</h3>
    <p class="muted">Four agents, each standing in for a body with its own view of the alert. They search the knowledge base themselves and must quote what they rely on; code checks every quote. They cannot approve: their objections go back to the drafter once, and any left open go to the people below.</p>
    ${rounds}${(inst.notes || []).map((n) => `<p class="muted">${esc(n)}</p>`).join("")}`;
}

const DECISION_TEXT = { release: "Cleared for broadcast", waiting: "Waiting for people to approve", blocked: "Blocked" };

let state = null;
$("draft").onclick = async () => {
  const inputs = [...$("inputs").children].map((d) => ({
    text: d.querySelector(".in-text").value, verified: d.querySelector(".in-ver").checked, source: d.querySelector(".in-src").value,
  }));
  $("draftStatus").textContent = "Drafting and reviewing (up to about 90 seconds for new text; the prefilled example is instant)…";
  $("draftOut").innerHTML = "";
  const res = await post("/api/draft", { inputs, zone: $("zone").value, exercise: $("exercise").checked });
  $("draftStatus").textContent = "";
  if (res.error) { $("draftOut").innerHTML = `<p class="fail">${esc(res.error)}</p>`; return; }
  state = res.state;
  const f = res.fields;
  const ar = (res.versions || []).find((v) => v.language.startsWith("ar"));
  $("draftOut").innerHTML = `
    <div class="row"><div><h3>English draft</h3><p><strong>${esc(f.headline)}</strong><br>${esc(f.description)}<br><em>${esc(f.instruction)}</em></p>
      <p class="muted">${esc(f.status)} · ${esc(f.severity)} · ${esc(f.urgency)}${res.attempts > 1 ? ` · redrafted ${res.attempts - 1} time(s) after gate feedback or reviewer objections` : ""}</p>
      ${f.left_out?.length ? `<p class="muted">Left out: ${esc(f.left_out.join("; "))}</p>` : ""}
      <p class="muted">Note for the approver: ${esc(f.note_for_reviewer)}</p></div>
    ${ar ? `<div><h3>Arabic (${ar.method === "template" ? "vetted template " + esc(ar.template_id) : "machine translated"})</h3><p class="ar"><strong>${esc(ar.headline)}</strong><br>${esc(ar.description)}<br><em>${esc(ar.instruction)}</em></p></div>` : ""}</div>
    <p class="decision ${res.decision === "release" ? "pass" : res.decision === "blocked" ? "fail" : "pending"}">Gate: ${DECISION_TEXT[res.decision]}</p>
    ${verdictTable(res.verdicts)}
    ${reviewsBlock(res.institutions)}
    <h3>Approve</h3>
    ${res.institutions && res.institutions.open_objections.length ? `<p class="pending">${res.institutions.open_objections.length} objection(s) still open. The approvers must read them before release.</p>
      <label><input type="checkbox" id="ack" style="width:auto"> I have read the open objections and still approve</label>` : ""}
    <p class="muted">A high-impact alert needs two different people. Machine-translated Arabic also needs someone who reads Arabic to approve the wording.</p>
    <div class="row"><label>Duty officer name<input id="a1" placeholder="name"></label><label>Supervisor name<input id="a2" placeholder="name"></label>
    ${ar && ar.method === "machine" ? `<label>Arabic wording approved by<input id="a3" placeholder="name"></label>` : ""}</div>
    <button id="approve">Approve, sign and run the final check</button>
    <div id="releaseOut"></div>
    <details><summary>CAP XML (before approval)</summary><pre>${esc(res.xml)}</pre></details>`;
  $("approve").onclick = approve;
};

async function approve() {
  const approvals = [
    { name: $("a1").value, role: "duty-officer", scope: "release" },
    { name: $("a2").value, role: "supervisor", scope: "release" },
  ];
  if ($("a3")) approvals.push({ name: $("a3").value, role: "arabic-reviewer", scope: "language:ar" });
  const res = await post("/api/approve", { state, approvals, ack_objections: $("ack") ? $("ack").checked : false });
  if (res.error) { $("releaseOut").innerHTML = `<p class="fail">${esc(res.error)}</p>`; return; }
  $("releaseOut").innerHTML = `<p class="decision ${res.decision === "release" ? "pass" : "fail"}">Final check: ${DECISION_TEXT[res.decision]}${res.objections_unacknowledged ? " (open objections not yet read by an approver)" : ""}</p>
    ${verdictTable(res.verdicts)}
    <details open><summary>Audit log (${res.log.length} records; ${esc(res.log_check)})</summary><pre>${esc(res.log.map((r) => `${r.seq} ${r.actor} ${r.action} ${r.hash.slice(0, 12)} ← ${r.prev.slice(0, 12)}`).join("\n"))}</pre></details>
    <details><summary>Signed CAP XML</summary><pre>${esc(res.xml)}</pre></details>`;
}

$("check").onclick = async () => {
  $("checkOut").innerHTML = $("review").checked ? `<p class="muted">Checking, and asking the reviewers…</p>` : "";
  const res = await post("/api/check", { xml: $("xml").value, profile: $("profile").value, review: $("review").checked });
  $("checkOut").innerHTML = res.error ? `<p class="fail">${esc(res.error)}</p>` :
    `<p class="decision">${DECISION_TEXT[res.decision]}</p>${verdictTable(res.verdicts)}
     ${res.reviews ? reviewsBlock({ rounds: [{ round: 1, reviews: res.reviews }], notes: [] }) : ""}
     ${res.review_error ? `<p class="fail">${esc(res.review_error)}</p>` : ""}`;
};

fetch("/web/results/bench.json").then((r) => r.json()).then((b) => {
  $("bench").innerHTML = `<table><tr><th>Incident</th><th>What happened</th><th>As sent: gate result</th><th>Rules that fired</th><th>Official finding</th><th>Match?</th><th>Agents alone on the real message</th><th>AI drafter on the same inputs</th></tr>
  ${b.incidents.map((i) => `<tr><td>${esc(i.title)}<br><span class="muted">${esc(i.date)}${i.heldout ? " · held out" : ""}</span></td><td>${esc(i.outcome)}</td>
    <td class="${i.as_sent.decision === "blocked" ? "fail" : "pass"}">${esc(i.as_sent.decision)}</td>
    <td>${esc(i.as_sent.failed.join(", "))}</td><td>${esc(i.finding.body)}: “${esc(i.finding.quote)}”</td>
    <td>${i.match ? "yes" : "no"} <span class="muted">(expected ${esc(i.expected.join(", "))})</span></td>
    <td>${i.agents_on_real ? (i.agents_on_real.length ? "named " + esc(i.agents_on_real.join(", ")) : "missed") : "not run"}</td>
    <td>${i.ai ? esc(i.ai.summary) : "not run"}</td></tr>`).join("")}</table>
  <p class="muted">${esc(b.note || "")}</p>`;
}).catch(() => { $("bench").textContent = "Replay results not built yet."; });

fetch("/web/results/audit.json").then((r) => r.json()).then((a) => {
  $("auditOut").innerHTML = `<p>${esc(a.headline)}</p><table><tr><th>Source</th><th>Alerts</th><th>Any AI marker</th><th>Any approver marker</th><th>Signed</th></tr>
  ${a.rows.map((r) => `<tr><td>${esc(r.source)}</td><td>${r.alerts}</td><td>${r.ai}</td><td>${r.approver}</td><td>${r.signed}</td></tr>`).join("")}</table>
  <p class="muted">${esc(a.note || "")}</p>`;
}).catch(() => { $("auditOut").textContent = "Audit results not built yet."; });

fetch("/web/results/ablation.json").then((r) => r.json()).then((a) => {
  const s = a.summary;
  const mark = (x) => (x ? `<td class="pass">named</td>` : `<td class="fail">missed</td>`);
  $("ablationOut").innerHTML = `<table><tr><th>Setup</th><th>Faults named before broadcast (of ${s.cases})</th></tr>
    <tr><td>No checks (AI pipeline alone)</td><td>0</td></tr>
    <tr><td>12 rules only</td><td>${s.named.rules}</td></tr>
    <tr><td>4 institution agents only</td><td>${s.named.agents}</td></tr>
    <tr><td>Rules and agents</td><td>${s.named.both}</td></tr></table>
    <p>Only the agents named: ${esc(s.only_agents.join(", ") || "none")}. Only the rules named: ${esc(s.only_rules.join(", ") || "none")}. Neither: ${esc(s.neither.join(", ") || "none")}.</p>
    <p class="muted">On the ${s.clean_drafts} clean drafts (no fault) the agents raised ${s.clean_objections} objection(s) in ${s.clean_drafts_with_objection} draft(s). ${s.dropped_for_bad_quotes} objection(s) in the fault runs were dropped because their quote did not match word for word.</p>
    <details><summary>Every case</summary><table><tr><th>Fault</th><th>Copies</th><th>Scenario</th><th>Rules</th><th>Agents</th></tr>
    ${a.cases.map((c) => `<tr><td>${esc(c.fault)} ${esc(c.title)}</td><td>${esc(c.copies)}</td><td>${esc(c.scenario)}</td>
      ${c.rules_named.length ? `<td class="pass">${esc(c.rules_named.join(", "))}</td>` : mark(false)}
      ${c.agents_named.length ? `<td class="pass">${c.agents_named.map((h) => esc(h.by + ": " + h.issue)).join("<br>")}</td>` : mark(false)}</tr>`).join("")}</table></details>
    <p class="muted">${esc(a.note)}</p>`;
}).catch(() => { $("ablationOut").textContent = "Ablation results not built yet."; });

$("feedBtn").onclick = async () => {
  $("feedStatus").textContent = "Fetching the feed…";
  $("feedOut").innerHTML = "";
  const r = await post("/api/feed", { feed: $("feed").value });
  $("feedStatus").textContent = "";
  if (r.error) { $("feedOut").innerHTML = `<p class="fail">${esc(r.feed || "")} ${esc(r.error)}</p>`; return; }
  $("feedOut").innerHTML = `<p><strong>${esc(r.feed)}</strong>: ${r.checked} alert(s) checked${r.unreadable ? `, ${r.unreadable} could not be fetched` : ""}.
    Held: ${r.held}. Signed: ${r.signed}. Record AI involvement or an approver: ${r.with_ai_or_approver_record}.
    Too long for one cell broadcast message as written: ${r.too_long_for_cell_broadcast}.</p>
    <table><tr><th>Alert</th><th>Sent</th><th>Status / type</th><th>Languages</th><th>Result</th></tr>
    ${r.alerts.map((a) => a.error ? `<tr><td colspan="5" class="muted">${esc(a.link)}: ${esc(a.error)}</td></tr>` :
      `<tr><td>${esc(a.headline || a.event || a.identifier)}</td><td>${esc(a.sent)}</td><td>${esc(a.status)} / ${esc(a.msgType)}</td><td>${esc(a.languages.join(", "))}</td>
       <td class="${a.failed.length ? "fail" : "pass"}">${a.failed.length ? "held: " + esc(a.verdicts.filter((v) => a.failed.includes(v.rule)).map((v) => v.rule + " " + v.detail).join("; ")) : "passes these rules"}${a.too_long_for_cell_broadcast ? `<br><span class="muted">note: over 15 cell broadcast pages as written</span>` : ""}</td></tr>`).join("")}</table>
    <p class="muted">${esc(r.note)}</p>`;
};

fetch("/web/results/ablation-prereg.json").then((r) => r.json()).then((a) => {
  const s = a.summary;
  $("preregOut").innerHTML = `<table><tr><th>Setup</th><th>Faults named before broadcast (of ${s.cases})</th></tr>
    <tr><td>No checks</td><td>0</td></tr><tr><td>12 rules only</td><td>${s.named.rules}</td></tr>
    <tr><td>4 institution agents only</td><td>${s.named.agents}</td></tr><tr><td>Rules and agents</td><td>${s.named.both}</td></tr></table>
    <p>Missed by both: ${esc(s.neither.join(", ") || "none")}.</p>
    <details><summary>Every case</summary><table><tr><th>Fault</th><th>Scenario</th><th>Rules</th><th>Agents</th></tr>
    ${a.cases.map((c) => `<tr><td>${esc(c.fault)} ${esc(c.title)}</td><td>${esc(c.scenario)}</td>
      <td class="${c.rules_named.length ? "pass" : "fail"}">${esc(c.rules_named.join(", ") || "missed")}</td>
      <td class="${c.agents_named.length ? "pass" : "fail"}">${c.agents_named.length ? c.agents_named.map((h) => esc(h.by + ": " + h.issue)).join("<br>") : "missed"}</td></tr>`).join("")}</table></details>
    <p class="muted">${esc(a.note)}</p>`;
}).catch(() => { $("preregOut").textContent = "Not built yet."; });
