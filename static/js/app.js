const $ = (id) => document.getElementById(id);

const searchInput = $("searchInput");
const matchSelect = $("matchSelect");
const fieldSelect = $("fieldSelect");
const searchBtn = $("searchBtn");
const resultsContainer = $("resultsContainer");
const resultsCount = $("resultsCount");
const detailContent = $("detailContent");
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

const SUPPLIER_PHONE_KEYS = ["נייד ספק", "טלפון עבודה ספק", "נייח ספק"];
const EXPORT_SEARCH_LIMIT = 500;

const COMPACT_TABLE_THRESHOLD = 8;
const MAX_VARIANTS_PREVIEW = 100;

let drawerBound = false;

let lastSearch = { q: "", match: "contains", field: "all" };
let searchState = { groups: [], items: [] };
let exportState = { makt: null, entityId: null };

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

function enterMobileFocus(label) {
  if (!isMobileView()) return;
  document.querySelector(".app")?.classList.add("mobile-focus");
  if (mobileFocusBar) mobileFocusBar.hidden = false;
  if (mobileFocusLabel) mobileFocusLabel.textContent = label;
  requestAnimationFrame(() => {
    $("detailPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function exitMobileFocus() {
  hideDescFloatTip();
  document.querySelector(".app")?.classList.remove("mobile-focus");
  $("variantsDrawer")?.classList.remove("collapsed-mobile");
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
    $("variantsDrawer").hidden = true;
    clearSelection();
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
  } catch {
    statusBadge.textContent = "שרת לא זמין";
    statusBadge.className = "badge badge--err";
  }
}

function clearSelection() {
  resultsContainer.querySelectorAll(".selected").forEach((el) => el.classList.remove("selected"));
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
    <p class="results-mode-hint">נמצאו ${groups.length} מק״טים – לחץ על שורה לצפייה בוריאנטים וספקים</p>
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
  const drawerEl = $("variantsDrawer");
  if (drawerEl) drawerEl.hidden = true;

  resultsContainer.querySelectorAll(".summary-row").forEach((row) => {
    const open = () => selectGroupFromTable(Number(row.dataset.groupIdx), row);
    row.addEventListener("click", open);
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open();
      }
    });
  });
  bindDescTips(resultsContainer);
}

function renderVariantsInDrawer(group, makt, groupIdx) {
  const drawer = $("variantsDrawer");
  const body = $("variantsDrawerBody");
  const title = $("drawerTitle");
  if (!drawer || !body) return;

  const variants = group.variants || [];
  title.textContent = `מק״ט ${makt} · ${variants.length} וריאנטים`;

  const preview = variants.slice(0, MAX_VARIANTS_PREVIEW);
  const more = variants.length - preview.length;

  body.innerHTML = renderVariantsTable(preview, groupIdx, makt, group.supplier_count);
  if (more > 0) {
    body.innerHTML += `<p class="more-hint">מוצגים ${MAX_VARIANTS_PREVIEW} מתוך ${variants.length}</p>`;
  }

  drawer.hidden = false;
  requestAnimationFrame(() => {
    drawer.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });

  body.querySelectorAll(".variant-table-row").forEach((row) => {
    const pick = () => {
      body.querySelectorAll(".variant-table-row").forEach((r) => r.classList.remove("selected"));
      row.classList.add("selected");
      const v = variants[Number(row.dataset.variantIdx)];
      if (v) selectVariantData(v, makt, variants.length);
    };
    row.addEventListener("click", pick);
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        pick();
      }
    });
  });
}

async function selectGroupFromTable(groupIdx, rowEl) {
  const group = searchState.groups[groupIdx];
  if (!group) return;

  clearSelection();
  rowEl?.classList.add("selected");

  const makt = getMakt(group);
  const variants = group.variants || [];
  const count = variants.length;

  if (count > 1) {
    setExportMakt(makt, null);
    renderVariantsInDrawer(group, makt, groupIdx);
    renderMaktSummary(makt, count);
    await loadSuppliers(makt, count);
    enterMobileFocus(`מק״ט ${makt} · בחר וריאנט`);
    return;
  }

  $("variantsDrawer") && ($("variantsDrawer").hidden = true);
  if (count === 1) {
    await selectVariantData(variants[0], makt, 1);
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
    const pick = () => {
      list.querySelectorAll(".variant-table-row").forEach((r) => r.classList.remove("selected"));
      row.classList.add("selected");
      selectVariantData(variants[Number(row.dataset.variantIdx)], makt, count);
    };
    row.addEventListener("click", pick);
  });

  resultsContainer.querySelector('[data-action="toggle-variants"]')?.addEventListener("click", (e) => {
    const btn = e.currentTarget;
    const listEl = $("variantListSingle");
    const open = listEl.classList.toggle("is-collapsed");
    btn.querySelector(".chevron").textContent = open ? "▸" : "▾";
  });
  bindDescTips(resultsContainer);
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
  detailContent.innerHTML = `
    <p class="entity-id-small">${esc(item.entity_id)}</p>
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

async function selectVariantData(item, makt, variantCount) {
  if (!item?.entity_id) return;

  setExportMakt(makt, item.entity_id);
  renderMaktSummary(makt, variantCount);
  await loadSuppliers(makt, variantCount);
  const drawer = $("variantsDrawer");
  if (drawer) drawer.classList.add("collapsed-mobile");
  enterMobileFocus(`מק״ט ${makt}`);

  detailContent.innerHTML = '<p class="detail-empty">טוען...</p>';
  try {
    const full = await api(`/api/item/${encodeURIComponent(item.entity_id)}`);
    renderDetail(full);
  } catch {
    renderDetail(item);
  }
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

  searchBtn.disabled = true;
  resultsContainer.innerHTML = '<p class="empty-state">מחפש...</p>';
  detailContent.className = "detail-empty";
  detailContent.textContent = "בחר מק״ט מהטבלה";
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
      const g = groups[0];
      const count = g.variant_count || g.variants?.length || 0;
      if (count > 1) {
        await selectGroupFromTable(0, null);
        renderMaktSummary(getMakt(g), count);
        await loadSuppliers(getMakt(g), count);
      } else if (count === 1) {
        await selectVariantData(g.variants[0], getMakt(g), 1);
      }
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

backToResultsBtn?.addEventListener("click", () => {
  exitMobileFocus();
  resultsContainer?.scrollIntoView({ behavior: "smooth", block: "start" });
});

exportSearchBtn?.addEventListener("click", exportSearchResults);
exportMaktBtn?.addEventListener("click", exportMaktSuppliers);

checkHealth();
updateExportButtons();
updateCurl();
