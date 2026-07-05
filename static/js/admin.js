const $ = (id) => document.getElementById(id);

const TOKEN_KEY = "kms_admin_token1";
let lastPreview = null;
let selectedFile = null;

const adminToken = $("adminToken");
const csvFile = $("csvFile");
const previewBtn = $("previewBtn");
const applyBtn = $("applyBtn");
const saveTokenBtn = $("saveTokenBtn");
const loadHistoryBtn = $("loadHistoryBtn");
const historyEntityId = $("historyEntityId");

function getToken() {
  return sessionStorage.getItem(TOKEN_KEY) || adminToken?.value?.trim() || "";
}

function showToast(msg, isError = false) {
  const el = $("toast");
  if (!el) return;
  el.textContent = msg;
  el.style.background = isError ? "#b91c1c" : "#1e293b";
  el.hidden = false;
  setTimeout(() => { el.hidden = true; }, 4000);
}

function authHeaders() {
  const token = getToken();
  if (!token) throw new Error("חסר אסימון מנהל");
  return { "X-Admin-Token": token };
}

async function apiPostFile(path, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(path, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `שגיאה ${res.status}`);
  return data;
}

async function apiGet(path) {
  const res = await fetch(path, { headers: authHeaders() });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `שגיאה ${res.status}`);
  return data;
}

