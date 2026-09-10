"use strict";

const state = { patients: [], active: null, ctx: null, thread: [], reportBuilt: false };

const $ = (id) => document.getElementById(id);
const fmt = (v, d = "–") => (v === null || v === undefined ? d : v);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function j(method, url, body, headers) {
  const opts = { method, headers: headers || {} };
  if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const r = await fetch(url, opts);
  return { ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) };
}

const TAG_LABELS = {
  fasting: "Fasting", pre: "Pre-meal", postbreakfast: "Post-breakfast",
  postlunch: "Post-lunch", postdinner: "Post-dinner", postprandial: "Post (generic)",
};
const SLOTS = [
  { key: "post_breakfast", label: "Post-Breakfast", color: "var(--pb)" },
  { key: "post_lunch", label: "Post-Lunch", color: "var(--pl)" },
  { key: "post_dinner", label: "Post-Dinner", color: "var(--pd)" },
];
const QUICK = ["fasting 128", "post breakfast 158", "post lunch 170", "post dinner 190",
               "2 roti, dal, sabzi", "yes", "correct m"];

// ---------- boot / patients ----------
async function boot() {
  const h = await fetch("/healthz").then((r) => r.json()).catch(() => ({}));
  const ch = $("channel");
  ch.textContent = "channel: " + (h.channel || "?");
  if (h.ok === true) ch.classList.add("ok");

  setupTabs();
  setupAddPatient();
  const q = await j("GET", "/api/v1/patients");
  if (q.ok && q.data.length) {
    state.patients = q.data;
    renderPatients();
    selectPatient(state.patients[0].id);
  } else {
    $("patient-list").textContent = "no patients — start the server with a seeded DB";
  }
}

function setupAddPatient() {
  const btnAdd = $("btn-add-patient");
  const box = $("add-patient-box");
  const btnSave = $("btn-save-patient");
  const btnCancel = $("btn-cancel-patient");
  const err = $("new-p-err");
  if (!btnAdd || !box) return;

  btnAdd.onclick = () => {
    box.style.display = box.style.display === "none" ? "block" : "none";
    err.textContent = "";
  };
  btnCancel.onclick = () => {
    box.style.display = "none";
    err.textContent = "";
  };
  btnSave.onclick = async () => {
    const name = $("new-p-name").value.trim();
    const phone = $("new-p-phone").value.trim();
    const key = $("new-p-key").value.trim() || "aahaar-2026";
    if (!name || !phone) {
      err.textContent = "Please enter name and phone.";
      return;
    }
    btnSave.disabled = true;
    const r = await j("POST", "/api/v1/patients", { name, phone }, { "X-Aahaar-Key": key });
    btnSave.disabled = false;
    if (r.ok) {
      box.style.display = "none";
      $("new-p-name").value = "";
      $("new-p-phone").value = "";
      err.textContent = "";
      const q = await j("GET", "/api/v1/patients");
      if (q.ok) {
        state.patients = q.data;
        renderPatients();
        selectPatient(r.data.id);
      }
    } else {
      err.textContent = "error: " + (r.data.error || ("HTTP " + r.status));
    }
  };
}

function renderPatients() {
  const el = $("patient-list");
  el.innerHTML = "";
  for (const p of state.patients) {
    const c = document.createElement("div");
    c.className = "pcard" + (p.id === state.active ? " active" : "");
    const w = p.window || "none";
    c.innerHTML =
      `<div class="pname">${esc(p.name)}</div>` +
      `<div class="pid">UHID ${esc(p.uh_id || "—")}</div>` +
      `<div class="pmeta"><span class="caregiver">CG: ${esc(p.caregiver || "—")}</span>` +
      `<span class="wstatus ${w}">${w}</span></div>`;
    c.onclick = () => selectPatient(p.id);
    el.appendChild(c);
  }
}

async function selectPatient(id) {
  state.active = id;
  state.reportBuilt = false;
  renderPatients();
  $("report-preview").hidden = true;
  $("report-preview").innerHTML = "";
  const plink = $("pdf-link");
  if (plink) plink.remove();
  $("report-actions").innerHTML = '<button id="build">Build doctor report</button>';
  $("build").onclick = buildReport;
  $("report-note").textContent = "";
  $("ov-empty").textContent = "loading…";

  await loadContext();
  renderOverview();
  const m = state.ctx && state.metrics;
  $("ov-empty").hidden = !!m;
  $("ov-body").hidden = !m;
  if (!m) $("ov-empty").textContent = "no window data yet — run the demo first.";

  seedThread();
  seedSender();
  loadAudit();
}

