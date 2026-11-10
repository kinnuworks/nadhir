const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const STATUS = { pass: ["pass", "passes"], fail: ["fail", "fails"], pending: ["pending", "waiting"], warn: ["warn", "note"], "n/a": ["na", "not relevant"] };
const pill = (s) => { const [c, label] = STATUS[s] || ["na", s]; return `<span class="pill pill--${c}">${esc(label)}</span>`; };

const DEFAULT_INPUTS = [
  {
    text: "ABU DHABI, 4th March, 2026 (WAM) -- The National Centre of Meteorology (NCM) has warned of active northwesterly winds affecting various areas across the UAE, expected to be fresh to strong at times, causing blowing dust and sand and reducing horizontal visibility to less than 2,000 metres in some coastal and inland areas. The centre stated that the expected weather conditions began at 14:55 and continue until 19:00 this evening. It urged members of the public to exercise caution, especially while driving on open roads, due to the possibility of reduced horizontal visibility caused by blowing dust.",
    verified: true,
    source: "NCM via WAM, 4 Mar 2026",
  },
  {
    text: "Social media post: a dam near Al Ain has burst, everyone leave the area now",
    verified: false,
    source: "illustrative rumour (not real)",
  },
];

/* ---------- inputs ---------- */
function inputRow(item) {
  const div = document.createElement("div");
  div.className = "input" + (item.verified ? "" : " is-unverified");
  div.innerHTML = `<textarea class="in-text" aria-label="Input text" placeholder="Paste a bulletin, a report or a field note">${esc(item.text)}</textarea>
    <div class="input__meta">
      <label class="toggle"><input type="checkbox" class="in-ver switch" ${item.verified ? "checked" : ""}> Verified source</label>
      <input class="in-src" aria-label="Source" placeholder="Source" value="${esc(item.source)}">
    </div>`;
  const box = div.querySelector(".in-ver");
  box.onchange = () => div.classList.toggle("is-unverified", !box.checked);
  return div;
}
DEFAULT_INPUTS.forEach((i) => $("inputs").appendChild(inputRow(i)));
$("add").onclick = () => { const r = inputRow({ text: "", verified: true, source: "" }); $("inputs").appendChild(r); r.querySelector("textarea").focus(); };

async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  try { return await r.json(); } catch { return { error: `The server answered ${r.status}. Please try again.` }; }
}

/* ---------- pipeline rail ---------- */
const STEPS = ["draft", "translate", "rules", "review", "people"];
function setStep(name, state) {
  const li = document.querySelector(`#steps [data-step="${name}"]`);
  if (li) li.className = state ? `is-${state}` : "";
}
let ticker = null;
function animateSteps() {
  STEPS.forEach((s) => setStep(s, ""));
  let k = 0;
  setStep(STEPS[0], "active");
  ticker = setInterval(() => { if (k < 3) { setStep(STEPS[k], "ok"); k += 1; setStep(STEPS[k], "active"); } }, 1400);
}
function settleSteps(res) {
  clearInterval(ticker);
  const failed = res.verdicts.filter((v) => v.status === "fail").map((v) => v.rule);
  const open = res.institutions ? res.institutions.open_objections.length : 0;
  setStep("draft", "ok");
  setStep("translate", "ok");
  setStep("rules", failed.length ? "block" : "ok");
  setStep("review", open ? "wait" : "ok");
  setStep("people", res.decision === "blocked" ? "block" : "wait");
}

/* ---------- shared renderers ---------- */
const ICON = {
  release: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  waiting: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l2.5 2"/></svg>',
  blocked: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round"><path d="M7 7l10 10M17 7 7 17"/></svg>',
};
const DECISION_TEXT = { release: "Cleared for broadcast", waiting: "Waiting for people to approve", blocked: "Blocked" };

