"use strict";
P.chevron = '<path d="M9 5l7 7-7 7"/>';
P.arrow = '<path d="M7 17L17 7M7 7h10v10"/>';
P.monitor =
  '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>';
P.sidebar = '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>';
let theme = "dark";
/** Apply the chosen theme to the dashboard and native window. */
function applyTheme(next) {
  theme = next === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = theme === "light" ? "#eef1f5" : "#252525";
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
    new Intl.NumberFormat(I18n.locale(), {minimumFractionDigits: unit ? (n >= 100 ? 1 : 2) : 0, maximumFractionDigits: unit ? (n >= 100 ? 1 : 2) : 0}).format(n),
    ["B", "KB", "MB", "GB", "TB"][unit],
  ];
};
const fmt = (n) => bytes(n).join(" ");
const ago = (t) => {
  if (!t) return "Not recorded";
  const d = Math.max(0, Math.floor((Date.now() / 1000 - t) / 86400));
  const formatter = new Intl.RelativeTimeFormat(I18n.locale(), {numeric: 'auto'});
  return d < 30 ? formatter.format(-d, 'day')
    : d < 365 ? formatter.format(-Math.floor(d / 30), 'month')
      : formatter.format(-Math.floor(d / 365), 'year');
};
const itemName = item => item.name_key
  ? I18n.t(item.name_key, item.name_values || {}) + (item.name_detail ? ': ' + item.name_detail : '')
  : item.name;
const sum = (items) => items.reduce((n, i) => n + i.size, 0);
const distinctStorage = (items) => {
  const parents = new Set();
  return [...items].sort((a,b) => (a.path || '').length - (b.path || '').length).filter(item => {
    if (!item.path) return true;
    let path = item.path;
    while (path) {
      if (parents.has(path)) return false;
      path = path.slice(0, path.lastIndexOf('/'));
    }
    parents.add(item.path);
    return true;
  });
};
const eligible = (i) => i && !i.protected && !i.managed && i.category !== "Ghost Files";
const safetyLabel = { safe: "Safe", caution: "Caution", risky: "Risky" };
const safety = (s) =>
  `<span class="safety ${s}"><i class="dot"></i>${esc(I18n.t(safetyLabel[s] || s))}</span>`;
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
function scanIndicator(message = 'Scanning in progress', options = {}) {
  const feature = options.feature || view;
  return LoaderUI.render(message, {feature, key:`${feature}:${S.scan_id || 'initial'}`, ...options});
}
const empty = (title, description, symbol = "search", action = "", { scanning = false, showLoader = true, percent = null } = {}) =>
  `<div class="empty ${scanning ? "is-scanning" : ""}">${scanning && showLoader ? scanIndicator(title, {centered:true, description, actions:action, percent}) : `${scanning ? '' : LoaderUI.artwork(view)}<h3>${esc(title)}</h3><p>${esc(description)}</p>${action}`}</div>`;
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
let lastCleanup = null;
try {
  mode = localStorage.getItem("mdc_mode") === "dev" ? "dev" : "normal";
} catch {}
const group = (i) =>
  mode === "dev" && i.category === "Developer & Pro Tools"
    ? i.group || i.category
    : i.category;
const canSelect = () =>
  ready && !S.scanning && !S.error && !S.busy && !busy && !connectionError && !ToolkitUI.isRunning() && !(HistoryUI.isRunning() || I18n.isRunning());
const viewStates = new Map();
const formDrafts = new Map();
const draftFields = new Set(['automationHours','automationInterval']);
const selectedItems = () =>
  S.items.filter((i) => eligible(i) && selected.has(i.id));