// ---------- live WhatsApp numbers (operator-linked) ----------
function seedSender() {
  const p = state.patients.find((x) => x.id === state.active);
  const sel = $("sender");
  if (!sel || !p) return;
  const prev = sel.value;
  sel.innerHTML = "";
  const opts = [{ value: p.patient_phone || "", label: "Patient (" + (p.patient_phone || "—") + ")" }];
  if (p.caregiver_phone) opts.push({ value: p.caregiver_phone, label: "Caregiver (" + p.caregiver_phone + ")" });
  opts.push({ value: "+919999999999", label: "Unknown number (guard)" });
  for (const o of opts) {
    const el = document.createElement("option");
    el.value = o.value;
    el.textContent = o.label;
    sel.appendChild(el);
  }
  if (prev && Array.from(sel.options).some((o) => o.value === prev)) sel.value = prev;
}

function populateLive() {
  const p = state.patients.find((x) => x.id === state.active);
  if (!p) return;
  $("live-patient").value = p.patient_phone || "";
  $("live-caregiver").value = p.caregiver_phone || "";
  $("live-note").textContent = "";
}

async function saveLive() {
  const btn = $("live-save");
  btn.disabled = true;
  const key = $("live-key").value.trim();
  const r = await j("POST", "/api/v1/patients/" + state.active + "/linked",
    { patient_phone: $("live-patient").value.trim(),
      caregiver_phone: $("live-caregiver").value.trim() },
    { "X-Aahaar-Key": key });
  btn.disabled = false;
  const note = $("live-note");
  if (r.ok) {
    const cg = r.data.caregiver_phone
      ? " + caregiver <b>" + esc(r.data.caregiver_phone) + "</b>" : "";
    note.innerHTML = "linked: patient <b>" + esc(r.data.patient_phone) + "</b>" + cg +
      ". Add these same numbers as Meta recipients, then message the test number from that phone.";
    const q = await j("GET", "/api/v1/patients");
    if (q.ok) { state.patients = q.data; renderPatients(); }
    seedSender();
  } else {
    note.textContent = "error: " + (r.data.error || ("HTTP " + r.status));
  }
}

async function sendDirectMessage() {
  const btn = $("direct-msg-send");
  const input = $("direct-msg-text");
  const note = $("direct-msg-note");
  const text = (input.value || "").trim();
  if (!text) return;
  btn.disabled = true;
  const key = $("live-key").value.trim() || "aahaar-2026";
  const r = await j("POST", "/api/v1/patients/" + state.active + "/message",
    { message: text },
    { "X-Aahaar-Key": key });
  btn.disabled = false;
  if (r.ok) {
    note.innerHTML = `<span style="color: green;">Sent WhatsApp to <b>${esc(r.data.sent_to)}</b>: "${esc(text)}"</span>`;
    input.value = "";
    loadAudit();
  } else {
    note.textContent = "error: " + (r.data.error || ("HTTP " + r.status));
  }
}

// ---------- context ----------
async function loadContext() {
  const mid = state.active;
  const [m, ctx] = await Promise.all([
    j("GET", `/api/v1/patients/${mid}/metrics`),
    j("GET", `/api/v1/patients/${mid}/report`),
  ]);
  if (Number.isNaN(Number(mid))) return;
  state.metrics = m.ok ? m.data : null;
  state.ctx = ctx.ok ? ctx.data : null;
  renderHeader();
}

function renderHeader() {
  const m = state.metrics;
  if (!m) { $("window-info").textContent = "no window"; return; }
  const d = m.window_dates || {};
  const short = (s) => (s || "").slice(8, 10) + " " + monthName(s);
  $("window-info").textContent = `${short(d.start)} – ${short(d.end)}`;
}
function monthName(iso) {
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  try { return months[Number(iso.slice(5, 7)) - 1] + " " + iso.slice(0, 4); } catch (e) { return ""; }
}

