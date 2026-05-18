const $ = (id) => document.getElementById(id);

const searchInput = $("searchInput");
const matchSelect = $("matchSelect");
const fieldSelect = $("fieldSelect");
const searchBtn = $("searchBtn");
const resultsContainer = $("resultsContainer");
const resultsCount = $("resultsCount");
const detailContent = $("detailContent");
const detailPanel = $("detailPanel");
const suppliersBody = $("suppliersBody");
const suppliersCount = $("suppliersCount");
const suppliersMakt = $("suppliersMakt");
const statusBadge = $("statusBadge");
const toast = $("toast");
const toggleCurlBtn = $("toggleCurlBtn");
const curlPanel = $("curlPanel");
const curlCode = $("curlCode");
const copyCurlBtn = $("copyCurlBtn");
const mobileFocusBar = $("mobileFocusBar");
const mobileFocusLabel = $("mobileFocusLabel");
const backToResultsBtn = $("backToResultsBtn");
const exportSearchBtn = $("exportSearchBtn");
const exportMaktBtn = $("exportMaktBtn");
const exportAiBtn = $("exportAiBtn");
const aiQueryInput = $("aiQueryInput");
const aiSearchBtn = $("aiSearchBtn");
const aiResultsContainer = $("aiResultsContainer");
const aiStatusBadge = $("aiStatusBadge");
const selectionPlaceholder = $("selectionPlaceholder");
const selectionContent = $("selectionContent");
const selectionHeroBody = $("selectionHeroBody");
const variantsPanel = $("variantsPanel");
const workspaceAside = $("workspaceAside");
const workspaceEl = $("workspace");
const aiSearchDetails = document.querySelector(".ai-search-details");

const SUPPLIER_PHONE_KEYS = ["נייד ספק", "טלפון עבודה ספק", "נייח ספק"];
const EXPORT_SEARCH_LIMIT = 500;

const COMPACT_TABLE_THRESHOLD = 8;
const MAX_VARIANTS_PREVIEW = 100;

let drawerBound = false;
let resultsDelegationBound = false;

let lastSearch = { q: "", match: "contains", field: "all" };
let searchState = { groups: [], items: [] };
let exportState = { makt: null, entityId: null };
let lastAiSearch = { query: "", count: 0 };

const VARIANT_KEYS = [
  ["רמת בסיס", "בסיס"],
  ["רמת חריגה", "חריגה"],
  ["אחוז לחריגה", "אחוז"],
  ["סוג זכאי", "זכאי"],
  ["סוג סכום", "סוג סכום"],
  ["סכום", "סכום"],
];

async function api(path) {
  const res = await fetch(path);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "שגיאה בשרת");
  }
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "שגיאה בשרת");
  }
  return res.json();
}

function showToast(msg, isError = false) {
  toast.textContent = msg;
  toast.className = isError ? "toast toast--error" : "toast";
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, 3500);
}

function esc(text) {
  if (text == null || text === "") return "—";
  const d = document.createElement("div");
  d.textContent = String(text);
  return d.innerHTML;
}

function getMakt(item) {
  return String(item?.['מק"ט'] ?? item?.מקט ?? "").trim();
}

function setExportMakt(makt, entityId = null) {
  exportState.makt = makt || null;
  exportState.entityId = entityId || null;
  updateExportButtons();
}

function updateExportButtons() {
  if (exportSearchBtn) {
    exportSearchBtn.disabled = !(searchState.items?.length > 0);
  }
  if (exportMaktBtn) {
    exportMaktBtn.disabled = !exportState.makt;
  }
  if (exportAiBtn) {
    exportAiBtn.disabled = !(lastAiSearch.count > 0 && lastAiSearch.query);
  }
}

function exportAiSearchResults() {
  const query = lastAiSearch.query || aiQueryInput?.value?.trim();
  if (!query || query.length < 3) {
    showToast("בצע חיפוש חכם לפני ייצוא", true);
    return;
  }
  const params = new URLSearchParams({
    query,
    limit_makts: "50",
  });
  downloadExport(`/api/export/ai/search?${params}`, "kms_ai_search.xlsx");
}

async function downloadExport(url, fallbackName) {
  try {
    showToast("מייצא לאקסל...");
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "שגיאה בייצוא");
    }
    const blob = await res.blob();
    let name = fallbackName;
    const cd = res.headers.get("Content-Disposition");
    if (cd) {
      const m = cd.match(/filename\*=UTF-8''([^;]+)/i);
      if (m) name = decodeURIComponent(m[1]);
    }
    const a = document.createElement("a");
    const href = URL.createObjectURL(blob);
    a.href = href;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
    showToast("הקובץ הורד בהצלחה");
  } catch (e) {
    showToast(e.message, true);
  }
}

function exportSearchResults() {
  if (!lastSearch.q) {
    showToast("בצע חיפוש לפני ייצוא", true);
    return;
  }
  const params = new URLSearchParams({
    q: lastSearch.q,
    match: lastSearch.match,
    field: lastSearch.field,
    limit: String(EXPORT_SEARCH_LIMIT),
  });
  downloadExport(`/api/export/search?${params}`, "kms_search.xlsx");
}

