/* Loaded only after opting in. All deletion goes through /api/clean. */
"use strict";
P.ghost = '<path d="M5 21V9a7 7 0 0 1 14 0v12l-3-2-4 2-4-2-3 2Z"/><path d="M9 9v2m6-2v2m-5 4h4"/>';
P.chevron_left = '<path d="M15 18l-6-6 6-6"/>';
P.chevron_right = '<path d="M9 18l6-6-6-6"/>';
window.GhostUI = (() => {
  let config = null, report = null, status = null, timer, entering = false, error = "", wasScanning = false, setupPolling = false;
  let setupModel = "", setupTimer, active = false;
  const PAGE_SIZE = 10;
  let page = 1;
  let searchQuery = "";
  let verdictFilter = "all";
  let sortBy = "size";

  const labels = {likely_safe:"Likely safe", review:"Review first", keep:"Locked"};
  const enabled = () => S.features?.ghosts_level > 0;
  const running = () => report && [report.scan, report.haunt, report.setup].some(j => !j.done);
  const locked = () => !canSelect() || running();
  const version = () => ({scan_id:report.scan_id, revision:report.revision});
  const local = () => `<p class="ghost-privacy">${icon("shield")}Narration happens on this Mac only. Your files stay yours.</p>`;

  function leave() {
    active = false;
    clearTimeout(timer);
    timer = null;
  }

  async function enter(force = false) {
    if (!enabled() || entering) return;
    const opening = !active;
    active = ["ghosts", "settings"].includes(view);
    if (!force && timer) return;
    entering = true;
    clearTimeout(timer);
    timer = null;
    try {
      const [c, r] = await Promise.all([api("/api/ghosts/config"), api("/api/ghosts/state")]);
      if (!enabled()) return;
      config = c;
      const prevGhosts = report ? report.ghosts : null;
      const prevScanId = report ? report.scan_id : null;
      report = r;
      status = r.ai || status;
      error = "";
      if (config.level !== S.features.ghosts_level) {
        S.features.ghosts_level = config.level;
        if (config.level === 0) return leave();
      }
      const scanFinished = wasScanning && r.scan.done && !r.scan.error && !r.scan.cancelled;
      wasScanning = !r.scan.done;

      const hasWorkspace = !!document.querySelector(".ghost-workspace");
      if (active && (!hasWorkspace || opening || force)) {
        draw();
      } else if (active && view === "ghosts") {
        updateView(prevGhosts, prevScanId);
      }

      // The Ollama probe can be slow; never hold the list back for it.
      if (opening && config.level === 2) {
        try {
          status = await api("/api/ghosts/setup/status");
          if (active && enabled()) updateView(prevGhosts, prevScanId);
        } catch {}
      }
      if (config.level === 2 && scanFinished) {
        await api("/api/ghosts/haunt", {});
        wasScanning = false;
      }
    } catch (e) {
      error = e.message;
      if (active) draw();
    } finally {
      entering = false;
      if (active && enabled()) timer = setTimeout(() => { timer = null; enter(); }, running() ? 1200 : 6000);
    }
  }

  function progress(job, kind) {
    if (!job || (job.done && !job.error && !job.cancelled)) return "";
    return `<div class="ghost-progress" role="status"><div><strong>${esc(job.error || job.msg)}</strong>${!job.done ? button("Cancel", "ghost-cancel", {data:{kind}}) : ""}</div>${!job.done ? `<progress max="100" ${job.pct == null ? "" : `value="${job.pct}"`} aria-label="${esc(kind)} progress"></progress>` : ""}</div>`;
  }

  function renderProgressHtml() {
    if (!report) return "";
    return progress(report.scan, "scan") + progress(report.haunt, "haunt") + progress(report.setup, "setup");
  }

  function renderSummaryHtml() {
    if (!report) return "";
    const rawGhosts = report.ghosts.filter(g => !g.hidden);
    const totalBytes = rawGhosts.reduce((n, g) => n + g.size_bytes, 0);
    const stats = Object.keys(labels).map(v => `${labels[v]}: ${fmt(rawGhosts.filter(g => g.final_verdict === v).reduce((n, g) => n + g.size_bytes, 0))}`);
    return `<strong>${rawGhosts.length} ${rawGhosts.length === 1 ? "ghost" : "ghosts"}, ${fmt(totalBytes)}</strong>
      <p>${stats.map(esc).join(" · ")}</p>
      <small>Moving files to Trash keeps them recoverable; space is freed when you empty it yourself.</small>`;
  }

  function renderHistoryHtml() {
    if (!report || !report.ofrenda || !report.ofrenda.length) {
      return '<div class="history-empty">Your cleanup history will appear here after a successful move to Trash.</div>';
    }
    return `<ol class="history-list">${report.ofrenda.slice().reverse().map(e => `<li><strong>${esc(e.name)}</strong><span>${fmt(e.size_bytes)} · ${esc(e.date.slice(0,10))}</span><p>${esc(e.farewell || "Moved to Trash")}</p></li>`).join("")}</ol>`;
  }

  function renderCardsHtml() {
    if (!report) return "";
    const rawGhosts = report.ghosts.filter(g => !g.hidden);
    const hidden = report.ghosts.length - rawGhosts.length;

    let list = rawGhosts.slice();
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      list = list.filter(g =>
        (g.name_guess && g.name_guess.toLowerCase().includes(q)) ||
        (g.path && g.path.toLowerCase().includes(q)) ||
        (g.bundle_id && g.bundle_id.toLowerCase().includes(q)) ||
        (g.kind && g.kind.toLowerCase().includes(q))
      );
    }
    if (verdictFilter !== "all") {
      list = list.filter(g => g.final_verdict === verdictFilter);
    }

    if (sortBy === "size") {
      list.sort((a, b) => b.size_bytes - a.size_bytes);
    } else if (sortBy === "name") {
      list.sort((a, b) => (a.name_guess || "").localeCompare(b.name_guess || ""));
    } else if (sortBy === "age") {
      list.sort((a, b) => b.age_days - a.age_days);
    }

    const totalPages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
    if (page > totalPages) page = totalPages;
    if (page < 1) page = 1;
    const startIdx = (page - 1) * PAGE_SIZE;
    const pageItems = list.slice(startIdx, startIdx + PAGE_SIZE);
    const safeOnPage = pageItems.filter(g => g.final_verdict === "likely_safe");

    return `${safeOnPage.length > 1 ? `<div class="ghost-batch-bar">
      <span>${safeOnPage.length} likely safe items on this page (${fmt(safeOnPage.reduce((n, g) => n + g.size_bytes, 0))})</span>
      ${button(`Banish ${safeOnPage.length} safe items on this page`, "ghost-banish-page-safe", {symbol:"trash", style:"primary", disabled:locked()})}
    </div>` : ""}

    <div class="ghost-cards-stack">
      ${pageItems.length ? pageItems.map(card).join("") : empty(
        report.scanned ? "No matching ghosts found" : "Let’s see what’s lingering",
        report.scanned ? (searchQuery || verdictFilter !== "all" ? "Try clearing your search or filter." : "No unmatched leftovers were found in the readable Library locations, or you let them rest.") : "Compare Library leftovers with installed applications. The scan is read-only.",
        "ghost",
        report.scanned ? "" : button("Find ghosts", "ghost-scan", {style:"primary", disabled:locked()})
      )}
    </div>

    ${list.length > PAGE_SIZE ? `<nav class="ghost-pagination" aria-label="Ghosts pagination">
      <span class="pagination-info">Showing ${list.length ? startIdx + 1 : 0}–${Math.min(startIdx + PAGE_SIZE, list.length)} of ${list.length} ghosts</span>
      <div class="pagination-buttons">
        <button type="button" class="button ghost" data-action="ghost-page" data-page="1" ${page <= 1 ? "disabled" : ""} title="First page">« First</button>
        <button type="button" class="button ghost" data-action="ghost-page" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""} title="Previous page">‹ Prev</button>
        <span class="pagination-current">Page ${page} of ${totalPages}</span>
        <button type="button" class="button ghost" data-action="ghost-page" data-page="${page + 1}" ${page >= totalPages ? "disabled" : ""} title="Next page">Next ›</button>
        <button type="button" class="button ghost" data-action="ghost-page" data-page="${totalPages}" ${page >= totalPages ? "disabled" : ""} title="Last page">Last »</button>
      </div>
    </nav>` : ""}

    ${hidden ? `<div class="ghost-hidden-wrap">${button(`Show ${hidden} resting ${hidden === 1 ? "ghost" : "ghosts"}`, "ghost-show-hidden", {style:"ghost"})}</div>` : ""}`;
  }

  function updateCards() {
    const container = document.getElementById("ghostCardsContainer");
    if (container) {
      container.innerHTML = renderCardsHtml();
    }
  }

  function updateView(prevGhosts, prevScanId) {
    if (!report || !document.querySelector(".ghost-workspace")) return;

    // 1. Update progress bars
    const progWrap = document.getElementById("ghostProgressWrap");
    if (progWrap) {
      progWrap.innerHTML = renderProgressHtml();
    }

    // 2. Update scan button text and state
    const scanBtn = document.querySelector('[data-action="ghost-scan"]');
    if (scanBtn) {
      scanBtn.textContent = report.scan.done ? "Find ghosts" : "Finding ghosts…";
      scanBtn.disabled = locked();
    }

    // 3. Update summary counts
    const sumWrap = document.getElementById("ghostSummaryWrap");
    if (sumWrap) {
      sumWrap.innerHTML = renderSummaryHtml();
    }

    // 4. Update filter pills
    const rawGhosts = report.ghosts.filter(g => !g.hidden);
    const safeCount = rawGhosts.filter(g => g.final_verdict === "likely_safe").length;
    const reviewCount = rawGhosts.filter(g => g.final_verdict === "review").length;
    const lockedCount = rawGhosts.filter(g => g.final_verdict === "keep").length;
    document.querySelectorAll(".ghost-filter-pills .filter-pill").forEach(p => {
      const f = p.dataset.filter;
      if (f === "all") p.textContent = `All (${rawGhosts.length})`;
      else if (f === "likely_safe") p.textContent = `Safe (${safeCount})`;
      else if (f === "review") p.textContent = `Review (${reviewCount})`;
      else if (f === "keep") p.textContent = `Locked (${lockedCount})`;
    });

    // 5. Update cards if list changed
    const listChanged = !prevGhosts ||
      prevScanId !== report.scan_id ||
      prevGhosts.length !== report.ghosts.length ||
      prevGhosts.some((g, i) => g.id !== report.ghosts[i]?.id || g.hidden !== report.ghosts[i]?.hidden || g.unlocked !== report.ghosts[i]?.unlocked || g.final_verdict !== report.ghosts[i]?.final_verdict);

    if (listChanged) {
      updateCards();
    } else {
      // In-place text update for cards (hauntings) - no DOM replacement, no icon re-fetching!
      report.ghosts.forEach(g => {
        const cardEl = document.querySelector(`.ghost-card[data-ghost-id="${g.id}"]`);
        if (cardEl) {
          const hauntEl = cardEl.querySelector(".ghost-haunting");
          if (hauntEl && hauntEl.textContent !== g.haunting) hauntEl.textContent = g.haunting;
        }
      });
    }

    // 6. Update cleanup history
    const ofrWrap = document.getElementById("ghostOfrendaWrap");
    if (ofrWrap) {
      ofrWrap.innerHTML = renderHistoryHtml();
    }
  }

  function settings() {
    if (!config) return '<p class="note">Reading Ghost Files settings…</p>';
    const setup = config.setup;
    return `<div class="ghost-options"><div class="feature-setting"><div><h3>Local AI narration</h3><p>${config.level === 2 && status?.state === "READY" ? `AI: ${esc(config.model)} on 127.0.0.1` : "AI: not connected. Plain descriptions are available offline."}</p></div>${button("Set up AI narration", "ghost-setup", {disabled:!!S.busy})}</div>
      <label class="check-label"><input id="ghostAuto" type="checkbox" ${config.auto_start_ollama ? "checked" : ""}>Start Ollama automatically when needed, after setup consent</label>
      <label class="check-label"><input id="ghostStop" type="checkbox" ${config.stop_ollama_on_exit ? "checked" : ""}>Stop Ollama when I quit, only if Mac Deep Cleaner started it</label>
      <div class="feature-levels">${button("Save AI options", "ghost-save-options", {disabled:!!S.busy})}${button("Remove AI components", "ghost-remove", {disabled:!!S.busy || (!setup.models_pulled_by_mdc?.length && !setup.installed_by_mdc)})}</div>
      <p class="note">Turning Ghost Files off keeps installed AI components. Removal only offers components created by Mac Deep Cleaner.</p>${local()}${report ? progress(report.setup, "setup") : ""}</div>`;
  }

  function render() {
    if (!report) return empty("Looking for the local workspace…", error || "No files are changed by opening this page.", "ghost");
    const rawGhosts = report.ghosts.filter(g => !g.hidden);
    const safeCount = rawGhosts.filter(g => g.final_verdict === "likely_safe").length;
    const reviewCount = rawGhosts.filter(g => g.final_verdict === "review").length;
    const lockedCount = rawGhosts.filter(g => g.final_verdict === "keep").length;

    return `<div class="ghost-workspace">
      <header class="ghost-heading">
        <div>
          <h1>Some apps leave a little behind.</h1>
          <p>Ghost Files finds their traces. You decide what can rest.</p>
        </div>
        <div class="head-actions">
          ${button(report.scan.done ? "Find ghosts" : "Finding ghosts…", "ghost-scan", {symbol:"search", disabled:locked()})}
          ${button("Settings", "navigate", {data:{view:"settings"},symbol:"gear"})}
        </div>
      </header>
      ${banners()}
      ${error ? `<div class="error-banner" role="alert">${esc(error)}${button("Retry", "ghost-refresh")}</div>` : ""}
      
      <div id="ghostSummaryWrap" class="ghost-summary">
        ${renderSummaryHtml()}
      </div>

      <div id="ghostProgressWrap">
        ${renderProgressHtml()}
      </div>

      <div class="ghost-ai-banner">
        <div>
          ${local()}
          <p id="ghostAiDesc">${config?.level === 2 && status?.state === "READY" ? `Local model: ${esc(config.model)}. Model opinions can only make a verdict more cautious.` : "Showing plain descriptions. Add optional local AI narration."}</p>
        </div>
        <div id="ghostAiAction">
          ${button(config?.level === 2 && status?.state === "READY" ? "Narrate the rest" : "Set up AI narration", config?.level === 2 && status?.state === "READY" ? "ghost-haunt" : "ghost-setup", {disabled:locked()})}
        </div>
      </div>

      <div class="ghost-columns">
        <section class="ghost-list" aria-label="App leftovers">
          <div class="ghost-toolbar">
            <div class="ghost-search-wrap">
              <span class="search-icon">${icon("search")}</span>
              <input type="search" id="ghostSearch" class="ghost-search-input" placeholder="Search leftovers by name or path…" value="${esc(searchQuery)}" aria-label="Search leftovers">
            </div>
            <div class="ghost-filter-pills" role="radiogroup" aria-label="Filter by safety">
              <button type="button" class="filter-pill ${verdictFilter === "all" ? "active" : ""}" data-action="ghost-set-filter" data-filter="all">All (${rawGhosts.length})</button>
              <button type="button" class="filter-pill safe ${verdictFilter === "likely_safe" ? "active" : ""}" data-action="ghost-set-filter" data-filter="likely_safe">Safe (${safeCount})</button>
              <button type="button" class="filter-pill review ${verdictFilter === "review" ? "active" : ""}" data-action="ghost-set-filter" data-filter="review">Review (${reviewCount})</button>
              <button type="button" class="filter-pill locked ${verdictFilter === "keep" ? "active" : ""}" data-action="ghost-set-filter" data-filter="keep">Locked (${lockedCount})</button>
            </div>
            <div class="ghost-sort-wrap">
              <label for="ghostSort">Sort</label>
              <select id="ghostSort" class="ghost-sort-select" aria-label="Sort ghosts">
                <option value="size" ${sortBy === "size" ? "selected" : ""}>Largest size</option>
                <option value="name" ${sortBy === "name" ? "selected" : ""}>Name (A–Z)</option>
                <option value="age" ${sortBy === "age" ? "selected" : ""}>Oldest untouched</option>
              </select>
            </div>
          </div>

          <div id="ghostCardsContainer">
            ${renderCardsHtml()}
          </div>
        </section>

        <aside class="history-panel">
          <h2>Cleanup History</h2>
          <p>Recently removed leftovers moved to Trash.</p>
          <div id="ghostOfrendaWrap">
            ${renderHistoryHtml()}
          </div>
          ${button("Export history (.md)", "ghost-export", {symbol:"download"})}
        </aside>
      </div>

      <details class="ghost-limits">
        <summary>How these ghosts are found</summary>
        <p>A matching app was not found in the standard Applications folders. This does not prove the app is gone. Apps on external drives, shared folders, and background tools may still use this data. Name-only matches stay locked.</p>
        ${report.warnings.map(w => `<p>${esc(w)}</p>`).join("")}
      </details>
    </div>`;
  }

  function card(g) {
    const keep = g.final_verdict === "keep" && !g.unlocked;
    return `<article class="ghost-card" data-ghost-id="${g.id}" data-action="ghost-inspect" data-id="${g.id}">
      <div class="ghost-card-head">
        <span class="app-icon ghost-emblem" aria-hidden="true">
          <span>${icon("ghost")}</span>
          <img src="/api/ghosts/icon?id=${g.id}" alt="" loading="lazy" decoding="async" onerror="this.style.display='none'">
        </span>
        <div>
          <h2>${esc(g.name_guess)}</h2>
          <p>${esc(g.kind)} · ${g.age_days} days untouched</p>
        </div>
        <strong>${fmt(g.size_bytes)}</strong>
      </div>
      <p class="ghost-haunting">${esc(g.haunting)}</p>
      <div class="ghost-verdict ${g.final_verdict}">
        ${icon(keep ? "lock" : g.unlocked && g.final_verdict === "keep" ? "unlock" : "shield")}
        ${g.reason ? `<span>${esc(g.reason)}</span>` : ""}
      </div>
      <div class="ghost-card-actions">
        <div class="ghost-card-buttons">
          ${button("Inspect", "ghost-inspect", {symbol:"search", style:"ghost", data:{id:g.id}})}
          ${keep ? button("Review locked ghost", "ghost-unlock", {symbol:"lock", data:{id:g.id}, disabled:locked()}) : button("Banish to Trash", "ghost-banish", {symbol:"trash", style:"primary", data:{id:g.id}, disabled:locked()})}
          ${button("Let it rest", "ghost-hide", {style:"ghost", data:{id:g.id}, disabled:locked()})}
        </div>
        <span class="ghost-status-pill ${g.final_verdict}">${g.unlocked && g.final_verdict === "keep" ? "Unlocked for review" : labels[g.final_verdict]}</span>
      </div>
    </article>`;
  }

  let activeGhostDrawerId = null;

  async function openGhostDrawer(id, forceRefresh = false) {
    const g = report?.ghosts.find(x => x.id === id);
    if (!g) return;
    activeGhostDrawerId = id;
    detailKind = "ghost-inspect";

    const keep = g.final_verdict === "keep" && !g.unlocked;

    $("detailDialog").innerHTML = `
      <div class="drawer-head">
        <div class="ghost-drawer-title">
          <span class="app-icon ghost-emblem" aria-hidden="true">
            <span>${icon("ghost")}</span>
            <img src="/api/ghosts/icon?id=${g.id}" alt="" loading="lazy" decoding="async" onerror="this.style.display='none'">
          </span>
          <div>
            <h2>${esc(g.name_guess)}</h2>
            <small>${esc(g.kind)} · ${fmt(g.size_bytes)} · ${g.age_days} days untouched</small>
          </div>
        </div>
        ${button("", "close-detail", {symbol:"x",style:"ghost icon-only",aria:"Close inspector"})}
      </div>
      <div class="drawer-body ghost-inspect-drawer">
        <div id="ghostDrawerContent">
          <div class="ghost-loading-box">
            <span class="ghost-spinner"></span>
            <p>Analyzing ${esc(g.name_guess)} with web context and local files…</p>
          </div>
        </div>
      </div>
    `;

    Overlays.open($("detailDialog"));

    try {
      const data = await api(`/api/ghosts/explain?id=${id}${forceRefresh ? "&refresh=1" : ""}`);
      if (activeGhostDrawerId !== id) return;

      const contentEl = $("ghostDrawerContent");
      if (!contentEl) return;

      const fileRows = (data.files || []).map(f => `
        <div class="ghost-file-row">
          <span class="ghost-file-icon">${icon(f.is_dir ? "folder" : "file")}</span>
          <span class="ghost-file-name" title="${esc(f.name)}">${esc(f.name)}</span>
          <span class="ghost-file-size">${esc(f.size_fmt)}</span>
        </div>
      `).join("");

      contentEl.innerHTML = `
        <!-- Card 1: Safety Assessment -->
        <div class="ghost-drawer-card verdict-card ${g.final_verdict}">
          <div class="verdict-icon-wrap">
            ${icon(keep ? "lock" : g.unlocked && g.final_verdict === "keep" ? "unlock" : "shield")}
          </div>
          <div class="verdict-body">
            <div class="verdict-status">${g.unlocked && g.final_verdict === "keep" ? "Unlocked for review" : labels[g.final_verdict]}</div>
            <p class="verdict-desc">${esc(data.recommendation || g.reason)}</p>
          </div>
        </div>

        <!-- Card 2: About & Usage -->
        <div class="ghost-drawer-card">
          <div class="card-section">
            <span class="card-tag">About this application</span>
            <p class="card-text">${esc(data.summary)}</p>
          </div>
          <div class="card-divider"></div>
          <div class="card-section">
            <span class="card-tag">What it is used for & workflows</span>
            <p class="card-text">${esc(data.usage)}</p>
          </div>
        </div>

        <!-- Card 3: Leftover Contents & Files -->
        <div class="ghost-drawer-card">
          <div class="card-section">
            <span class="card-tag">Leftover Directory Contents</span>
            <p class="card-text">${esc(data.data_stored)}</p>
            <div class="ghost-path-bar">
              <code>${esc(data.path)}</code>
              ${button("Reveal", "ghost-reveal", {symbol:"folder", data:{id:g.id}, style:"ghost small"})}
            </div>
            ${data.files && data.files.length ? `
              <div class="ghost-files-list">
                <div class="ghost-files-head">Files inside folder (${data.files.length})</div>
                ${fileRows}
              </div>
            ` : ""}
          </div>
        </div>

        <!-- Card 4: Web Search Context -->
        <div class="ghost-drawer-card">
          <div class="card-section">
            <span class="card-tag">Web & GitHub search context</span>
            <div class="ghost-search-pills">
              <a href="${esc(data.search_links.google)}" target="_blank" rel="noopener" class="button ghost small search-pill">Google ↗</a>
              <a href="${esc(data.search_links.github)}" target="_blank" rel="noopener" class="button ghost small search-pill">GitHub ↗</a>
              <a href="${esc(data.search_links.duckduckgo)}" target="_blank" rel="noopener" class="button ghost small search-pill">DuckDuckGo ↗</a>
              ${button("Re-analyze ↻", "ghost-reanalyze", {data:{id:g.id}, style:"ghost small"})}
            </div>
            <p class="ghost-ai-source-badge">
              ${icon("sparkles")} Analysis source: ${esc(data.model || "local analysis")}
            </p>
          </div>
        </div>

        <div class="ghost-inspect-actions">
          ${keep ? button("Review locked ghost", "ghost-unlock", {symbol:"lock", data:{id:g.id}, disabled:locked()}) : button("Banish to Trash", "ghost-banish", {symbol:"trash", style:"primary", data:{id:g.id}, disabled:locked()})}
          ${button("Reveal in Finder", "ghost-reveal", {style:"ghost", data:{id:g.id}})}
          ${button("Let it rest", "ghost-hide", {style:"ghost", data:{id:g.id}, disabled:locked()})}
        </div>
      `;
    } catch(err) {
      const contentEl = $("ghostDrawerContent");
      if (contentEl) {
        contentEl.innerHTML = `<p class="review-warning">Could not inspect: ${esc(err.message)}</p>`;
      }
    }
  }

  async function setup() {
    if (config?.level !== 2) {
      config = await api("/api/ghosts/config", {level:2});
      S.features.ghosts_level = 2;
    }
    status = await api("/api/ghosts/setup/status");
    setupModel = config?.setup.model_selected ? config.model : status.recommended_model;
    setupDrawer();
    if (setupPolling) pollSetup();
  }

  function setupDrawer() {
    detailKind = "ghost-setup";
    const model = status.catalog.find(m => m.id === setupModel);
    const needInstall = status.state === "NOT_INSTALLED", needStart = ["NOT_INSTALLED","INSTALLED_NOT_RUNNING"].includes(status.state), needPull = !status.models.includes(setupModel);
    $("detailDialog").innerHTML = `<div class="drawer-head"><div><h2>Invite a local storyteller</h2><small>Optional AI, entirely on your Mac</small></div>${button("", "close-detail", {symbol:"x",style:"ghost icon-only",aria:"Close AI setup"})}</div><div class="drawer-body ghost-setup"><p>Ollama runs an open-weight model locally. Narration sends no file paths or usernames. Setup downloads the app and model to your Mac once.</p>
      <div class="ghost-detected"><strong>${status.state === "READY" ? "Ollama and your model are ready" : status.state === "NOT_INSTALLED" ? "Ollama is not installed" : status.state === "INSTALLED_NOT_RUNNING" ? "Ollama is installed and stopped" : "Ollama is running; choose a model"}</strong><p>${status.ram_gb || "Unknown"} GB RAM · ${status.free_gb} GB available</p><p>Recommended: ${esc(status.recommended_model)}</p></div>
      <label class="ghost-model-label">Narration model<select id="ghostModel" aria-label="Narration model">${status.catalog.map(m => `<option value="${m.id}" ${m.id === setupModel ? "selected" : ""}>${m.label}: ${m.id} (about ${m.approx_gb} GB)</option>`).join("")}</select></label>
      <p class="ghost-download-size">${needPull ? `About ${model.approx_gb} GB to download. At least ${(model.approx_gb * 1.5 + 1).toFixed(1)} GB free required, including working space.` : "This model is already downloaded. It will be reused."}${needInstall ? " Ollama itself is an additional download." : ""}</p>
      ${status.ram_gb < model.min_ram_gb ? '<p class="review-warning">This model may be slow or need more memory than your Mac has. Choose Light or use Ghosts without AI.</p>' : ""}
      <fieldset class="ghost-consents"><legend>Choose each step you allow</legend>
      ${needInstall ? `<label class="check-label"><input id="ghostInstall" type="checkbox">Install Ollama ${status.install_method === "brew" ? "using Homebrew" : "from the official download into ~/Applications"}</label>` : '<p>Existing Ollama installation will be reused.</p>'}
      ${needStart ? '<label class="check-label"><input id="ghostStart" type="checkbox">Start Ollama on this Mac when Ghost Files needs it</label>' : '<p>The running Ollama server will be reused. Only a server started by this Mac Deep Cleaner session can be stopped.</p>'}
      ${needPull ? `<label class="check-label"><input id="ghostPull" type="checkbox">Download ${esc(setupModel)} (about ${model.approx_gb} GB)</label>` : '<p>Your existing model will be reused and will not be marked as installed by us.</p>'}</fieldset>
      <div id="ghostSetupProgress" aria-live="polite"></div><div class="feature-levels">${button("Run approved steps", "ghost-run-setup", {style:"primary", disabled:setupPolling || status.port_conflict || (needPull && status.free_gb < model.approx_gb * 1.5 + 1)})}${button("Stay with no AI", "ghost-no-ai", {disabled:setupPolling})}</div>${local()}</div>`;
    Overlays.open($("detailDialog"));
    window.Dropdowns?.enhance($("detailDialog"));
    $("ghostModel")?.addEventListener("change", e => { setupModel = e.target.value; setupDrawer(); });
  }

  async function pollSetup() {
    clearTimeout(setupTimer);
    try {
      const result = await api("/api/ghosts/setup/progress");
      setupPolling = !result.done;
      if ($("ghostSetupProgress")) {
        $("ghostSetupProgress").innerHTML = progress(result,"setup") + (result.sample ? `<blockquote>${esc(result.sample)}</blockquote><p>Self-test passed. Your local storyteller is ready.</p>` : "") + (result.done && !result.error && !result.cancelled ? '<p>Completed.</p>' : "");
        $("detailDialog").querySelectorAll('[data-action="ghost-run-setup"], [data-action="ghost-no-ai"], #ghostModel, #ghostModelControl').forEach(e => e.disabled = setupPolling);
      }
      if (setupPolling) setupTimer = setTimeout(pollSetup, 700);
      else { await enter(true); }
    } catch(e) {
      toast(e.message, true);
      setupPolling = false;
    }
  }

  async function dispatch(action, el) {
    const id = Number(el?.dataset.id), g = report?.ghosts.find(x => x.id === id);

    if (action === "ghost-refresh") return enter(true);
    if (action === "ghost-setup") return setup();
    if (action === "ghost-scan") { await api("/api/ghosts/scan", {}); wasScanning = true; return enter(true); }
    if (action === "ghost-haunt") { await api("/api/ghosts/haunt", {rest:true}); return enter(true); }
    if (action === "ghost-cancel") { await api(`/api/ghosts/${el.dataset.kind}/cancel`, {}); return enter(true); }
    if (action === "ghost-save-options") {
      config = await api("/api/ghosts/config", {auto_start_ollama:$("ghostAuto").checked, stop_ollama_on_exit:$("ghostStop").checked});
      toast("AI options saved.");
      return;
    }
    if (action === "ghost-run-setup") {
      await api("/api/ghosts/setup/run", {model:setupModel, install_method:status.install_method, consent:{install:!!$("ghostInstall")?.checked, start:!!$("ghostStart")?.checked, pull:!!$("ghostPull")?.checked}});
      setupPolling = true;
      return pollSetup();
    }
    if (action === "ghost-no-ai") { closeDetail(); return setGhostLevel(1); }
    if (action === "ghost-show-hidden") { await api("/api/ghosts/show-hidden", {}); return enter(true); }

    if (action === "ghost-remove") {
      config = await api("/api/ghosts/config");
      const owned = config.setup;
      const models = owned.models_pulled_by_mdc || [];
      const canUninstall = ["brew", "app"].includes(owned.installed_by_mdc);
      const answer = await ask({
        title:"Remove AI components?",
        confirm:"Remove selected components",
        danger:true,
        body:`<p>Select the components installed by Mac Deep Cleaner to remove. Other models and the shared Ollama data folder are kept.</p>
          ${models.map((model, index) => `<label class="check-label"><input id="ghostRemove${index}" type="checkbox">Remove ${esc(model)}</label>`).join("")}
          ${canUninstall ? '<label class="check-label"><input id="ghostUninstall" type="checkbox">Uninstall Ollama installed by Mac Deep Cleaner</label>' : ""}`
      });
      if (!answer.confirmed) return;
      const selectedModels = models.filter((_, index) => $(`ghostRemove${index}`)?.checked);
      const uninstall = canUninstall && !!$("ghostUninstall")?.checked;
      if (!selectedModels.length && !uninstall) return toast("Select a component to remove.", true);
      await api("/api/ghosts/remove-ai", {models:selectedModels, uninstall, confirmed:true});
      return enter(true);
    }

    if (action === "ghost-export") {
      const data = await api("/api/ghosts/ofrenda");
      const blob = new Blob([data.markdown], {type:"text/markdown;charset=utf-8"});
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "cleanup-history.md";
      a.click();
      URL.revokeObjectURL(a.href);
      return;
    }
    if (action === "ghost-inspect") return openGhostDrawer(id);
    if (action === "ghost-reanalyze") return openGhostDrawer(id, true);

    // Pagination and filter actions
    if (action === "ghost-page") {
      page = Number(el.dataset.page) || 1;
      updateCards();
      document.querySelector(".ghost-list")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (action === "ghost-set-filter") {
      verdictFilter = el.dataset.filter || "all";
      page = 1;
      document.querySelectorAll(".ghost-filter-pills .filter-pill").forEach(p => {
        p.classList.toggle("active", p.dataset.filter === verdictFilter);
      });
      return updateCards();
    }

    if (action === "ghost-banish-page-safe") {
      const v = version();
      const rawGhosts = report.ghosts.filter(g => !g.hidden);
      let list = rawGhosts.slice();
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        list = list.filter(g =>
          (g.name_guess && g.name_guess.toLowerCase().includes(q)) ||
          (g.path && g.path.toLowerCase().includes(q)) ||
          (g.bundle_id && g.bundle_id.toLowerCase().includes(q)) ||
          (g.kind && g.kind.toLowerCase().includes(q))
        );
      }
      if (verdictFilter !== "all") {
        list = list.filter(g => g.final_verdict === verdictFilter);
      }
      const startIdx = (page - 1) * PAGE_SIZE;
      const pageItems = list.slice(startIdx, startIdx + PAGE_SIZE);
      const toBanish = pageItems.filter(g => g.final_verdict === "likely_safe");
      if (!toBanish.length) return;
      const ids = toBanish.map(g => g.id);
      const totalBytes = toBanish.reduce((sum, g) => sum + g.size_bytes, 0);
      const answer = await ask({
        title: `Banish ${toBanish.length} safe items to Trash?`,
        confirm: "Banish all to Trash",
        danger: false,
        body: `<p>These ${toBanish.length} leftovers (${fmt(totalBytes)}) are regenerable caches and logs.</p><p>They will be moved to the Trash where you can restore them anytime before emptying.</p>`
      });
      if (!answer.confirmed) return;
      busy = true; updateCards();
      try {
        const result = await api("/api/clean", {
          ...v,
          ids,
          ack: true,
          permanent: false,
          ghost_review_confirmed: true,
          ghost_reviewed_ids: ids
        });
        if (result.fails.length) toast(result.fails.map(f => f.join(": ")).join("; "), true);
        else toast(`Moved ${ids.length} items to Trash.`);
        if (result.warning) toast(result.warning, true);
      } finally {
        busy = false;
        await enter(true);
      }
      return;
    }

    if (!g) return;
    if (action === "ghost-reveal") return revealPath(g.path);
    if (action === "ghost-hide") { await api("/api/ghosts/hide", {...version(), id}); return enter(true); }
    if (action === "ghost-unlock") {
      const v = version();
      const answer = await ask({
        title:"Review this locked ghost",
        confirm:"Unlock for review",
        danger:true,
        phrase:"UNLOCK",
        body:`<p><strong>${esc(g.name_guess)}</strong></p><p class="ghost-path">${esc(g.path)}</p><p>${esc(g.reason)}</p><p>This may contain documents or data used by another app. Unlocking only allows a separate Trash review.</p>`
      });
      if (answer.confirmed) {
        await api("/api/ghosts/unlock", {...v, id, confirmed:true});
        return enter(true);
      }
      return;
    }
    if (action === "ghost-banish") {
      const v = version();
      const answer = await ask({
        title:"A final farewell?",
        confirm:"Banish to Trash",
        danger:g.final_verdict !== "likely_safe",
        body:`<div class="review-total"><strong>${esc(g.name_guess)}</strong><b>${fmt(g.size_bytes)}</b></div><p class="ghost-path">${esc(g.path)}</p><p>${esc(g.reason)}</p><p>Move this reviewed leftover to the Trash. You can restore it in Finder until you empty the Trash.</p>`
      });
      if (!answer.confirmed) return;
      busy = true; updateCards();
      try {
        const result = await api("/api/clean", {
          ...v,
          ids:[id],
          ack:true,
          permanent:false,
          ghost_review_confirmed:true,
          ghost_reviewed_ids:[id]
        });
        if (result.fails.length) toast(result.fails.map(f => f.join(": ")).join("; "), true);
        else toast("Moved to Trash. Recorded in cleanup history.");
        if (result.warning) toast(result.warning, true);
      } finally {
        busy = false;
        await enter(true);
      }
    }
  }

  // Click on card opens the research & inspection drawer
  document.addEventListener("click", (e) => {
    const cardEl = e.target.closest(".ghost-card");
    if (cardEl && !e.target.closest("button, a, input, select, details")) {
      const id = Number(cardEl.dataset.ghostId);
      if (id) openGhostDrawer(id);
    }
  });

  // Bind input listeners for search & sort
  document.addEventListener("input", (e) => {
    if (e.target && e.target.id === "ghostSearch") {
      searchQuery = e.target.value;
      page = 1;
      updateCards();
    }
  });

  document.addEventListener("change", (e) => {
    if (e.target && e.target.id === "ghostSort") {
      sortBy = e.target.value;
      page = 1;
      updateCards();
    }
  });

  return { enter, leave, render, settings, setup, dispatch, isRunning: () => running() || setupPolling };
})();
