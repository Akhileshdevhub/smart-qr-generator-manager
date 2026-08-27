/* Tiny API helper shared by every page.
   Stores the JWT in localStorage and attaches it as a Bearer header. This is a
   real web app served over HTTP, so localStorage is appropriate here (the
   trade-offs vs httpOnly cookies are discussed in the interview guide). */

const TOKEN_KEY = "qr_token";

const Auth = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
  isLoggedIn: () => !!localStorage.getItem(TOKEN_KEY),
};

async function api(path, { method = "GET", body = null, auth = true } = {}) {
  const headers = {};
  const opts = { method, headers };
  if (body !== null) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  if (auth && Auth.get()) headers["Authorization"] = "Bearer " + Auth.get();

  const res = await fetch(path, opts);
  if (res.status === 401) {
    Auth.clear();
    if (!location.pathname.startsWith("/login")) location.href = "/login";
    throw new Error("Not authenticated");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

/* Fetch a binary (image/pdf) endpoint that needs the auth header and return an
   object URL. Used for the saved-QR image and downloads. */
async function apiBlob(path, { method = "GET", body = null, auth = true } = {}) {
  const headers = {};
  const opts = { method, headers };
  if (body !== null) { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  if (auth && Auth.get()) headers["Authorization"] = "Bearer " + Auth.get();
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error("Failed to load image");
  return URL.createObjectURL(await res.blob());
}

/* Trigger a browser download for an authenticated file endpoint. */
async function downloadFile(path, filename) {
  const url = await apiBlob(path);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

function requireAuth() {
  if (!Auth.isLoggedIn()) location.href = "/login";
}

function toast(msg) {
  let wrap = document.querySelector(".toast-wrap");
  if (!wrap) { wrap = document.createElement("div"); wrap.className = "toast-wrap"; document.body.appendChild(wrap); }
  const t = document.createElement("div"); t.className = "toast"; t.textContent = msg;
  wrap.appendChild(t);
  setTimeout(() => t.remove(), 2600);
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