function exportMaktSuppliers() {
  const makt = exportState.makt;
  if (!makt) {
    showToast("בחר מק״ט להצגת ספקים", true);
    return;
  }
  const params = new URLSearchParams();
  if (exportState.entityId) params.set("entity_id", exportState.entityId);
  const qs = params.toString();
  downloadExport(
    `/api/export/makt/${encodeURIComponent(makt)}${qs ? `?${qs}` : ""}`,
    `kms_makt_${makt}.xlsx`
  );
}

function isMobileView() {
  return window.matchMedia("(max-width: 768px)").matches;
}

/** מספר ישראלי לחיוג + תצוגה (מוסיף 0 בתחילה אם חסר, למשל 3-9233345 → 03-9233345) */
function formatIsraeliPhone(raw) {
  const text = String(raw ?? "").trim();
  if (!text || text === "—" || text === "לא מוגדר") return null;

  let digits = text.replace(/[^\d]/g, "");
  if (!digits) return null;
  if (digits.startsWith("972")) digits = "0" + digits.slice(3);

  let display = text;

  if (!digits.startsWith("0") && digits.length >= 7) {
    const area = digits[0];
    const isMobile = digits.length === 9 && area === "5";
    const isLandline =
      digits.length >= 8 && digits.length <= 9 && "23489".includes(area);
    if (isMobile || isLandline) {
      digits = "0" + digits;
      if (!/^0/.test(text)) {
        display = text.replace(/^(\D*)(\d)/, "$10$2");
      }
    }
  }

  if (digits.length < 7) return null;
  return { tel: digits, display };
}

function normalizePhone(raw) {
  const f = formatIsraeliPhone(raw);
  return f ? f.tel : null;
}

function phoneLinkHtml(value) {
  const f = formatIsraeliPhone(value);
  if (!f) {
    const label = String(value ?? "").trim();
    return esc(label || "—");
  }
  return `<a href="tel:${f.tel}" class="tel-link">${esc(f.display)}</a>`;
}

let floatingDescTip = null;
let descTipAnchor = null;
let descTipShowMode = null;
let descTipsGlobalBound = false;

function ensureFloatingDescTip() {
  if (!floatingDescTip) {
    floatingDescTip = document.createElement("div");
    floatingDescTip.className = "desc-float-tip";
    floatingDescTip.hidden = true;
    document.body.appendChild(floatingDescTip);
  }
  return floatingDescTip;
}

function hideDescFloatTip() {
  descTipAnchor = null;
  descTipShowMode = null;
  if (!floatingDescTip) return;
  floatingDescTip.hidden = true;
  floatingDescTip.style.visibility = "";
  floatingDescTip.style.display = "";
  floatingDescTip.textContent = "";
}

function showDescFloatTip(e) {
  const el = e.currentTarget;
  const textEl = el.querySelector(".desc-tip-text");
  const full = el.getAttribute("data-full") || "";
  if (!full || full === "—") {
    hideDescFloatTip();
    return;
  }
  if (textEl && textEl.scrollWidth <= textEl.clientWidth + 2) {
    hideDescFloatTip();
    return;
  }

  const tip = ensureFloatingDescTip();
  descTipAnchor = el;
  descTipShowMode = e.type === "focus" ? "focus" : "pointer";
  tip.textContent = full;
  tip.hidden = false;
  tip.style.visibility = "hidden";
  tip.style.display = "block";

  const r = el.getBoundingClientRect();
  const tw = tip.offsetWidth;
  const th = tip.offsetHeight;
  let left = r.left;
  let top = r.bottom + 6;
  if (top + th > window.innerHeight - 8) top = r.top - th - 6;
  if (left + tw > window.innerWidth - 8) left = window.innerWidth - tw - 8;
  if (left < 8) left = 8;
  tip.style.left = `${left}px`;
  tip.style.top = `${top}px`;
  tip.style.visibility = "visible";
}

function onDescTipMouseOut(e) {
  const el = e.currentTarget;
  const next = e.relatedTarget;
  if (next instanceof Node && el.contains(next)) return;
  if (descTipAnchor === el) hideDescFloatTip();
}

function bindDescTipsGlobal() {
  if (descTipsGlobalBound) return;
  descTipsGlobalBound = true;

  document.addEventListener("scroll", hideDescFloatTip, true);
  window.addEventListener("resize", hideDescFloatTip);

  document.addEventListener(
    "pointerdown",
    (e) => {
      if (descTipAnchor?.contains(e.target)) return;
      hideDescFloatTip();
    },
    true
  );

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideDescFloatTip();
  });

  document.addEventListener("mousemove", (e) => {
    if (!descTipAnchor || floatingDescTip?.hidden || descTipShowMode !== "pointer") return;
    const t = e.target;
    if (t instanceof Node && descTipAnchor.contains(t)) return;
    hideDescFloatTip();
  });

  document.addEventListener("focusin", (e) => {
    if (!descTipAnchor || floatingDescTip?.hidden) return;
    if (e.target instanceof Node && descTipAnchor.contains(e.target)) return;
    hideDescFloatTip();
  });
}

