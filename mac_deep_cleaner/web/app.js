"use strict";
P.chevron = '<path d="M9 5l7 7-7 7"/>';
P.arrow = '<path d="M7 17L17 7M7 7h10v10"/>';
P.monitor =
  '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>';
P.sidebar = '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>';
let theme = "dark";
function applyTheme(next) {
  theme = next === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = theme === "light" ? "#dadada" : "#252525";
  try {
    window.webkit?.messageHandlers?.themeChange?.postMessage(theme);
  } catch {}
}
try { applyTheme(localStorage.getItem("mdc_theme")); } catch { applyTheme("dark"); }
// Long lists load their next page automatically when the footer scrolls into view.
let moreObserver = null;
function watchMore() {
  moreObserver?.disconnect();
  const next = document.querySelector('#main [data-action="more"]');
  if (!next || typeof IntersectionObserver !== "function") return;
  moreObserver = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) { moreObserver.disconnect(); next.click(); }
  }, { root: document.getElementById("main"), rootMargin: "400px 0px" });
  moreObserver.observe(next);
}
let sidebarExpanded = false;
function setSidebar(expanded) {
  sidebarExpanded = expanded;
  document.body.classList.toggle("sidebar-expanded", expanded);
  const toggle = document.getElementById("sidebarToggle");
  toggle.setAttribute("aria-expanded", String(expanded));
  toggle.setAttribute("aria-label", expanded ? "Collapse sidebar" : "Expand sidebar");
  toggle.title = expanded ? "Collapse sidebar" : "Expand sidebar";
}
const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icon = (n) =>
  `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${P[n] || P.file}</svg>`;
const bytes = (n) => {
  n = Math.max(0, Number(n) || 0);
  let unit = 0;
  while (n >= 1000 && unit < 4) {
    n /= 1000;
    unit++;
  }
  return [
    unit ? n.toFixed(n >= 100 ? 1 : 2) : String(Math.round(n)),
    ["B", "KB", "MB", "GB", "TB"][unit],
  ];
};
const fmt = (n) => bytes(n).join(" ");
const ago = (t) => {
  if (!t) return "Not recorded";
  const d = Math.max(0, Math.floor((Date.now() / 1000 - t) / 86400));
  return d < 1
    ? "Today"
    : d < 30
      ? `${d} days ago`
      : d < 365
        ? `${Math.floor(d / 30)} months ago`
        : `${Math.floor(d / 365)} years ago`;
};
const sum = (items) => items.reduce((n, i) => n + i.size, 0);
const eligible = (i) => i && !i.protected && !i.managed && i.category !== "Ghost Files";
const safetyLabel = { safe: "Safe", caution: "Caution", risky: "Risky" };
const safety = (s) =>
  `<span class="safety ${s}"><i class="dot"></i>${safetyLabel[s] || esc(s)}</span>`;
const attrs = (obj) =>
  Object.entries(obj)
    .map(([k, v]) => ` data-${k}="${esc(v)}"`)
    .join("");
const button = (
  label,
  action,
  { style = "", symbol = "", disabled = false, data = {}, aria = "" } = {},
) =>
  `<button type="button" class="button ${style}" data-action="${action}"${attrs(data)} ${disabled ? "disabled" : ""} ${aria ? `aria-label="${esc(aria)}"` : ""}>${symbol ? icon(symbol) : ""}${esc(label)}</button>`;
const empty = (title, description, symbol = "search", action = "", { scanning = false } = {}) =>
  `<div class="empty ${scanning ? "is-scanning" : ""}">${icon(symbol)}<h3>${esc(title)}</h3><p>${esc(description)}</p>${scanning ? '<div class="scan-pill"><span class="radar-dot"></span><span>Scanning in progress</span></div>' : ""}${action}</div>`;
const metric = (label, value, note) =>
  `<div class="metric"><span>${esc(label)}</span><b>${esc(value)}</b><small>${esc(note)}</small></div>`;
const bar = (parts) =>
  `<div class="bar" aria-hidden="true">${parts.map(([pct, color]) => `<i style="width:${Math.min(100, Math.max(0, pct))}%;background:${color}"></i>`).join("")}</div>`;
const navs = [
  ["clean", "Storage cleanup", "nav_clean"],
  ["optimize", "Optimize your Mac", "nav_optimize"],
  ["disks", "Disks & volumes", "nav_disks"],
  ["homebrew", "Homebrew", "nav_homebrew"],
  ["apps", "Applications", "nav_apps"],
  ["big", "Large files", "nav_big"],
  ["dups", "Duplicates", "nav_dups"],
  ["ghosts", "Ghost Files", "ghost"],
  ["settings", "Settings", "nav_settings"],
];
let S = {
    items: [],
    cats: [],
    tools: [],
    scanning: true,
    progress: "Connecting to the local scanner",
  },
  A = { apps: [], ready: false };
let ready = false,
  connectionError = "",
  appsError = "",
  bigError = "",
  view = "clean",
  mode = "normal",
  cat = "",
  q = "",
  minmb = 10,
  safetyFilter = "all",
  focusId = null;
let selected = new Set(),
  aq = "",
  asort = "total",
  idleOnly = false,
  openAppId = null,
  pickParts = new Set(),
  visibleLimit = 100,
  bigIds = [],
  bigReady = false;
let stateTimer,
  appsTimer,
  generation = 0,
  loading = false,
  appsLoading = false,
  bigLoading = false,
  busy = false,
  pendingAsk = null,
  detailKind = null;
try {
  mode = localStorage.getItem("mdc_mode") === "dev" ? "dev" : "normal";
} catch {}
const group = (i) =>
  mode === "dev" && i.category === "Developer & Pro Tools"
    ? i.group || i.category
    : i.category;
const canSelect = () =>
  ready && !S.scanning && !S.error && !S.busy && !busy && !connectionError;
const selectedItems = () =>
  S.items.filter((i) => eligible(i) && selected.has(i.id));
function totals() {
  const t = { all: 0, safe: 0, caution: 0, risky: 0 };
  for (const i of S.items)
    if (eligible(i)) {
      t.all += i.size;
      t[i.safety] = (t[i.safety] || 0) + i.size;
    }
  return t;
}
function groups() {
  const m = new Map();
  for (const i of S.items) {
    const n = group(i);
    if (!m.has(n)) m.set(n, []);
    m.get(n).push(i);
  }
  const order = S.cats.flatMap((c) =>
    c === "Developer & Pro Tools" && mode === "dev" ? S.tools : [c],
  );
  return [...new Set([...order, ...m.keys()])]
    .filter((n) => m.has(n))
    .map((n) => [n, m.get(n)]);
}

