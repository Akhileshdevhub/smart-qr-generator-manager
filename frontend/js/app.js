/* Single-page app logic for the authenticated area.
   Plain vanilla JS with hash-based routing (#dashboard, #generate, ...).
   Each view is a render function that fills the #view container. Kept
   deliberately framework-free and readable. */

requireAuth();

const view = document.getElementById("view");
const viewTitle = document.getElementById("viewTitle");
const charts = {};                     // live Chart.js instances, destroyed before re-render
const ACCENT = "#3b53d6";

// ---- content-type definitions used by the generator ----
const TYPES = {
  url:   { label: "URL",     fields: [["url", "Destination URL", "text", "https://example.com"]] },
  text:  { label: "Text",    fields: [["text", "Text", "textarea", "Hello from my QR project"]] },
  wifi:  { label: "Wi-Fi",   fields: [
            ["ssid", "Network name (SSID)", "text", ""],
            ["password", "Password", "text", ""],
            ["encryption", "Encryption", "select", ["WPA", "WEP", "nopass"]],
            ["hidden", "Hidden network", "checkbox", ""]] },
  vcard: { label: "Contact", fields: [
            ["name", "Full name", "text", ""],
            ["phone", "Phone", "text", ""],
            ["email", "Email", "text", ""],
            ["org", "Organisation", "text", ""],
            ["url", "Website", "text", ""],
            ["address", "Address", "text", ""]] },
  email: { label: "Email",   fields: [
            ["to", "Recipient", "text", "name@example.com"],
            ["subject", "Subject", "text", ""],
            ["body", "Body", "textarea", ""]] },
  phone: { label: "Phone",   fields: [["phone", "Phone number", "text", "+1 555 123 4567"]] },
};

// =====================================================================
// Routing
// =====================================================================
function route() {
  const name = (location.hash.replace("#", "").split("?")[0]) || "dashboard";
  document.querySelectorAll("#sideNav a").forEach((a) =>
    a.classList.toggle("active", a.dataset.view === name));
  document.getElementById("sidebar").classList.remove("open");
  const map = {
    dashboard: ["Dashboard", renderDashboard],
    generate: ["Generate QR", renderGenerate],
    codes: ["My QR Codes", renderCodes],
    analytics: ["Analytics", renderAnalytics],
    settings: ["Settings", renderSettings],
  };
  const [title, fn] = map[name] || map.dashboard;
  viewTitle.textContent = title;
  closeModal();  // never let a modal linger across a view change
  Object.values(charts).forEach((c) => c && c.destroy());
  fn();
}

window.addEventListener("hashchange", route);

async function init() {
  document.getElementById("menuBtn").addEventListener("click", () =>
    document.getElementById("sidebar").classList.toggle("open"));
  try {
    const me = await api("/api/auth/me");
    document.getElementById("whoami").textContent = me.display_name || me.email;
  } catch (e) { /* handled by api() 401 redirect */ }
  route();
}

// =====================================================================
// Dashboard
// =====================================================================
async function renderDashboard() {
  view.innerHTML = `<div class="empty"><span class="spinner"></span></div>`;
  const d = await api("/api/analytics/overview");
  const topRows = d.top_qr.length
    ? d.top_qr.map((q) => `<tr><td>${escapeHtml(q.name)}</td>
        <td><code>${escapeHtml(q.short_id)}</code></td>
        <td>${q.scan_count}</td></tr>`).join("")
    : `<tr><td colspan="3" class="muted">No QR codes yet. <a href="#generate">Create one</a>.</td></tr>`;

  view.innerHTML = `
    <div class="stats">
      <div class="stat"><div class="label">Total QR codes</div><div class="value">${d.total_qr}</div></div>
      <div class="stat"><div class="label">Active</div><div class="value">${d.active_qr}</div></div>
      <div class="stat"><div class="label">Total scans</div><div class="value">${d.total_scans}</div></div>
      <div class="stat"><div class="label">Scans this week</div><div class="value">${d.scans_this_week}</div></div>
    </div>
    <div class="chart-card">
      <h3>Scans over the last 14 days</h3>
      <canvas id="trend" height="90"></canvas>
    </div>
    <div class="card">
      <h3>Top QR codes by scans</h3>
      <table><thead><tr><th>Name</th><th>Short ID</th><th>Scans</th></tr></thead>
      <tbody>${topRows}</tbody></table>
    </div>`;

  lineChart("trend", d.scans_over_time);
}