function bindDescTips(container) {
  bindDescTipsGlobal();
  if (!container) return;
  container.querySelectorAll(".desc-tip:not([data-tip-bound])").forEach((el) => {
    el.dataset.tipBound = "1";
    el.addEventListener("mouseenter", showDescFloatTip);
    el.addEventListener("mouseout", onDescTipMouseOut);
    el.addEventListener("focus", showDescFloatTip);
    el.addEventListener("blur", hideDescFloatTip);
  });
}

/** תיאור מקוצר בטבלה + tooltip בהעברת עכבר / מיקוד */
function descCellHtml(text) {
  const full = String(text ?? "").trim() || "—";
  if (full === "—") return "—";
  const safe = esc(full);
  return `<span class="desc-tip" tabindex="0" data-full="${safe}"><span class="desc-tip-text">${safe}</span></span>`;
}

function supplierPhoneCell(s) {
  for (const key of SUPPLIER_PHONE_KEYS) {
    const val = s[key];
    const tel = normalizePhone(val);
    if (tel) return phoneLinkHtml(val);
  }
  return "—";
}

function formatDetailValue(key, value) {
  if (/טלפון|נייד|נייח/i.test(key)) return phoneLinkHtml(value);
  return esc(value);
}

function setAiSearchMode(active) {
  document.querySelector(".app")?.classList.toggle("app--ai-mode", Boolean(active));
  if (workspaceEl) {
    if (active) workspaceEl.setAttribute("hidden", "");
    else workspaceEl.removeAttribute("hidden");
  }
}

function showSelectionWorkspace(show) {
  if (selectionPlaceholder) {
    if (show) selectionPlaceholder.setAttribute("hidden", "");
    else selectionPlaceholder.removeAttribute("hidden");
  }
  if (selectionContent) {
    if (show) selectionContent.removeAttribute("hidden");
    else selectionContent.setAttribute("hidden", "");
  }
}