// The feature switch is core UI. Ghost code and assets are loaded only after opt-in.
let ghostAssets;
function ensureGhostFeature() {
  if (!S.features?.ghosts_level) return Promise.resolve();
  if (!ghostAssets) ghostAssets = new Promise((resolve, reject) => {
    const style = document.createElement("link");
    style.rel = "stylesheet"; style.href = "/assets/ghosts.css"; document.head.append(style);
    const script = document.createElement("script"); script.src = "/assets/ghosts.js";
    script.onload = resolve;
    script.onerror = () => { ghostAssets = null; reject(new Error("Ghost Files could not load. Reopen Settings to retry.")); };
    document.head.append(script);
  });
  return ghostAssets;
}
function syncGhostFeature() {
  if (!S.features?.ghosts_level) {
    window.GhostUI?.leave();
    if (view === "ghosts") view = "settings";
  } else if (["ghosts", "settings"].includes(view)) {
    ensureGhostFeature().then(() => { if (S.features?.ghosts_level) GhostUI.enter(); }).catch(e => toast(e.message, true));
  }
}
async function setGhostLevel(level) {
  await api("/api/ghosts/config", {level});
  S.features = {ghosts_level: level};
  if (level) {
    await ensureGhostFeature();
    await GhostUI.enter(true);
    if (level === 2) await GhostUI.setup();
  } else window.GhostUI?.leave();
  await load();
  draw();
}
function settingsView() {
  const level = S.features?.ghosts_level || 0;
  return `<div class="pagehead"><div><h1>Settings</h1><p>Choose what runs on your Mac.</p></div></div>${banners()}
    <section class="tool-section"><div class="section-title"><h2>Appearance</h2></div>
    <div class="feature-setting"><div><h3>Theme</h3><p>Switch between a dark and a light workspace.</p></div>
    <button type="button" class="theme-switch ${theme === "light" ? "is-light" : ""}" data-action="theme" role="switch" aria-checked="${theme === "light"}" aria-label="Light mode"><span class="theme-label">${icon(theme === "light" ? "sun" : "moon")}${theme === "light" ? "Light mode" : "Dark mode"}</span><span class="theme-track" aria-hidden="true"><i></i></span></button></div></section>
    <section class="tool-section"><div class="section-title"><h2>Experimental</h2></div>
    <div class="feature-setting"><div><h3>Ghost Files</h3><p>Find leftovers from apps you have deleted. Review each one before moving it to the Trash.</p></div>
    <button class="button ${level ? "primary" : ""}" data-action="feature-ghost-level" data-level="${level ? 0 : 1}" role="switch" aria-checked="${!!level}" aria-label="Ghost Files" ${busy || S.busy ? "disabled" : ""}>${level ? "On" : "Off"}</button></div>
    ${level ? `<div class="feature-levels" aria-label="Ghost Files mode">${button("Ghosts (no AI)", "feature-ghost-level", {style:level === 1 ? "primary" : "", data:{level:1},disabled:!!S.busy})}${button("Ghosts + AI narration", "feature-ghost-level", {style:level === 2 ? "primary" : "", data:{level:2},disabled:!!S.busy})}${button("Open Ghost Files", "navigate", {data:{view:"ghosts"},symbol:"arrow"})}</div>${window.GhostUI ? GhostUI.settings() : '<p>Loading feature settings…</p>'}` : '<p class="note">Off by default. No Ghost Files scanning, AI probing, or downloads run while disabled.</p>'}
    </section>`;
}

