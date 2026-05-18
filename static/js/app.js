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

const COMPACT_TABLE_THRESHOLD = 8;
const MAX_VARIANTS_PREVIEW = 100;

let drawerBound = false;

let lastSearch = { q: "", match: "contains", field: "all" };
let searchState = { groups: [], items: [] };

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

function cellVal(item, key) {
  const v = item[key];
  if (v == null || v === "" || v === "לא מוגדר") return "—";
  return esc(v);
}

function bindDrawerControls() {
  if (drawerBound) return;
  drawerBound = true;
  $("closeDrawerBtn")?.addEventListener("click", () => {
    $("variantsDrawer").hidden = true;
    clearSelection();
  });
}

function renderVariantsTable(variants, groupIdx, makt) {
  const rows = variants
    .map(
      (v, i) => `
    <tr class="variant-table-row" data-group-idx="${groupIdx}" data-variant-idx="${i}" tabindex="0">
      <td class="num-cell">${i + 1}</td>
      <td>${cellVal(v, "רמת בסיס")}</td>
      <td>${cellVal(v, "רמת חריגה")}</td>
      <td>${cellVal(v, "אחוז לחריגה")}</td>
      <td>${cellVal(v, "סוג זכאי")}</td>
      <td>${cellVal(v, "סוג סכום")}</td>
      <td class="num-cell"><strong>${cellVal(v, "סכום")}</strong></td>
    </tr>`
    )
    .join("");

  return `
    <div class="table-wrap variants-table-wrap">
      <table class="data-table variants-table">
        <thead>
          <tr>
            <th>#</th>
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
      return `
        <tr class="summary-row" data-group-idx="${idx}" tabindex="0">
          <td><span class="makt-badge makt-badge--sm">${esc(makt)}</span></td>
          <td class="desc-cell">${esc(desc)}</td>
          <td>${esc(zacai)}</td>
          <td class="num-cell">${count > 1 ? `<span class="pill">${count} וריאנטים</span>` : "1"}</td>
          <td class="num-cell">${esc(amountRange(variants))}</td>
        </tr>`;
    })
    .join("");

  resultsContainer.innerHTML = `
    <p class="results-mode-hint">נמצאו ${groups.length} מק״טים – לחץ על שורה לצפייה בוריאנטים וספקים</p>
    <div class="table-wrap summary-table-wrap">
      <table class="data-table summary-table">
        <thead>
          <tr>
            <th>מק״ט</th>
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

  body.innerHTML = renderVariantsTable(preview, groupIdx, makt);
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
    renderVariantsInDrawer(group, makt, groupIdx);
    renderMaktSummary(makt, count);
    await loadSuppliers(makt, count);
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
          <span class="group-title">${esc(group["תיאור פריט"] || variants[0]?.["תיאור פריט"])}</span>
        </div>
        <span class="variant-badge">${count} וריאנטים</span>
      </button>
      <div class="variant-list" id="variantListSingle"></div>
    </div>`;

  const list = $("variantListSingle");
  list.innerHTML = renderVariantsTable(variants.slice(0, MAX_VARIANTS_PREVIEW), 0, makt);
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
}

function renderResults(data) {
  const items = data.items || [];
  const groups = data.groups || [];
  searchState = { groups, items };

  resultsCount.textContent = `${items.length} תוצאות · ${groups.length} מק״טים`;

  if (!items.length) {
    resultsContainer.innerHTML = '<p class="empty-state">לא נמצאו תוצאות</p>';
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
        <dd>${esc(v)}</dd>
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
      '<tr class="empty-row"><td colspan="4">לא נמצאו ספקים מקושרים למק״ט זה</td></tr>';
    return;
  }

  suppliersBody.innerHTML = suppliers
    .map(
      (s) => `
    <tr>
      <td>${esc(s["שם ספק"])}</td>
      <td>${esc(s["יישוב קליניקה"])}</td>
      <td>${esc(s["אזור"])}</td>
      <td>${esc(s["האם בתוקף"])}</td>
    </tr>`
    )
    .join("");
}

async function loadSuppliers(makt, variantCount = 1) {
  if (!makt) {
    renderSuppliers("", [], 0);
    return;
  }
  suppliersBody.innerHTML =
    '<tr class="loading-row"><td colspan="4">טוען ספקים...</td></tr>';
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

  renderMaktSummary(makt, variantCount);
  await loadSuppliers(makt, variantCount);

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

  searchBtn.disabled = true;
  resultsContainer.innerHTML = '<p class="empty-state">מחפש...</p>';
  detailContent.className = "detail-empty";
  detailContent.textContent = "בחר מק״ט מהטבלה";
  suppliersBody.innerHTML =
    '<tr class="empty-row"><td colspan="4">בחר מק״ט להצגת ספקים</td></tr>';
  suppliersCount.textContent = "—";
  suppliersMakt.textContent = "";
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
checkHealth();
updateCurl();