function scrollToWorkspaceAside() {
  if (isMobileView()) return;
  workspaceAside?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderSelectionHero(makt, desc, variantCount, supplierCount) {
  if (!selectionHeroBody) return;
  const multi = variantCount > 1;
  selectionHeroBody.innerHTML = `
    <div class="selection-hero-inner">
      <div class="selection-hero-top">
        <span class="makt-badge">${esc(makt)}</span>
        ${supplierIndicatorHtml(supplierCount ?? 0)}
      </div>
      <p class="selection-hero-desc">${descCellHtml(desc)}</p>
      <p class="selection-hero-meta">
        ${multi ? `${variantCount} וריאנטים · הספקים זהים לכולם` : "וריאנט יחיד"}
        ${multi ? " · לחץ על וריאנט לפרטים נוספים" : ""}
      </p>
    </div>`;
  bindDescTips(selectionHeroBody);
}

function enterMobileFocus(label) {
  if (!isMobileView()) return;
  document.querySelector(".app")?.classList.add("mobile-focus");
  if (mobileFocusBar) mobileFocusBar.hidden = false;
  if (mobileFocusLabel) mobileFocusLabel.textContent = label;
  requestAnimationFrame(() => {
    workspaceAside?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function exitMobileFocus() {
  hideDescFloatTip();
  document.querySelector(".app")?.classList.remove("mobile-focus");
  variantsPanel?.classList.remove("collapsed-mobile");
  if (mobileFocusBar) mobileFocusBar.hidden = true;
}

function cellVal(item, key) {
  const v = item[key];
  if (v == null || v === "" || v === "לא מוגדר") return "—";
  return esc(v);
}

/** חיווי קטן: יש / אין ספקים מורשים למק״ט */
function supplierIndicatorHtml(count) {
  const n = Number(count);
  if (!Number.isFinite(n) || n < 0) {
    return '<span class="sup-indicator sup-indicator--none" title="אין ספקים מורשים">אין</span>';
  }
  if (n > 0) {
    const label = n === 1 ? "ספק אחד מורשה" : `${n} ספקים מורשים`;
    return `<span class="sup-indicator sup-indicator--yes" title="${esc(label)}">${n}</span>`;
  }
  return '<span class="sup-indicator sup-indicator--none" title="אין ספקים מורשים">אין</span>';
}

function bindDrawerControls() {
  if (drawerBound) return;
  drawerBound = true;
  $("closeDrawerBtn")?.addEventListener("click", () => {
    if (variantsPanel) variantsPanel.hidden = true;
  });
}

function renderVariantsTable(variants, groupIdx, makt, supplierCount) {
  const sup =
    supplierCount ??
    variants[0]?.supplier_count ??
    findGroup(makt)?.supplier_count ??
    0;
  const rows = variants
    .map(
      (v, i) => `
    <tr class="variant-table-row" data-group-idx="${groupIdx}" data-variant-idx="${i}" tabindex="0">
      <td class="num-cell" data-label="#">${i + 1}</td>
      <td class="sup-cell" data-label="ספקים">${supplierIndicatorHtml(v.supplier_count ?? sup)}</td>
      <td data-label="רמת בסיס">${cellVal(v, "רמת בסיס")}</td>
      <td data-label="רמת חריגה">${cellVal(v, "רמת חריגה")}</td>
      <td data-label="אחוז">${cellVal(v, "אחוז לחריגה")}</td>
      <td data-label="סוג זכאי">${cellVal(v, "סוג זכאי")}</td>
      <td data-label="סוג סכום">${cellVal(v, "סוג סכום")}</td>
      <td class="num-cell" data-label="סכום"><strong>${cellVal(v, "סכום")}</strong></td>
    </tr>`
    )
    .join("");

  return `
    <div class="table-wrap variants-table-wrap">
      <table class="data-table variants-table table--cards-mobile">
        <thead>
          <tr>
            <th>#</th>
            <th class="sup-col" title="ספקים מורשים למק״ט">ספקים</th>
            <th>רמת בסיס</th>
            <th>רמת חריגה</th>
            <th>אחוז</th>
            <th>סוג זכאי</th>
            <th>סוג סכום</th>
            <th>סכום</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function amountRange(variants) {
  const nums = variants
    .map((v) => parseFloat(String(v["סכום"] || "").replace(/,/g, "")))
    .filter((n) => !Number.isNaN(n));
  if (!nums.length) return "—";
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  if (min === max) return String(min);
  return `${min.toLocaleString("he-IL")} – ${max.toLocaleString("he-IL")}`;
}

function buildApiUrl() {
  const params = new URLSearchParams({
    q: lastSearch.q,
    match: lastSearch.match,
    field: lastSearch.field,
    limit: "200",
    grouped: "true",
  });
  return `${window.location.origin}/api/items?${params}`;
}

function updateCurl() {
  const url = buildApiUrl();
  curlCode.textContent = `curl -G "${url}" \\\n  -H "Accept: application/json"`;
}

async function checkHealth() {
  try {
    const h = await api("/health");
    const ok = Boolean(h.database_exists);
    statusBadge.textContent = ok ? `מחובר · v${h.version}` : "אין בסיס נתונים";
    statusBadge.className = ok ? "badge badge--ok" : "badge badge--err";
    await updateAiStatus();
  } catch {
    statusBadge.textContent = "שרת לא זמין";
    statusBadge.className = "badge badge--err";
    if (aiStatusBadge) {
      aiStatusBadge.textContent = "לא זמין";
      aiStatusBadge.className = "badge badge--err";
    }
  }
}

async function updateAiStatus() {
  if (!aiStatusBadge) return;
  try {
    const st = await api("/api/ai/status");
    aiStatusBadge.textContent = "חינמי · מקומי";
    aiStatusBadge.className = "badge badge--ok";
    aiStatusBadge.title = st.hint || "חיפוש חכם ללא עלות";
  } catch {
    aiStatusBadge.textContent = "חינמי";
    aiStatusBadge.className = "badge";
  }
}

function isSupplierNearest(s) {
  return s.is_nearest === true || s.is_nearest === 1 || s.is_nearest === "true";
}

function applyNearestFallback(suppliers, userLocation) {
  if (!suppliers?.length) return [];
  const list = suppliers.map((s) => ({ ...s }));
  if (list.some(isSupplierNearest)) return list;
  if (!userLocation) return list;

  let bestIdx = 0;
  let bestScore = -1;
  list.forEach((s, i) => {
    const sc = Number(s.proximity_score) || 0;
    if (sc > bestScore) {
      bestScore = sc;
      bestIdx = i;
    }
  });
  list[bestIdx].is_nearest = true;
  return list;
}

function renderProximityCell(s, nearest) {
  if (nearest) {
    const hint = s.proximity_label
      ? `<span class="proximity-tag proximity-tag--sub">${esc(s.proximity_label)}</span>`
      : "";
    return `<span class="nearest-badge">הכי קרוב</span>${hint}`;
  }
  if (s.proximity_label) {
    return `<span class="proximity-tag">${esc(s.proximity_label)}</span>`;
  }
  return "—";
}

function renderAiSupplierRows(suppliers, userLocation) {
  const rows = applyNearestFallback(suppliers, userLocation);
  if (!rows.length) {
    return '<tr><td colspan="7">אין ספקים מורשים למק״ט זה</td></tr>';
  }
  return rows
    .map((s) => {
      const nearest = isSupplierNearest(s);
      const rowCls = nearest ? "supplier-row supplier-row--nearest" : "supplier-row";
      return `
      <tr class="${rowCls}">
        <td class="proximity-cell" data-label="קרבה">${renderProximityCell(s, nearest)}</td>
        <td data-label="שם ספק">${esc(s["שם ספק"])}</td>
        <td data-label="יישוב">${esc(s["יישוב קליניקה"])}</td>
        <td data-label="טלפון">${supplierPhoneCell(s)}</td>
        <td data-label="אזור">${esc(s["אזור"])}</td>
        <td data-label="בתוקף">${esc(s["האם בתוקף"])}</td>
        <td data-label="מחיר">${esc(s["מחיר הסכם"])}</td>
      </tr>`;
    })
    .join("");
}

function renderAiResults(data) {
  if (!aiResultsContainer) return;
  aiResultsContainer.hidden = false;

  const parsed = data.parsed || {};
  const loc = data.user_location || parsed.location_normalized || parsed.location;
  let parsedHtml = `<strong>ניתוח:</strong> ${esc(parsed.explanation || "—")}`;
  if (loc) parsedHtml += ` · <strong>מיקום:</strong> ${esc(loc)}`;
  if (parsed.search_phrase) {
    parsedHtml += ` · <strong>ביטוי:</strong> ${esc(parsed.search_phrase)}`;
  }
  if (parsed.product_terms?.length) {
    parsedHtml += ` · <strong>מילים:</strong> ${esc(parsed.product_terms.join(", "))}`;
  }

  if (!data.results?.length) {
    setAiSearchMode(false);
    lastAiSearch = { query: data.query || aiQueryInput?.value?.trim() || "", count: 0 };
    updateExportButtons();
    aiResultsContainer.innerHTML = `
      <p class="ai-parsed">${parsedHtml}</p>
      <p class="empty-state">${esc(data.message || "לא נמצאו תוצאות")}</p>`;
    return;
  }

  const cards = data.results
    .map((r) => {
      const makt = r['מק"ט'];
      const note = r.supplier_note
        ? `<p class="hint-inline">${esc(r.supplier_note)}</p>`
        : "";
      return `
      <article class="ai-makt-card">
        <h3>מק״ט <span class="makt-badge makt-badge--sm">${esc(makt)}</span></h3>
        <p class="ai-makt-meta">${esc(r["תיאור פריט"])} · ${r.variant_count || 0} וריאנטים · ${r.supplier_count || 0} ספקים</p>
        ${note}
        <div class="ai-suppliers-wrap table-wrap">
          <table class="data-table ai-suppliers-table">
            <thead>
              <tr>
                <th class="proximity-col">קרבה</th>
                <th>שם ספק</th>
                <th>יישוב</th>
                <th>טלפון</th>
                <th>אזור</th>
                <th>בתוקף</th>
                <th>מחיר</th>
              </tr>
            </thead>
            <tbody>${renderAiSupplierRows(r.suppliers, loc)}</tbody>
          </table>
        </div>
      </article>`;
    })
    .join("");

  aiResultsContainer.innerHTML = `
    <p class="ai-parsed">${parsedHtml}</p>
    <p class="results-mode-hint">נמצאו ${data.count} מק״טים${
      loc
        ? ` · ספק אחד מסומן כהכי קרוב ל־${esc(loc)}`
        : " · לסימון קרבה ציין יישוב (למשל: סל חיפה או גר בחיפה)"
    }</p>
    ${cards}`;
  setAiSearchMode((data.results?.length || 0) > 0);
  lastAiSearch = {
    query: data.query || aiQueryInput?.value?.trim() || "",
    count: data.count || data.results?.length || 0,
  };
  updateExportButtons();
  aiResultsContainer.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function doAiSearch() {
  const query = aiQueryInput?.value?.trim();
  if (!query || query.length < 3) {
    showToast("הזן תיאור חיפוש (לפחות 3 תווים)", true);
    return;
  }
  if (aiSearchBtn) aiSearchBtn.disabled = true;
  if (aiSearchDetails && !aiSearchDetails.open) aiSearchDetails.open = true;
  if (aiResultsContainer) {
    aiResultsContainer.hidden = false;
    aiResultsContainer.innerHTML = '<p class="empty-state">מחפש...</p>';
  }
  try {
    const data = await apiPost("/api/ai/search", { query });
    renderAiResults(data);
    if (data.message && !data.count) showToast(data.message, true);
    else showToast(`נמצאו ${data.count} מק״טים`);
  } catch (e) {
    setAiSearchMode(false);
    lastAiSearch = { query: query, count: 0 };
    updateExportButtons();
    if (aiResultsContainer) {
      aiResultsContainer.innerHTML = `<p class="empty-state">${esc(e.message)}</p>`;
    }
    showToast(e.message, true);
  } finally {
    if (aiSearchBtn) aiSearchBtn.disabled = false;
  }
}

function clearSelection() {
  document.querySelectorAll(".summary-row.selected, .variant-table-row.selected").forEach((el) => {
    el.classList.remove("selected");
  });
}

function bindResultsDelegation() {
  if (!resultsContainer || resultsDelegationBound) return;
  resultsDelegationBound = true;

  resultsContainer.addEventListener("click", (e) => {
    const row = e.target.closest(".summary-row");
    if (!row || !resultsContainer.contains(row)) return;
    selectGroupFromTable(Number(row.dataset.groupIdx), row);
  });

  resultsContainer.addEventListener("keydown", (e) => {
    const row = e.target.closest(".summary-row");
    if (!row || !resultsContainer.contains(row)) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      selectGroupFromTable(Number(row.dataset.groupIdx), row);
    }
  });
}

function bindVariantRow(row, variants, makt, variantCount) {
  const pick = () => {
    const tbody = row.closest("tbody");
    tbody?.querySelectorAll(".variant-table-row").forEach((r) => r.classList.remove("selected"));
    row.classList.add("selected");
    const v = variants[Number(row.dataset.variantIdx)];
    if (v) selectVariantData(v, makt, variantCount);
  };
  row.addEventListener("click", pick);
  row.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      pick();
    }
  });
}

function findGroup(makt) {
  return searchState.groups.find((g) => getMakt(g) === makt);
}

/** טבלת סיכום – כשיש הרבה מק"טים (חיפוש "מכיל") */
function renderCompactTable(groups) {
  const rows = groups
    .map((group, idx) => {
      const makt = getMakt(group);
      const variants = group.variants || [];
      const count = group.variant_count || variants.length;
      const desc = group["תיאור פריט"] || variants[0]?.["תיאור פריט"] || "—";
      const zacai = variants[0]?.["סוג זכאי"] || "—";
      const supCount = group.supplier_count ?? 0;
      return `
        <tr class="summary-row" data-group-idx="${idx}" tabindex="0">
          <td data-label="מק״ט"><span class="makt-badge makt-badge--sm">${esc(makt)}</span></td>
          <td class="sup-cell" data-label="ספקים">${supplierIndicatorHtml(supCount)}</td>
          <td class="desc-cell" data-label="תיאור">${descCellHtml(desc)}</td>
          <td data-label="סוג זכאי">${esc(zacai)}</td>
          <td class="num-cell" data-label="וריאנטים">${count > 1 ? `<span class="pill">${count} וריאנטים</span>` : "1"}</td>
          <td class="num-cell" data-label="טווח סכום">${esc(amountRange(variants))}</td>
        </tr>`;
    })
    .join("");

  resultsContainer.innerHTML = `
    <div class="table-wrap summary-table-wrap">
      <table class="data-table summary-table table--cards-mobile">
        <thead>
          <tr>
            <th>מק״ט</th>
            <th class="sup-col" title="ספקים מורשים">ספקים</th>
            <th>תיאור</th>
            <th>סוג זכאי</th>
            <th>וריאנטים</th>
            <th>טווח סכום</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  bindDrawerControls();
  bindResultsDelegation();
  if (variantsPanel) variantsPanel.hidden = true;
  bindDescTips(resultsContainer);
}

function renderVariantsInDrawer(group, makt, groupIdx) {
  const panel = variantsPanel || $("variantsPanel");
  const body = $("variantsDrawerBody");
  const title = $("drawerTitle");
  if (!panel || !body) return;

  const variants = group.variants || [];
  title.textContent = `מק״ט ${makt} · ${variants.length} וריאנטים`;

  const preview = variants.slice(0, MAX_VARIANTS_PREVIEW);
  const more = variants.length - preview.length;

  body.innerHTML = renderVariantsTable(preview, groupIdx, makt, group.supplier_count);
  if (more > 0) {
    body.innerHTML += `<p class="more-hint">מוצגים ${MAX_VARIANTS_PREVIEW} מתוך ${variants.length}</p>`;
  }

  panel.hidden = false;
  panel.classList.remove("collapsed-mobile");

  body.querySelectorAll(".variant-table-row").forEach((row) => {
    bindVariantRow(row, variants, makt, variants.length);
  });
}

async function selectGroupFromTable(groupIdx, rowEl) {
  const group = searchState.groups[groupIdx];
  if (!group) return;

  try {
    clearSelection();
    rowEl?.classList.add("selected");

    const makt = getMakt(group);
    const variants = group.variants || [];
    const count = variants.length;
    const desc = group["תיאור פריט"] || variants[0]?.["תיאור פריט"] || "—";

    showSelectionWorkspace(true);
    renderSelectionHero(makt, desc, count, group.supplier_count ?? 0);
    setExportMakt(makt, null);

    if (count > 1) {
      renderVariantsInDrawer(group, makt, groupIdx);
    } else if (variantsPanel) {
      variantsPanel.hidden = true;
    }

    detailContent.className = "detail-empty";
    detailContent.textContent = "טוען פרטים...";

    await loadSuppliers(makt, count);

    if (variants.length) {
      await loadVariantDetail(variants[0], makt);
    } else {
      detailContent.className = "detail-empty";
      detailContent.textContent = "לא נמצאו וריאנטים למק״ט זה";
    }

    enterMobileFocus(count > 1 ? `מק״ט ${makt} · בחר וריאנט` : `מק״ט ${makt}`);
    scrollToWorkspaceAside();
    detailPanel?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) {
    detailContent.className = "detail-empty";
    detailContent.textContent = "שגיאה בטעינת פרטים";
    showToast(e.message || "שגיאה בטעינת פרטים", true);
  }
}

/** Collapse – רק כשמק"ט אחד עם כמה וריאנטים */
function renderSingleMaktCollapse(group) {
  const makt = getMakt(group);
  const variants = group.variants || [];
  const count = variants.length;

  resultsContainer.innerHTML = `
    <p class="results-mode-hint">מק״ט ${esc(makt)} · ${count} וריאנטים (שילובי רמות וסכומים)</p>
    <div class="group-card expanded" data-group-idx="0">
      <button type="button" class="group-header open" data-action="toggle-variants">
        <span class="chevron">▾</span>
        <div class="group-main">
          <span class="makt-badge">${esc(makt)}</span>
          <span class="group-title">${descCellHtml(group["תיאור פריט"] || variants[0]?.["תיאור פריט"])}</span>
        </div>
        <span class="variant-badge">${count} וריאנטים</span>
        ${supplierIndicatorHtml(group.supplier_count ?? 0)}
      </button>
      <div class="variant-list" id="variantListSingle"></div>
    </div>`;

  const list = $("variantListSingle");
  list.innerHTML = renderVariantsTable(
    variants.slice(0, MAX_VARIANTS_PREVIEW),
    0,
    makt,
    group.supplier_count
  );
  if (variants.length > MAX_VARIANTS_PREVIEW) {
    list.innerHTML += `<p class="more-hint">מוצגים ${MAX_VARIANTS_PREVIEW} מתוך ${variants.length}</p>`;
  }

  list.querySelectorAll(".variant-table-row").forEach((row) => {
    bindVariantRow(row, variants, makt, count);
  });

  resultsContainer.querySelector('[data-action="toggle-variants"]')?.addEventListener("click", (e) => {
    const btn = e.currentTarget;
    const listEl = $("variantListSingle");
    const open = listEl.classList.toggle("is-collapsed");
    btn.querySelector(".chevron").textContent = open ? "▸" : "▾";
  });
  bindDescTips(resultsContainer);
  bindResultsDelegation();
}

function renderResults(data) {
  hideDescFloatTip();
  const items = data.items || [];
  const groups = data.groups || [];
  searchState = { groups, items };

  resultsCount.textContent = `${items.length} תוצאות · ${groups.length} מק״טים`;

  if (!items.length) {
    resultsContainer.innerHTML = '<p class="empty-state">לא נמצאו תוצאות</p>';
    updateExportButtons();
    return;
  }

  if (groups.length > COMPACT_TABLE_THRESHOLD) {
    renderCompactTable(groups);
    return;
  }

  if (groups.length === 1 && (groups[0].variant_count || groups[0].variants?.length) > 1) {
    renderSingleMaktCollapse(groups[0]);
    updateExportButtons();
    return;
  }

  renderCompactTable(groups);
  updateExportButtons();
}

function renderMaktSummary(makt, variantCount) {
  detailContent.className = "detail-grid";
  detailContent.innerHTML = `
    <div class="makt-summary">
      <p class="makt-summary-title">מק״ט <strong>${esc(makt)}</strong></p>
      <p class="makt-summary-desc">${variantCount} וריאנטים · הספקים חלים על כל הוריאנטים</p>
      <p class="hint-inline">לחץ על וריאנט לפרטים מלאים</p>
    </div>`;
}

function renderDetail(item) {
  if (!item || typeof item !== "object") {
    detailContent.className = "detail-empty";
    detailContent.textContent = "אין פרטים להצגה";
    return;
  }
  const skip = new Set(["authorized_suppliers"]);
  const rows = Object.entries(item)
    .filter(([k]) => !skip.has(k))
    .map(
      ([k, v]) => `
      <div class="detail-row">
        <dt>${esc(k)}</dt>
        <dd>${formatDetailValue(k, v)}</dd>
      </div>`
    )
    .join("");

  const note = item.special_note
    ? `<div class="detail-note">${esc(item.special_note)}</div>`
    : "";

  detailContent.className = "detail-grid";
  const entityLabel = item.entity_id || item.entityId;
  detailContent.innerHTML = `
    ${entityLabel ? `<p class="entity-id-small">${esc(entityLabel)}</p>` : ""}
    ${rows}
    ${note}
  `;
}

function renderSuppliers(makt, suppliers, variantCount) {
  const suffix =
    variantCount > 1 ? ` · ${variantCount} וריאנטים` : "";
  suppliersMakt.innerHTML = makt
    ? `מק״ט: <strong>${esc(makt)}</strong>${suffix}`
    : "";
  suppliersCount.textContent = suppliers.length;

  if (!suppliers.length) {
    suppliersBody.innerHTML =
      '<tr class="empty-row"><td colspan="5">לא נמצאו ספקים מקושרים למק״ט זה</td></tr>';
    return;
  }

  suppliersBody.innerHTML = suppliers
    .map(
      (s) => `
    <tr>
      <td data-label="שם ספק">${esc(s["שם ספק"])}</td>
      <td data-label="יישוב">${esc(s["יישוב קליניקה"])}</td>
      <td data-label="טלפון">${supplierPhoneCell(s)}</td>
      <td data-label="אזור">${esc(s["אזור"])}</td>
      <td data-label="בתוקף">${esc(s["האם בתוקף"])}</td>
    </tr>`
    )
    .join("");
}

async function loadSuppliers(makt, variantCount = 1) {
  if (!makt) {
    setExportMakt(null);
    renderSuppliers("", [], 0);
    return;
  }
  setExportMakt(makt, exportState.entityId);
  suppliersBody.innerHTML =
    '<tr class="loading-row"><td colspan="5">טוען ספקים...</td></tr>';
  try {
    const data = await api(`/api/makt/${encodeURIComponent(makt)}/suppliers`);
    renderSuppliers(makt, data.suppliers || [], variantCount);
  } catch (e) {
    renderSuppliers(makt, [], variantCount);
    showToast(e.message, true);
  }
}

function renderDetailPreview(item) {
  if (!item) return;
  renderDetail(item);
}

async function loadVariantDetail(item, makt) {
  if (!item) return;

  const entityId = item.entity_id || item.entityId;
  if (entityId) setExportMakt(makt, entityId);

  renderDetailPreview(item);

  if (!entityId) return;

  try {
    const full = await api(`/api/item/${encodeURIComponent(entityId)}`);
    renderDetail(full);
  } catch {
    renderDetail(item);
  }
}

async function selectVariantData(item, makt, variantCount) {
  if (!item) return;
  showSelectionWorkspace(true);
  detailContent.className = "detail-empty";
  detailContent.textContent = "טוען פרטים...";
  await loadSuppliers(makt, variantCount);
  await loadVariantDetail(item, makt);
  if (variantsPanel && variantCount > 1) {
    variantsPanel.classList.add("collapsed-mobile");
  }
  enterMobileFocus(`מק״ט ${makt}`);
  scrollToWorkspaceAside();
}

async function doSearch() {
  const q = searchInput.value.trim();
  if (!q) {
    showToast("הזן ערך לחיפוש", true);
    return;
  }

  lastSearch = { q, match: matchSelect.value, field: fieldSelect.value };
  updateCurl();
  hideDescFloatTip();
  exitMobileFocus();
  setAiSearchMode(false);
  showSelectionWorkspace(false);

  searchBtn.disabled = true;
  resultsContainer.innerHTML = '<p class="empty-state">מחפש...</p>';
  detailContent.className = "detail-empty";
  detailContent.textContent = "בחר שורה מטבלת התוצאות";
  suppliersBody.innerHTML =
    '<tr class="empty-row"><td colspan="4">בחר מק״ט להצגת ספקים</td></tr>';
  suppliersCount.textContent = "—";
  suppliersMakt.textContent = "";
  setExportMakt(null);
  clearSelection();

  const params = new URLSearchParams({
    q,
    match: lastSearch.match,
    field: lastSearch.field,
    limit: "200",
    grouped: "true",
  });

  try {
    const data = await api(`/api/items?${params}`);
    renderResults(data);

    if (data.count >= 200) {
      showToast("מוצגות 200 תוצאות ראשונות – צמצם חיפוש לדיוק");
    }

    const groups = data.groups || [];
    if (groups.length === 1) {
      const row = resultsContainer.querySelector(".summary-row");
      await selectGroupFromTable(0, row);
    }
  } catch (e) {
    resultsContainer.innerHTML = `<p class="empty-state">${esc(e.message)}</p>`;
    resultsCount.textContent = "0";
    if (e.message !== "לא נמצאו תוצאות") showToast(e.message, true);
  } finally {
    searchBtn.disabled = false;
  }
}

toggleCurlBtn.addEventListener("click", () => {
  const open = curlPanel.hidden;
  curlPanel.hidden = !open;
  toggleCurlBtn.setAttribute("aria-expanded", open ? "true" : "false");
  toggleCurlBtn.textContent = open ? "הסתר cURL" : "הצג cURL (למפתחים)";
  if (open) updateCurl();
});

copyCurlBtn.addEventListener("click", async () => {
  updateCurl();
  try {
    await navigator.clipboard.writeText(curlCode.textContent);
    showToast("הועתק ללוח");
  } catch {
    showToast("לא ניתן להעתיק", true);
  }
});

fieldSelect.addEventListener("change", () => {
  const isSupplier = fieldSelect.value === "ספק";
  searchInput.placeholder = isSupplier
    ? "שם ספק..."
    : "מק״ט, תיאור, סוג זכאי...";
});

searchBtn.addEventListener("click", doSearch);
searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") doSearch();
});

bindDrawerControls();
bindResultsDelegation();

backToResultsBtn?.addEventListener("click", () => {
  exitMobileFocus();
  resultsContainer?.scrollIntoView({ behavior: "smooth", block: "start" });
});

exportSearchBtn?.addEventListener("click", exportSearchResults);
exportMaktBtn?.addEventListener("click", exportMaktSuppliers);
exportAiBtn?.addEventListener("click", exportAiSearchResults);

aiSearchBtn?.addEventListener("click", doAiSearch);
aiQueryInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) doAiSearch();
});

checkHealth();
updateExportButtons();
updateCurl();