// =====================================================================
// Generator
// =====================================================================
const gen = { type: "url", mode: "static", logoFile: null };
let previewTimer = null;

function renderGenerate() {
  view.innerHTML = `
    <div class="gen-grid">
      <div>
        <div class="card" style="margin-bottom:20px;">
          <label>Content type</label>
          <div class="type-tabs" id="typeTabs"></div>

          <label>Mode</label>
          <div class="mode-toggle" id="modeToggle">
            <label data-mode="static" class="sel"><input type="radio" name="mode" value="static" checked hidden>
              <span><span class="t">Static</span><br><span class="d">Content encoded directly. Cannot be changed later.</span></span></label>
            <label data-mode="dynamic"><input type="radio" name="mode" value="dynamic" hidden>
              <span><span class="t">Dynamic</span><br><span class="d">Editable redirect. Change the destination anytime (URL only).</span></span></label>
          </div>
          <div id="modeNote"></div>

          <div id="fields" style="margin-top:12px;"></div>

          <div class="field">
            <label for="qrName">Project name</label>
            <input type="text" id="qrName" placeholder="My website" maxlength="120">
          </div>
        </div>

        <div class="card">
          <h3 style="font-size:15px;">Style</h3>
          <div class="row">
            <div class="field"><label>Foreground</label><input type="color" id="fg" value="#000000"></div>
            <div class="field"><label>Background</label><input type="color" id="bg" value="#ffffff"></div>
          </div>
          <div class="row">
            <div class="field"><label>Size (px/module): <span id="scaleVal">10</span></label>
              <input type="range" id="scale" min="4" max="20" value="10"></div>
            <div class="field"><label>Quiet zone: <span id="borderVal">4</span></label>
              <input type="range" id="border" min="1" max="10" value="4"></div>
          </div>
          <div class="row">
            <div class="field"><label>Error correction</label>
              <select id="error">
                <option value="L">L — 7%</option>
                <option value="M" selected>M — 15%</option>
                <option value="Q">Q — 25%</option>
                <option value="H">H — 30% (best for logos)</option>
              </select></div>
            <div class="field"><label>Centre logo (optional)</label>
              <input type="file" id="logo" accept="image/png,image/jpeg,image/webp"></div>
          </div>
        </div>
      </div>

      <div class="preview-panel">
        <div class="preview-box">
          <img id="preview" alt="QR preview">
          <div id="warnings" style="margin-top:12px; text-align:left;"></div>
          <button class="btn" id="genBtn" style="width:100%; margin-top:14px;">Generate &amp; save</button>
        </div>
        <p class="hint" style="margin-top:10px;">A logo is applied after saving, on the saved code.</p>
      </div>
    </div>`;

  // type tabs
  const tabs = document.getElementById("typeTabs");
  tabs.innerHTML = Object.entries(TYPES).map(([k, v]) =>
    `<button data-type="${k}" class="${k === gen.type ? "active" : ""}">${v.label}</button>`).join("");
  tabs.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    if (gen.mode === "dynamic" && b.dataset.type !== "url") return;
    gen.type = b.dataset.type;
    tabs.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
    renderFields(); schedulePreview();
  }));

  // mode toggle
  document.querySelectorAll("#modeToggle label").forEach((l) => l.addEventListener("click", () => {
    gen.mode = l.dataset.mode;
    document.querySelectorAll("#modeToggle label").forEach((x) => x.classList.toggle("sel", x === l));
    l.querySelector("input").checked = true;
    const note = document.getElementById("modeNote");
    if (gen.mode === "dynamic") {
      gen.type = "url";
      tabs.querySelectorAll("button").forEach((x) => {
        x.classList.toggle("active", x.dataset.type === "url");
        x.disabled = x.dataset.type !== "url";
        x.style.opacity = x.dataset.type !== "url" ? .4 : 1;
      });
      note.innerHTML = `<div class="alert info">Dynamic codes encode a short redirect URL, so you can change the destination later without reprinting.</div>`;
    } else {
      tabs.querySelectorAll("button").forEach((x) => { x.disabled = false; x.style.opacity = 1; });
      note.innerHTML = "";
    }
    renderFields(); schedulePreview();
  }));

  ["fg", "bg", "error"].forEach((id) =>
    document.getElementById(id).addEventListener("input", schedulePreview));
  document.getElementById("scale").addEventListener("input", (e) => {
    document.getElementById("scaleVal").textContent = e.target.value; schedulePreview(); });
  document.getElementById("border").addEventListener("input", (e) => {
    document.getElementById("borderVal").textContent = e.target.value; schedulePreview(); });
  document.getElementById("logo").addEventListener("change", (e) => {
    gen.logoFile = e.target.files[0] || null; });
  document.getElementById("genBtn").addEventListener("click", onGenerate);

  renderFields();
  schedulePreview();
}