function esc(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderTable(headers, rows, rowFn) {
  if (!rows?.length) return '<p class="empty-msg">אין רשומות</p>';
  const head = headers.map((h) => `<th>${esc(h)}</th>`).join("");
  const body = rows.map(rowFn).join("");
  return `<table class="admin-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function renderPreview(data) {
  lastPreview = data;
  $("summarySection").hidden = false;
  $("sumNew").textContent = data.summary?.new ?? 0;
  $("sumUpdated").textContent = data.summary?.updated ?? 0;
  $("sumDeleted").textContent = data.summary?.deleted ?? 0;
  $("sumUnchanged").textContent = data.summary?.unchanged ?? 0;

  $("tabNew").innerHTML = renderTable(
    ["entity_id", 'מק"ט', "תיאור", "סוג זכאי", "סוג סכום", "רמת בסיס", "רמת חריגה"],
    data.new,
    (r) => `<tr>
      <td><code>${esc(r.entity_id)}</code></td>
      <td>${esc(r['מק"ט'])}</td>
      <td>${esc(r["תיאור פריט"])}</td>
      <td>${esc(r["סוג זכאי"])}</td>
      <td>${esc(r["סוג סכום"])}</td>
      <td>${esc(r["רמת בסיס"])}</td>
      <td>${esc(r["רמת חריגה"])}</td>
    </tr>`
  );

  $("tabUpdated").innerHTML = renderTable(
    ["entity_id", 'מק"ט', "תיאור", "שינויים"],
    data.updated,
    (r) => {
      const changes = (r.changes || [])
        .map((c) => `<li><strong>${esc(c.field)}</strong>: ${esc(c.old ?? "—")} → ${esc(c.new ?? "—")}</li>`)
        .join("");
      const restored = r.restored ? '<span class="badge-restored">שוחזר</span>' : "";
      return `<tr>
        <td><code>${esc(r.entity_id)}</code> ${restored}</td>
        <td>${esc(r['מק"ט'])}</td>
        <td>${esc(r["תיאור פריט"])}</td>
        <td><ul class="changes-list">${changes || "<li>שוחזר ממחיקה</li>"}</ul></td>
      </tr>`;
    }
  );

  $("tabDeleted").innerHTML = renderTable(
    ["entity_id", 'מק"ט', "תיאור"],
    data.deleted,
    (r) => `<tr>
      <td><code>${esc(r.entity_id)}</code></td>
      <td>${esc(r['מק"ט'])}</td>
      <td>${esc(r["תיאור פריט"])}</td>
    </tr>`
  );

  applyBtn.disabled = !(data.summary?.new || data.summary?.updated || data.summary?.deleted);
}

async function loadSyncRuns() {
  try {
    const data = await apiGet("/api/admin/sync-runs?limit=30");
    $("tabRuns").innerHTML = renderTable(
      ["#", "קובץ", "התחלה", "סטטוס", "חדש", "עודכן", "נמחק", "ללא שינוי"],
      data.runs,
      (r) => `<tr>
        <td>${r.id}</td>
        <td>${esc(r.filename)}</td>
        <td>${esc(r.started_at)}</td>
        <td>${esc(r.status)}</td>
        <td>${r.added_count}</td>
        <td>${r.updated_count}</td>
        <td>${r.deleted_count}</td>
        <td>${r.unchanged_count}</td>
      </tr>`
    );
  } catch (e) {
    $("tabRuns").innerHTML = `<p class="empty-msg">${esc(e.message)}</p>`;
  }
}

async function loadVariantHistory() {
  const eid = historyEntityId?.value?.trim();
  if (!eid) {
    showToast("הזן entity_id", true);
    return;
  }
  try {
    const data = await apiGet(`/api/admin/items/${encodeURIComponent(eid)}/history`);
    $("historyResults").innerHTML = renderTable(
      ["תאריך", "פעולה", "שדה", "ישן", "חדש", "סנכרון"],
      data.history,
      (h) => `<tr>
        <td>${esc(h.changed_at)}</td>
        <td>${esc(h.action)}</td>
        <td>${esc(h.field_name || "—")}</td>
        <td>${esc(h.old_value ?? "—")}</td>
        <td>${esc(h.new_value ?? "—")}</td>
        <td>${esc(h.sync_filename || h.sync_run_id || "—")}</td>
      </tr>`
    );
  } catch (e) {
    $("historyResults").innerHTML = `<p class="empty-msg">${esc(e.message)}</p>`;
  }
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("tab--active", t.dataset.tab === name);
  });
  ["new", "updated", "deleted", "runs", "history"].forEach((n) => {
    const panel = $(`tab${n.charAt(0).toUpperCase()}${n.slice(1)}`);
    if (panel) panel.hidden = n !== name;
  });
  if (name === "runs") loadSyncRuns();
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

saveTokenBtn?.addEventListener("click", () => {
  const t = adminToken?.value?.trim();
  if (!t) {
    showToast("הזן אסימון", true);
    return;
  }
  sessionStorage.setItem(TOKEN_KEY, t);
  showToast("האסימון נשמר");
});

csvFile?.addEventListener("change", () => {
  selectedFile = csvFile.files?.[0] || null;
  previewBtn.disabled = !selectedFile;
  applyBtn.disabled = true;
  lastPreview = null;
});

previewBtn?.addEventListener("click", async () => {
  if (!selectedFile) return;
  previewBtn.disabled = true;
  try {
    const data = await apiPostFile("/api/admin/items/sync/preview", selectedFile);
    renderPreview(data);
    showToast("תצוגה מקדימה הושלמה");
  } catch (e) {
    showToast(e.message, true);
  } finally {
    previewBtn.disabled = !selectedFile;
  }
});

applyBtn?.addEventListener("click", async () => {
  if (!selectedFile) return;
  if (!lastPreview) {
    showToast("הרץ תצוגה מקדימה קודם", true);
    return;
  }
  const s = lastPreview.summary;
  const msg = `להחיל? חדש: ${s.new}, עודכן: ${s.updated}, נמחק: ${s.deleted}`;
  if (!confirm(msg)) return;

  applyBtn.disabled = true;
  try {
    const result = await apiPostFile("/api/admin/items/sync/apply", selectedFile);
    showToast(`הסנכרון הושלם (#${result.sync_run_id})`);
    renderPreview({ ...lastPreview, summary: result.summary, new: [], updated: [], deleted: [] });
    lastPreview = null;
    applyBtn.disabled = true;
    loadSyncRuns();
  } catch (e) {
    showToast(e.message, true);
    applyBtn.disabled = false;
  }
});

loadHistoryBtn?.addEventListener("click", loadVariantHistory);

const saved = sessionStorage.getItem(TOKEN_KEY);
if (saved && adminToken) adminToken.value = saved;

loadSyncRuns();