// ---------- overview ----------
function renderOverview() {
  const m = state.metrics, ctx = state.ctx;
  if (!m || !ctx) return;

  const tir = m.tir || {};
  const tirClass = tir.in >= 70 ? "green" : tir.in >= 50 ? "amber" : "red";
  const adhClass = m.adherence_index >= 80 ? "green" : m.adherence_index >= 50 ? "amber" : "red";
  const cards = [
    ["Adherence", adhClass, fmt(m.adherence_index) + "%"],
    ["Mean fasting", "green", fmt(m.mean_fpg)],
    ["Mean PPBG", "", fmt(m.mean_ppbg)],
    ["In range 70–180", tirClass, fmt(tir.in) + "%"],
    ["Readings", "", fmt(m.readings_count)],
    ["Meals logged", "", fmt(m.meals_count)],
  ];
  $("stat-cards").innerHTML = cards.map(([l, cls, v]) =>
    `<div class="stat ${cls}"><b>${v}</b><span>${l}</span></div>`).join("");

  const segs = [[tir.in, "var(--green)"], [tir.above, "var(--red)"], [tir.below, "var(--amber)"]];
  $("tir-bar").innerHTML = segs.map(([p, c]) => {
    const w = Math.max(p, p > 0 ? 4 : 0);
    const label = p >= 10 ? p + "%" : "";
    return `<div style="flex:${w};background:${c}">${label}</div>`;
  }).join("");
  $("tir-legend").innerHTML =
    [["In Range", tir.in, "var(--green)"], ["Above Range", tir.above, "var(--red)"],
     ["Below Range", tir.below, "var(--amber)"]]
      .map(([l, p, c]) => `<span><i class="dot" style="background:${c}"></i>${l}: <b>${fmt(p)}%</b></span>`)
      .join("");

  $("slot-bars").innerHTML = SLOTS.map(({ key, label, color }) => {
    const s = m[key] || {};
    const mean = s.mean;
    const w = mean ? Math.max(3, Math.round(mean / 240 * 100)) : 0;
    let delta = "";
    if (s.weekday && s.weekend) {
      const d = s.weekend - s.weekday;
      delta = `<div class="delta">weekdays ${fmt(s.weekday)} → weekends ${fmt(s.weekend)} (${d >= 0 ? "+" : ""}${d}) mg/dL</div>`;
    } else if (s.weekday || s.weekend) {
      delta = `<div class="delta">weekday ${fmt(s.weekday)} · weekend ${fmt(s.weekend)} mg/dL</div>`;
    }
    return `<div class="slotbar">
      <div class="row"><span>${label}</span><b>${fmt(mean)} mg/dL</b></div>
      <div class="track"><div class="fill" style="width:${w}%;background:${color}"></div></div>
      ${delta}</div>`;
  }).join("");

  const byTag = ctx.glucose_by_tag || {};
  const order = ["fasting", "pre", "postbreakfast", "postlunch", "postdinner", "postprandial"];
  const rows = [`<tr><th>Context</th><th>Count</th><th>Mean (mg/dL)</th></tr>`];
  for (const t of order) {
    const vals = byTag[t];
    if (!vals || !vals.length) continue;
    rows.push(`<tr><td>${TAG_LABELS[t] || t}</td><td>${vals.length}</td><td>${(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1)}</td></tr>`);
  }
  $("tag-table").innerHTML = rows.length > 1 ? `<table class="tbl">${rows.join("")}</table>` : "no readings logged";

  const diet = ctx.meals || {};
  const av = ctx.avoid || {};
  const genus = (ctx.top_genera || []).slice(0, 3)
    .map((g) => `<span class="mini-chip">${esc(g[0])} · ${g[2]}%</span>`).join("");
  $("diet-info").innerHTML =
    `<div class="kpi"><span>High-GI share</span><b>${fmt(diet.high_gi_share)}%</b></div>` +
    `<div class="kpi"><span>Carb Volatility (CVI)</span><b>${fmt(diet.carb_volatility)}</b></div>` +
    `<div class="kpi"><span>Avoid-list hits</span><b>${fmt(av.count)}</b></div>` +
    `<div class="kpi"><span>Top staple genera</span></div><div class="chiprow">${genus || "<span class='mini-chip'>—</span>"}</div>`;

  const pats = ctx.patterns || [];
  $("patterns").innerHTML = pats.length
    ? pats.map(([t, b]) => `<div class="pattern"><b>${esc(t)}</b><p>${esc(b)}</p></div>`).join("")
    : "no patterns for this window";
}

// ---------- trends ----------
async function showTrends() {
  if (!state.active) return;
  const note = $("trend-note");
  note.textContent = "loading charts…";
  const base = `/api/v1/patients/${state.active}/report/charts`;
  const top = await j("GET", base + "?which=top");
  if (top.status === 404) {
    await j("POST", `/api/v1/patients/${state.active}/report/build`);
  }
  const m = state.metrics;
  const d = (m && m.window_dates) || {};
  note.textContent = `${d.start || ""} – ${d.end || ""} · target 70–180 mg/dL · weekend bands shaded`;
  $("chart-top").src = base + "?which=top&t=" + Date.now();
  $("chart-bottom").src = base + "?which=bottom&t=" + Date.now();
}

