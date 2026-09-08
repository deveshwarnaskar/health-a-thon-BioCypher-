"use strict";

const state = { patients: [], active: null };

async function j(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(url, opts);
  return r.json();
}

async function boot() {
  const h = await fetch("/healthz").then((r) => r.json()).catch(() => ({}));
  document.getElementById("channel").textContent = "channel: " + (h.channel || "?");

  state.patients = await j("GET", "/api/v1/patients");
  if (!state.patients.length) return;
  renderPatients();
  selectPatient(state.patients[0].id);
}

function renderPatients() {
  const el = document.getElementById("patient-list");
  el.innerHTML = "";
  for (const p of state.patients) {
    const c = document.createElement("div");
    c.className = "chip" + (p.id === state.active ? " active" : "");
    c.textContent = `${p.name} · window: ${p.window || "none"}`;
    c.onclick = () => selectPatient(p.id);
    el.appendChild(c);
  }
}

async function selectPatient(id) {
  state.active = id;
  renderPatients();
  document.getElementById("build").disabled = false;
  document.getElementById("pdf-link").hidden = true;
  const m = await j("GET", `/api/v1/patients/${id}/metrics`).catch(() => null);
  const box = document.getElementById("metrics");
  if (!m) { box.innerHTML = "no closed/ℹ window data yet — run the demo first."; return; }
  const t = m.tir || {};
  box.innerHTML = `
    <div class="metric"><b>${m.adherence_index ?? "–"}%</b><span>Adherence</span></div>
    <div class="metric"><b>${m.mean_fpg ?? "–"}</b><span>Mean fasting</span></div>
    <div class="metric"><b>${m.mean_ppbg ?? "–"}</b><span>Mean PPBG</span></div>
    <div class="metric"><b>${t.in ?? "–"}%</b><span>In range 70–180</span></div>
    <div class="metric"><b>${m.weekday_ppbg ?? "–"}</b><span>PPBG weekdays</span></div>
    <div class="metric"><b>${m.weekend_ppbg ?? "–"}</b><span>PPBG weekends</span></div>
  `;
  loadLog();
}

async function buildReport() {
  document.getElementById("report-note").textContent = "building…";
  const r = await j("POST", `/api/v1/patients/${state.active}/report/build`);
  if (r.pdf) {
    document.getElementById("pdf-link").hidden = false;
    document.getElementById("pdf-link").href = `/api/v1/patients/${state.active}/report/file`;
    document.getElementById("pdf-link").textContent = "Open PDF (2 pages)";
    document.getElementById("report-note").textContent =
      `built at ${r.pdf} · TIR ${r.metrics.tir.in}%`;
  } else {
    document.getElementById("report-note").textContent = "error: " + (r.error || "unknown");
  }
}

async function sendMsg(ev) {
  ev.preventDefault();
  const sender = document.getElementById("sender").value;
  const text = document.getElementById("msg").value.trim();
  if (!text) return;
  const r = await j("POST", "/api/v1/inbound", {
    patient_id: state.active, sender_phone: sender, kind: "text", text,
  });
  const log = document.getElementById("send-log");
  log.textContent = `[in]  ${sender} → ${text}\n[out] ` +
    (r.replies || []).join(" | ") + "\n" + log.textContent;
  document.getElementById("msg").value = "";
  loadLog();
}

async function loadLog() {
  const d = await j("GET", `/api/v1/patients/${state.active}/log`).catch(() => ({}));
  const out = (d.outbound || []).slice(-12).reverse()
    .map((o) => `[${o.kind}→${o.route}] ${o.body}`).join("\n");
  document.getElementById("log").textContent = out || "–";
}

document.getElementById("build").onclick = buildReport;
document.getElementById("msg-form").onsubmit = sendMsg;
boot();