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
  loadAudit();
}

// ---------- live WhatsApp numbers (operator-linked) ----------
function populateLive() {
  const p = state.patients.find((x) => x.id === state.active);
  if (!p) return;
  $("live-patient").value = p.patient_phone || "";
  $("live-caregiver").value = p.caregiver_phone || "";
  $("live-note").textContent = "";
  refreshLiveInbound();
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

async function loadDiagnostics() {
  const diagBox = $("diag-summary");
  if (!diagBox) return;
  const r = await j("GET", "/api/v1/debug/status");
  if (!r.ok || !r.data) {
    diagBox.textContent = "Failed to load diagnostic status.";
    return;
  }
  const d = r.data;
  const lastDisp = d.last_dispatch || {};
  let dispText = lastDisp.status || "none";
  if (lastDisp.http_code) dispText += ` (HTTP ${lastDisp.http_code})`;
  if (lastDisp.error) dispText += ` - ${typeof lastDisp.error === 'object' ? JSON.stringify(lastDisp.error) : lastDisp.error}`;

  diagBox.innerHTML = `
    <div><b>Channel:</b> ${esc(d.channel)}</div>
    <div><b>Cloud Ready:</b> <span style="color:${d.cloud_ready ? '#10b981' : '#ef4444'}">${d.cloud_ready ? 'Yes (configured)' : 'No (missing token/id)'}</span></div>
    <div><b>Meta Token:</b> <code>${esc(d.meta_token_masked)}</code></div>
    <div><b>Gemini AI Key:</b> ${d.gemini_api_key_configured ? '<span style="color:#10b981">Active (' + esc(d.gemini_key_masked) + ')</span>' : '<span style="color:#f59e0b">Not configured on Render (using fast local parsing)</span>'}</div>
    <div><b>Last Outbound Dispatch:</b> ${esc(dispText)}</div>
    <div style="margin-top:0.4rem;padding-top:0.4rem;border-top:1px dashed #ccc;">
      <div><b>Webhook Callback URL:</b> <code>https://aahaar-573f.onrender.com/api/v1/webhooks/whatsapp</code></div>
      <div><b>Webhook Verify Token:</b> <code>aahaar-verify</code></div>
      <div><b>Webhook Incoming Hits:</b> <span style="font-weight:bold;color:${(d.webhook_events_count || 0) > 0 ? '#10b981' : '#f59e0b'}">${d.webhook_events_count || 0} callbacks received from Meta</span></div>
      ${(d.webhook_events_count || 0) === 0 ? '<div style="margin-top:0.3rem;padding:0.4rem;background:#fffbeb;color:#92400e;border-radius:4px;font-size:0.8rem;"><b>Meta Webhook Setup:</b> In Meta Developer Portal &rarr; WhatsApp &rarr; Configuration &rarr; Webhook: set Callback URL to the URL above, Verify Token to <code>aahaar-verify</code>, and click <b>Manage</b> to <b>SUBSCRIBE</b> to the <code>messages</code> field.</div>' : ''}
    </div>
  `;
}

async function testWhatsAppPing() {
  const phoneInput = $("diag-test-phone");
  const phone = (phoneInput.value || "").trim();
  const resBox = $("diag-test-result");
  if (!phone) {
    resBox.innerHTML = `<span style="color:#ef4444">Please enter a recipient phone number (e.g. +917439030190).</span>`;
    return;
  }
  resBox.innerHTML = `<span class="muted">Sending test ping to Meta...</span>`;
  const r = await j("POST", "/api/v1/debug/test-whatsapp", { phone: phone, message: "Aahaar Diagnostic: Live WhatsApp Test Ping!" });
  if (r.ok && r.data && r.data.success) {
    resBox.innerHTML = `<span style="color:#10b981">✓ Success! Meta accepted message for delivery. HTTP 200 OK</span>`;
  } else {
    const err = (r.data && r.data.error) ? JSON.stringify(r.data.error, null, 2) : "Unknown error";
    const code = (r.data && r.data.http_code) ? `HTTP ${r.data.http_code}: ` : "";
    resBox.innerHTML = `<span style="color:#ef4444">✗ Meta Error: ${code}${esc(err)}</span>`;
  }
  loadDiagnostics();
}

async function subscribeWabaWebhooks() {
  const wabaInput = $("diag-waba-id");
  const wabaId = (wabaInput ? wabaInput.value : "").trim();
  const resBox = $("waba-sub-result");
  if (!resBox) return;
  resBox.innerHTML = `<span class="muted">Contacting Meta Graph API to subscribe WABA webhooks...</span>`;
  const r = await j("POST", "/api/v1/debug/meta/subscribe", { waba_id: wabaId || null });
  if (r.ok && r.data && r.data.success) {
    resBox.innerHTML = `<span style="color:#10b981;font-weight:bold;">✓ Success! WABA ${esc(r.data.waba_id || "")} is now subscribed to your webhooks in Meta! Send a WhatsApp message to test now.</span>`;
  } else {
    const err = (r.data && r.data.error) ? (typeof r.data.error === 'object' ? JSON.stringify(r.data.error, null, 2) : r.data.error) : "Unknown error";
    resBox.innerHTML = `<span style="color:#ef4444;">✗ Subscription Notice: ${esc(err)}</span>`;
  }
  loadDiagnostics();
}

async function testGeminiAPI() {
  const keyInput = $("diag-gemini-key");
  const apiKey = (keyInput ? keyInput.value : "").trim();
  const resBox = $("gemini-test-result");
  if (!resBox) return;
  resBox.innerHTML = `<span class="muted">Testing Gemini API connection...</span>`;
  const r = await j("POST", "/api/v1/debug/test-gemini", { api_key: apiKey || null });
  if (r.ok && r.data && r.data.success) {
    resBox.innerHTML = `<span style="color:#10b981;font-weight:bold;">✓ Active! Model: ${esc(r.data.model)}</span>\n<span class="muted">Reply: "${esc(r.data.reply)}"</span>`;
  } else {
    const err = (r.data && r.data.error) ? (typeof r.data.error === 'object' ? JSON.stringify(r.data.error, null, 2) : r.data.error) : "Connection failed";
    const details = (r.data && r.data.details) ? "\n" + r.data.details.join("\n") : "";
    resBox.innerHTML = `<span style="color:#ef4444;">✗ Error: ${esc(err)}${esc(details)}</span>`;
  }
  loadDiagnostics();
}

// ---------- context ----------
async function loadContext() {
  const mid = state.active;
  if (!mid || Number.isNaN(Number(mid))) return;
  const [m, ctx] = await Promise.all([
    j("GET", `/api/v1/patients/${mid}/metrics`),
    j("GET", `/api/v1/patients/${mid}/report`),
  ]);
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

// ---------- daily log (day + slot view) ----------
const SLOT_LABELS = {
  Morning: "Morning", Afternoon: "Afternoon", Evening: "Evening",
  Fasting: "Fasting", "Pre-meal": "Pre-meal", Other: "Other",
};

async function loadDayLog() {
  const body = $("daylog-body");
  const note = $("daylog-note");
  if (!body || !state.active) return;
  note.textContent = "loading…";
  body.innerHTML = '<div class="empty">loading…</div>';
  const r = await j("GET", `/api/v1/patients/${state.active}/daily-log`);
  if (!r.ok || !r.data) {
    note.textContent = "";
    body.innerHTML = '<div class="empty">no data yet — readings and meals appear here once logged.</div>';
    return;
  }
  const days = r.data.days || [];
  note.textContent = `${days.length} day${days.length === 1 ? "" : "s"}`;
  if (!days.length) {
    body.innerHTML = '<div class="empty">no readings or meals logged yet.</div>';
    return;
  }
  body.innerHTML = days.map((d) => {
    const rows = (d.readings || []).map((g) => {
      const badge = g.status === "pending"
        ? `<span class="badge warn" title="value not confirmed by the patient yet">needs confirmation${g.candidates && g.candidates.length ? " · " + esc(g.candidates.join(" v/s ")) : ""}</span>`
        : "";
      const sl = (g.slot_label && SLOT_LABELS[g.slot_label]) ? SLOT_LABELS[g.slot_label] : (TAG_LABELS[g.tag] || g.tag || "");
      return `<tr><td>${hhmm(g.ts)}</td><td><span class="slot-chip">${esc(sl)}</span></td>`
        + `<td class="num"><b>${fmt(g.value)}</b> mg/dL</td><td>${badge}</td></tr>`;
    }).join("");
    const mealRows = (d.meals || []).map((m) => {
      const items = (m.items || []).map((i) => esc(i.item || "")).join(", ");
      const src = m.source === "ai" ? " (AI)" : "";
      return `<div class="meal-line"><span>${hhmm(m.ts)}</span>`
        + `${m.portion ? `<span class="slot-chip">${esc((m.portion || "").toUpperCase())}</span>` : ""}`
        + `<span class="meal-items">${items}</span>`
        + `<span class="muted">${fmt(m.carbs)}g carbs · GI ${fmt(m.gi)}${src}</span></div>`;
    }).join("");
    return `<div class="card daylog-card"><h3>${esc(d.date)}</h3>`
      + (rows ? `<table class="daylog-table"><thead><tr><th>time</th><th>slot</th><th>sugar</th><th></th></tr></thead><tbody>${rows}</tbody></table>` : `<p class="muted">no readings</p>`)
      + (mealRows ? `<h4 style="margin:0.7rem 0 0.3rem;font-size:0.85rem;">Meals</h4>${mealRows}` : "")
      + `</div>`;
  }).join("");
}
function setupTabs() {
  document.querySelectorAll("#tabs button").forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll("#tabs button").forEach((x) => x.classList.remove("active"));
      document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      $("tab-" + b.dataset.tab).classList.add("active");
      if (b.dataset.tab === "trends") showTrends();
      if (b.dataset.tab === "daylog") loadDayLog();
      if (b.dataset.tab === "report" && state.reportBuilt) loadPreview();
      if (b.dataset.tab === "audit") loadAudit();
      if (b.dataset.tab === "messages") { scrollThread(); refreshLiveInbound(); }
      if (b.dataset.tab === "live") { populateLive(); loadDiagnostics(); }
    };
  });

  $("live-save").onclick = saveLive;
  const dmBtn = $("direct-msg-send");
  if (dmBtn) dmBtn.onclick = sendDirectMessage;
  const pingBtn = $("btn-test-ping");
  if (pingBtn) pingBtn.onclick = testWhatsAppPing;
  const wabaBtn = $("btn-subscribe-waba");
  if (wabaBtn) wabaBtn.onclick = subscribeWabaWebhooks;
  const geminiBtn = $("btn-test-gemini");
  if (geminiBtn) geminiBtn.onclick = testGeminiAPI;
  const intakeBtn = $("btn-run-intake");
  if (intakeBtn) intakeBtn.onclick = runIntakeAnalysis;
}