function renderFields() {
  const wrap = document.getElementById("fields");
  wrap.innerHTML = TYPES[gen.type].fields.map(([key, label, kind, extra]) => {
    if (kind === "textarea")
      return `<div class="field"><label>${label}</label><textarea rows="3" data-key="${key}">${extra || ""}</textarea></div>`;
    if (kind === "select")
      return `<div class="field"><label>${label}</label><select data-key="${key}">${
        extra.map((o) => `<option value="${o}">${o}</option>`).join("")}</select></div>`;
    if (kind === "checkbox")
      return `<div class="field"><label style="display:flex;gap:8px;align-items:center;font-weight:500;">
        <input type="checkbox" data-key="${key}" style="width:auto;"> ${label}</label></div>`;
    return `<div class="field"><label>${label}</label><input type="text" data-key="${key}" value="${escapeHtml(extra || "")}"></div>`;
  }).join("");
  wrap.querySelectorAll("[data-key]").forEach((el) =>
    el.addEventListener("input", schedulePreview));
}

function collectContent() {
  const content = {};
  document.querySelectorAll("#fields [data-key]").forEach((el) => {
    content[el.dataset.key] = el.type === "checkbox" ? el.checked : el.value;
  });
  return content;
}

function collectStyle() {
  return {
    fg_color: document.getElementById("fg").value,
    bg_color: document.getElementById("bg").value,
    scale: parseInt(document.getElementById("scale").value, 10),
    border: parseInt(document.getElementById("border").value, 10),
    error: document.getElementById("error").value,
  };
}

function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(updatePreview, 300);
}

async function updatePreview() {
  const content = collectContent();
  const body = { qr_type: gen.type, mode: gen.mode, content, style: collectStyle() };
  if (gen.mode === "dynamic") body.destination_url = content.url;
  try {
    const res = await fetch("/api/qr/preview", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const warnBox = document.getElementById("warnings");
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      warnBox.innerHTML = `<div class="alert warn">${escapeHtml(err.detail || "Fill in the fields to preview")}</div>`;
      return;
    }
    document.getElementById("preview").src = URL.createObjectURL(await res.blob());
    const warnings = JSON.parse(res.headers.get("X-Scan-Warnings") || "[]");
    warnBox.innerHTML = warnings.map((w) =>
      `<div class="alert ${w.level === "warning" ? "warn" : "info"}">${escapeHtml(w.message)}</div>`).join("");
    if (gen.logoFile)
      warnBox.innerHTML += `<div class="alert info">A logo will be added on save; error correction becomes H automatically.</div>`;
  } catch (e) { /* ignore transient */ }
}

async function onGenerate() {
  const name = document.getElementById("qrName").value.trim();
  if (!name) { toast("Please give your QR a name"); return; }
  const content = collectContent();
  const body = { name, qr_type: gen.type, mode: gen.mode, content, style: collectStyle() };
  if (gen.mode === "dynamic") body.destination_url = content.url;

  const btn = document.getElementById("genBtn");
  btn.disabled = true; btn.textContent = "Saving...";
  try {
    const proj = await api("/api/qr", { method: "POST", body });
    if (gen.logoFile) {
      const fd = new FormData(); fd.append("file", gen.logoFile);
      const r = await fetch(`/api/qr/${proj.id}/logo`, {
        method: "POST", headers: { Authorization: "Bearer " + Auth.get() }, body: fd });
      if (!r.ok) toast("QR saved, but the logo was rejected");
    }
    gen.logoFile = null;
    toast("QR code saved");
    location.hash = "#codes";
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false; btn.textContent = "Generate & save";
  }
}