// ---------- report ----------
async function buildReport() {
  const btn = $("build");
  btn.disabled = true;
  btn.textContent = "building…";
  const r = await j("POST", `/api/v1/patients/${state.active}/report/build`);
  btn.disabled = false;
  btn.textContent = "Build doctor report";
  const note = $("report-note");
  if (r.ok && r.data.pdf) {
    state.reportBuilt = true;
    const a = document.createElement("a");
    a.id = "pdf-link";
    a.className = "btnlink";
    a.href = `/api/v1/patients/${state.active}/report/file`;
    a.target = "_blank";
    a.textContent = "Open PDF (2 pages)";
    $("report-actions").appendChild(a);
    await loadPreview();
    note.textContent = `built — TIR ${r.data.metrics.tir.in}% in range · preview below · ${r.data.pdf.split("/").pop()}`;
  } else {
    note.textContent = "error: " + (r.data.error || "unknown");
  }
}

async function loadPreview() {
  const el = $("report-preview");
  const r = await j("GET", `/api/v1/patients/${state.active}/report/preview`);
  if (r.ok && r.data.html) {
    el.innerHTML = r.data.html;
    el.hidden = false;
  }
  const note = $("report-note");
  if (r.ok && r.data.html && el.hidden === false) {
    note.textContent = `on-screen report updated${r.data.built ? " · PDF ready to open" : ""}`;
  }
}

// ---------- messages / chat ----------
function setupTabs() {
  document.querySelectorAll("#tabs button").forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll("#tabs button").forEach((x) => x.classList.remove("active"));
      document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      $("tab-" + b.dataset.tab).classList.add("active");
      if (b.dataset.tab === "trends") showTrends();
      if (b.dataset.tab === "report" && state.reportBuilt) loadPreview();
      if (b.dataset.tab === "audit") loadAudit();
      if (b.dataset.tab === "messages") scrollThread();
      if (b.dataset.tab === "live") populateLive();
    };
  });

  renderQuick();
  $("msg-form").onsubmit = sendMsg;
  $("live-save").onclick = saveLive;
  const dmBtn = $("direct-msg-send");
  if (dmBtn) dmBtn.onclick = sendDirectMessage;
}

function renderQuick() {
  $("quick-chips").innerHTML = QUICK.map((q) =>
    `<button type="button" class="chip-send" onclick="quickSend('${esc(q)}')">${esc(q)}</button>`).join("");
}

function quickSend(text) {
  $("msg").value = text;
  sendMsg(new Event("submit"));
}

function renderThread() {
  const el = $("thread");
  if (!state.thread.length) {
    el.innerHTML = '<div class="thread-empty">send a message below to start the conversation</div>';
    return;
  }
  el.innerHTML = state.thread.map((m) => {
    if (m.kind === "sys") return `<div class="bub sys">${esc(m.text)}</div>`;
    const who = m.kind === "in" ? `<span class="who">${esc(m.sender || "")}</span>` : "";
    return `<div class="bub ${m.kind}">${who}${esc(m.text)}<span class="when">${m.when || ""}</span></div>`;
  }).join("");
}

let pollTimer = null;
let lastLogHash = "";

async function refreshThreadAndContext(forceScroll = false) {
  if (!state.active) return;
  const r = await j("GET", `/api/v1/patients/${state.active}/log`);
  if (!r.ok || !r.data) return;

  const inbounds = (r.data.inbound || []).map((m) => ({
    id: m.id,
    ts: m.ts,
    kind: "in",
    sender: (m.role === "caregiver" ? "Caregiver" : "Patient") + (m.sender_phone ? ` (${m.sender_phone})` : ""),
    text: m.raw_text,
    when: hhmm(m.ts),
  }));

  const outbounds = (r.data.outbound || []).map((o) => ({
    id: o.id,
    ts: o.ts,
    kind: "out",
    sender: "Aahaar",
    text: o.body,
    when: hhmm(o.ts),
  }));

  const all = inbounds.concat(outbounds);
  // Sort by database sequential id so new live messages are always at the bottom
  all.sort((a, b) => (a.id && b.id) ? (a.id - b.id) : (a.ts || "").localeCompare(b.ts || ""));
  const recent = all.slice(-40);

  const hash = JSON.stringify(recent.map((x) => [x.kind, x.text, x.when]));
  if (hash !== lastLogHash) {
    lastLogHash = hash;
    state.thread = recent;
    renderThread();
    if (forceScroll || recent.length <= 5) scrollThread();
    await loadContext();
    renderOverview();
    const m = state.ctx && state.metrics;
    $("ov-empty").hidden = !!m;
    $("ov-body").hidden = !m;
    loadAudit();
  }
}

