"use strict";
const HomebrewUI = (() => {
  let report = null, loading = false, message = "", tab = "overview", query = "", filter = "all", limit = 80;
  const tabs = [["overview", "Packages"], ["groups", "Dependency groups"], ["heaviest", "Heaviest"], ["updates", "Updates"], ["tidy", "Tidy"], ["services", "Services"]];
  const busyNow = () => ToolkitUI.locked();
  const packageButton = (p, text = p.full_name) => `<button class="brew-package-link" data-action="brew-inspect" data-package="${esc(p.id)}">${esc(text)}</button>`;
  const action = (label, name, target = "", danger = false, disabled = false) => button(label, "brew-plan", {style:danger ? "danger" : "", data:{tool:name, package:target}, disabled: disabled || busyNow()});
  function byId(id) { return report?.packages.find(p => p.id === id); }
  async function refresh(force = true) {
    if (loading) return;
    loading = true; message = ""; if (view === "homebrew") draw();
    try { report = await api(force ? "/api/brew/refresh" : "/api/brew", force ? {} : undefined); }
    catch (e) { message = e.message; }
    finally { loading = false; if (view === "homebrew") draw(); }
  }
  function enter() { if (!report && !loading) refresh(false); ToolkitUI.enter("homebrew"); }
  function row(p) {
    return `<div class="brew-package-row"><div>${packageButton(p)}<p>${esc(p.description || p.kind)}</p><div class="brew-badges"><span>${esc(p.group)}</span>${p.pinned ? '<span class="brew-pin">Pinned</span>' : ""}${p.shared ? `<span>Shared by ${p.roots.length} roots</span>` : ""}${p.disabled ? '<span class="brew-warning">Disabled upstream</span>' : p.deprecated ? '<span class="brew-warning">Deprecated</span>' : ""}</div></div><div class="brew-version">${esc(p.versions.join(", "))}${p.outdated ? `<small>Update: ${esc(p.latest)}</small>` : ""}</div><div class="brew-size">${p.size === null ? "Unknown" : fmt(p.size)}<small>${esc(p.size_scope)}</small></div>${button("Why installed?", "brew-inspect", {style:"link", data:{package:p.id}})}</div>`;
  }
  function list(packages) {
    return packages.length ? `<div class="brew-package-list">${packages.slice(0,limit).map(row).join("")}</div><div class="list-footer"><span>${Math.min(limit,packages.length)} of ${packages.length} packages</span>${packages.length > limit ? button("Show more", "brew-more", {style:"link"}) : ""}</div>` : empty("No matching packages", "Try another search or filter, or refresh after changing Homebrew.", "search");
  }
  function render() {
    let html = `<div class="pagehead"><div><h1>Homebrew</h1><p>Know why it’s installed. Keep the packages you need.</p></div><div class="head-actions">${button(loading ? "Reading Homebrew…" : "Refresh", "brew-refresh", {symbol:"refresh", disabled:loading || busyNow()})}</div></div>`;
    if (message) html += `<div class="error-banner" role="alert">${icon("alert")}<span>${esc(message)}</span></div>`;
    if (!report) return html + empty(loading ? "Reading your Homebrew environment…" : "Homebrew inventory unavailable", "Collecting installed packages, dependency receipts, sizes, and service status. Large installations can take a minute.", "code", "", {scanning:loading});
    if (!report.available) return html + empty("Homebrew is not installed", report.message, "code", '<a class="button" href="https://brew.sh" target="_blank" rel="noopener noreferrer">Homebrew installation guide</a>');
    const stats = report.stats;
    html += `<div class="brew-environment"><span>${icon("code")}<strong>${esc(report.prefix)}</strong></span><span>${stats.formulae} formulae</span><span>${stats.casks} casks</span><span>${fmt(stats.size)} measured</span><span>Checked ${new Date(report.checked_at*1000).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}</span></div><div class="brew-nav" role="navigation" aria-label="Homebrew views">${tabs.map(([id,label]) => `<button data-action="brew-tab" data-tab="${id}" class="${tab===id ? "active" : ""}" aria-pressed="${tab===id}">${label}${id === "updates" ? ` <span>${report.update_status ? stats.outdated : "?"}</span>` : id === "tidy" ? ` <span>${stats.orphans}</span>` : ""}</button>`).join("")}</div>`;
    if (report.warnings.length) html += `<details class="tool-warning"><summary>${report.warnings.length} inventory notes${!report.removal_checks ? " · package removal disabled" : ""}</summary><ul>${report.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul></details>`;
    if (tab === "tidy") {
      const orphans = report.packages.filter(p => p.orphan);
      html += `<div class="brew-tidy-intro"><h2>A smaller environment, with a review at each step</h2><p>Homebrew’s dry run found ${orphans.length} unused ${orphans.length === 1 ? "dependency" : "dependencies"}${stats.orphan_size ? `, measuring ${fmt(stats.orphan_size)}` : ""}. Scripts and apps outside Homebrew may still use these packages.</p></div><section class="brew-tidy-step"><div><span class="brew-step">1</span><h3>Review unused dependencies</h3><p>Pinned packages, registered services, and packages needed by retained dependencies stay installed. Mark any package you use as “Keep”.</p></div>${action("Review removal", "tidy", "", true, !orphans.length || !report.removal_checks)}</section>${orphans.length ? list(orphans) : '<p class="brew-empty-note">No eligible unused dependencies were found.</p>'}<section class="brew-tidy-step"><div><span class="brew-step">2</span><h3>Review caches and old versions</h3><p>See Homebrew’s cleanup preview before permanently removing old downloads and package versions. This step does not autoremove dependencies.</p></div>${action("Preview cleanup", "cleanup")}</section>`;
    } else if (tab === "services") {
      html += `<p class="brew-section-note">Services for your current user. Starting a service registers it at login; stopping unregisters it. System-wide services require separate administrator management.</p><div class="brew-service-list">${report.packages.filter(p => p.has_service).map(p => `<div class="brew-service-row"><div>${packageButton(p)}<small>${esc(p.service)}</small></div><div>${action("Start", "service-start", p.id)}${action("Stop", "service-stop", p.id)}${action("Restart", "service-restart", p.id)}</div></div>`).join("") || empty("No services found", "Installed packages with Homebrew service definitions will appear here.", "gear")}</div>`;
    } else {
      html += `<div class="brew-toolbar">${searchField("brewSearch", query, "Search packages, descriptions or taps")}${tab === "overview" ? `<select id="brewGroup" aria-label="Package group"><option value="all">All packages</option>${report.groups.map(g => `<option value="${esc(g)}" ${g === filter ? "selected" : ""}>${esc(g)}</option>`).join("")}<option value="shared" ${filter === "shared" ? "selected" : ""}>Shared dependencies</option><option value="pinned" ${filter === "pinned" ? "selected" : ""}>Pinned formulae</option></select>` : ""}</div>`;
      const matches = p => `${p.full_name} ${p.description} ${p.tap}`.toLowerCase().includes(query.toLowerCase());
      let packages = report.packages.filter(matches);
      if (tab === "groups") {
        const roots = report.packages.filter(p => p.requested !== false || p.pinned || !['not registered','none','stopped','unloaded'].includes(p.service));
        html += '<p class="brew-section-note">Each group starts with a requested or protected package. Shared dependencies can appear in several groups; the environment total counts each package once.</p><div class="brew-groups">';
        for (const root of roots) {
          const members = report.packages.filter(p => p.roots.includes(root.id));
          if (!matches(root) && !members.some(matches)) continue;
          html += `<details class="brew-dependency-group"><summary><span>${icon(root.kind === "cask" ? "apps" : "code")}<strong>${esc(root.full_name)}</strong><small>${esc(root.kind)}</small></span><span>${members.length} dependencies</span></summary><div class="brew-group-body"><div class="brew-group-root">${packageButton(root, "Why " + root.full_name + " is installed")}</div>${members.length ? members.map(p => `<div class="brew-group-member">${packageButton(p)}<span>${p.shared ? `Shared by ${p.roots.length} roots` : "Used by this root"}</span></div>`).join("") : '<p>No installed runtime dependencies recorded.</p>'}</div></details>`;
        }
        html += '</div>';
      } else {
        if (tab === "heaviest") {
          packages = packages.filter(p => p.kind === "formula").sort((a,b) => (b.size||0)-(a.size||0));
          html += '<p class="brew-section-note">Formulae ranked by allocated Cellar size, including old installed versions. Cask applications moved outside Caskroom are excluded.</p>';
        } else if (tab === "updates") {
          packages = packages.filter(p => p.outdated);
          html += `<div class="brew-update-note"><p>${report.update_status ? "Available updates from local Homebrew metadata. This is not a vulnerability scan. Self-updating and latest-version casks follow Homebrew’s normal update rules." : "Update status is incomplete. Refresh metadata, then retry the inventory."}</p>${action("Update metadata", "update")}</div>`;
        } else {
          packages = packages.filter(p => filter === "all" || filter === "shared" && p.shared || filter === "pinned" && p.pinned || p.group === filter).sort((a,b) => a.full_name.localeCompare(b.full_name));
        }
        html += list(packages);
      }
    }
    html += `<div class="brew-footer"><div>${action("Run brew doctor", "doctor")}${button("Export Brewfile", "brew-export", {symbol:"download", data:{format:"brewfile"}})}${button("Export JSON", "brew-export", {symbol:"download", data:{format:"json"}})}</div><p>Commands run under your account. Homebrew may fetch package metadata over the network. ${stats.unmeasured ? `${stats.unmeasured} package sizes are unavailable. ` : ""}Caskroom measurements exclude app bundles moved elsewhere.</p></div>`;
    return html + ToolkitUI.history();
  }
  async function inspect(id) {
    const data = await api('/api/brew/explain?package=' + encodeURIComponent(id));
    const p = data.package, displayNames = ids => ids.map(key => byId(key) ? packageButton(byId(key)) : esc(key)).join("");
    detailKind = "homebrew";
    $("detailDialog").innerHTML = `<div class="drawer-head"><span class="file-icon">${icon(p.kind === "cask" ? "apps" : "code")}</span><div><h2>${esc(p.full_name)}</h2><small>${esc(p.kind)} · ${esc(p.tap)}</small></div>${button("", "close-detail", {style:"ghost icon-only", symbol:"x", aria:"Close package details"})}</div><div class="drawer-body"><p>${esc(p.description)}</p><div class="brew-explanation"><h3>Why it’s installed</h3><p>${p.requested === true ? p.kind === "cask" ? "Casks are retained as top-level applications." : "Homebrew records this as intentionally installed." : p.requested === null ? "The installation receipt does not say why it was installed. It is retained for review." : p.orphan ? "Homebrew lists this as an unused dependency. External scripts or apps may still use it." : "This formula was installed as a dependency."}${p.pinned ? " It is pinned against upgrades." : ""}</p>${p.roots.length ? `<h4>Needed by these roots</h4><div class="brew-dependency-links">${displayNames(p.roots)}</div>` : ""}</div><dl class="facts"><div><dt>Installed</dt><dd>${esc(p.versions.join(", "))}</dd></div><div><dt>Measured size</dt><dd>${p.size === null ? "Unknown" : fmt(p.size)} · ${esc(p.size_scope)}</dd></div><div><dt>Update</dt><dd>${p.outdated ? esc(p.latest) : "No update reported"}</dd></div><div><dt>Service</dt><dd>${esc(p.service)}</dd></div></dl><div class="brew-package-actions">${action("Upgrade", "upgrade", p.id, false, !p.outdated || p.pinned || !report.update_status)}${p.kind === "formula" ? action(p.pinned ? "Unpin" : "Pin", p.pinned ? "unpin" : "pin", p.id) + action(p.requested === true ? "Mark as dependency" : "Keep", p.requested === true ? "mark-dependency" : "keep", p.id) : ""}${action("Uninstall", "uninstall", p.id, true, !report.removal_checks || p.pinned || p.runtime_required_by.length > 0 || !['not registered','none','stopped','unloaded'].includes(p.service))}</div>${p.runtime_required_by.length ? '<p class="note">Uninstall is blocked while installed packages depend on this package.</p>' : ""}<section class="inspect-section"><h3>Direct installed dependencies (${p.dependencies.length})</h3><div class="brew-dependency-links">${displayNames(p.dependencies) || '<p>None recorded.</p>'}</div></section><section class="inspect-section"><h3>Reverse dependency tree</h3><p class="note">Each indented package depends on the one above it. Repeated branches are collapsed.</p><div class="brew-reverse-tree">${data.tree.rows.map(r => `<div style="--tree-depth:${Math.min(r.depth,8)}">${r.depth ? '<span aria-hidden="true">↳</span>' : ''}${byId(r.id) ? packageButton(byId(r.id)) : esc(r.name)}${r.cycle ? '<small>Cycle</small>' : r.repeated ? '<small>Shown above</small>' : ''}</div>`).join("")}</div>${data.tree.truncated ? '<p class="note">Showing the first 250 nodes. Export JSON to inspect the complete graph.</p>' : ""}</section></div>`;
    Overlays.open($("detailDialog"));
  }
  async function dispatch(name, el) {
    if (name === 'brew-refresh') return refresh();
    if (name === 'brew-tab') { tab = el.dataset.tab; query = ""; filter = "all"; limit = 80; return draw(); }
    if (name === 'brew-more') { limit += 80; return draw(); }
    if (name === 'brew-inspect') return inspect(el.dataset.package);
    if (name === 'brew-plan') return ToolkitUI.prepare('brew', {action:el.dataset.tool, target:el.dataset.package});
    if (name === 'brew-export') {
      const isJSON = el.dataset.format === 'json';
      const contents = isJSON ? JSON.stringify(report,null,2) : (await api('/api/brew/export')).brewfile;
      const url = URL.createObjectURL(new Blob([contents],{type:isJSON ? 'application/json' : 'application/octet-stream'}));
      const link = document.createElement('a'); link.href = url; link.download = isJSON ? 'homebrew-report.json' : 'Brewfile'; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
  }
  document.addEventListener('input', event => { if (event.target.id === 'brewSearch') { query = event.target.value; limit=80; draw(); } });
  document.addEventListener('change', event => { if (event.target.id === 'brewGroup') { filter = event.target.value; limit=80; draw(); } });
  document.addEventListener('mdc-job-finished', event => {
    if (event.detail.kind === 'brew') { report = null; if (view === 'homebrew') refresh(); }
  });
  return {render, enter, dispatch};
})();