// =====================================================================
// My QR Codes
// =====================================================================
async function renderCodes() {
  view.innerHTML = `<div class="empty"><span class="spinner"></span></div>`;
  const items = await api("/api/qr");
  if (!items.length) {
    view.innerHTML = `<div class="empty">No QR codes yet.<br><br><a class="btn" href="#generate">Create your first QR</a></div>`;
    return;
  }
  const rows = items.map((q) => `
    <tr>
      <td>
        <strong>${escapeHtml(q.name)}</strong><br>
        <span class="muted" style="font-size:12px;">${escapeHtml(q.destination_url || "")}</span>
      </td>
      <td><span class="badge ${q.mode}">${q.mode}</span></td>
      <td>${TYPES[q.qr_type] ? TYPES[q.qr_type].label : q.qr_type}</td>
      <td>${q.scan_count}</td>
      <td><span class="badge ${q.active ? "active" : "inactive"}">${q.active ? "active" : "inactive"}</span></td>
      <td style="white-space:nowrap;">
        <button class="btn small secondary" data-act="view" data-id="${q.id}">Open</button>
        <button class="btn small secondary" data-act="analytics" data-id="${q.id}">Analytics</button>
        <button class="btn small secondary" data-act="edit" data-id="${q.id}">Edit</button>
        <button class="btn small danger" data-act="delete" data-id="${q.id}">Delete</button>
      </td>
    </tr>`).join("");

  view.innerHTML = `<div class="card"><table>
    <thead><tr><th>Name</th><th>Mode</th><th>Type</th><th>Scans</th><th>Status</th><th></th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;

  view.querySelectorAll("button[data-act]").forEach((b) => b.addEventListener("click", () => {
    const id = b.dataset.id, act = b.dataset.act;
    if (act === "analytics") location.hash = `#analytics?id=${id}`;
    else if (act === "delete") confirmDelete(id);
    else if (act === "edit") openEditor(id);
    else if (act === "view") openViewer(id);
  }));
}

async function openViewer(id) {
  const q = await api(`/api/qr/${id}`);
  const imgUrl = await apiBlob(`/api/qr/${id}/image`);
  const verify = await api(`/api/qr/${id}/verify`);
  modal(`
    <h3>${escapeHtml(q.name)}</h3>
    <div style="text-align:center;">
      <img src="${imgUrl}" width="220" style="border:1px solid var(--border);border-radius:8px;padding:8px;">
    </div>
    <p class="muted" style="text-align:center;">
      <span class="badge ${q.mode}">${q.mode}</span>
      ${verify.verified ? '<span class="badge active">✓ verified scannable</span>' : '<span class="badge inactive">could not verify</span>'}
    </p>
    ${q.redirect_url ? `<p class="hint">Encoded redirect: <code>${escapeHtml(q.redirect_url)}</code></p>` : ""}
    <p class="hint">Points to: <code>${escapeHtml(q.destination_url || "")}</code></p>
    <div style="margin-top:14px; display:flex; gap:8px; flex-wrap:wrap;">
      <button class="btn small" data-dl="png">PNG</button>
      <button class="btn small" data-dl="svg">SVG</button>
      <button class="btn small" data-dl="pdf">PDF</button>
      <button class="btn small secondary" id="dupBtn">Duplicate</button>
      <button class="btn small secondary" data-close>Close</button>
    </div>`);
  document.querySelectorAll("[data-dl]").forEach((b) => b.addEventListener("click", () =>
    downloadFile(`/api/qr/${id}/download?fmt=${b.dataset.dl}`, `${q.name}.${b.dataset.dl}`)));
  document.getElementById("dupBtn").addEventListener("click", async () => {
    await api(`/api/qr/${id}/duplicate`, { method: "POST" }); closeModal(); toast("Duplicated"); renderCodes();
  });
}