function seedThread() {
  state.thread = [];
  lastLogHash = "";
  const el = $("thread");
  el.innerHTML = '<div class="thread-empty">loading live WhatsApp conversation...</div>';
  refreshThreadAndContext(true).then(() => {
    scrollThread();
  });
  refreshLiveInbound();
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(() => {
    refreshThreadAndContext(false);
    refreshLiveInbound();
  }, 3000);
}

async function refreshLiveInbound() {
  const r = await j("GET", "/api/v1/inbound/live?limit=15");
  if (!r.ok || !r.data || !r.data.messages) return;
  const feed = $("live-inbound-feed");
  if (!feed) return;
  if (!r.data.messages.length) {
    feed.innerHTML = '<div class="muted">No incoming WhatsApp messages received yet.</div>';
    return;
  }
  feed.innerHTML = r.data.messages.map((m) => {
    const isUnlinked = (m.patient_name || "").includes("Unlinked");
    const linkBtn = isUnlinked && m.sender_phone
      ? `<button type="button" class="btn-sm" style="margin-left:8px;padding:2px 6px;font-size:11px;cursor:pointer;" onclick="linkActivePhone('${esc(m.sender_phone)}')">Link to active patient</button>`
      : "";
    return `<div style="padding: 4px 0; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
      <div>
        <span class="badge" style="font-size:10px;background:${isUnlinked ? '#e65100' : '#2e7d32'};color:white;">${esc(m.patient_name)}</span>
        <b>${esc(m.sender_phone || "unknown")}:</b> "${esc(m.raw_text)}"
        <span class="muted" style="font-size:11px;">(${hhmm(m.ts)})</span>
      </div>
      <div>${linkBtn}</div>
    </div>`;
  }).join("");
  const countEl = $("live-inbound-count");
  if (countEl) countEl.textContent = `${r.data.messages.length} live`;
}

window.linkActivePhone = async function(phone) {
  if (!state.active) {
    alert("Please select an active patient first.");
    return;
  }
  const key = prompt("Enter Operator Key to link " + phone + " to this patient:", "aahaar-2026");
  if (!key) return;
  const r = await j("POST", `/api/v1/patients/${state.active}/linked`, {
    patient_phone: phone
  }, { "X-Aahaar-Key": key });
  if (r.ok) {
    alert("Phone linked successfully!");
    await loadPatients();
    await refreshThreadAndContext(true);
    await refreshLiveInbound();
  } else {
    alert("Failed to link phone: " + (r.data ? r.data.error : "Unknown error"));
  }
};


function hhmm(iso) {
  try { return String(iso).slice(11, 16); } catch (e) { return ""; }
}

function scrollThread() {
  const el = $("thread");
  if (el) el.scrollTop = el.scrollHeight;
}

async function sendMsg(ev) {
  ev.preventDefault();
  const text = $("msg").value.trim();
  if (!text) return;
  const sender = $("sender").value;
  $("msg").value = "";

  // 1. Immediately display inbound message bubble
  state.thread.push({ kind: "in", sender, text, when: nowHHMM() });
  $("chat-state").textContent = "sending…";
  renderThread();
  scrollThread();

  // 2. Dispatch to backend
  const r = await j("POST", "/api/v1/inbound", {
    patient_id: state.active, sender_phone: sender, kind: "text", text,
  });
  $("chat-state").textContent = "ready";

  // 3. Immediately display bot replies
  if (r.ok && r.data && r.data.replies && r.data.replies.length) {
    for (const reply of r.data.replies) {
      state.thread.push({ kind: "out", sender: "Aahaar", text: reply, when: nowHHMM() });
    }
    renderThread();
    scrollThread();
  }

  // 4. Refresh stats and audit
  await loadContext();
  renderOverview();
  const m = state.ctx && state.metrics;
  $("ov-empty").hidden = !!m;
  $("ov-body").hidden = !m;
  loadAudit();
}

function nowHHMM() {
  const d = new Date();
  return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
}

// ---------- audit ----------
async function loadAudit() {
  if (!state.active) return;
  const r = await j("GET", `/api/v1/patients/${state.active}/log`);
  const el = $("audit");
  if (!r.ok || !r.data.audit) { el.textContent = "no audit entries"; return; }
  el.innerHTML = r.data.audit.slice(0, 80).map((a) =>
    `<div><span class="muted">${String(a.ts).slice(11, 19)}</span> · ${esc(a.actor)} · ${esc(a.action)}${a.detail ? " — " + esc(a.detail) : ""}</div>`).join("");
}

boot();
window.quickSend = quickSend;