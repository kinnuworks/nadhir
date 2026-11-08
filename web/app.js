const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const cls = (s) => (s === "n/a" ? "na" : s);

const DEFAULT_INPUTS = [
  { text: "National Center of Meteorology: blowing dust and a dust storm over Al Ain, horizontal visibility below 500 metres at times, until 18:00 today.", verified: true, source: "NCM bulletin (sample wording)" },
  { text: "Social media post: the dam near Al Ain has burst, everyone leave now", verified: false, source: "unverified social post" },
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

const DECISION_TEXT = { release: "Cleared for broadcast", waiting: "Waiting for people to approve", blocked: "Blocked" };

let state = null;
$("draft").onclick = async () => {
  const inputs = [...$("inputs").children].map((d) => ({
    text: d.querySelector(".in-text").value, verified: d.querySelector(".in-ver").checked, source: d.querySelector(".in-src").value,
  }));
  $("draftStatus").textContent = "Drafting (about 20-40 seconds)…";
  $("draftOut").innerHTML = "";
  const res = await post("/api/draft", { inputs, zone: $("zone").value, exercise: $("exercise").checked });
  $("draftStatus").textContent = "";
  if (res.error) { $("draftOut").innerHTML = `<p class="fail">${esc(res.error)}</p>`; return; }
  state = res.state;
  const f = res.fields;
  const ar = (res.versions || []).find((v) => v.language.startsWith("ar"));
  $("draftOut").innerHTML = `
    <div class="row"><div><h3>English draft</h3><p><strong>${esc(f.headline)}</strong><br>${esc(f.description)}<br><em>${esc(f.instruction)}</em></p>
      <p class="muted">${esc(f.status)} · ${esc(f.severity)} · ${esc(f.urgency)}${res.attempts > 1 ? ` · redrafted ${res.attempts - 1} time(s) after gate feedback` : ""}</p>
      ${f.left_out?.length ? `<p class="muted">Left out: ${esc(f.left_out.join("; "))}</p>` : ""}
      <p class="muted">Note for the approver: ${esc(f.note_for_reviewer)}</p></div>
    ${ar ? `<div><h3>Arabic (${ar.method === "template" ? "vetted template " + esc(ar.template_id) : "machine translated"})</h3><p class="ar"><strong>${esc(ar.headline)}</strong><br>${esc(ar.description)}<br><em>${esc(ar.instruction)}</em></p></div>` : ""}</div>
    <p class="decision ${res.decision === "release" ? "pass" : res.decision === "blocked" ? "fail" : "pending"}">Gate: ${DECISION_TEXT[res.decision]}</p>
    ${verdictTable(res.verdicts)}
    <h3>Approve</h3>
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
  const res = await post("/api/approve", { state, approvals });
  if (res.error) { $("releaseOut").innerHTML = `<p class="fail">${esc(res.error)}</p>`; return; }
  $("releaseOut").innerHTML = `<p class="decision ${res.decision === "release" ? "pass" : "fail"}">Final check: ${DECISION_TEXT[res.decision]}</p>
    ${verdictTable(res.verdicts)}
    <details open><summary>Audit log (${res.log.length} records; ${esc(res.log_check)})</summary><pre>${esc(res.log.map((r) => `${r.seq} ${r.actor} ${r.action} ${r.hash.slice(0, 12)} ← ${r.prev.slice(0, 12)}`).join("\n"))}</pre></details>
    <details><summary>Signed CAP XML</summary><pre>${esc(res.xml)}</pre></details>`;
}

$("check").onclick = async () => {
  const res = await post("/api/check", { xml: $("xml").value, profile: $("profile").value });
  $("checkOut").innerHTML = res.error ? `<p class="fail">${esc(res.error)}</p>` :
    `<p class="decision">${DECISION_TEXT[res.decision]}</p>${verdictTable(res.verdicts)}`;
};

fetch("/web/results/bench.json").then((r) => r.json()).then((b) => {
  $("bench").innerHTML = `<table><tr><th>Incident</th><th>What happened</th><th>As sent: gate result</th><th>Rules that fired</th><th>Official finding</th><th>Match?</th><th>AI drafter on the same inputs</th></tr>
  ${b.incidents.map((i) => `<tr><td>${esc(i.title)}<br><span class="muted">${esc(i.date)}</span></td><td>${esc(i.outcome)}</td>
    <td class="${i.as_sent.decision === "blocked" ? "fail" : "pass"}">${esc(i.as_sent.decision)}</td>
    <td>${esc(i.as_sent.failed.join(", "))}</td><td>${esc(i.finding.body)}: “${esc(i.finding.quote)}”</td>
    <td>${i.match ? "yes" : "no"} <span class="muted">(expected ${esc(i.expected.join(", "))})</span></td>
    <td>${i.ai ? esc(i.ai.summary) : "not run"}</td></tr>`).join("")}</table>
  <p class="muted">${esc(b.note || "")}</p>`;
}).catch(() => { $("bench").textContent = "Replay results not built yet."; });

fetch("/web/results/audit.json").then((r) => r.json()).then((a) => {
  $("auditOut").innerHTML = `<p>${esc(a.headline)}</p><table><tr><th>Source</th><th>Alerts</th><th>Any AI marker</th><th>Any approver marker</th><th>Signed</th></tr>
  ${a.rows.map((r) => `<tr><td>${esc(r.source)}</td><td>${r.alerts}</td><td>${r.ai}</td><td>${r.approver}</td><td>${r.signed}</td></tr>`).join("")}</table>
  <p class="muted">${esc(a.note || "")}</p>`;
}).catch(() => { $("auditOut").textContent = "Audit results not built yet."; });