async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    body && path.includes("/clean") ? 960000 : path === "/api/disks" || path === "/api/health" || path.startsWith("/api/brew") || path.endsWith("/plan") ? 600000 : 20000,
  );
  try {
    const r = await fetch(path, {
      ...(body === undefined
        ? {}
        : {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-MDC-Token": document.querySelector('meta[name="mdc-session"]').content },
            body: JSON.stringify(body),
          }),
      signal: controller.signal,
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok)
      throw new Error(
        data.error ||
          (r.status === 403
            ? "Session expired. Reopen the dashboard link printed in your terminal."
            : `Request failed (${r.status}). Please try again.`),
      );
    return data;
  } catch (e) {
    if (e.name === "AbortError")
      throw new Error(
        "The request timed out. Check that Mac Deep Cleaner is still running.",
      );
    throw e;
  } finally {
    clearTimeout(timeout);
  }
}
async function load() {
  if (loading) return;
  loading = true;
  const g = generation;
  clearTimeout(stateTimer);
  try {
    const next = await api("/api/state");
    if (g !== generation) return;
    const changed =
      ready &&
      S.scan_id !== undefined &&
      (next.scan_id !== S.scan_id || next.revision !== S.revision);
    if (changed) {
      selected.clear();
      focusId = null;
      bigIds = [];
      bigReady = false;
      A = { apps: [], ready: false };
      closeDetail();
    }
    if (!ready && next.initial_view && navs.some(n => n[0] === next.initial_view) && view === "clean") view = next.initial_view;
    if (!ready && next.settings) {
      mode = next.settings.mode;
      minmb = next.settings.min_mb;
      if (next.settings.theme) applyTheme(next.settings.theme);
    }
    S = next;
    syncGhostFeature();
    ready = true;
    connectionError = next.error || "";
    selected = new Set(
      [...selected].filter((id) =>
        S.items.some((i) => i.id === id && eligible(i)),
      ),
    );
    draw();
    if (view === "big" && !S.scanning && !bigReady) loadBig();
    if (view === "apps" && !A.ready) loadApps();
    if (["optimize", "disks"].includes(view)) ToolkitUI.enter(view);
    if (view === "homebrew") HomebrewUI.enter();
    stateTimer = setTimeout(load, S.scanning || S.busy ? 1400 : 10000);
  } catch (e) {
    connectionError = e.message;
    draw();
    stateTimer = setTimeout(load, 5000);
  } finally {
    loading = false;
  }
}
async function loadApps() {
  if (appsLoading) return;
  appsLoading = true;
  clearTimeout(appsTimer);
  const g = generation;
  try {
    const result = await api("/api/apps");
    if (g !== generation) return;
    if (result.scan_id && result.scan_id !== S.scan_id) return;
    A = result;
    appsError = result.error || "";
    if (view === "apps") draw();
    if (openAppId !== null && detailKind === "app") renderAppDrawer();
    if (!A.ready) appsTimer = setTimeout(loadApps, 1400);
  } catch (e) {
    appsError = e.message;
    if (view === "apps") draw();
  } finally {
    appsLoading = false;
  }
}
async function loadBig() {
  if (bigLoading || S.scanning) return;
  bigLoading = true;
  const g = generation;
  try {
    const result = await api("/api/biggest");
    const next = await api("/api/state");
    if (g !== generation || next.scan_id !== S.scan_id) return;
    bigIds = result.ids;
    S = next;
    bigReady = true;
    bigError = "";
    if (view === "big") draw();
  } catch (e) {
    bigError = e.message;
    if (view === "big") draw();
  } finally {
    bigLoading = false;
  }
}
function toast(message, error = false) {
  const item = document.createElement("div");
  item.className = "toast" + (error ? " error" : "");
  item.innerHTML =
    icon(error ? "alert" : "check") +
    `<span>${esc(message)}</span><button aria-label="Dismiss notification">${icon("x")}</button>`;
  item.querySelector("button").onclick = () => item.remove();
  $("toasts").append(item);
  setTimeout(() => item.remove(), error ? 10000 : 6500);
}
function chrome() {
  const title = navs.find((n) => n[0] === view)[1];
  $("navigation").innerHTML = navs
    .filter(([v]) => v !== "ghosts" || S.features?.ghosts_level > 0)
    .map(
      ([v, name, symbol]) =>
        `<button class="nav-button ${view === v ? "active" : ""}" data-action="navigate" data-view="${v}" title="${name}" aria-label="${name}" ${view === v ? 'aria-current="page"' : ""}>${icon(symbol)}<span class="nav-full">${name}</span><span class="nav-short">${{ clean: "Cleanup", apps: "Apps", big: "Large files", dups: "Duplicates", optimize: "Optimize", disks: "Disks", homebrew: "Homebrew", ghosts: "Ghosts", settings: "Settings" }[v]}</span></button>`,
    )
    .join("");
  $("modeSwitch").innerHTML = `<button class="rail-control mode-control ${mode === "dev" ? "enabled" : ""}" data-action="mode" data-mode="${mode === "dev" ? "normal" : "dev"}" role="switch" aria-checked="${mode === "dev"}" aria-label="Developer mode" title="Developer mode: ${mode === "dev" ? "on" : "off"}">${icon("code")}<span class="rail-label">Developer mode</span><span class="mode-indicator" aria-hidden="true"></span></button>`;
  $("breadcrumb").innerHTML =
    `${icon("monitor")}<span>This Mac</span><span aria-hidden="true">/</span><strong>${title}</strong>`;
  $("status").className =
    "status" + (connectionError ? " offline" : S.scanning ? " working" : "");
  $("status").textContent = connectionError
    ? "Disconnected"
    : !ready
      ? "Connecting"
      : S.scanning
        ? "Scan in progress"
        : "Scan complete";
  document.title = `${title} — Mac Deep Cleaner`;
}
function pagehead(title, subtitle) {
  return `<div class="pagehead"><div><h1>${title}</h1><p>${subtitle}</p></div><div class="head-actions">${button(S.scanning ? "Scanning" : "Rescan", "rescan", { symbol: "refresh", disabled: !ready || S.scanning || busy })}</div></div>`;
}
function banners() {
  return (
    (connectionError
      ? `<div class="error-banner" role="alert">${icon("alert")}<span>${esc(connectionError)}</span>${button("Retry", "retry")}</div>`
      : "") +
    (ready && S.scanning
      ? `<div class="scan-banner" role="status">${icon("refresh")}<span>Scanning your Mac. ${esc(S.progress || "Finding storage you can review…")}</span></div>`
      : "")
  );
}
function overview() {
  const t = totals(),
    [n, u] = bytes(t.all),
    disk = S.disk,
    used = disk?.total
      ? Math.min(100, Math.round((disk.used / disk.total) * 100))
      : null,
    C = 2 * Math.PI * 59;
  return `<section class="overview" aria-label="Storage overview"><div class="overview-main"><div><div class="overview-label">${icon("clean")}${S.scanning ? "Potential space found so far" : "Potential to reclaim"}</div><div class="storage-number">${ready ? n : "—"}<span>${ready ? u : ""}</span></div><p class="overview-copy">${S.scanning ? "Results will be ready to review when the scan finishes." : `${S.items.filter(eligible).length.toLocaleString()} items found across your Mac. You choose what goes.`}</p><div class="overview-cta">${button("Select safe items", "select-safe", { style: "primary", symbol: "check", disabled: !canSelect() || !S.items.some((i) => eligible(i) && i.safety === "safe" && !i.manual && i.action !== "root") })}<small>Review before removing anything</small></div></div><div class="disk-panel"><div class="disk-ring"><svg viewBox="0 0 148 148" aria-hidden="true"><circle class="ticks" cx="74" cy="74" r="70"/><circle class="track" cx="74" cy="74" r="59"/><circle class="usage" cx="74" cy="74" r="59" stroke-dasharray="${(C * (used || 0)) / 100} ${C}"/></svg><div class="ring-label"><b>${used === null ? "—" : used + "%"}</b><span>disk used</span></div></div><div class="disk-info"><h3>Your Mac’s storage</h3><p>Available<strong class="free">${disk ? fmt(disk.free) : "—"}</strong></p><p>Total capacity<strong>${disk ? fmt(disk.total) : "—"}</strong></p></div></div></div>${S.scanning ? '<div class="scan-track"><i></i></div>' : ""}<div class="risk-summary">${[
    ["safe", "Safe to remove"],
    ["caution", "Review first"],
    ["risky", "Needs care"],
  ]
    .map(
      ([key, label]) =>
        `<button class="risk-stat" data-action="safety-summary" data-safety="${key}" aria-label="Show ${key} items"><div><span class="stat-label"><i class="dot ${key}"></i>${label}</span><b>${fmt(t[key])}</b></div>${icon("chevron")}</button>`,
    )
    .join("")}</div></section>`;
}
function filteredRows(source = S.items) {
  const query = q.toLowerCase().trim();
  return source
    .filter(
      (i) =>
        (!cat || group(i) === cat) &&
        (safetyFilter === "all" || i.safety === safetyFilter) &&
        (i.size >= minmb * 1e6 || i.size === 0) &&
        `${i.name} ${i.path}`.toLowerCase().includes(query),
    )
    .sort((a, b) => b.size - a.size || a.id - b.id);
}
function searchField(id, value, placeholder) {
  return `<label class="search">${icon("search")}<span class="sr-only">${placeholder}</span><input type="search" id="${id}" placeholder="${placeholder}" value="${esc(value)}" autocomplete="off"></label>`;
}
function filters(rows, { categories = true } = {}) {
  const gs = groups();
  return `<div class="toolbar">${searchField("itemSearch", q, "Search files, folders or paths")}${categories ? `<select id="categoryFilter" class="category-filter" aria-label="Category"><option value="">All categories</option>${gs.map(([n, r]) => `<option value="${esc(n)}" ${cat === n ? "selected" : ""}>${esc(n)} (${r.length})</option>`).join("")}</select>` : ""}<select id="sizeFilter" aria-label="Minimum item size">${[
    [0, "Any size"],
    [1, "Over 1 MB"],
    [10, "Over 10 MB"],
    [100, "Over 100 MB"],
    [1000, "Over 1 GB"],
  ]
    .map(
      ([n, name]) =>
        `<option value="${n}" ${minmb === n ? "selected" : ""}>${name}</option>`,
    )
    .join(
      "",
    )}</select></div><div class="filter-row"><div class="filter-tabs" aria-label="Filter by safety">${["all", "safe", "caution", "risky"].map((s) => `<button class="filter-tab ${s === safetyFilter ? "active" : ""}" data-action="safety" data-safety="${s}" aria-pressed="${s === safetyFilter}">${s === "all" ? "All items" : safetyLabel[s]}</button>`).join("")}</div><span>${rows.length.toLocaleString()} results, largest first</span></div>`;
}
function fileIcon(i) {
  const name = CATI[i.category] || (mode === "dev" ? "code" : "folder");
  return `<span class="file-icon ${name === "cache" ? "cache-icon" : name === "code" ? "code-icon" : ""}">${icon(name)}</span>`;
}
function fileList(rows) {
  if (!ready && !connectionError)
    return `<div aria-label="Loading files">${[1, 2, 3, 4].map(() => '<div class="skeleton-row"><div class="skeleton"></div></div>').join("")}</div>`;
  if (!rows.length)
    return empty(
      S.scanning ? "Scanning your Mac…" : "No matching items",
      S.scanning
        ? "Searching storage across your system. Results appear here as they are discovered."
        : "Try another search, category, or minimum size.",
      S.scanning ? "refresh" : "search",
      button("Reset filters", "reset-filters", {
        style: "ghost",
        disabled: S.scanning,
      }),
      { scanning: S.scanning },
    );
  const mx = rows[0].size || 1;
  return `<div class="list-head" aria-hidden="true"><span></span><span>Name</span><span>Safety</span><span class="size">Size</span></div>${rows
    .slice(0, visibleLimit)
    .map(
      (i) =>
        `<div class="item-row ${selected.has(i.id) ? "selected" : ""} ${focusId === i.id ? "focused" : ""}"><input type="checkbox" data-select="${i.id}" aria-label="Select ${esc(i.name)}" ${selected.has(i.id) ? "checked" : ""} ${!eligible(i) || !canSelect() ? "disabled" : ""}><button class="item-main" data-action="inspect" data-id="${i.id}" aria-label="Details for ${esc(i.name)}">${fileIcon(i)}<span class="item-text"><span class="item-name">${esc(i.name)}${i.protected ? '<span class="tag">Protected</span>' : i.managed ? '<span class="tag">macOS</span>' : i.active_project ? '<span class="tag">Active</span>' : ""}</span><span class="item-path" title="${esc(i.path)}">${esc(i.path || "Managed by a terminal command")}</span></span></button>${safety(i.safety)}<span class="item-size">${fmt(i.size)}<span class="size-bar"><i style="width:${Math.max(3, (i.size / mx) * 100)}%"></i></span></span></div>`,
    )
    .join(
      "",
    )}<div class="list-footer"><span>${Math.min(visibleLimit, rows.length)} of ${rows.length.toLocaleString()} items</span>${rows.length > visibleLimit ? button("Show more", "more", { style: "link" }) : "<span>Sorted by size</span>"}</div>`;
}
function inspectorContent(i, { close = true } = {}) {
  if (i?.category === "Ghost Files") return `<div class="inspect-heading"><h3>${esc(i.name)}</h3>${close ? button("", "close-inspector", {style:"ghost icon-only",symbol:"x",aria:"Close details"}) : ""}</div><div class="inspect-content"><p>${esc(i.reason)}</p><p class="path">${esc(i.path)}</p>${button("Review in Ghost Files", "navigate", {data:{view:"ghosts"},style:"primary"})}</div>`;
  if (!i)
    return `<div class="inspector-empty">${icon("file")}<h3>A closer look</h3><p>Select a file to see its location and what happens when it’s removed.</p><small>${icon("shield")}Protected files stay on your Mac. Every cleanup starts with a review.</small></div>`;
  return `<div class="inspect-heading">${fileIcon(i)}<div><h3>${esc(i.name)}</h3><small>${fmt(i.size)}</small></div>${close ? button("", "close-inspector", { style: "ghost icon-only", symbol: "x", aria: "Close details" }) : ""}</div><div class="inspect-content"><dl class="facts"><div><dt>Safety</dt><dd>${safety(i.safety)}</dd></div><div><dt>Status</dt><dd>${i.protected ? "Protected" : i.managed ? "Managed by macOS" : i.active_project ? "Active project" : i.readonly ? "Read-only" : "Available for review"}</dd></div><div><dt>Category</dt><dd>${esc(group(i))}</dd></div></dl><section class="inspect-section"><h3>Location</h3><p class="path">${esc(i.path || "No local file path")}</p></section><section class="inspect-section"><h3>What happens if removed</h3><p>${esc(i.reason || "Review this item before removing it.")}</p>${i.regen ? `<small>${esc(i.regen)}</small>` : ""}</section>${i.keep ? `<section class="inspect-section"><h3>Original copy kept</h3><p class="path">${esc(i.keep)}</p></section>` : ""}${mode === "dev" && i.cmd ? `<section class="inspect-section"><h3>Terminal command</h3><code>${esc(i.cmd)}</code></section>` : ""}<div class="inspect-actions">${eligible(i) ? button(selected.has(i.id) ? "Remove from selection" : "Add to cleanup", "toggle", { style: selected.has(i.id) ? "" : "primary", symbol: selected.has(i.id) ? "x" : "check", disabled: !canSelect(), data: { id: i.id } }) : ""}${i.path ? button("Reveal in Finder", "reveal", { symbol: "folder", data: { id: i.id } }) + button("Copy path", "copy", { symbol: "dup", data: { id: i.id } }) + button("Keep out of future scans", "pin", { style: "link", symbol: "pin", data: { id: i.id }, disabled: !canSelect() }) : ""}</div></div>`;
}
function workspace(rows) {
  return `<div class="workspace"><section class="list-panel" aria-label="Files">${fileList(rows)}</section><aside class="inspector" aria-label="File inspector">${inspectorContent(S.items.find((i) => i.id === focusId))}</aside></div>`;
}
function cleanView() {
  const rows = filteredRows();
  return (
    pagehead(
      "Storage cleanup",
      "Make room for what matters. Start with a closer look.",
    ) +
    banners() +
    overview() +
    `<div class="section-title" id="filesTitle"><h2>Explore your files</h2><span class="count">${S.items.length.toLocaleString()}</span>${button("Select caution items", "select-caution", { style: "link", disabled: !canSelect() })}</div>` +
    filters(rows) +
    workspace(rows) +
    `<p class="note">${icon("shield")}Nothing is removed until you review and confirm. Some items need extra care.</p>`
  );
}
function bigView() {
  const ids = new Set(bigIds),
    source = S.items.filter((i) => ids.has(i.id));
  const rows = filteredRows(source);
  return (
    pagehead(
      "Large files",
      "Find the files with the biggest footprint on your Mac.",
    ) +
    banners() +
    `<div class="metrics">${metric("Files found", source.length.toLocaleString(), "Up to 100 largest files")}${metric("Combined size", fmt(sum(source)), "Includes protected files")}${metric("Largest file", source.length ? fmt(Math.max(...source.map((i) => i.size))) : "—", "Sorted from largest to smallest")}${metric("Protected files", source.filter((i) => !eligible(i)).length, "Kept out of every cleanup")}</div>` +
    (bigError
      ? `<div class="error-banner">${esc(bigError)}${button("Retry", "retry-big")}</div>`
      : "") +
    filters(rows, { categories: false }) +
    (S.scanning || !bigReady
      ? `<div class="list-panel">${empty(S.scanning ? "Analyzing file sizes…" : "Loading large files", S.scanning ? "Scanning for the largest files on your Mac. Results will appear when complete." : "Reading the results from your Mac.", S.scanning ? "refresh" : "file", "", { scanning: S.scanning })}</div>`
      : workspace(rows))
  );
}
function appIcon(a) {
  return `<span class="app-icon"><span aria-hidden="true">${esc((a.name.match(/[A-Za-z0-9]/) || ["?"])[0].toUpperCase())}</span><img src="/api/icon?id=${a.id}&generation=${encodeURIComponent(A.apps_id || S.scan_id || "")}" alt="" loading="lazy" decoding="async"></span>`;
}
function appsView() {
  let apps = A.apps.filter(
    (a) =>
      (!idleOnly || (a.idle_days > 180 && !a.running)) &&
      `${a.name} ${a.bundle_id}`
        .toLowerCase()
        .includes(aq.toLowerCase().trim()),
  );
  const key = {
    total: (a) => -a.total,
    size: (a) => -a.size,
    data: (a) => -a.data_size,
    used: (a) => a.last_used || 0,
    name: (a) => a.name.toLowerCase(),
  }[asort];
  apps.sort((a, b) => (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0));
  const mx = Math.max(1, ...A.apps.map((a) => a.total)),
    idle = A.apps.filter((a) => a.idle_days > 180 && !a.running && !a.apple);
  return (
    pagehead(
      "Applications",
      "Your apps, their data, and the space they leave behind.",
    ) +
    banners() +
    (appsError
      ? `<div class="error-banner">${esc(appsError)}${button("Retry", "retry-apps")}</div>`
      : "") +
    (!A.ready
      ? `<div class="scan-banner" role="status">${icon("refresh")}<span>Analyzing applications${A.total ? ` (${A.progress} of ${A.total})` : ""}. App data appears as it’s measured.</span></div>`
      : "") +
    `<div class="metrics">${metric("Applications", A.apps.length, A.ready ? "Installed on your Mac" : "Analysis in progress")}${metric("App size", fmt(sum(A.apps)), "Application bundles")}${metric("Stored data", fmt(A.apps.reduce((n, a) => n + a.data_size, 0)), "Caches, support and settings")}${metric("Unused for 6 months", idle.length, fmt(idle.reduce((n, a) => n + a.total, 0)) + " combined footprint")}</div><div class="toolbar">${searchField("appSearch", aq, "Search applications")}<select id="appSort" aria-label="Sort applications">${[
      ["total", "Total footprint"],
      ["size", "App size"],
      ["data", "Stored data"],
      ["used", "Least recently used"],
      ["name", "Name"],
    ]
      .map(
        ([v, n]) =>
          `<option value="${v}" ${v === asort ? "selected" : ""}>${n}</option>`,
      )
      .join(
        "",
      )}</select>${button(idleOnly ? "Showing idle apps" : "Idle apps only", "idle", { style: idleOnly ? "primary" : "", symbol: "cache" })}</div><div class="section-title"><span class="muted" style="font-size:12px">${apps.length} applications${idleOnly ? " unused for 6+ months" : ""}</span></div>${
      apps.length
        ? `<div class="apps-grid">${apps
            .map(
              (a) =>
                `<button class="app-card" data-action="app" data-id="${a.id}"><div class="app-card-top">${appIcon(a)}<div><h3>${esc(a.name)}</h3><small>${a.running ? "Running now" : esc(a.category || a.source || "Application")}</small></div></div><div class="app-card-bottom"><b class="num">${fmt(a.total)}</b><span>${ago(a.last_used)}</span></div>${bar(
                  [
                    [(a.size / mx) * 100, "#f0f0f0"],
                    [(a.cache_size / mx) * 100, "#8ccbb2"],
                    [
                      (Math.max(0, a.data_size - a.cache_size) / mx) * 100,
                      "#9c9c9c",
                    ],
                  ],
                )}</button>`,
            )
            .join(
              "",
            )}</div><div class="app-legend"><span><i class="dot" style="color:var(--accent)"></i>Application</span><span><i class="dot safe"></i>Caches</span><span><i class="dot" style="color:#9c9c9c"></i>Other stored data</span></div>`
        : empty(
            A.ready
              ? "No matching applications"
              : "Measuring applications…",
            A.ready
              ? "Try another search or turn off the idle filter."
              : "Measuring disk footprints and caches for all installed apps.",
            A.ready ? "apps" : "refresh",
            A.ready
              ? button("Reset filters", "reset-apps", { style: "ghost" })
              : "",
            { scanning: !A.ready },
          )
    }`
  );
}
function duplicateSets() {
  const sets = new Map();
  for (const i of S.items.filter((i) => i.category === "Duplicate Files")) {
    const k = i.set_id || i.keep || String(i.id);
    if (!sets.has(k)) sets.set(k, []);
    sets.get(k).push(i);
  }
  return [...sets.values()].sort((a, b) => sum(b) - sum(a));
}
function duplicatesView() {
  const sets = duplicateSets(),
    query = q.trim().toLowerCase(),
    matches = sets.filter((g) =>
      g.some((i) =>
        `${i.name} ${i.path} ${i.keep}`.toLowerCase().includes(query),
      ),
    );
  const rows = sets.flat();
  return (
    pagehead(
      "Duplicate files",
      "Keep the original. Let go of the extra copies.",
    ) +
    banners() +
    `<div class="metrics">${metric("Duplicate groups", sets.length, "Matched by file content")}${metric("Extra copies", rows.length, "Available for review")}${metric("Potential to reclaim", fmt(sum(rows)), "Only extra copies counted")}${metric("Originals kept", sets.length, "One copy is always protected")}</div><div class="toolbar">${searchField("duplicateSearch", q, "Search duplicate files or paths")}</div><p class="note" style="margin:0 0 20px">${icon("shield")}Files are compared by content. The original copy shown in each group stays on your Mac.</p>${
      matches.length
        ? matches
            .slice(0, visibleLimit)
            .map((g) => {
              const all = g.filter(eligible).every((i) => selected.has(i.id));
              return `<section class="duplicate-card"><div class="duplicate-head"><span class="file-icon">${icon("dup")}</span><div><h3>${esc(g[0].name)}</h3><p>${g.length + 1} copies found. ${fmt(sum(g))} in extra copies.</p></div>${button(all ? "Deselect extras" : "Select extras", "duplicate-set", { symbol: all ? "x" : "check", data: { ids: g.map((i) => i.id).join(",") }, disabled: !canSelect() })}</div><div class="kept-copy">${icon("shield")}<span><strong>Keeping</strong> ${esc(g[0].keep)}</span></div>${g.map((i) => `<label class="duplicate-file"><input type="checkbox" data-select="${i.id}" aria-label="Select duplicate ${esc(i.path)}" ${selected.has(i.id) ? "checked" : ""} ${!canSelect() || !eligible(i) ? "disabled" : ""}><span>${esc(i.path)}</span><b>${fmt(i.size)}</b></label>`).join("")}</section>`;
            })
            .join("") +
          (matches.length > visibleLimit
            ? button("Show more groups", "more", { style: "ghost" })
            : "")
        : empty(
            S.scanning ? "Checking for duplicates…" : "No duplicate files found",
            S.scanning
              ? "Scanning and comparing file hashes. Matching copies will appear here."
              : q
                ? "Try another name or path."
                : "There are no extra copies in the scanned locations.",
            S.scanning ? "refresh" : "dup",
            "",
            { scanning: S.scanning },
          )
    }`
  );
}
function preserveFocus(render) {
  const active = document.activeElement,
    position = { x: window.scrollX, y: window.scrollY },
    id = active?.id,
    action = active?.dataset.action,
    signature = active?.outerHTML;
  let selection;
  try {
    selection = [active.selectionStart, active.selectionEnd];
  } catch {}
  render();
  let target = id && $(id);
  if (!target && active?.dataset.select)
    target = document.querySelector(
      `[data-select="${Number(active.dataset.select)}"]`,
    );
  if (!target && action)
    target = [...document.querySelectorAll("[data-action]")].find(
      (e) => e.outerHTML === signature,
    );
  if (target) {
    target.focus({ preventScroll: true });
    if (selection && selection[0] != null)
      try {
        target.setSelectionRange(...selection);
      } catch {}
  }
  window.scrollTo(position.x, position.y);
}
function draw({ animate = false } = {}) {
  preserveFocus(() => {
    chrome();
    $("main").innerHTML = {
      clean: cleanView,
      apps: appsView,
      big: bigView,
      dups: duplicatesView,
      optimize: ToolkitUI.optimizeView,
      disks: ToolkitUI.diskView,
      homebrew: HomebrewUI.render,
      settings: settingsView,
      ghosts: () => window.GhostUI ? GhostUI.render() : empty("Opening Ghost Files…", "Loading the optional workspace."),
    }[view]();
    drawSelection();
    Dropdowns.enhance($("main"));
    watchMore();
  });
  if (animate) {
    $("main").classList.remove("page-enter");
    void $("main").offsetWidth;
    $("main").classList.add("page-enter");
  }
  if (detailKind === "file" && $("detailDialog").open) {
    const i = S.items.find((i) => i.id === focusId);
    if (i) {
      const d = $("detailDialog"),
        y = d.scrollTop,
        action = d.contains(document.activeElement)
          ? document.activeElement.dataset.action
          : null;
      d.innerHTML = inspectorContent(i);
      d.scrollTop = y;
      if (action)
        d.querySelector(`[data-action="${action}"]`)?.focus({
          preventScroll: true,
        });
    } else closeDetail();
  }
}
function drawSelection() {
  const items = selectedItems(),
    el = $("selection");
  el.hidden = !items.length || ["optimize", "disks", "homebrew", "ghosts", "settings"].includes(view);
  if (!items.length) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = `<span class="selection-icon">${icon("check")}</span><div class="selection-summary"><strong>${items.length} ${items.length === 1 ? "item" : "items"} selected</strong><small>${fmt(sum(items))} ready for review</small></div><button class="clear" data-action="clear-selection">Clear</button>${button(busy ? "Working…" : "Review cleanup", "review", { style: "primary", symbol: "arrow", disabled: !canSelect() })}`;
}
function navigate(v) {
  if (!navs.some((n) => n[0] === v) || (v === "ghosts" && !S.features?.ghosts_level)) return;
  window.GhostUI?.leave();
  if (matchMedia("(max-width:900px)").matches) setSidebar(false);
  view = v;
  q = "";
  cat = "";
  safetyFilter = "all";
  minmb = 10;
  focusId = null;
  visibleLimit = 100;
  closeDetail();
  draw({ animate: true });
  window.scrollTo({ top: 0, behavior: "instant" });
  if (["optimize", "disks"].includes(v)) ToolkitUI.enter(v);
  if (v === "homebrew") HomebrewUI.enter();
  if (["ghosts", "settings"].includes(v) && S.features?.ghosts_level) ensureGhostFeature().then(() => GhostUI.enter()).catch(e => toast(e.message, true));
  if (v === "apps" && !A.ready) loadApps();
  if (v === "big" && !S.scanning && !bigReady) loadBig();
}
function toggle(id) {
  if (!canSelect()) return;
  const i = S.items.find((i) => i.id === id);
  if (!eligible(i)) return;
  selected.has(id) ? selected.delete(id) : selected.add(id);
  draw();
}
function selectLevel(level) {
  if (!canSelect()) return;
  let count = 0;
  for (const i of S.items) {
    if (
      !eligible(i) ||
      i.safety !== level ||
      (level === "safe" && (i.manual || i.action === "root"))
    )
      continue;
    if (!selected.has(i.id)) count++;
    selected.add(i.id);
  }
  draw();
  toast(
    count
      ? `${count} ${level} ${count === 1 ? "item added" : "items added"} to your review.`
      : `All eligible ${level} items are already selected.`,
  );
}
function inspect(id) {
  focusId = id;
  draw();
  if (matchMedia("(max-width:1240px)").matches) {
    detailKind = "file";
    $("detailDialog").innerHTML = inspectorContent(
      S.items.find((i) => i.id === id),
    );
    Overlays.open($("detailDialog"));
  }
}
function closeDetail() {
  openAppId = null;
  detailKind = null;
  pickParts.clear();
  return Overlays.close($("detailDialog"));
}
function showApp(id) {
  openAppId = id;
  pickParts.clear();
  detailKind = "app";
  renderAppDrawer();
  Overlays.open($("detailDialog"));
}
function renderAppDrawer() {
  const a = A.apps.find((a) => a.id === openAppId);
  if (!a) return closeDetail();
  const parts = [
    ...(a.removable
      ? [
          {
            label: "Application bundle",
            path: a.path,
            size: a.size,
            kind: "app",
          },
        ]
      : []),
    ...a.parts,
  ];
  const total = a.total || 1,
    scroll = $("detailDialog").scrollTop;
  const focusPart = document.activeElement?.dataset.part;
  $("detailDialog").innerHTML =
    `<div class="drawer-head">${appIcon(a)}<div><h2>${esc(a.name)}</h2><small>${esc(a.version || "Version unavailable")} / ${esc(a.source || "Application")}${a.running ? " / Running now" : ""}</small></div>${button("", "close-detail", { style: "ghost icon-only", symbol: "x", aria: "Close application details" })}</div><div class="drawer-body"><div class="metrics">${metric("Total footprint", fmt(a.total), "App and stored data")}${metric("Caches", fmt(a.cache_size), "Can be regenerated")}${metric("Last opened", ago(a.last_used), a.running ? "Running now" : "")}</div>${bar(
      [
        [(a.size / total) * 100, "#f0f0f0"],
        [(a.cache_size / total) * 100, "#8ccbb2"],
        [(Math.max(0, a.data_size - a.cache_size) / total) * 100, "#9c9c9c"],
      ],
    )}<p class="note path">${esc(a.path)}</p><div class="drawer-actions">${a.cache_size ? button("Clear caches", "app-clean", { style: "primary", symbol: "cache", data: { mode: "caches" }, disabled: busy || !A.ready || !canSelect() }) : ""}${a.removable ? button("Uninstall app", "app-clean", { style: "danger", symbol: "trash", data: { mode: "uninstall" }, disabled: busy || a.running || !A.ready || !canSelect() }) : ""}${button("Reveal in Finder", "reveal-app", { symbol: "folder" })}</div>${a.running ? '<p class="review-warning">Quit this app before uninstalling it or removing its application bundle.</p>' : ""}<div class="section-title"><h2>What this app stores</h2><span class="count">${parts.length}</span></div>${parts.length ? parts.map((p, index) => `<label class="part-row"><input type="checkbox" data-part="${index}" ${pickParts.has(p.path) ? "checked" : ""} ${busy || !A.ready || !canSelect() || (p.path === a.path && a.running) ? "disabled" : ""} aria-label="Select ${esc(p.label)}"><span>${esc(p.label)}<span class="tag">${esc(p.kind)}</span><small>${esc(p.path)}</small></span><b>${fmt(p.size)}</b></label>`).join("") : empty("No stored data found", "This app has no removable data in the scanned locations.", "folder")}<div class="drawer-footer">${button(`Remove selected parts${pickParts.size ? " (" + pickParts.size + ")" : ""}`, "app-clean", { symbol: "trash", data: { mode: "pick" }, disabled: !pickParts.size || busy || !A.ready || !canSelect() })}</div><p class="note">${icon("shield")}Application files go to the Trash. You’ll review the removal first.</p></div>`;
  $("detailDialog").scrollTop = scroll;
  if (focusPart !== undefined)
    $("detailDialog")
      .querySelector(`[data-part="${Number(focusPart)}"]`)
      ?.focus({ preventScroll: true });
}
function ask({
  title,
  body,
  confirm = "Confirm",
  danger = false,
  phrase = "",
  allowPermanent = false,
  requiresBackup = false,
}) {
  return new Promise((resolve) => {
    pendingAsk = { resolve, phrase, allowPermanent, confirm, danger, requiresBackup };
    $("confirmDialog").innerHTML =
      `<div class="modal-head"><h2 id="confirmTitle">${esc(title)}</h2>${button("", "cancel-confirm", { style: "ghost icon-only", symbol: "x", aria: "Close confirmation" })}</div><div class="modal-body">${body}${allowPermanent ? '<label class="check-label"><input id="permanent" type="checkbox">Delete permanently instead of using Trash</label><div class="review-warning" id="permanentWarning" hidden>Permanent deletion cannot be undone.</div>' : ""}<label class="phrase-label" id="phraseLabel" ${phrase ? "" : "hidden"}>Type <strong id="phraseText">${esc(phrase)}</strong> to continue<input type="text" id="confirmPhrase" autocomplete="off" spellcheck="false" aria-label="Confirmation phrase"></label></div><div class="modal-actions">${button("Cancel", "cancel-confirm")}${button(confirm, "confirm", { style: danger ? "danger" : "primary", disabled: !!phrase || requiresBackup })}</div>`;
    Overlays.open($("confirmDialog"));
    $("confirmDialog").querySelector('[data-action="cancel-confirm"]').focus();
  });
}
function updateConfirmation() {
  if (!pendingAsk) return;
  const perm = !!$("permanent")?.checked,
    phrase = pendingAsk.phrase || (perm ? "DELETE" : "");
  $("phraseLabel").hidden = !phrase;
  $("phraseText").textContent = phrase;
  if ($("permanentWarning")) $("permanentWarning").hidden = !perm;
  const btn = $("confirmDialog").querySelector('[data-action="confirm"]');
  btn.disabled = (!!phrase && $("confirmPhrase").value !== phrase) || (pendingAsk.requiresBackup && !$("diskBackupAck")?.checked);
  btn.className =
    "button " + (pendingAsk.danger || perm ? "danger" : "primary");
  btn.textContent = perm ? "Delete permanently" : pendingAsk.confirm;
}
function finishAsk(confirmed) {
  if (!pendingAsk) return;
  const pending = pendingAsk,
    permanent = !!$("permanent")?.checked,
    phrase = pending.phrase || (permanent ? "DELETE" : "");
  if (confirmed && phrase && $("confirmPhrase").value !== phrase) return;
  const backupAck = !!$("diskBackupAck")?.checked;
  if (confirmed && pending.requiresBackup && !backupAck) return;
  pendingAsk = null;
  Overlays.close($("confirmDialog")).then(() => pending.resolve({ confirmed, permanent, phrase, backupAck }));
}
function reviewList(items) {
  return `<div class="review-total"><span>${items.length} ${items.length === 1 ? "item" : "items"} selected</span><b>${fmt(sum(items))}</b></div><div class="review-items">${items.map((i) => `<div class="review-item"><span>${esc(i.name)}</span><b>${fmt(i.size)}</b></div>`).join("")}</div>`;
}
function resultToast(r, permanent = false) {
  if (r.fails?.length)
    toast(
      `${r.fails.length} ${r.fails.length === 1 ? "item could" : "items could"} not be removed. ${r.fails.map((f) => f.join(": ")).join("; ")}`,
      true,
    );
  if (r.freed)
    toast(
      `${fmt(r.freed)} processed.${permanent ? "" : " Files moved to Trash still use disk space until Trash is emptied."}`,
    );
  if (r.root?.length)
    ask({
      title: "Terminal action needed",
      body:
        "<p>These items need administrator access. The commands have not been run.</p>" +
        r.root.map((cmd) => `<p><code>${esc(cmd)}</code></p>`).join(""),
      confirm: "Done",
    });
  if (!r.freed && !r.fails?.length && !r.root?.length)
    toast("No files were removed. The items may have changed since the scan.");
}
async function reviewCleanup() {
  if (!canSelect()) return;
  const items = selectedItems();
  if (!items.length) return;
  const risky = items.some((i) => i.safety === "risky"),
    special = items.filter((i) =>
      ["cmd", "empty", "evict", "root"].includes(i.action),
    ),
    g = generation,
    scanId = S.scan_id,
    revision = S.revision;
  const answer = await ask({
    title: "Review your cleanup",
    body:
      reviewList(items) +
      `<p>Files are moved to the Trash by default. Review the selection before continuing.</p>${risky ? '<div class="review-warning">Risky items may contain personal data that cannot be regenerated.</div>' : ""}${special.length ? `<div class="review-warning">${special.map((i) => esc(i.name) + ": " + { empty: "empties this location permanently", cmd: "runs its cleanup command; changes may be permanent", evict: "removes the local cloud copy", root: "requires a command in Terminal" }[i.action]).join("<br>")}</div>` : ""}`,
    confirm: special.length ? "Remove selected items" : "Move to Trash",
    danger: risky || special.some((i) => ["empty", "cmd"].includes(i.action)),
    phrase: risky ? "I UNDERSTAND" : "",
    allowPermanent: true,
  });
  if (!answer.confirmed) return;
  if (
    g !== generation ||
    scanId !== S.scan_id ||
    revision !== S.revision ||
    S.scanning
  )
    return toast(
      "The scan changed. Review your new results before cleaning.",
      true,
    );
  busy = true;
  draw();
  try {
    const r = await api("/api/clean", {
      ids: items.map((i) => i.id),
      permanent: answer.permanent,
      ack: risky,
      permanent_ack: answer.permanent,
      scan_id: scanId,
      revision,
    });
    selected.clear();
    focusId = null;
    bigReady = false;
    A = { apps: [], ready: false };
    closeDetail();
    resultToast(r, answer.permanent);
    await load();
    if (view === "apps") await loadApps();
  } catch (e) {
    toast(e.message, true);
    await load();
  } finally {
    busy = false;
    draw();
  }
}
async function cleanApp(m) {
  if (busy || !canSelect() || !A.ready) return;
  const a = A.apps.find((a) => a.id === openAppId);
  if (!a) return;
  const picked = [...pickParts];
  if (m === "pick" && !picked.length) return;
  if (a.running && (m === "uninstall" || picked.includes(a.path)))
    return toast("Quit this app before removing its application bundle.", true);
  const risky = m !== "caches",
    g = generation,
    scanId = S.scan_id,
    revision = S.revision,
    appsId = A.apps_id;
  const answer = await ask({
    title:
      m === "uninstall"
        ? `Uninstall ${a.name}?`
        : m === "caches"
          ? `Clear ${a.name} caches?`
          : "Remove selected app files?",
    body: `<p>${m === "uninstall" ? "The application and all its stored data will be moved to the Trash." : m === "caches" ? "Caches, logs, and saved window state will be moved to the Trash. The app may rebuild these files." : `${picked.length} selected ${picked.length === 1 ? "part" : "parts"} will be moved to the Trash.`}</p>${risky ? '<div class="review-warning">Stored data can include settings, local documents, and sign-in information.</div>' : ""}`,
    confirm: m === "caches" ? "Clear caches" : "Move to Trash",
    danger: risky,
  });
  if (!answer.confirmed) return;
  if (
    g !== generation ||
    scanId !== S.scan_id ||
    revision !== S.revision ||
    !canSelect()
  )
    return toast("The scan changed. Review the app again.", true);
  busy = true;
  renderAppDrawer();
  drawSelection();
  try {
    const r = await api("/api/app/clean", {
      id: a.id,
      mode: m,
      picked,
      permanent: false,
      ack: risky,
      scan_id: scanId,
      revision,
      apps_id: appsId,
    });
    closeDetail();
    resultToast(r);
    bigReady = false;
    await loadApps();
    await load();
  } catch (e) {
    toast(e.message, true);
  } finally {
    busy = false;
    draw();
    if (openAppId !== null) renderAppDrawer();
  }
}
async function rescan() {
  if (S.scanning || busy) return;
  if (selected.size) {
    const answer = await ask({
      title: "Start a new scan?",
      body: "<p>Your current selection will be cleared. No files will be removed.</p>",
      confirm: "Rescan",
    });
    if (!answer.confirmed) return;
  }
  busy = true;
  draw();
  try {
    await api("/api/rescan", {});
    generation++;
    clearTimeout(stateTimer);
    clearTimeout(appsTimer);
    selected.clear();
    focusId = null;
    bigIds = [];
    bigReady = false;
    A = { apps: [], ready: false };
    S = { ...S, items: [], scanning: true, progress: "Starting a fresh scan" };
    closeDetail();
    stateTimer = setTimeout(load, 100);
    toast("A fresh scan is underway.");
  } catch (e) {
    toast(e.message, true);
    await load();
  } finally {
    busy = false;
    draw();
  }
}
async function revealPath(path) {
  const r = await api("/api/reveal", { path });
  if (!r.ok)
    throw new Error(
      "Finder could not reveal this location. It may have moved or been removed.",
    );
  toast("Location opened in Finder.");
}
async function dispatch(action, el) {
  if (action === "feature-ghost-level") return setGhostLevel(Number(el.dataset.level));
  if (action.startsWith("ghost-")) return window.GhostUI?.dispatch(action, el);
  if (action.startsWith("brew-")) return HomebrewUI.dispatch(action, el);
  if (action.startsWith("toolkit-")) return ToolkitUI.dispatch(action, el);
  const id = Number(el.dataset.id),
    i = S.items.find((x) => x.id === id);
  switch (action) {
    case "toggle-sidebar": return setSidebar(!sidebarExpanded);
    case "collapse-sidebar": return setSidebar(false);
    case "navigate":
      return navigate(el.dataset.view);
    case "theme": {
      applyTheme(theme === "light" ? "dark" : "light");
      try { localStorage.setItem("mdc_theme", theme); } catch {}
      // Persist best-effort; the choice applies immediately even if a scan holds the lock.
      api("/api/settings", { theme }).catch(() => {});
      return draw();
    }
    case "mode":
      mode = el.dataset.mode;
      await api("/api/settings", { mode });
      try {
        localStorage.setItem("mdc_mode", mode);
      } catch {}
      cat = "";
      visibleLimit = 100;
      return draw();
    case "retry":
      return load();
    case "retry-apps":
      return loadApps();
    case "retry-big":
      return loadBig();
    case "rescan":
      return rescan();
    case "select-safe":
      return selectLevel("safe");
    case "select-caution":
      return selectLevel("caution");
    case "safety":
    case "safety-summary":
      safetyFilter = el.dataset.safety;
      visibleLimit = 100;
      draw();
      if (action === "safety-summary")
        $("filesTitle")?.scrollIntoView({
          behavior: matchMedia("(prefers-reduced-motion:reduce)").matches
            ? "instant"
            : "smooth",
          block: "start",
        });
      return;
    case "inspect":
      return inspect(id);
    case "close-inspector":
      focusId = null;
      closeDetail();
      return draw();
    case "toggle":
      return toggle(id);
    case "copy":
      if (i?.path) {
        try {
          await navigator.clipboard.writeText(i.path);
          toast("Path copied.");
        } catch {
          toast(
            "Could not copy the path. Select it in the file details instead.",
            true,
          );
        }
      }
      return;
    case "reveal":
      if (i?.path) return revealPath(i.path);
      return;
    case "pin":
      if (!i || !canSelect()) return;
      {
        const answer = await ask({
          title: "Keep out of future scans?",
          body: `<p>This location will be excluded from future scans.</p><p class="path">${esc(i.path)}</p>`,
          confirm: "Exclude location",
        });
        if (answer.confirmed) {
          await api("/api/pin", {
            path: i.path,
            scan_id: S.scan_id,
            revision: S.revision,
          });
          selected.delete(id);
          focusId = null;
          closeDetail();
          await load();
          toast("Location excluded from future scans.");
        }
      }
      return;
    case "reset-filters":
      q = "";
      cat = "";
      minmb = 0;
      safetyFilter = "all";
      visibleLimit = 100;
      return draw();
    case "reset-apps":
      aq = "";
      idleOnly = false;
      return draw();
    case "more":
      visibleLimit += 100;
      return draw();
    case "idle":
      idleOnly = !idleOnly;
      return draw();
    case "app":
      return showApp(id);
    case "close-detail":
      return closeDetail();
    case "reveal-app":
      {
        const a = A.apps.find((x) => x.id === openAppId);
        if (a) return revealPath(a.path);
      }
      return;
    case "app-clean":
      return cleanApp(el.dataset.mode);
    case "duplicate-set":
      if (!canSelect()) return;
      {
        const ids = el.dataset.ids
            .split(",")
            .map(Number)
            .filter((id) => eligible(S.items.find((i) => i.id === id))),
          all = ids.every((id) => selected.has(id));
        ids.forEach((id) => (all ? selected.delete(id) : selected.add(id)));
        draw();
      }
      return;
    case "clear-selection":
      selected.clear();
      return draw();
    case "review":
      return reviewCleanup();
    case "cancel-confirm":
      return finishAsk(false);
    case "confirm":
      return finishAsk(true);
  }
}
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-action]");
  if (el && !el.disabled)
    Promise.resolve(dispatch(el.dataset.action, el)).catch((error) =>
      toast(error.message, true),
    );
});
document.addEventListener("input", (e) => {
  const el = e.target;
  if (el.id === "confirmPhrase") return updateConfirmation();
  if (["itemSearch", "duplicateSearch", "appSearch"].includes(el.id)) {
    if (el.id === "appSearch") aq = el.value;
    else q = el.value;
    visibleLimit = 100;
    draw();
  }
});
document.addEventListener("change", (e) => {
  const el = e.target;
  if (el.dataset.select !== undefined) return toggle(Number(el.dataset.select));
  if (el.dataset.part !== undefined) {
    const a = A.apps.find((a) => a.id === openAppId);
    if (!a) return;
    const parts = [...(a.removable ? [{ path: a.path }] : []), ...a.parts],
      part = parts[Number(el.dataset.part)];
    if (part) {
      el.checked ? pickParts.add(part.path) : pickParts.delete(part.path);
      renderAppDrawer();
    }
    return;
  }
  if (["permanent", "diskBackupAck"].includes(el.id)) return updateConfirmation();
  if (el.id === "categoryFilter") {
    cat = el.value;
    focusId = null;
  } else if (el.id === "sizeFilter") minmb = Number(el.value);
  else if (el.id === "appSort") asort = el.value;
  else return;
  visibleLimit = 100;
  draw();
});
Overlays.bind($("confirmDialog"), () => finishAsk(false));
Overlays.bind($("detailDialog"), closeDetail);
matchMedia("(max-width:1240px)").addEventListener("change", (e) => {
  if (!e.matches && detailKind === "file") closeDetail();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && sidebarExpanded && !document.querySelector("dialog[open]")) {
    setSidebar(false);
    $("sidebarToggle").focus();
  }
  if (
    (e.metaKey || e.ctrlKey) &&
    e.key.toLowerCase() === "k" &&
    !$("confirmDialog").open &&
    !$("detailDialog").open
  ) {
    e.preventDefault();
    document.querySelector("main input[type=search]")?.focus();
  }
});
document.addEventListener(
  "load",
  (event) => {
    if (event.target.matches?.(".app-icon img"))
      event.target.classList.add("loaded");
  },
  true,
);
document.addEventListener(
  "error",
  (event) => {
    if (event.target.matches?.(".app-icon img")) event.target.remove();
  },
  true,
);
$("brandMark").innerHTML =
  '<img src="/assets/app_icon.png" alt="" width="34" height="34">';
$("sidebarToggle").innerHTML = icon("sidebar") + '<span class="rail-label">Sidebar</span>';
$("main").addEventListener("animationend", (event) => {
  if (event.target === $("main")) $("main").classList.remove("page-enter");
});
draw();
load();