async function openEditor(id) {
  const q = await api(`/api/qr/${id}`);
  modal(`
    <h3>Edit “${escapeHtml(q.name)}”</h3>
    <div class="field"><label>Name</label><input type="text" id="eName" value="${escapeHtml(q.name)}"></div>
    ${q.mode === "dynamic" ? `<div class="field"><label>Destination URL (changing this keeps the same QR image)</label>
      <input type="text" id="eDest" value="${escapeHtml(q.destination_url || "")}"></div>` : ""}
    <div class="field"><label style="display:flex;gap:8px;align-items:center;font-weight:500;">
      <input type="checkbox" id="eActive" style="width:auto;" ${q.active ? "checked" : ""}> Active (inactive codes stop redirecting)</label></div>
    <div class="row">
      <div class="field"><label>Foreground</label><input type="color" id="eFg" value="${q.style.fg_color || "#000000"}"></div>
      <div class="field"><label>Background</label><input type="color" id="eBg" value="${q.style.bg_color || "#ffffff"}"></div>
    </div>
    <div class="field"><label>Logo</label>
      <input type="file" id="eLogo" accept="image/png,image/jpeg,image/webp">
      ${q.has_logo ? `<button class="btn small secondary" id="rmLogo" style="margin-top:8px;">Remove current logo</button>` : ""}
    </div>
    <div style="margin-top:14px; display:flex; gap:8px; justify-content:flex-end;">
      <button class="btn secondary" data-close>Cancel</button>
      <button class="btn" id="saveEdit">Save</button>
    </div>`);

  const rm = document.getElementById("rmLogo");
  if (rm) rm.addEventListener("click", async () => {
    await api(`/api/qr/${id}/logo`, { method: "DELETE" }); toast("Logo removed"); closeModal(); });

  document.getElementById("saveEdit").addEventListener("click", async () => {
    const body = {
      name: document.getElementById("eName").value.trim(),
      active: document.getElementById("eActive").checked,
      style: { ...q.style, fg_color: document.getElementById("eFg").value, bg_color: document.getElementById("eBg").value },
    };
    const dest = document.getElementById("eDest");
    if (dest) body.destination_url = dest.value.trim();
    try {
      await api(`/api/qr/${id}`, { method: "PUT", body });
      const lf = document.getElementById("eLogo").files[0];
      if (lf) {
        const fd = new FormData(); fd.append("file", lf);
        await fetch(`/api/qr/${id}/logo`, { method: "POST", headers: { Authorization: "Bearer " + Auth.get() }, body: fd });
      }
      closeModal(); toast("Saved"); renderCodes();
    } catch (e) { toast(e.message); }
  });
}

function confirmDelete(id) {
  modal(`<h3>Delete this QR code?</h3>
    <p class="muted">This permanently removes the project and its scan history. If it's a printed dynamic code, it will stop redirecting.</p>
    <div style="display:flex; gap:8px; justify-content:flex-end;">
      <button class="btn secondary" data-close>Cancel</button>
      <button class="btn danger" id="delYes">Delete</button></div>`);
  document.getElementById("delYes").addEventListener("click", async () => {
    await api(`/api/qr/${id}`, { method: "DELETE" }); closeModal(); toast("Deleted"); renderCodes();
  });
}

// =====================================================================
// Analytics (per-QR)
// =====================================================================
async function renderAnalytics() {
  view.innerHTML = `<div class="empty"><span class="spinner"></span></div>`;
  const items = await api("/api/qr");
  const dynamics = items.filter((q) => q.mode === "dynamic");
  const preId = new URLSearchParams(location.hash.split("?")[1] || "").get("id");

  if (!dynamics.length) {
    view.innerHTML = `<div class="empty">Analytics are recorded for <strong>dynamic</strong> QR codes.<br>
      Create a dynamic code and its scans will appear here.<br><br>
      <a class="btn" href="#generate">Create a dynamic QR</a></div>`;
    return;
  }

  const options = dynamics.map((q) =>
    `<option value="${q.id}" ${String(q.id) === preId ? "selected" : ""}>${escapeHtml(q.name)} (${q.scan_count} scans)</option>`).join("");
  view.innerHTML = `
    <div class="field" style="max-width:360px;">
      <label>Select a dynamic QR code</label>
      <select id="pickQr">${options}</select>
    </div>
    <div id="analyticsBody"></div>`;
  document.getElementById("pickQr").addEventListener("change", (e) => loadQrAnalytics(e.target.value));
  loadQrAnalytics(document.getElementById("pickQr").value);
}