function decision(kind, prefix, sub) {
  return `<div class="decision decision--${kind}" role="status"><span class="decision__icon">${ICON[kind] || ""}</span>
    <div>${esc(prefix)}${DECISION_TEXT[kind] || esc(kind)}${sub ? `<small>${esc(sub)}</small>` : ""}</div></div>`;
}

function sources(list) {
  return `<div class="srcs">${list.map((s) => s.url
    ? `<details><summary>${esc(s.id)}</summary><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title || s.id)}</a>${s.quote ? `<blockquote>“${esc(s.quote)}”</blockquote>` : ""}<small class="t-micro">${esc(s.status)}</small></details>`
    : `<span class="t-mono t-micro">${esc(s.id)}</span>`).join("")}</div>`;
}

function verdictList(vs) {
  const order = { fail: 0, pending: 1, warn: 2, pass: 3, "n/a": 4 };
  const sorted = [...vs].sort((a, b) => (order[a.status] ?? 5) - (order[b.status] ?? 5));
  return `<div class="rules">${sorted.map((v) => `<div class="rule is-${STATUS[v.status] ? STATUS[v.status][0] : "na"}">
      ${pill(v.status)}
      <div><p class="rule__name"><span class="t-mono">${esc(v.rule)}</span>${esc(v.title)}</p><p class="rule__why">${esc(v.detail)}</p></div>
      ${sources(v.sources || [])}</div>`).join("")}</div>`;
}

const POSITION = { agree: ["pass", "agrees"], object: ["pending", "objects"], escalate: ["fail", "escalates to a person"] };