async function runIntakeAnalysis() {
  const note = $("intake-result");
  const key = ($("intake-key")?.value || "").trim();
  if (!key) {
    note.textContent = "Enter the operator key first (AAHAAR_OP_KEY, demo default aahaar-2026).";
    return;
  }
  const send = $("intake-auto-send")?.checked ?? false;
  note.textContent = send
    ? "Running intake analysis and releasing follow-ups via WhatsApp..."
    : "Running intake analysis over stored messages (no WhatsApp messages will be sent)...";
  try {
    const r = await j("POST", "/api/v1/analyze/stored?limit=25", { limit: 25, send }, { "X-Aahaar-Key": key });
    if (r.ok) {
      const sent = r.data.sent ?? 0;
      if (sent > 0) {
        note.textContent =
          `analyzed ${r.data.analyzed ?? 0} · follow-ups sent ${sent} · skipped ${r.data.skipped ?? 0}
(sent one at a time via the doctor's WhatsApp channel; Gemini only reads stored rows)`;
      } else {
        note.textContent =
          `analyzed ${r.data.analyzed ?? 0} · nothing sent. Review the AI hints in the feed — tick "Send follow-up via WhatsApp" and run again to release follow-ups for messages that need them.`;
      }
      if (state.active) refreshThreadAndContext();
    } else {
      note.textContent = "error: " + (r.data.error || "HTTP " + r.status);
    }
  } catch (e) {
    note.textContent = "error: " + e.message;
  }
}