async function loadQrAnalytics(id) {
  const body = document.getElementById("analyticsBody");
  body.innerHTML = `<div class="empty"><span class="spinner"></span></div>`;
  const a = await api(`/api/qr/${id}/analytics`);
  Object.values(charts).forEach((c) => c && c.destroy());

  body.innerHTML = `
    ${a.contains_demo_data ? `<div class="alert warn">This code includes <strong>synthetic demo scans</strong> from the seed script — not real visitors.</div>` : ""}
    <div class="stats">
      <div class="stat"><div class="label">Total scans</div><div class="value">${a.total_scans}</div></div>
      <div class="stat"><div class="label">Today</div><div class="value">${a.scans_today}</div></div>
      <div class="stat"><div class="label">This week</div><div class="value">${a.scans_this_week}</div></div>
      <div class="stat"><div class="label">Devices</div><div class="value">${a.device_breakdown.length}</div></div>
    </div>
    <div class="chart-card"><h3>Scans over the last 14 days</h3><canvas id="aTrend" height="90"></canvas></div>
    <div class="two-col">
      <div class="chart-card"><h3>By device</h3><canvas id="aDevice" height="150"></canvas></div>
      <div class="chart-card"><h3>By browser</h3><canvas id="aBrowser" height="150"></canvas></div>
    </div>`;

  if (a.total_scans === 0) {
    body.innerHTML += `<div class="empty">No scans recorded yet for this code.</div>`;
    return;
  }
  lineChart("aTrend", a.scans_over_time);
  doughnutChart("aDevice", a.device_breakdown);
  barChart("aBrowser", a.browser_breakdown);
}

// =====================================================================
// Settings
// =====================================================================
async function renderSettings() {
  const me = await api("/api/auth/me");
  view.innerHTML = `
    <div class="card" style="max-width:480px; margin-bottom:20px;">
      <h3>Profile</h3>
      <div class="field"><label>Email</label><input type="text" value="${escapeHtml(me.email)}" disabled></div>
      <div class="field"><label>Display name</label><input type="text" id="dn" value="${escapeHtml(me.display_name)}"></div>
      <button class="btn" id="saveProfile">Save</button>
    </div>
    <div class="card" style="max-width:480px;">
      <h3>Session</h3>
      <p class="muted">Log out of this browser.</p>
      <button class="btn danger" id="logout">Log out</button>
    </div>`;
  document.getElementById("saveProfile").addEventListener("click", async () => {
    await api("/api/auth/me", { method: "PUT", body: { display_name: document.getElementById("dn").value } });
    toast("Profile updated");
    document.getElementById("whoami").textContent = document.getElementById("dn").value || me.email;
  });
  document.getElementById("logout").addEventListener("click", () => { Auth.clear(); location.href = "/login"; });
}

// =====================================================================
// Chart helpers (Chart.js)
// =====================================================================
function lineChart(id, series) {
  const el = document.getElementById(id); if (!el || !window.Chart) return;
  charts[id] = new Chart(el, {
    type: "line",
    data: { labels: series.map((p) => p.date.slice(5)),
      datasets: [{ data: series.map((p) => p.count), borderColor: ACCENT,
        backgroundColor: "rgba(59,83,214,.1)", fill: true, tension: .3, pointRadius: 2 }] },
    options: { plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });
}
function doughnutChart(id, items) {
  const el = document.getElementById(id); if (!el || !window.Chart) return;
  charts[id] = new Chart(el, {
    type: "doughnut",
    data: { labels: items.map((i) => i.label),
      datasets: [{ data: items.map((i) => i.count),
        backgroundColor: ["#3b53d6", "#22a06b", "#e0982f", "#b45cd6", "#d65c7a", "#6b7280"] }] },
    options: { plugins: { legend: { position: "bottom" } } },
  });
}
function barChart(id, items) {
  const el = document.getElementById(id); if (!el || !window.Chart) return;
  charts[id] = new Chart(el, {
    type: "bar",
    data: { labels: items.map((i) => i.label),
      datasets: [{ data: items.map((i) => i.count), backgroundColor: ACCENT }] },
    options: { plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });
}

// =====================================================================
// Modal helpers
// =====================================================================
function modal(html) {
  const root = document.getElementById("modalRoot");
  root.innerHTML = `<div class="modal-backdrop"><div class="modal">${html}</div></div>`;
  root.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", closeModal));
  root.querySelector(".modal-backdrop").addEventListener("click", (e) => {
    if (e.target.classList.contains("modal-backdrop")) closeModal();
  });
}
function closeModal() { document.getElementById("modalRoot").innerHTML = ""; }
// Close any open modal with the Escape key.
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

init();