function evidence(e) {
  if (e.kind === "clause") {
    const src = e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title || e.ref)}</a>` : esc(e.title || e.ref);
    return `<li>“${esc(e.quote)}”<small>${src}${e.locator ? ", " + esc(e.locator) : ""} · clause ${esc(e.ref)}</small></li>`;
  }
  return `<li>“${esc(e.quote)}”<small>quoted from the ${esc(e.ref)} it was shown</small></li>`;
}

function reviewerCard(r) {
  const [pc, plabel] = POSITION[r.position] || ["na", r.position];
  const objections = r.objections.length ? r.objections.map((o) => `<div class="objection">
      <div class="objection__tags"><span class="rule-chip">${esc(o.field)}</span>${o.blocking ? '<span class="pill pill--pending">blocking</span>' : ""}${o.policy_cited ? '<span class="pill pill--info">cites the knowledge base</span>' : ""}</div>
      <p><b>${esc(o.issue)}</b></p>
      <p class="fix">Fix: ${esc(o.fix)}</p>
      <ul class="ev">${o.evidence.map(evidence).join("")}</ul>
      <p class="uae">UAE text on this: ${o.uae_basis && o.uae_basis.status === "cites_uae" ? `“${esc(o.uae_basis.quote)}” (${esc(o.uae_basis.title || o.uae_basis.ref)})` : "none found in the UAE texts searched"}</p>
    </div>`).join("") : `<p class="t-small">${esc(r.summary)}</p>`;
  return `<article class="reviewer">
    <div class="reviewer__head"><p class="reviewer__who t-title">${esc(r.name)}<small>stands in for ${esc(r.stands_for)}</small></p><span class="pill pill--${pc}">${esc(plabel)}</span></div>
    ${objections}
    ${r.dropped.length ? `<p class="t-micro">${r.dropped.length} objection(s) dropped: no quote matched its source word for word.</p>` : ""}
    ${r.no_basis.length ? `<p class="t-micro">No clause found to back: ${r.no_basis.map((n) => esc(n.concern)).join("; ")}</p>` : ""}
    ${r.queries.length ? `<div class="queries" aria-label="What it searched for">${r.queries.map((q) => `<span class="chip chip--soft">${esc(q)}</span>`).join("")}</div>` : ""}
    ${r.clauses.length ? `<details><summary>${r.clauses.length} clauses read</summary>${r.clauses.map((c) => `<div class="clause-row"><span class="t-mono">${esc(c.id)}</span> · ${esc(c.title)} ${esc(c.locator || "")}</div>`).join("")}</details>` : ""}
  </article>`;
}

function reviewsBlock(inst) {
  if (!inst || !inst.rounds || !inst.rounds.length) return "";
  return `<div class="res-head"><h3>Institution reviewers</h3><span class="t-small">They can object, but they can't approve.</span></div>
    <p class="t-small">Four agents, each standing in for a body with its own partial view of the alert. They search the knowledge base themselves and must quote what they rely on; code checks every quote. Their objections go back to the drafter once, and any still open go to the people below.</p>
    ${inst.rounds.map((rd) => `${inst.rounds.length > 1 ? `<p class="eyebrow">Round ${rd.round}${rd.round > 1 ? ", after the redraft" : ""}</p>` : ""}
      <div class="reviewers">${rd.reviews.map(reviewerCard).join("")}</div>`).join("")}
    ${(inst.notes || []).map((n) => `<p class="t-small">${esc(n)}</p>`).join("")}`;
}

/* ---------- draft ---------- */
$("heroDraft").onclick = () => {
  $("console").scrollIntoView({ behavior: "smooth", block: "start" });
  $("draft").click();
};
let state = null;
$("draft").onclick = async () => {
  const inputs = [...$("inputs").children].map((d) => ({
    text: d.querySelector(".in-text").value, verified: d.querySelector(".in-ver").checked, source: d.querySelector(".in-src").value,
  }));
  const btn = $("draft");
  btn.disabled = true;
  $("draftStatus").innerHTML = '<span class="spin"></span>Drafting and reviewing. The prefilled example takes about 20 seconds; new text can take up to about 90.';
  $("draftOut").innerHTML = "";
  animateSteps();
  const res = await post("/api/draft", { inputs, zone: $("zone").value, exercise: $("exercise").checked });
  btn.disabled = false;
  $("draftStatus").textContent = "";
  if (res.error) {
    clearInterval(ticker); STEPS.forEach((s) => setStep(s, ""));
    $("draftOut").innerHTML = `<p class="err">${esc(res.error)}</p>`;
    return;
  }
  settleSteps(res);
  state = res.state;
  const f = res.fields;
  const ar = (res.versions || []).find((v) => v.language.startsWith("ar"));
  const open = res.institutions ? res.institutions.open_objections.length : 0;
  const failed = res.verdicts.filter((v) => v.status === "fail").length;
  const pend = res.verdicts.filter((v) => v.status === "pending").map((v) => v.rule);
  const failedIds = res.verdicts.filter((v) => v.status === "fail").map((v) => v.rule);
  const sub = res.decision === "blocked" ? `Failed: ${failedIds.join(", ")}. A person has to fix the cause before this alert can go out.`
    : res.decision === "waiting" ? `Rules ${pend.join(", ")} need named approvers (filled in below)${open ? `, and ${open} reviewer objection${open > 1 ? "s are" : " is"} still open for them to read` : ""}. No rule failed.` : "";
  $("draftOut").innerHTML = `
    <div class="res-head"><h3>The draft</h3><span class="t-small">${res.attempts > 1 ? `The drafter rewrote it ${res.attempts - 1} time${res.attempts > 2 ? "s" : ""} after rule feedback or reviewer objections. This is the final version.` : "First draft."}</span></div>
    <div class="drafts">
      <article class="draft"><div class="draft__lang"><span class="eyebrow">English</span><span class="pill pill--info">${esc(f.severity)} · ${esc(f.urgency)}</span></div>
        <p class="draft__headline">${esc(f.headline)}</p><p>${esc(f.description)}</p><p class="instr">${esc(f.instruction)}</p>
        <div class="draft__meta"><span class="rule-chip">status ${esc(f.status)}</span><span class="rule-chip">certainty ${esc(f.certainty || "")}</span></div></article>
      ${ar ? `<article class="draft draft--ar" lang="ar"><div class="draft__lang"><span class="eyebrow">Arabic · العربية</span>${ar.method === "template" ? `<span class="pill pill--pass">vetted template ${esc(ar.template_id)}</span>` : '<span class="pill pill--pending">machine translated</span>'}</div>
        <p class="draft__headline">${esc(ar.headline)}</p><p>${esc(ar.description)}</p><p class="instr">${esc(ar.instruction)}</p></article>` : ""}
    </div>
    ${f.left_out?.length ? `<div class="note"><b>Left out by the drafter</b><ul class="leftout">${f.left_out.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>` : ""}
    ${f.note_for_reviewer ? `<p class="note"><b>Note for the approver:</b> ${esc(f.note_for_reviewer)}</p>` : ""}
    ${decision(res.decision, "Gate: ", sub)}
    <div class="res-head"><h3>Twelve rules</h3><span class="t-small">Open a source to read the quote it relies on.</span></div>
    ${verdictList(res.verdicts)}
    ${reviewsBlock(res.institutions)}
    <div class="approve" id="approveBox">
      <div class="res-head"><h3>Approve</h3><span class="t-small">A severe alert needs two different people.</span></div>
      ${open ? `<label class="ack"><input type="checkbox" id="ack"> ${open} reviewer objection(s) are still open. I have read them and still approve.</label>` : ""}
      <div class="approve__fields">
        <label class="field">Duty officer<input id="a1" placeholder="Name" autocomplete="off"></label>
        <label class="field">Supervisor<input id="a2" placeholder="A different name" autocomplete="off"></label>
        ${ar && ar.method === "machine" ? `<label class="field">Arabic wording approved by<input id="a3" placeholder="Someone who reads Arabic" autocomplete="off"></label>` : ""}
      </div>
      <div><button id="approve" class="btn btn-candy" type="button">Approve, sign and run the final check</button></div>
      <div id="releaseOut" class="results"></div>
    </div>
    <details class="disclosure"><summary>CAP XML before approval</summary><pre class="terminal">${esc(res.xml)}</pre></details>`;
  $("approve").onclick = approve;
  $("draftOut").scrollIntoView({ behavior: "smooth", block: "start" });
};

async function approve() {
  const approvals = [
    { name: $("a1").value, role: "duty-officer", scope: "release" },
    { name: $("a2").value, role: "supervisor", scope: "release" },
  ];
  if ($("a3")) approvals.push({ name: $("a3").value, role: "arabic-reviewer", scope: "language:ar" });
  $("approve").disabled = true;
  const res = await post("/api/approve", { state, approvals, ack_objections: $("ack") ? $("ack").checked : false });
  $("approve").disabled = false;
  if (res.error) { $("releaseOut").innerHTML = `<p class="err">${esc(res.error)}</p>`; return; }
  setStep("people", res.decision === "release" ? "ok" : res.decision === "blocked" ? "block" : "wait");
  const sub = res.decision === "release" ? "Signed. The approvers' roles and the AI's part are written into the alert."
    : res.objections_unacknowledged ? "Open objections have not been read by an approver yet." : "Some rules still wait for a person; see below.";
  $("releaseOut").innerHTML = `${decision(res.decision, "Final check: ", sub)}
    ${verdictList(res.verdicts)}
    <details class="disclosure" open><summary>Audit log: ${esc(res.log_check)}</summary>
      <pre class="terminal">${res.log.map((r) => `<span class="h">${String(r.seq).padStart(2, "0")}</span> ${esc(r.actor)} · ${esc(r.action)}  ${esc(r.hash.slice(0, 12))} ← ${esc(r.prev.slice(0, 12))}`).join("\n")}</pre></details>
    <details class="disclosure"><summary>Signed CAP XML</summary><pre class="terminal">${esc(res.xml)}</pre></details>`;
  $("releaseOut").scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- paste a single alert ---------- */
$("check").onclick = async () => {
  $("checkOut").innerHTML = `<p class="t-small"><span class="spin"></span>${$("review").checked ? "Checking, and asking the reviewers…" : "Checking…"}</p>`;
  const res = await post("/api/check", { xml: $("xml").value, profile: $("profile").value, review: $("review").checked });
  $("checkOut").innerHTML = res.error ? `<p class="err">${esc(res.error)}</p>` :
    `${decision(res.decision, "", "")}${verdictList(res.verdicts)}
     ${res.reviews ? reviewsBlock({ rounds: [{ round: 1, reviews: res.reviews }], notes: [] }) : ""}
     ${res.review_error ? `<p class="err">${esc(res.review_error)}</p>` : ""}`;
};

/* ---------- live feed ---------- */
$("feedBtn").onclick = async () => {
  $("feedStatus").innerHTML = '<span class="spin"></span>Fetching the feed…';
  $("feedBtn").disabled = true;
  const r = await post("/api/feed", { feed: $("feed").value });
  $("feedBtn").disabled = false;
  $("feedStatus").textContent = "";
  if (r.error) { $("feedOut").innerHTML = `<p class="err">${esc(r.feed || "")} ${esc(r.error)}</p>`; return; }
  $("feedOut").innerHTML = `<p class="t-title">${esc(r.feed)}</p>
    <div class="feed-sum"><span class="pill pill--info">${r.checked} checked</span><span class="pill pill--${r.held ? "fail" : "pass"}">${r.held} held</span>
      <span class="pill pill--na">${r.signed} signed</span><span class="pill pill--na">${r.with_ai_or_approver_record} record AI or an approver</span>
      ${r.too_long_for_cell_broadcast ? `<span class="pill pill--pending">${r.too_long_for_cell_broadcast} too long for one cell broadcast message</span>` : ""}
      ${r.unreadable ? `<span class="pill pill--na">${r.unreadable} unreadable</span>` : ""}</div>
    ${r.alerts.map((a) => a.error ? `<div class="feed-row"><small>${esc(a.link)}: ${esc(a.error)}</small></div>` :
      `<div class="feed-row"><div><p class="t-title">${esc(a.headline || a.event || a.identifier)}</p>
        <small>${esc(a.sent)} · ${esc(a.status)} / ${esc(a.msgType)} · ${esc(a.languages.join(", "))}</small></div>
        ${a.failed.length ? pill("fail") : pill("pass")}
        ${a.failed.length ? `<p class="why">${esc(a.verdicts.filter((v) => a.failed.includes(v.rule)).map((v) => v.rule + ": " + v.detail).join("; "))}</p>` : ""}</div>`).join("")}
    <p class="t-micro">${esc(r.note)}</p>`;
};

/* ---------- published results ---------- */
fetch("/web/results/bench.json").then((r) => r.json()).then((b) => {
  const all = b.incidents;
  const held = all.filter((i) => i.heldout);
  const rules = all.filter((i) => i.match).length;
  const heldRules = held.filter((i) => i.match).length;
  const both = all.filter((i) => i.match || (i.agents_on_real || []).some((x) => i.expected.includes(x))).length;
  $("pf-replays").innerHTML = `${rules} <span>of ${all.length}</span>`;
  $("pf-replays-l").textContent = `real alert failures caught by the rules, scored against the official finding. Held out: ${heldRules} of ${held.length}.`;
  $("benchStats").innerHTML = [
    [rules, all.length, "official findings matched by the rules alone"],
    [heldRules, held.length, "held-out failures caught by the frozen rules"],
    [both, all.length, "caught by rules or reviewer agents"],
  ].map(([n, d, l], k) => `<div class="stat reveal" style="--i:${k}"><p class="stat__n t-mono">${n} <span>of ${d}</span></p><p class="t-small">${l}</p></div>`).join("");
  const items = [...all].sort((x, y) => (x.heldout === y.heldout ? x.date.localeCompare(y.date) : x.heldout ? 1 : -1));
  const chips = (xs) => xs.length ? xs.map((x) => `<span class="rule-chip">${esc(x)}</span>`).join("") : '<span class="t-micro">none</span>';
  $("bench").innerHTML = `<div class="replay replay--head" role="row"><span role="columnheader">Failure</span><span role="columnheader">Rules that fired</span><span role="columnheader">Matches the finding</span><span role="columnheader">Agents alone</span></div>` +
    items.map((i) => `<details class="replay${i.match ? "" : " is-miss"}${i.heldout ? " is-held" : ""}" role="row">
      <summary>
        <span class="replay__what" role="cell"><span class="replay__year">${esc(i.date.slice(0, 4))}${i.heldout ? '<em>held out</em>' : ""}</span><b>${esc(i.title)}</b></span>
        <span class="replay__rules" role="cell"><span class="replay__lbl">Rules</span>${chips(i.as_sent.failed)}</span>
        <span role="cell"><span class="replay__lbl">Finding</span>${i.match ? '<span class="pill pill--pass">yes</span>' : `<span class="pill pill--fail">${i.not_counted && i.not_counted.rules ? "not counted" : "missed"}</span>`} <span class="t-micro">key ${esc(i.expected.join(", ") || "none")}</span></span>
        <span role="cell"><span class="replay__lbl">Agents</span>${i.agents_on_real ? (i.agents_on_real.length ? chips(i.agents_on_real) : '<span class="pill pill--fail">missed</span>') : "not run"}</span>
      </summary>
      <div class="replay__more"><p>${esc(i.outcome)}${i.not_counted ? Object.values(i.not_counted).map((t) => `<span class="nc">Not counted: ${esc(t)}</span>`).join("") : ""}</p><blockquote>“${esc(i.finding.quote)}”<cite>${esc(i.finding.body)}</cite></blockquote></div>
    </details>`).join("") + `<p class="t-small bench-note">${esc(b.note || "")} Open a row for the official finding.</p>`;
  observeReveals($("benchStats"));
}).catch(() => { $("bench").innerHTML = '<p class="t-small">Replay results not built yet.</p>'; });

/* ---------- hero preview tabs ---------- */
document.querySelectorAll(".preview__tabs [role=tab]").forEach((t) => {
  t.onclick = () => {
    document.querySelectorAll(".preview__tabs [role=tab]").forEach((o) => {
      const on = o === t;
      o.setAttribute("aria-selected", on);
      $(o.getAttribute("aria-controls")).hidden = !on;
    });
  };
});

/* ---------- audit log tamper check (same bytes as Python json.dumps(sort_keys=True, ensure_ascii=False)) ---------- */
const pyjson = (v) => {
  if (v === null) return "null";
  if (Array.isArray(v)) return "[" + v.map(pyjson).join(", ") + "]";
  if (typeof v === "object") return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ": " + pyjson(v[k])).join(", ") + "}";
  return JSON.stringify(v);
};
const sha256 = async (t) => [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t)))].map((x) => x.toString(16).padStart(2, "0")).join("");
const LOG_LABEL = { inputs: "event inputs", draft: "draft", translate: "Arabic translation", review: "review", approve: "approval", "objections-at-approval": "open objections read", "release-check": "final check", broadcast: "broadcast" };
let logOrig = null, logNow = null, tamperStage = 0;
async function checkChain(recs) {
  let prev = "0".repeat(64), broke = -1, why = "";
  const rows = [];
  for (const [k, r] of recs.entries()) {
    const { hash, ...body } = r;
    const h = await sha256(pyjson(body));
    let ok = true, note = "";
    if (broke < 0 && r.prev !== prev) { ok = false; note = "previous-hash link broken"; }
    else if (broke < 0 && h !== hash) { ok = false; note = "content does not match its hash"; }
    if (!ok && broke < 0) { broke = k; why = note; }
    rows.push({ r, h, state: broke < 0 ? "ok" : k === broke ? "bad" : "after", note });
    prev = hash;
  }
  return { rows, broke, why };
}
async function drawChain() {
  if (!crypto.subtle) { $("chainState").textContent = "this browser can't hash"; return; }
  const { rows, broke, why } = await checkChain(logNow);
  $("chainState").className = `pill pill--${broke < 0 ? "pass" : "fail"}`;
  $("chainState").textContent = broke < 0 ? `${rows.length} steps, chain intact` : `broken at step ${broke}: ${why}`;
  $("chain").innerHTML = rows.map(({ r, h, state, note }) => `<li class="crow is-${state}">
      <span class="crow__seq t-mono">${String(r.seq).padStart(2, "0")}</span>
      <span class="crow__what"><b>${esc(r.actor)}</b> · ${esc(LOG_LABEL[r.action] || r.action)}${state === "bad" ? `<em>${esc(note)}</em>` : ""}</span>
      <span class="crow__hash t-mono">${esc(h.slice(0, 10))} <i>←</i> ${esc(r.prev.slice(0, 10))}</span></li>`).join("");
}
fetch("/web/results/log-sample.jsonl").then((r) => r.text()).then((t) => {
  logOrig = t.split("\n").filter(Boolean).map((l) => JSON.parse(l));
  logNow = structuredClone(logOrig);
  drawChain();
}).catch(() => { $("chainState").textContent = "log not found"; });
$("tamperBtn").onclick = async () => {
  if (!logNow) return;
  if (tamperStage === 0) {
    const f = logNow[1].payload.fields;
    f.description = f.description.replace("2,000", "3,000");
    tamperStage = 1;
    $("tamperBtn").textContent = "Now recompute step 1's hash to hide it";
    $("tamperNote").innerHTML = 'Step 1 now says visibility under <b>3,000</b> metres. Its stored hash no longer matches its content.';
  } else if (tamperStage === 1) {
    const { hash, ...body } = logNow[1];
    logNow[1].hash = await sha256(pyjson(body));
    tamperStage = 2;
    $("tamperBtn").hidden = true;
    $("tamperNote").innerHTML = "Step 1's hash is fixed, so step 2's link to it breaks instead. To hide the edit, someone would have to rewrite every later hash, and the head would then differ from any copy kept elsewhere. That is why the head hash should be held by a second party.";
  }
  $("resetBtn").hidden = false;
  drawChain();
};
$("resetBtn").onclick = () => {
  logNow = structuredClone(logOrig); tamperStage = 0;
  $("tamperBtn").hidden = false; $("resetBtn").hidden = true;
  $("tamperBtn").textContent = "Change one character in step 1";
  $("tamperNote").textContent = "Step 1 is the drafter's text. The edit swaps one digit in the visibility figure, the kind of change nobody would spot by eye.";
  drawChain();
};

function bars(s, ofLabel) {
  const rows = [["No checks", s.named.none ?? 0], ["12 rules only", s.named.rules], ["4 reviewer agents only", s.named.agents], ["Rules and agents", s.named.both]];
  return `<div class="bars-list" role="img" aria-label="${rows.map(([l, v]) => `${l}: ${v} of ${s.cases}`).join("; ")}">
    ${rows.map(([l, v], k) => `<div class="bar${k === 3 ? " is-top" : ""}" title="${esc(l)}: ${v} of ${s.cases} faults named"><span class="bar__label">${esc(l)}</span>
      <span class="bar__track"><span class="bar__fill" style="width:${(v / s.cases) * 100}%"></span></span><span class="bar__val">${v}/${s.cases}</span></div>`).join("")}</div>
    <p class="bars-note">${ofLabel}</p>`;
}

fetch("/web/results/ablation-prereg.json").then((r) => r.json()).then((a) => {
  const s = a.summary;
  $("preregOut").innerHTML = bars(s, `Only the agents named ${s.only_agents.length}, including meaning changes in the Arabic. Only the rules named ${esc(s.only_rules.join(", ") || "none")}. Missed by both: ${esc(s.neither.join(", ") || "none")}. Reported as they came out.`) +
    `<details><summary>Every case</summary><div class="table-wrap"><table class="mini-table"><tr><th>Fault</th><th>Rules</th><th>Agents</th></tr>
    ${a.cases.map((c) => `<tr><td><span class="t-mono">${esc(c.fault)}</span> ${esc(c.title)}</td><td>${c.rules_named.length ? esc(c.rules_named.join(", ")) : pill("fail").replace("fails", "missed")}</td>
      <td>${c.agents_named.length ? c.agents_named.map((h) => esc(h.by)).join(", ") : pill("fail").replace("fails", "missed")}</td></tr>`).join("")}</table></div></details>`;
  observeBars($("preregOut"));
}).catch(() => { $("preregOut").innerHTML = '<p class="t-small">Not built yet.</p>'; });

fetch("/web/results/ablation.json").then((r) => r.json()).then((a) => {
  const s = a.summary;
  $("ablationOut").innerHTML = bars(s, `On ${s.clean_drafts} clean drafts with no fault, the agents raised ${s.clean_objections} objection(s). ${s.dropped_for_bad_quotes} objection(s) in the fault runs were dropped because their quote didn't match word for word.`) +
    `<details><summary>Every case</summary><div class="table-wrap"><table class="mini-table"><tr><th>Fault</th><th>Rules</th><th>Agents</th></tr>
    ${a.cases.map((c) => `<tr><td><span class="t-mono">${esc(c.fault)}</span> ${esc(c.title)}</td><td>${c.rules_named.length ? esc(c.rules_named.join(", ")) : pill("fail").replace("fails", "missed")}</td>
      <td>${c.agents_named.length ? c.agents_named.map((h) => esc(h.by)).join(", ") : pill("fail").replace("fails", "missed")}</td></tr>`).join("")}</table></div></details>
    <p class="t-micro">${esc(a.note)}</p>`;
  observeBars($("ablationOut"));
}).catch(() => { $("ablationOut").innerHTML = '<p class="t-small">Not built yet.</p>'; });