// ---------- messages / chat ----------
function renderThread() {
  const el = $("thread");
  if (!state.thread.length) {
    el.innerHTML = '<div class="thread-empty">No messages yet &mdash; patient WhatsApp messages appear here.</div>';
    return;
  }
  el.innerHTML = state.thread.map((m) => {
    if (m.kind === "sys") return `<div class="bub sys">${esc(m.text)}</div>`;
    const who = m.kind === "in" ? `<span class="who">${esc(m.sender || "")}</span>` : "";
    return `<div class="bub ${m.kind}">${who}${esc(m.text)} <span class="when">${m.when || ""}</span></div>`;
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
  // Sort chronologically by timestamp, placing inbound before outbound on identical second
  all.sort((a, b) => {
    const cmp = (a.ts || "").localeCompare(b.ts || "");
    if (cmp !== 0) return cmp;
    if (a.kind !== b.kind) return a.kind === "in" ? -1 : 1;
    return (a.id || 0) - (b.id || 0);
  });
  const recent = all.length > 60 ? all.slice(-60) : all;

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
  const targets = [
    { feed: $("live-inbound-feed"), count: $("live-inbound-count") },
    { feed: $("live-inbound-feed-live"), count: $("live-inbound-count-live") },
  ];
  for (const t of targets) {
    if (!t.feed) continue;
    if (!r.data.messages.length) {
      t.feed.innerHTML = '<div class="muted">No incoming WhatsApp messages received yet.</div>';
    } else {
      t.feed.innerHTML = r.data.messages.map((m) => {
        const isUnlinked = (m.patient_name || "").includes("Unlinked");
        const linkBtn = isUnlinked && m.sender_phone
          ? `<button type="button" class="btn-sm" style="margin-left:8px;padding:2px 6px;font-size:11px;cursor:pointer;" onclick="linkActivePhone('${esc(m.sender_phone)}')">Link to active patient</button>`
          : "";
        const aiNote = m.ai && m.ai.should_reply && m.ai.reply
          ? `<div style="font-size:11px;color:#7a5d00;margin-top:2px;">AI intake follow-up: "${esc(m.ai.reply)}" (${esc(m.ai.analyzed_by || "offline")})</div>`
          : "";
        return `<div style="padding: 4px 0; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
      <div>
        <span class="badge" style="font-size:10px;background:${isUnlinked ? '#e65100' : '#2e7d32'};color:white;">${esc(m.patient_name)}</span>
        <b>${esc(m.sender_phone || "unknown")}:</b> "${esc(m.raw_text)}"
        <span class="muted" style="font-size:11px;">(${hhmm(m.ts)})</span>
        ${aiNote}
      </div>
      <div>${linkBtn}</div>
    </div>`;
      }).join("");
    }
    if (t.count) t.count.textContent = `${r.data.messages.length} live`;
  }
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
  if (!iso) return "";
  try {
    let s = String(iso).trim();
    if (!s.endsWith("Z") && !s.includes("+") && !s.includes("-", 10)) {
      s += "Z";
    }
    const d = new Date(s);
    if (isNaN(d.getTime())) return String(iso).slice(11, 16);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: true });
  } catch (e) {
    return String(iso).slice(11, 16);
  }
}

function scrollThread() {
  const el = $("thread");
  if (el) el.scrollTop = el.scrollHeight;
}

// ---------- audit ----------
async function loadAudit() {
  if (!state.active) return;
  const r = await j("GET", `/api/v1/patients/${state.active}/log`);
  const el = $("audit");
  if (!r.ok || !r.data.audit) { el.textContent = "no audit entries"; return; }
  el.innerHTML = r.data.audit.slice(0, 80).map((a) =>
    `<div><span class="muted">${hhmm(a.ts)}</span> · ${esc(a.actor)} · ${esc(a.action)}${a.detail ? " — " + esc(a.detail) : ""}</div>`).join("");
}

boot();