function totals() {
  const t = { all: 0, safe: 0, caution: 0, risky: 0 };
  for (const i of distinctStorage(S.items.filter(eligible)))
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
/** Render workspace settings, offline languages, and background controls. */
function settingsView() {
  const level = S.features?.ghosts_level || 0;
  return `<div class="pagehead"><div><h1>${esc(I18n.t("Settings"))}</h1><p>${esc(I18n.t("Choose what runs on your Mac."))}</p></div></div>${banners()}
    <div class="settings-stream">
      <section class="settings-section">
        <div class="settings-section-head">
          <h2>${icon("sun")}${esc(I18n.t("Appearance"))}</h2>
          <p>${esc(I18n.t("Switch between a dark and a light workspace."))}</p>
        </div>
        <div class="settings-row">
          <div>
            <h3>${esc(I18n.t("Theme"))}</h3>
            <p>${esc(I18n.t(theme === "light" ? "Light mode" : "Dark mode"))}</p>
          </div>
          <button type="button" class="theme-switch ${theme === "light" ? "is-light" : ""}" data-action="theme" role="switch" aria-checked="${theme === "light"}" aria-label="${esc(I18n.t("Light mode"))}"><span class="theme-label">${icon(theme === "light" ? "sun" : "moon")}${esc(I18n.t(theme === "light" ? "Light mode" : "Dark mode"))}</span><span class="theme-track" aria-hidden="true"><i></i></span></button>
        </div>
        <div class="settings-row">
          <div>
            <h3>${esc(I18n.t("Developer options"))}</h3>
            <p>${esc(I18n.t("Show low-level command details and developer tools."))}</p>
          </div>
          <button type="button" class="button ${mode === "dev" ? "primary" : ""}" data-action="mode" data-mode="${mode === "dev" ? "normal" : "dev"}" role="switch" aria-checked="${mode === "dev"}">${esc(I18n.t(mode === "dev" ? "Enabled" : "Off by default"))}</button>
        </div>
      </section>

      ${BackgroundUI.settings()}
      ${I18n.settings()}

      <section class="settings-section">
        <div class="settings-section-head">
          <h2>${icon("ghost")}${esc(I18n.t("Experimental"))}</h2>
          <p>${esc(I18n.t("Find leftovers from apps you have deleted. Review each one before moving it to the Trash."))}</p>
        </div>
        <div class="settings-row">
          <div>
            <h3>${esc(I18n.t("Ghost Files"))}</h3>
            <p>${esc(I18n.t("Find leftovers from apps you have deleted. Review each one before moving it to the Trash."))}</p>
          </div>
          <button class="button ${level ? "primary" : ""}" data-action="feature-ghost-level" data-level="${level ? 0 : 1}" role="switch" aria-checked="${!!level}" aria-label="Ghost Files" ${busy || S.busy ? "disabled" : ""}>${esc(I18n.t(level ? "On" : "Off"))}</button>
        </div>
        ${level ? `<div class="feature-levels" aria-label="Ghost Files mode">${button(I18n.t("Ghosts (no AI)"), "feature-ghost-level", {style:level === 1 ? "primary" : "", data:{level:1},disabled:!!S.busy})}${button(I18n.t("Ghosts + AI narration"), "feature-ghost-level", {style:level === 2 ? "primary" : "", data:{level:2},disabled:!!S.busy})}${button(I18n.t("Open Ghost Files"), "navigate", {data:{view:"ghosts"},symbol:"arrow"})}</div>${window.GhostUI ? GhostUI.settings() : `<p>${esc(I18n.t("Loading feature settings…"))}</p>`}` : `<p class="note">${esc(I18n.t("Off by default. No Ghost Files scanning, AI probing, or downloads run while disabled."))}</p>`}
      </section>

      <section class="settings-section">
        <div class="settings-section-head"><h2>${esc(I18n.t('Ghost allowlist'))}</h2><p>${esc(I18n.t('Dismissed Ghost Files stay off future Ghost scans. Remove an entry to reconsider it.'))}</p></div>
        ${(S.settings?.ghost_allowlist || []).map(path => `<div class="settings-row"><p class="path" data-no-translate>${esc(path)}</p>${button(I18n.t('Remove from allowlist'), 'allowlist-remove', {data:{path},disabled:!!S.busy})}</div>`).join('') || `<p>${esc(I18n.t('No dismissed ghosts.'))}</p>`}
      </section>

      <section class="settings-section settings-about-section">
        <div class="about-card-content">
          <div>
            <h3 style="font-size:15px;margin:0 0 4px">${esc(I18n.t("About Mac Deep Cleaner"))}</h3>
            <p>${esc(I18n.t("All scanning, analysis, and maintenance runs locally on your Mac."))}</p>
          </div>
          <div style="display:flex;gap:10px;align-items:center">
            ${S.version ? `<span class="badge" data-no-translate>v${esc(S.version)}</span>` : ''}
            <small style="color:var(--muted)">${esc(I18n.t("macOS Native"))}</small>
          </div>
        </div>
      </section>
    </div>`;
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
      ToolkitUI.invalidate();
      selected.clear();
      focusId = null;
      bigIds = [];
      bigReady = false;
      A = { apps: [], ready: false };
      if (detailKind !== 'history') closeDetail();
    }
    if (!ready) {
      const [route, tab] = location.hash.slice(1).split('/');
      const initial = navs.some(n => n[0] === route) ? route : next.initial_view;
      if (navs.some(n => n[0] === initial)) view = initial;
      window.history.replaceState({mdcView:view}, '', location.pathname + '#' + view + (view === 'clean' && tab === 'history' ? '/history' : ''));
    }
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
    if (!(view === "settings" && $("languagePackFile")?.files.length)) draw();
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
  while ($("toasts").children.length > 4) $("toasts").firstElementChild.remove();
  setTimeout(() => item.remove(), error ? 10000 : 6500);
}
function chrome() {
  const title = navs.find((n) => n[0] === view)[1];
  $("navigation").innerHTML = navs
    .filter(([v]) => v !== "ghosts" || S.features?.ghosts_level > 0)
    .map(
      ([v, name, symbol]) =>
        `<button class="nav-button ${view === v ? "active" : ""}" data-action="navigate" data-view="${v}" title="${esc(I18n.t(name))}" aria-label="${esc(I18n.t(name))}" ${view === v ? 'aria-current="page"' : ""}>${icon(symbol)}<span class="nav-full">${esc(I18n.t(name))}</span><span class="nav-short">${esc(I18n.t({ clean: "Cleanup", apps: "Apps", big: "Large files", dups: "Duplicates", optimize: "Optimize", disks: "Disks", homebrew: "Homebrew", ghosts: "Ghosts", settings: "Settings" }[v]))}</span></button>`,
    )
    .join("");
  $("modeSwitch").innerHTML = `<button class="rail-control mode-control ${mode === "dev" ? "enabled" : ""}" data-action="mode" data-mode="${mode === "dev" ? "normal" : "dev"}" role="switch" aria-checked="${mode === "dev"}" aria-label="${esc(I18n.t("Developer mode"))}" title="${esc(I18n.t("Developer mode"))}: ${mode === "dev" ? "on" : "off"}">${icon("code")}<span class="rail-label">${esc(I18n.t("Developer mode"))}</span><span class="mode-indicator" aria-hidden="true"></span></button>`;
  $("breadcrumb").innerHTML =
    `${icon("monitor")}<span>${esc(I18n.t("This Mac"))}</span><span aria-hidden="true">/</span><strong>${esc(I18n.t(title))}</strong>`;
  updateActivityStatus();
  document.title = `${I18n.t(title)} — Mac Deep Cleaner`;
}
function updateActivityStatus() {
  const scanning = S.scanning || !!document.querySelector('#main .scan-indicator');
  const working = S.busy || busy || ToolkitUI.isRunning() || (HistoryUI.isRunning() || I18n.isRunning()) || window.GhostUI?.isRunning();
  $("status").className =
    "status" + (connectionError ? " offline" : scanning || working ? " working" : "");
  $("status").textContent = I18n.t(connectionError
    ? "Disconnected"
    : !ready
      ? "Connecting"
    : working
      ? "Working…"
    : scanning
        ? "Scan in progress"
        : "Scan complete");
}
function pagehead(title, subtitle) {
  return `<div class="pagehead"><div><h1>${esc(I18n.t(title))}</h1><p>${esc(I18n.t(subtitle))}</p></div><div class="head-actions">${view === "clean" ? button(I18n.t("Cleanup history"), "history-open", {symbol:"file"}) : ""}${button(S.scanning ? I18n.t("Scanning") : I18n.t("Rescan"), "rescan", { symbol: "refresh", disabled: !ready || S.scanning || S.busy || busy || ToolkitUI.isRunning() || (HistoryUI.isRunning() || I18n.isRunning()) })}</div></div>`;
}
function banners() {
  return (
    (connectionError
      ? `<div class="error-banner" role="alert">${icon("alert")}<span>${esc(connectionError)}</span>${button("Retry", "retry")}</div>`
      : "") +
    (S.warnings?.length ? `<details class="scan-limits"><summary>${icon('shield')}${esc(I18n.t('Some locations could not be scanned'))}</summary><p>${esc(I18n.t('macOS denied access to these locations. Review privacy permissions, then rescan for complete results.'))}</p><ul>${S.warnings.map(path => `<li class="path" data-no-translate>${esc(path)}</li>`).join('')}</ul>${button(I18n.t('Privacy settings'), 'toolkit-open', {data:{action:'privacy-settings'},style:'link'})}</details>` : '')
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
  return `<section class="overview" aria-label="${esc(I18n.t("Storage overview"))}">${(S.scanning || !ready) && !connectionError ? scanIndicator(S.progress || "Finding storage you can review…", {feature:'clean',embedded:true,centered:!S.items.length}) : ""}<div class="overview-main"><div><div class="overview-label">${icon("clean")}${esc(I18n.t(S.scanning ? "Potential space found so far" : "Potential to reclaim"))}</div><div class="storage-number">${ready ? n : "—"}<span>${ready ? u : ""}</span></div><p class="overview-copy">${S.scanning ? esc(I18n.t("Results will be ready to review when the scan finishes.")) : `${S.items.filter(eligible).length.toLocaleString(I18n.locale())} ${esc(I18n.t("items found across your Mac. You choose what goes."))}`}</p><div class="overview-cta">${button(I18n.t("Select safe items"), "select-safe", { style: "primary", symbol: "check", disabled: !canSelect() || !S.items.some((i) => eligible(i) && i.safety === "safe" && !i.manual && i.action === "trash") })}<small>${esc(I18n.t("Review before removing anything"))}</small></div></div><div class="disk-panel"><div class="disk-ring"><svg viewBox="0 0 148 148" aria-hidden="true"><circle class="ticks" cx="74" cy="74" r="70"/><circle class="track" cx="74" cy="74" r="59"/><circle class="usage" cx="74" cy="74" r="59" stroke-dasharray="${(C * (used || 0)) / 100} ${C}"/></svg><div class="ring-label"><b>${used === null ? "—" : used + "%"}</b><span>${esc(I18n.t("disk used"))}</span></div></div><div class="disk-info"><h3>${esc(I18n.t("Your Mac’s storage"))}</h3><p>${esc(I18n.t("Available"))}<strong class="free">${disk ? fmt(disk.free) : "—"}</strong></p><p>${esc(I18n.t("Total capacity"))}<strong>${disk ? fmt(disk.total) : "—"}</strong></p></div></div></div><div class="risk-summary">${[
    ["safe", I18n.t("Safe to remove")],
    ["caution", I18n.t("Review first")],
    ["risky", I18n.t("Needs care")],
  ]
    .map(
      ([key, label]) =>
        `<button class="risk-stat" data-action="safety-summary" data-safety="${key}" aria-label="${esc(I18n.t("Show"))} ${esc(label)}"><div><span class="stat-label"><i class="dot ${key}"></i>${esc(label)}</span><b>${fmt(t[key])}</b></div>${icon("chevron")}</button>`,
    )
    .join("")}</div></section>`;
}
function filteredRows(source = S.items) {
  const query = q.toLocaleLowerCase(I18n.locale()).trim();
  return source
    .filter(
      (i) =>
        (!cat || group(i) === cat) &&
        (safetyFilter === "all" || i.safety === safetyFilter) &&
        (i.size >= minmb * 1e6 || i.size === 0) &&
        `${itemName(i)} ${i.name} ${i.path}`.toLocaleLowerCase(I18n.locale()).includes(query),
    )
    .sort((a, b) => b.size - a.size || a.id - b.id);
}
function searchField(id, value, placeholder) {
  return `<label class="search">${icon("search")}<span class="sr-only">${esc(placeholder)}</span><input type="search" id="${id}" placeholder="${esc(placeholder)}" value="${esc(value)}" autocomplete="off"></label>`;
}
function filters(rows, { categories = true } = {}) {
  const gs = groups();
  return `<div class="toolbar">${searchField("itemSearch", q, I18n.t("Search files, folders or paths"))}${categories ? `<select id="categoryFilter" class="category-filter" aria-label="${esc(I18n.t("Category"))}"><option value="">${esc(I18n.t("All categories"))}</option>${gs.map(([n, r]) => `<option value="${esc(n)}" ${cat === n ? "selected" : ""}>${esc(n)} (${r.length})</option>`).join("")}</select>` : ""}<select id="sizeFilter" aria-label="${esc(I18n.t("Minimum item size"))}">${[
    [0, I18n.t("Any size")],
    [1, I18n.t("Over 1 MB")],
    [10, I18n.t("Over 10 MB")],
    [100, I18n.t("Over 100 MB")],
    [1000, I18n.t("Over 1 GB")],
  ]
    .map(
      ([n, name]) =>
        `<option value="${n}" ${minmb === n ? "selected" : ""}>${esc(name)}</option>`,
    )
    .join(
      "",
    )}</select></div><div class="filter-row"><div class="filter-tabs" aria-label="${esc(I18n.t("Filter by safety"))}">${["all", "safe", "caution", "risky"].map((s) => `<button class="filter-tab ${s === safetyFilter ? "active" : ""}" data-action="safety" data-safety="${s}" aria-pressed="${s === safetyFilter}">${s === "all" ? esc(I18n.t("All items")) : esc(safetyLabel[s])}</button>`).join("")}</div><span>${rows.length.toLocaleString(I18n.locale())} ${esc(I18n.t("results, largest first"))}</span></div>`;
}
function fileIcon(i) {
  const name = CATI[i.category] || (mode === "dev" ? "code" : "folder");
  return `<span class="file-icon ${name === "cache" ? "cache-icon" : name === "code" ? "code-icon" : ""}">${icon(name)}</span>`;
}
function fileList(rows) {
  if (!ready && !connectionError)
    return empty("Scanning your Mac…", "Searching storage across your system. Results appear here as they are discovered.", "file", "", {scanning:true,showLoader:view !== 'clean'});
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
      { scanning: S.scanning, showLoader: false },
    );
  const mx = rows[0].size || 1;
  return `<div class="list-head" aria-hidden="true"><span></span><span>Name</span><span>Safety</span><span class="size">Size</span></div>${rows
    .slice(0, visibleLimit)
    .map(
      (i) =>
        `<div class="item-row ${selected.has(i.id) ? "selected" : ""} ${focusId === i.id ? "focused" : ""}"><input type="checkbox" data-select="${i.id}" aria-label="Select ${esc(itemName(i))}" ${selected.has(i.id) ? "checked" : ""} ${!eligible(i) || !canSelect() ? "disabled" : ""}><button class="item-main" data-action="inspect" data-id="${i.id}" aria-label="Details for ${esc(itemName(i))}">${fileIcon(i)}<span class="item-text"><span class="item-name"><span data-no-translate>${esc(itemName(i))}</span>${i.protected ? '<span class="tag">Protected</span>' : i.managed ? '<span class="tag">macOS</span>' : i.active_project ? '<span class="tag">Active</span>' : ""}</span><span class="item-path" title="${esc(i.path)}">${esc(i.path || "Managed by a terminal command")}</span></span></button>${safety(i.safety)}<span class="item-size">${fmt(i.size)}<span class="size-bar"><i style="width:${Math.max(3, (i.size / mx) * 100)}%"></i></span></span></div>`,
    )
    .join(
      "",
    )}<div class="list-footer"><span>${Math.min(visibleLimit, rows.length)} of ${rows.length.toLocaleString(I18n.locale())} items</span>${rows.length > visibleLimit ? button("Show more", "more", { style: "link" }) : "<span>Sorted by size</span>"}</div>`;
}
function inspectorContent(i, { close = true } = {}) {
  if (i?.category === "Ghost Files") return `<div class="inspect-heading"><h3 data-no-translate>${esc(itemName(i))}</h3>${close ? button("", "close-inspector", {style:"ghost icon-only",symbol:"x",aria:I18n.t("Close details")}) : ""}</div><div class="inspect-content"><p>${esc(i.reason)}</p><p class="path">${esc(i.path)}</p>${button(I18n.t("Review in Ghost Files"), "navigate", {data:{view:"ghosts"},style:"primary"})}</div>`;
  if (!i)
    return `<div class="inspector-empty">${icon("file")}<h3>${esc(I18n.t("A closer look"))}</h3><p>${esc(I18n.t("Select a file to see its location and what happens when it’s removed."))}</p><small>${icon("shield")}${esc(I18n.t("Protected files stay on your Mac. Every cleanup starts with a review."))}</small></div>`;
  return `<div class="inspect-heading">${fileIcon(i)}<div><h3 data-no-translate>${esc(itemName(i))}</h3><small>${fmt(i.size)}</small></div>${close ? button("", "close-inspector", { style: "ghost icon-only", symbol: "x", aria: I18n.t("Close details") }) : ""}</div><div class="inspect-content"><dl class="facts"><div><dt>${esc(I18n.t("Safety"))}</dt><dd>${safety(i.safety)}</dd></div><div><dt>${esc(I18n.t("Status"))}</dt><dd>${esc(I18n.t(i.protected ? "Protected" : i.managed ? "Managed by macOS" : i.active_project ? "Active project" : i.readonly ? "Read-only" : "Available for review"))}</dd></div><div><dt>${esc(I18n.t("Category"))}</dt><dd>${esc(group(i))}</dd></div></dl><section class="inspect-section"><h3>${esc(I18n.t("Location"))}</h3><p class="path">${esc(i.path || I18n.t("No local file path"))}</p></section><section class="inspect-section"><h3>${esc(I18n.t("What happens if removed"))}</h3><p>${esc(i.reason || I18n.t("Review this item before removing it."))}</p>${i.regen ? `<small>${esc(i.regen)}</small>` : ""}</section>${i.keep ? `<section class="inspect-section"><h3>${esc(I18n.t("Original copy kept"))}</h3><p class="path">${esc(i.keep)}</p></section>` : ""}${mode === "dev" && i.cmd ? `<section class="inspect-section"><h3>${esc(I18n.t("Terminal command"))}</h3><code>${esc(i.cmd)}</code></section>` : ""}<div class="inspect-actions">${eligible(i) ? button(I18n.t(selected.has(i.id) ? "Remove from selection" : "Add to cleanup"), "toggle", { style: selected.has(i.id) ? "" : "primary", symbol: selected.has(i.id) ? "x" : "check", disabled: !canSelect(), data: { id: i.id } }) : ""}${i.path ? button(I18n.t("Reveal in Finder"), "reveal", { symbol: "folder", data: { id: i.id } }) + button(I18n.t("Copy path"), "copy", { symbol: "dup", data: { id: i.id } }) + button(I18n.t("Keep out of future scans"), "pin", { style: "link", symbol: "pin", data: { id: i.id }, disabled: !canSelect() }) : ""}</div></div>`;
}
function workspace(rows) {
  return `<div class="workspace"><section class="list-panel" aria-label="${esc(I18n.t("Files"))}">${fileList(rows)}</section><aside class="inspector" aria-label="${esc(I18n.t("File inspector"))}">${inspectorContent(S.items.find((i) => i.id === focusId))}</aside></div>`;
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
    `<div class="section-title" id="filesTitle"><h2>${esc(I18n.t("Explore your files"))}</h2><span class="count">${S.items.length.toLocaleString(I18n.locale())}</span>${button(I18n.t("Select caution items"), "select-caution", { style: "link", disabled: !canSelect() })}</div>` +
    filters(rows) +
    workspace(rows) +
    `<p class="note">${icon("shield")}${esc(I18n.t("Nothing is removed until you review and confirm. Some items need extra care."))}</p>`
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
    `<div class="metrics">${metric("Files found", source.length.toLocaleString(I18n.locale()), "Up to 100 largest files")}${metric("Combined size", fmt(sum(source)), "Includes protected files")}${metric("Largest file", source.length ? fmt(Math.max(...source.map((i) => i.size))) : "—", "Sorted from largest to smallest")}${metric("Protected files", source.filter((i) => !eligible(i)).length, "Kept out of every cleanup")}</div>` +
    (bigError
      ? `<div class="error-banner">${esc(bigError)}${button("Retry", "retry-big")}</div>`
      : "") +
    filters(rows, { categories: false }) +
    (S.scanning || !bigReady
      ? `<div class="list-panel">${empty(S.scanning ? "Analyzing file sizes…" : "Loading large files", S.scanning ? "Scanning for the largest files on your Mac. Results will appear when complete." : "Reading the results from your Mac.", "file", "", { scanning: S.scanning || !bigError })}</div>`
      : workspace(rows))
  );
}
function appIcon(a) {
  return `<span class="app-icon"><span aria-hidden="true">${esc((a.name.match(/[A-Za-z0-9]/) || ["?"])[0].toUpperCase())}</span><img src="/api/icon?id=${a.id}&generation=${encodeURIComponent(A.apps_id || S.scan_id || "")}" alt="" loading="lazy" decoding="async"></span>`;
}
/** Render the filtered application inventory and theme-aware storage breakdown. */
function appsView() {
  if (!A.ready && !A.apps.length && !appsError) return pagehead('Applications', 'Your apps, their data, and the space they leave behind.') + banners() + empty('Analyzing applications', 'Measuring disk footprints and caches for all installed apps.', 'apps', '', {scanning:true,percent:A.total ? A.progress*100/A.total : null});
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
    (!A.ready && !appsError
      ? scanIndicator('Analyzing applications', {percent: A.total ? A.progress * 100 / A.total : null})
      : "") +
    `<div class="metrics">${metric("Applications", A.apps.length, A.ready ? "Installed on your Mac" : "Analysis in progress")}${metric("App size", fmt(sum(A.apps)), "Application bundles")}${metric("Stored data", fmt(A.apps.reduce((n, a) => n + a.data_size, 0)), "Caches, support and settings")}${metric("Unused for 6 months", idle.length, I18n.t("{size} combined footprint", {size: fmt(idle.reduce((n, a) => n + a.total, 0))}))}</div><div class="toolbar">${searchField("appSearch", aq, "Search applications")}<select id="appSort" aria-label="Sort applications">${[
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
                `<button class="app-card" data-action="app" data-id="${a.id}"><div class="app-card-top">${appIcon(a)}<div><h3 data-no-translate>${esc(a.name)}</h3><small>${a.running ? "Running now" : esc(a.category || a.source || "Application")}</small></div></div><div class="app-card-bottom"><b class="num">${fmt(a.total)}</b><span>${ago(a.last_used)}</span></div>${bar(
                  [
                    [(a.size / mx) * 100, "var(--accent)"],
                    [(a.cache_size / mx) * 100, "var(--safe)"],
                    [
                      (Math.max(0, a.data_size - a.cache_size) / mx) * 100,
                      "var(--muted)",
                    ],
                  ],
                )}</button>`,
            )
            .join(
              "",
            )}</div><div class="app-legend"><span><i class="dot" style="color:var(--accent)"></i>Application</span><span><i class="dot safe"></i>Caches</span><span><i class="dot" style="color:var(--muted)"></i>Other stored data</span></div>`
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
            { scanning: !A.ready, showLoader: false },
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
  if (S.scanning && !rows.length) return pagehead('Duplicate files', 'Keep the original. Let go of the extra copies.') + banners() + empty('Checking for duplicates…', 'Scanning and comparing file hashes. Matching copies will appear here.', 'dup', '', {scanning:true});
  return (
    pagehead(
      "Duplicate files",
      "Keep the original. Let go of the extra copies.",
    ) +
    banners() +
    (S.scanning ? scanIndicator("Checking for duplicates…") : "") +
    `<div class="metrics">${metric(I18n.t("Duplicate groups"), sets.length, I18n.t("Matched by file content"))}${metric(I18n.t("Extra copies"), rows.length, I18n.t("Available for review"))}${metric(I18n.t("Potential to reclaim"), fmt(sum(rows)), I18n.t("Only extra copies counted"))}${metric(I18n.t("Originals kept"), sets.length, I18n.t("One copy is always protected"))}</div><div class="toolbar">${searchField("duplicateSearch", q, I18n.t("Search duplicate files or paths"))}</div><p class="note" style="margin:0 0 20px">${icon("shield")}${esc(I18n.t("Files are compared by content. The original copy shown in each group stays on your Mac."))}</p>${
      matches.length
        ? matches
            .slice(0, visibleLimit)
            .map((g) => {
              const all = g.filter(eligible).every((i) => selected.has(i.id));
              return `<section class="duplicate-card"><div class="duplicate-head"><span class="file-icon">${icon("dup")}</span><div><h3>${esc(g[0].name)}</h3><p>${g.length + 1} ${esc(I18n.t("copies found"))}. ${fmt(sum(g))} ${esc(I18n.t("in extra copies"))}.</p></div>${button(I18n.t(all ? "Deselect extras" : "Select extras"), "duplicate-set", { symbol: all ? "x" : "check", data: { ids: g.map((i) => i.id).join(",") }, disabled: !canSelect() })}</div><div class="kept-copy">${icon("shield")}<span><strong>${esc(I18n.t("Keeping"))}</strong> ${esc(g[0].keep)}</span></div>${g.map((i) => `<label class="duplicate-file"><input type="checkbox" data-select="${i.id}" aria-label="${esc(I18n.t("Select duplicate"))} ${esc(i.path)}" ${selected.has(i.id) ? "checked" : ""} ${!canSelect() || !eligible(i) ? "disabled" : ""}><span>${esc(i.path)}</span><b>${fmt(i.size)}</b></label>`).join("")}</section>`;
            })
            .join("") +
          (matches.length > visibleLimit
            ? button(I18n.t("Show more groups"), "more", { style: "ghost" })
            : "")
        : empty(
            S.scanning ? I18n.t("Checking for duplicates…") : I18n.t("No duplicate files found"),
            S.scanning
              ? I18n.t("Scanning and comparing file hashes. Matching copies will appear here.")
              : q
                ? I18n.t("Try another name or path.")
                : I18n.t("There are no extra copies in the scanned locations."),
            S.scanning ? "refresh" : "dup",
            "",
            { scanning: S.scanning, showLoader: false },
          )
    }`
  );
}
/** Redraw while preserving form drafts, scroll position, and keyboard focus. */
function preserveFocus(render) {
  // Keep unsaved form edits through periodic state refreshes.
  const draftIds = ['languageSearch','languageSelect','automationHours','automationInterval'];
  const drafts = new Map(draftIds.filter(id => $(id)).map(id => [id, $(id).value]));
  const mainTop = $("main")?.scrollTop;
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
  for (const [draftId, value] of drafts) if ($(draftId)) $(draftId).value = value;
  for (const [draftId, value] of formDrafts) if ($(draftId)) $(draftId).value = value;
  Dropdowns.enhance($("main"));
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
  if (mainTop !== undefined && $("main")) $("main").scrollTop = mainTop;
}
function draw({ animate = false } = {}) {
  preserveFocus(() => {
    chrome();
    $("main").innerHTML = cleanupResult() + {
      clean: cleanView,
      apps: appsView,
      big: bigView,
      dups: duplicatesView,
      optimize: ToolkitUI.optimizeView,
      disks: ToolkitUI.diskView,
      homebrew: HomebrewUI.render,
      settings: settingsView,
      ghosts: () => window.GhostUI ? GhostUI.render() : empty("Opening Ghost Files…", "Loading the optional workspace."),
    }[view]() + relatedTools();
    drawSelection();
    LoaderUI.sync($("main"));
    Dropdowns.enhance($("main"));
    updateActivityStatus();
    watchMore();
    if (window.I18n?.translateDOM) I18n.translateDOM();
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
  el.innerHTML = `<span class="selection-icon">${icon("check")}</span><div class="selection-summary"><strong>${items.length} ${esc(I18n.t("Selected items"))}</strong><small>${fmt(sum(distinctStorage(items)))} ${esc(I18n.t("Available for review"))}</small></div><button class="clear" data-action="clear-selection">${esc(I18n.t("Clear"))}</button>${button(busy ? I18n.t("Working…") : I18n.t("Review cleanup"), "review", { style: "primary", symbol: "arrow", disabled: !canSelect() })}`;
}
function relatedTools() {
  const targets = {
    clean:[['big','Large files'],['dups','Duplicates'],['disks','Disks & volumes']],
    apps:[['optimize','Optimize your Mac'],['ghosts','Ghost Files']],
    big:[['dups','Duplicates'],['clean','Storage cleanup']],
    dups:[['big','Large files'],['clean','Storage cleanup']],
    optimize:[['apps','Applications'],['disks','Disks & volumes'],['homebrew','Homebrew']],
    disks:[['big','Large files'],['clean','Storage cleanup'],['optimize','Optimize your Mac']],
    homebrew:[['apps','Applications'],['optimize','Optimize your Mac'],['clean','Storage cleanup']],
    ghosts:[['apps','Applications'],['clean','Storage cleanup'],['settings','Settings']],
    settings:[['clean','Storage cleanup'],['optimize','Optimize your Mac']],
  }[view] || [];
  return `<nav class="related-tools" aria-label="${esc(I18n.t('Related tools'))}"><span>${esc(I18n.t('Related tools'))}</span>${targets.filter(([v]) => v !== 'ghosts' || S.features?.ghosts_level).map(([v,label,tab]) => `<a class="button link" href="#${v}${tab ? '/' + tab : ''}" data-action="related-tool" data-view="${v}" ${tab ? `data-tab="${tab}"` : ''}>${icon('arrow')}${esc(I18n.t(label))}</a>`).join('')}</nav>`;
}
function navigate(v, options = {}) {
  if (!navs.some((n) => n[0] === v) || (v === "ghosts" && !S.features?.ghosts_level)) return;
  window.GhostUI?.leave();
  HomebrewUI.leave();
  Dropdowns.close();
  viewStates.set(view, {q, cat, safetyFilter, minmb, focusId, visibleLimit, scroll:$('main').scrollTop});
  if (matchMedia("(max-width:900px)").matches) setSidebar(false);
  view = v;
  const saved = options.reset ? null : viewStates.get(v);
  q = options.query ?? saved?.q ?? "";
  cat = options.category ?? saved?.cat ?? "";
  safetyFilter = saved?.safetyFilter ?? "all";
  minmb = options.minmb ?? saved?.minmb ?? S.settings?.min_mb ?? 10;
  focusId = saved?.focusId ?? null;
  visibleLimit = saved?.visibleLimit ?? 100;
  closeDetail();
  draw({ animate: true });
  window.scrollTo({ top: 0, behavior: "instant" });
  if ($("main")) { $("main").scrollTop = saved?.scroll || 0; $("main").focus({preventScroll:true}); }
  if (options.history !== false) {
    window.history.pushState({mdcView:v}, '', location.pathname + '#' + v);
  }
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
      (level === "safe" && (i.manual || i.action !== "trash"))
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
/** Render app storage details and guarded removal actions. */
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
    `<div class="drawer-head">${appIcon(a)}<div><h2 data-no-translate>${esc(a.name)}</h2><small>${esc(a.version || "Version unavailable")} / ${esc(a.source || "Application")}${a.running ? " / Running now" : ""}</small></div>${button("", "close-detail", { style: "ghost icon-only", symbol: "x", aria: "Close application details" })}</div><div class="drawer-body"><div class="metrics">${metric("Total footprint", fmt(a.total), "App and stored data")}${metric("Caches", fmt(a.cache_size), "Can be regenerated")}${metric("Last opened", ago(a.last_used), a.running ? "Running now" : "")}</div>${bar(
      [
        [(a.size / total) * 100, "var(--accent)"],
        [(a.cache_size / total) * 100, "var(--safe)"],
        [(Math.max(0, a.data_size - a.cache_size) / total) * 100, "var(--muted)"],
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
  if (pendingAsk) return Promise.resolve({confirmed:false, permanent:false, phrase:'', backupAck:false});
  return new Promise((resolve) => {
    pendingAsk = { resolve, phrase, allowPermanent, confirm, danger, requiresBackup };
    $("confirmDialog").innerHTML =
      `<div class="modal-head"><h2 id="confirmTitle">${esc(title)}</h2>${button("", "cancel-confirm", { style: "ghost icon-only", symbol: "x", aria: "Close confirmation" })}</div><div class="modal-body">${body}${allowPermanent ? '<label class="check-label"><input id="permanent" type="checkbox">Delete permanently instead of using Trash</label><div class="review-warning" id="permanentWarning" hidden>Permanent deletion cannot be undone.</div>' : ""}<label class="phrase-label" id="phraseLabel" ${phrase ? "" : "hidden"}>Type <strong id="phraseText" data-no-translate>${esc(phrase)}</strong> to continue<input type="text" id="confirmPhrase" autocomplete="off" spellcheck="false" aria-label="Confirmation phrase"></label></div><div class="modal-actions">${button("Cancel", "cancel-confirm")}${button(confirm, "confirm", { style: danger ? "danger" : "primary", disabled: !!phrase || requiresBackup })}</div>`;
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
  btn.textContent = I18n.t(perm ? "Delete permanently" : pendingAsk.confirm);
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
  return `<div class="review-total"><span>${items.length} ${items.length === 1 ? "item" : "items"} selected</span><b>${fmt(sum(distinctStorage(items)))}</b></div><div class="review-items">${items.map((i) => `<div class="review-item"><span>${esc(itemName(i))}</span><b>${fmt(i.size)}</b></div>`).join("")}</div>`;
}
function cleanupResult() {
  if (!lastCleanup || !['clean','apps','big','dups'].includes(view)) return '';
  const rows = lastCleanup.results || [];
  const completed = rows.filter(r => r.ok && r.message !== 'included in selected parent').length;
  const failed = rows.filter(r => r.ok === false).length;
  const moved = rows.some(r => r.ok && r.action === 'trash') && !lastCleanup.permanent;
  const outcomes = {trash:lastCleanup.permanent ? 'Deleted permanently' : 'Moved to Trash',
    empty:'Trash emptied', evict:'Local copy removed', cmd:'Command completed', root:'Terminal action needed'};
  return `<section class="cleanup-result ${failed ? 'has-failures' : ''}" aria-label="${esc(I18n.t('Cleanup results'))}">
    <div class="cleanup-result-heading">${icon(failed ? 'alert' : 'check')}<div><h2>${esc(I18n.t('Cleanup results'))}</h2><p>${esc(I18n.t('{completed} completed · {failed} failed', {completed, failed}))} · ${fmt(lastCleanup.processed_bytes ?? lastCleanup.freed)}</p></div>${button('', 'dismiss-cleanup-result', {style:'ghost icon-only',symbol:'x',aria:I18n.t('Dismiss results')})}</div>
    ${moved ? `<p>${esc(I18n.t('Moved files can be restored from Cleanup history. Trash still uses disk space.'))}</p>` : ''}
    <details ${failed ? 'open' : ''}><summary>${esc(I18n.t('View results'))}</summary><ul>${rows.map(r => `<li><div><strong data-no-translate>${esc(r.name)}</strong><span>${esc(I18n.t(r.ok === false ? r.message : r.message === 'included in selected parent' ? 'Included in selected folder' : outcomes[r.action] || r.message))}</span></div>${icon(r.ok === false ? 'alert' : r.ok ? 'check' : 'terminal')}</li>`).join('')}</ul></details>
    ${moved ? `<a class="button link" href="#clean/history" data-action="history-open">${esc(I18n.t('Cleanup history'))}${icon('arrow')}</a>` : ''}
  </section>`;
}
function resultToast(r, permanent = false) {
  const inlineResults = r.results && ['clean','apps','big','dups'].includes(view);
  if (inlineResults) {
    // Earlier selection and operation notices must not obscure the final report.
    $('toasts').querySelectorAll('.toast:not(.error)').forEach(item => item.remove());
  }
  if (r.results) {
    lastCleanup = {...r, permanent};
    if (['clean','apps','big','dups'].includes(view)) $('main').scrollTop = 0;
  }
  if (r.fails?.length && !inlineResults)
    toast(
      `${r.fails.length} ${r.fails.length === 1 ? "item could" : "items could"} not be removed. ${r.fails.map((f) => f.join(": ")).join("; ")}`,
      true,
    );
  if (r.freed && !inlineResults)
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
  if (r.warning) toast(r.warning, true);
  if (!inlineResults && !r.freed && !r.fails?.length && !r.root?.length && !r.results?.some(row => row.ok))
    toast("No files were removed. The items may have changed since the scan.");
}
async function reviewCleanup() {
  if (!canSelect()) return;
  const items = selectedItems();
  if (!items.length) return;
  const emptyTrash = items.some(i => i.action === 'empty');
  if (emptyTrash && items.length !== 1) return toast(I18n.t('Empty Trash separately from other cleanup operations.'), true);
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
      `<p>Files are moved to the Trash by default. Review the selection before continuing.</p>${risky ? '<div class="review-warning">Risky items may contain personal data that cannot be regenerated.</div>' : ""}${special.length ? `<div class="review-warning">${special.map((i) => esc(itemName(i)) + ": " + { empty: "empties this location permanently", cmd: "runs its cleanup command; changes may be permanent", evict: "removes the local cloud copy", root: "requires a command in Terminal" }[i.action]).join("<br>")}</div>` : ""}`,
    confirm: emptyTrash ? "Empty Trash" : special.length ? "Remove selected items" : "Move to Trash",
    danger: risky || special.some((i) => ["empty", "cmd"].includes(i.action)),
    phrase: emptyTrash ? "DELETE" : risky ? "I UNDERSTAND" : "",
    allowPermanent: !emptyTrash && items.some(i => i.action === 'trash'),
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
      permanent_ack: answer.permanent || emptyTrash,
      scan_id: scanId,
      revision,
    });
    selected.clear();
    focusId = null;
    bigReady = false;
    A = { apps: [], ready: false };
    closeDetail();
    resultToast(r, answer.permanent || emptyTrash);
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
  if (S.scanning || S.busy || busy || ToolkitUI.isRunning() || (HistoryUI.isRunning() || I18n.isRunning())) return;
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
/** Route dashboard actions to their workspace or authenticated service operation. */
async function dispatch(action, el) {
  if (action === "related-tool") return navigate(el.dataset.view, {tab:el.dataset.tab});
  if (action === "feature-ghost-level") return setGhostLevel(Number(el.dataset.level));
  if (action.startsWith("ghost-")) return window.GhostUI?.dispatch(action, el);
  if (action.startsWith("background-")) return BackgroundUI.dispatch(action, el);
  if (action === "quick-language" || action.startsWith("locale-")) return I18n.dispatch(action, el);
  if (action === 'history-open') return HistoryUI.open();
  if (action === 'history-restore') return HistoryUI.restore(el.dataset.id);
  if (action === 'allowlist-remove') {
    await api('/api/settings/ghost-allowlist/remove', {path:el.dataset.path});
    return load();
  }
  if (action.startsWith("brew-")) return HomebrewUI.dispatch(action, el);
  if (action.startsWith("toolkit-")) return ToolkitUI.dispatch(action, el);
  const id = Number(el.dataset.id),
    i = S.items.find((x) => x.id === id);
  switch (action) {
    case "toggle-sidebar":
      setSidebar(!sidebarExpanded);
      try { localStorage.setItem('mdc_sidebar', sidebarExpanded ? 'expanded' : 'collapsed'); } catch {}
      return;
    case "dismiss-cleanup-result": lastCleanup = null; return draw();
    case "collapse-sidebar": return setSidebar(false);
    case "navigate":
      return navigate(el.dataset.view);
    case "language": { return I18n.activate(el.dataset.language); }
    case "theme": {
      applyTheme(theme === "light" ? "dark" : "light");
      try { localStorage.setItem("mdc_theme", theme); } catch {}
      // Persist best-effort; the choice applies immediately even if a scan holds the lock.
      api("/api/settings", { theme }).catch(() => {});
      return draw();
    }
    case "mode":
      await api("/api/settings", { mode:el.dataset.mode });
      mode = el.dataset.mode;
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
      if (el.dataset.path) return revealPath(el.dataset.path);
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
  if (el?.tagName === 'A' && (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)) return;
  if (el?.tagName === 'A') e.preventDefault();
  if (el && !el.disabled)
    Promise.resolve(dispatch(el.dataset.action, el)).catch((error) =>
      toast(error.message, true),
    );
});
document.addEventListener("input", (e) => {
  const el = e.target;
  if (draftFields.has(el.id)) formDrafts.set(el.id, el.value);
  if (el.id === "automationHours") return BackgroundUI.syncInterval();
  if (el.id === "confirmPhrase") return updateConfirmation();
  if (["itemSearch", "duplicateSearch", "appSearch"].includes(el.id)) {
    if (e.isComposing) return;
    if (el.id === "appSearch") aq = el.value;
    else q = el.value;
    visibleLimit = 100;
    draw();
  }
});
document.addEventListener("change", (e) => {
  const el = e.target;
  if (draftFields.has(el.id)) formDrafts.set(el.id, el.value);
  if (el.id === "automationInterval") return BackgroundUI.changeInterval(el.value);
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
window.addEventListener('popstate', event => {
  if (event.state?.mdcView) navigate(navs.some(n => n[0] === event.state.mdcView) ? event.state.mdcView : "clean", {history:false});
});
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
function preferredSidebar() {
  let preference;
  try { preference = localStorage.getItem('mdc_sidebar'); } catch {}
  setSidebar(matchMedia('(min-width:1180px)').matches && preference !== 'collapsed');
}
preferredSidebar();
matchMedia('(min-width:1180px)').addEventListener('change', preferredSidebar);
$("main").addEventListener("animationend", (event) => {
  if (event.target === $("main")) $("main").classList.remove("page-enter");
});
draw();
load();

// Native menu bar actions use the same authenticated and versioned cleanup path.
window.MDCNative = {
  metrics: async () => ({free: S.disk?.free, scanning:S.scanning, busy:!!S.busy || busy}),
  safeClean: async () => {
    try { await BackgroundUI.dispatch('background-clean'); }
    catch (e) { toast(e.message, true); }
  },
  checkUpdates: async () => {
    navigate('settings');
    try { await BackgroundUI.dispatch('background-update'); }
    catch (e) { toast(e.message, true); }
  }
};

I18n.init();
if (location.hash === '#clean/history') {
  const openHistory = () => ready ? HistoryUI.open() : setTimeout(openHistory, 100);
  openHistory();
}