fetch("/web/results/audit.json").then((r) => r.json()).then((a) => {
  const total = a.rows.reduce((n, r) => n + r.alerts, 0);
  const ai = a.rows.reduce((n, r) => n + r.ai, 0);
  $("auditOut").innerHTML = `<div class="audit-big"><div><b class="t-mono">${total.toLocaleString("en")}</b><span>live public alerts read</span></div>
      <div><b class="t-mono">${ai}</b><span>record that AI or machine translation was involved</span></div>
      <div><b class="t-mono">0</b><span>record who approved them (17 US alerts carry a vendor login name)</span></div></div>
    <details><summary class="link">Per feed</summary><div class="table-wrap"><table class="mini-table"><tr><th>Source</th><th>Alerts</th><th>AI marker</th><th>Approver marker</th><th>Signed</th></tr>
    ${a.rows.map((r) => `<tr><td>${esc(r.source)}</td><td class="t-mono">${r.alerts}</td><td class="t-mono">${r.ai}</td><td class="t-mono">${r.approver}</td><td class="t-mono">${r.signed}</td></tr>`).join("")}</table></div></details>
    <p class="t-micro" style="margin-top:12px">${esc(a.note || "")}</p>`;
}).catch(() => { $("auditOut").innerHTML = '<p class="t-small">Audit results not built yet.</p>'; });

/* ---------- reveal helpers for content that arrives after load ---------- */
function observeReveals(root) {
  const els = root.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) { els.forEach((e) => e.classList.add("in")); return; }
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { rootMargin: "0px 0px -8% 0px" });
  els.forEach((e, k) => { e.style.setProperty("--i", k % 3); io.observe(e); });
}
function observeBars(root) {
  if (!("IntersectionObserver" in window)) { root.classList.add("in"); return; }
  const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { root.classList.add("in"); io.disconnect(); } }, { threshold: 0.3 });
  io.observe(root);
}
