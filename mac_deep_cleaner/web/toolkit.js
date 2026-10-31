"use strict";

// The storage map is the focal point; maintenance uses quiet, scannable rows.
const ToolkitUI = (() => {
  let health = null, disks = null, healthError = "", disksError = "";
  let healthLoading = false, disksLoading = false, selectedDisk = "", showSystemDisks = false;
  let jobs = [], jobsTimer, jobsLoading = false, preparing = false;
  let submissionPending = false, statusUncertain = false;
  const isRunning = () => submissionPending || statusUncertain || jobs.some(j => j.status === "running");
  const labels = {"verify-volume": "Verify filesystem", "verify-disk": "Verify partition map",
    mount: "Mount", unmount: "Unmount", eject: "Eject", rename: "Rename",
    "add-volume": "Add APFS volume", erase: "Erase disk", partition: "Partition disk"};
  const isTools = () => ["optimize", "disks", "homebrew"].includes(view);
  const locked = () => busy || S.busy || preparing || isRunning();
  const head = (title, description, kind, loading) => `<div class="pagehead"><div><h1>${title}</h1><p>${description}</p></div><div class="head-actions">${button(loading ? "Checking…" : "Refresh", "toolkit-refresh", {symbol: "refresh", disabled: loading || locked(), data: {kind}})}</div></div>`;
  const error = (message) => message ? `<div class="error-banner" role="alert">${icon("alert")}<span>${esc(message)}</span></div>` : "";
  const shortcut = (title, action, symbol = "arrow") => button(title, "toolkit-open", {symbol, data: {tool: action}, disabled: health?.supported === false});
  const stamp = value => value ? `Checked ${new Date(value * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})}` : "";

  async function refresh(kind) {
    if (kind === "optimize") {
      if (healthLoading) return;
      healthLoading = true; healthError = ""; if (isTools()) draw();
      try { health = await api("/api/health"); } catch (e) { healthError = e.message; }
      finally { healthLoading = false; }
    } else {
      if (disksLoading) return;
      disksLoading = true; disksError = ""; if (isTools()) draw();
      try {
        disks = await api("/api/disks");
        if (!disks.devices.some(d => d.id === selectedDisk)) selectedDisk = disks.startup_id || disks.devices[0]?.id || "";
      } catch (e) { disksError = e.message; }
      finally { disksLoading = false; }
    }
    if (isTools()) draw();
  }
  async function loadJobs() {
    if (jobsLoading) return;
    jobsLoading = true;
    clearTimeout(jobsTimer);
    try {
      const next = (await api("/api/jobs")).jobs;
      statusUncertain = false;
      const finished = next.filter(j => j.status !== "running" && jobs.some(p => p.id === j.id && p.status === "running"));
      const changed = JSON.stringify(jobs) !== JSON.stringify(next);
      jobs = next;
      for (const j of finished) {
        document.dispatchEvent(new CustomEvent("mdc-job-finished", {detail:j}));
        toast(`${j.title}: ${j.status === "succeeded" ? "completed" : "failed — view operation results"}.`, j.status === "failed");
        if (j.kind === "disk" && view === "disks") refresh("disks");
      }
      if (changed && isTools()) draw();
    } catch (e) {
      if (isTools()) toast(`Cannot read operation status: ${e.message}`, true);
    } finally {
      jobsLoading = false;
      if (isTools() || isRunning()) jobsTimer = setTimeout(loadJobs, jobs.some(j => j.status === "running") ? 1500 : 8000);
    }
  }
  function enter(kind) {
    if (kind === "optimize" && !health && !healthLoading) refresh(kind);
    if (kind === "disks" && !disks && !disksLoading) refresh(kind);
    loadJobs();
  }
  function history() {
    if (!jobs.length) return "";
    return `<section class="tool-history" aria-label="Operation results"><div class="section-title"><h2>Operation results</h2><span class="muted">This session</span></div>${jobs.slice(-5).reverse().map(j => `<details class="job-result" ${j.status === "failed" ? "open" : ""}><summary><span>${icon(j.status === "running" ? "refresh" : j.status === "failed" ? "alert" : "check")}${esc(j.title)}</span><span class="job-status ${j.status}">${j.status === "running" ? "Running…" : j.status === "succeeded" ? "Completed" : "Failed"}</span></summary>${j.status === "running" ? '<p role="status">Keep Mac Deep Cleaner open. Some operations take several minutes. Check for a macOS permission dialog.</p>' : ""}<pre>${esc(j.error || j.output || "Waiting for command output…")}</pre></details>`).join("")}</section>`;
  }
  function optimizeView() {
    let html = head("Optimize your Mac", "Understand what needs attention. Choose a task and review every change.", "optimize", healthLoading) + error(healthError);
    if (!health) return html + empty(healthLoading ? "Checking your Mac…" : "Health check unavailable", "Refresh to read memory, storage, battery, and process activity.", "monitor", "", {scanning: healthLoading});
    const h = health, low = h.disk.free / h.disk.total < 0.15;
    html += `<section class="health-overview"><div class="health-heading"><span class="health-emblem">${icon("monitor")}</span><div><h2>Your Mac, at a glance</h2><p>macOS ${esc(h.os || "unavailable")} · ${stamp(h.checked_at)}</p></div>${button("Export report", "toolkit-export", {symbol: "download"})}</div><div class="health-metrics">${metric("Memory pressure", h.pressure, `${h.memory_total ? fmt(h.memory_total) + " installed" : "Memory size unavailable"} · ${h.swap} swap used`)}${metric("Storage available", fmt(h.disk.free), `${fmt(h.disk.total)} total capacity`)}${metric("Background definitions", h.launch_agents.length, "Launch agents and daemons; not a running count")}</div><p class="health-footnote">${icon("shield")}macOS manages memory automatically. These tools diagnose issues and perform specific maintenance; they do not promise a speed boost.</p></section>`;
    html += `<section class="tool-section"><div class="section-title"><h2>Start here</h2></div><div class="recommendation"><div>${icon(low ? "alert" : "disk")}<div><h3>${low ? "Your startup storage is getting full" : "Keep room for your next project"}</h3><p>Review caches, downloads, and large files before removing them.</p></div></div>${button("Review storage", "navigate", {data:{view:"clean"}})}</div><div class="recommendation"><div>${icon(h.pressure === "High" || h.pressure === "Elevated" ? "alert" : "apps")}<div><h3>${h.pressure === "Normal" ? "Memory pressure is normal" : "Check apps using memory"}</h3><p>Inspect CPU and memory use, then quit apps you no longer need.</p></div></div>${shortcut("Activity Monitor", "activity-monitor")}</div><div class="recommendation"><div>${icon("gear")}<div><h3>Choose what starts with your Mac</h3><p>Review login items and background activity in System Settings.</p></div></div>${shortcut("Manage login items", "login-items")}</div></section>`;
    for (const group of ["Everyday maintenance", "Developer tools"]) {
      html += `<section class="tool-section"><div class="section-title"><h2>${group}</h2>${group === "Developer tools" ? button("Review developer files", "toolkit-dev-files", {style:"link"}) : ""}</div><div class="maintenance-list">${h.tools.filter(t => t.group === group).map(t => `<article class="maintenance-row"><span class="tool-symbol">${icon(group === "Developer tools" ? "code" : "cache")}</span><div><h3>${esc(t.title)}</h3><p>${esc(t.description)}</p>${!t.available ? `<small>Requires ${esc(t.requirement)}</small>` : ""}</div>${button(t.changes ? "Review task" : "Run check", "toolkit-plan", {data: {tool: t.id}, disabled: !t.available || locked()})}</article>`).join("")}</div></section>`;
    }
    html += `<div class="diagnostic-columns"><section class="tool-section"><div class="section-title"><h2>Processes using CPU</h2></div><p class="muted">Sampled at refresh. CPU can exceed 100% across multiple cores.</p><div class="process-table"><div class="process-row process-head"><span>Process</span><span>CPU</span><span>Memory</span></div>${h.processes.map(p => `<div class="process-row"><span title="PID ${p.pid}">${esc(p.name)}<small>PID ${p.pid}</small></span><span>${p.cpu.toFixed(1)}%</span><span>${fmt(p.memory)}</span></div>`).join("") || '<p>No process data available.</p>'}</div></section><section class="tool-section"><div class="section-title"><h2>System details</h2></div><dl class="system-details"><dt>Battery and power</dt><dd>${esc(h.battery)}</dd><dt>Uptime and load</dt><dd>${esc(h.uptime || "Unavailable")}</dd><dt>Spotlight</dt><dd>${esc(h.spotlight || "Unavailable")}</dd></dl><details class="agent-details"><summary>Background definitions (${h.launch_agents.length})</summary><p>These files define background tasks. Presence does not mean a task is enabled or running.</p><ul>${h.launch_agents.map(a => `<li>${esc(a.name)}<small>${esc(a.location)}</small></li>`).join("") || '<li>No definitions found.</li>'}</ul></details></section></div>`;
    html += `<section class="tool-section"><div class="section-title"><h2>macOS controls</h2></div><div class="system-shortcuts">${h.shortcuts.filter(s => !["login-items", "activity-monitor"].includes(s.id)).map(s => shortcut(s.title, s.id)).join("")}</div></section>`;
    if (h.warnings.length) html += `<details class="tool-warning"><summary>Some checks were unavailable</summary><ul>${h.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul></details>`;
    return html + history();
  }
  function diskView() {
    let html = head("Disks & volumes", "Inspect shared storage, manage external drives, and review every disk change.", "disks", disksLoading) + error(disksError);
    if (!disks) return html + empty(disksLoading ? "Reading disk information…" : "Disk information unavailable", "Connect an external drive or refresh to inspect your Mac’s storage.", "disk", "", {scanning: disksLoading});
    const visibleDevices = disks.devices.filter(d => showSystemDisks || d.visible !== false);
    if (!visibleDevices.some(d => d.id === selectedDisk)) selectedDisk = visibleDevices.find(d => d.id === disks.startup_id)?.id || visibleDevices[0]?.id || "";
    const d = visibleDevices.find(d => d.id === selectedDisk);
    const hiddenCount = disks.devices.filter(d => d.visible === false).length;
    html += disks.warnings.map(error).join("");
    if (!d) return html + empty("No disks available", disks.supported ? "Refresh after connecting a drive." : "Disk tools require macOS.", "disk");
    const used = d.used ?? (d.free !== null ? d.total - d.free : null);
    const other = d.used !== null ? d.other : 0;
    const percent = n => d.total ? (n || 0) / d.total * 100 : 0;
    html += `<div class="disk-workspace"><section class="disk-browser" aria-label="Connected disks"><div class="disk-browser-heading"><h2>Your storage</h2>${hiddenCount ? `<button class="button link" data-action="toolkit-system-disks" aria-pressed="${showSystemDisks}">${showSystemDisks ? "Hide system volumes" : `Show system volumes (${hiddenCount})`}</button>` : ""}</div><div class="disk-device-list">${visibleDevices.map(x => `<button class="disk-choice ${x.id === selectedDisk ? "active" : ""}" data-action="toolkit-disk-select" data-target="${esc(x.id)}" aria-pressed="${x.id === selectedDisk}">${icon(x.kind === "disk" ? "disk" : "folder")}<span><strong>${esc(x.name)}</strong><small>${x.id === disks.startup_id ? "Startup volume" : x.kind === "disk" ? x.internal ? "Internal drive" : "External drive" : x.kind === "container" ? "Shared APFS container" : x.system_managed ? "Managed by macOS" : "Volume"} · ${fmt(x.total)}</small></span>${x.id === selectedDisk ? icon("check") : ""}</button>`).join("")}</div>${!showSystemDisks && hiddenCount ? '<p class="disk-filter-note">Recovery, boot, and system partitions are hidden. They remain protected.</p>' : ""}</section><section class="disk-detail"><div class="disk-heading"><span class="drive-emblem">${icon("disk")}</span><div><h2>${esc(d.name)}</h2><p>${esc(d.format)}${d.encrypted ? " · Encrypted" : ""}${d.snapshot ? " · Startup snapshot" : ""}</p><small>${esc(d.id)} · ${esc(d.protocol)}</small></div><strong>${fmt(d.total)}</strong></div><div class="volume-map" aria-label="Storage usage">${used !== null ? `<span class="volume-used" style="width:${percent(used)}%"></span><span class="volume-other" style="width:${percent(other)}%"></span>` : '<span class="volume-unknown"></span>'}</div><div class="volume-legend"><span><i class="volume-used"></i>Used<strong>${used === null ? "Not reported" : fmt(used)}</strong></span>${other ? `<span><i class="volume-other"></i>Other volumes & metadata<strong>${fmt(other)}</strong></span>` : ""}<span><i></i>Free${d.kind === "container" || d.format.includes("APFS") ? " in container" : ""}<strong>${d.free === null ? "Not reported" : fmt(d.free)}</strong></span></div>${d.format.includes("APFS") || d.kind === "container" ? '<p class="disk-explanation">APFS volumes share the container’s free space. Other volumes, snapshots, and filesystem metadata can occupy space beyond the selected volume. Purgeable space is not counted as free here.</p>' : ""}<dl class="disk-facts">${[["Mount point", d.mount || "Not mounted"], ["Type", d.snapshot ? "APFS snapshot" : d.kind], ["Access", d.writable ? "Read and write" : "Read-only / locked"], ["SMART status", d.smart], ["Roles", d.roles.join(", ") || "None"], ["UUID", d.uuid || "Not reported"]].map(([k,v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl><div class="disk-actions">${d.actions.map(action => button(labels[action], "toolkit-disk-action", {style: ["erase", "partition"].includes(action) ? "danger" : "", disabled: locked(), data: {tool: action, target: d.id}})).join("")}</div>${d.protected_reason ? `<p class="disk-protected">${icon("shield")}${esc(d.protected_reason)}</p>` : '<p class="note">Erasing or repartitioning removes all data on the selected physical disk. Back up the drive first.</p>'}<div class="disk-native"><div><h3>First Aid, encryption & advanced layouts</h3><p>Use Disk Utility for repairs, encrypted volumes, secure erase where supported, or resizing existing partitions.</p></div>${shortcut("Open Disk Utility", "disk-utility")}</div></section></div><p class="note">${stamp(disks.checked_at)}. Reconnects and layout changes require a fresh review.</p>`;
    return html + history();
  }
  function options(apfsOnly = false) {
    return Object.entries(disks?.formats || {}).filter(([k]) => !apfsOnly || k.startsWith("APFS")).map(([k,v]) => `<option value="${esc(k)}">${esc(v)}</option>`).join("");
  }
  function partitionRow(index) {
    return `<fieldset class="partition-fields"><legend>Partition ${index + 1}</legend><label>Name<input name="part-name" value="${index === 0 ? "Mac Files" : index === 1 ? "Shared Files" : "Volume " + (index + 1)}" maxlength="64" required></label><label>Format<select name="part-format">${options()}</select></label><label>Size in GB<input name="part-size" type="number" min="1" max="100000" step="1" value="20" required></label><span class="partition-remainder" hidden>Uses the remaining space</span></fieldset>`;
  }
  function updatePartitionSizes() {
    const rows = [...$("diskOperationForm").querySelectorAll(".partition-fields")];
    rows.forEach((row, index) => {
      const last = index === rows.length - 1;
      row.querySelector('[name="part-size"]').disabled = last;
      row.querySelector('[name="part-size"]').parentElement.hidden = last;
      row.querySelector('.partition-remainder').hidden = !last;
    });
    $("addPartition").disabled = rows.length >= 4;
    $("removePartition").disabled = rows.length <= 2;
    Dropdowns.enhance($("diskOperationForm"));
  }
  function diskForm(action, target) {
    const device = disks.devices.find(d => d.id === target);
    if (!device) return;
    detailKind = "toolkit";
    $("detailDialog").innerHTML = `<div class="drawer-head"><div><h2>${esc(labels[action])}</h2><small>${esc(device.name)} · ${esc(device.id)} · ${fmt(device.total)}</small></div>${button("", "close-detail", {symbol:"x", style:"ghost icon-only", aria:"Close disk setup"})}</div><div class="drawer-body"><form id="diskOperationForm" data-operation="${esc(action)}" data-target="${esc(target)}">${action === "partition" ? `<div class="review-warning">This replaces the entire disk layout and permanently erases every file on this disk. To keep existing data, use Disk Utility to resize partitions or add an APFS volume instead.</div><div id="partitionRows">${partitionRow(0)}${partitionRow(1)}</div><div class="partition-controls"><button type="button" id="addPartition" class="button" data-action="toolkit-part-add">Add partition</button><button type="button" id="removePartition" class="button" data-action="toolkit-part-remove">Remove last</button></div><p class="note">Two to four partitions, GUID scheme. The last partition uses remaining space. Leave at least 2 GB for it and disk overhead.</p>` : `<p class="${action === "erase" ? "review-warning" : "note"}">${action === "erase" ? "Every volume and file on this physical disk will be permanently erased. Formatting is not a secure wipe." : action === "add-volume" ? "The new volume shares free space with the other volumes in this external APFS container." : "Scripts and apps that use the old volume path may need updating."}</p><div class="disk-form-fields"><label>Volume name<input name="volume-name" value="${esc(action === "rename" ? device.name : "Untitled")}" maxlength="64" required></label>${action !== "rename" ? `<label>Format<select name="volume-format">${options(action === "add-volume")}</select></label>` : ""}</div>${action === "erase" ? '<p class="note">APFS is for modern Macs; ExFAT works with Mac and Windows. The disk will use a GUID partition map.</p>' : ""}`}<div class="drawer-footer">${button("Review operation", "toolkit-disk-review", {style:"primary", symbol:"arrow"})}</div></form></div>`;
    Overlays.open($("detailDialog"));
    if (action === "partition") updatePartitionSizes();
    else Dropdowns.enhance($("diskOperationForm"));
  }
  async function prepare(kind, body) {
    if (locked() || pendingAsk) return;
    preparing = true; draw();
    let plan;
    try { plan = await api(kind === "disk" ? "/api/disks/plan" : kind === "brew" ? "/api/brew/plan" : "/api/tools/plan", body); }
    finally { preparing = false; draw(); }
    const backup = plan.danger && kind === "disk";
    const answer = await ask({title: plan.title, confirm: plan.title, danger: plan.danger,
      phrase: plan.phrase, requiresBackup: backup,
      body: `${plan.target ? `<div class="review-total"><span>${esc(plan.target.name)}<small>${esc(plan.target.id)} · ${esc(plan.target.protocol)}</small></span><b>${fmt(plan.target.total)}</b></div>` : ""}<p>${esc(plan.description)}</p>${plan.layout.length ? `<div class="review-items">${plan.layout.map(p => `<div class="review-item"><span>${esc(p.name)}<small>${esc(p.format)}</small></span><b>${esc(p.size)}</b></div>`).join("")}</div>` : ""}${plan.packages?.length ? `<div class="review-items">${plan.packages.map(p => `<div class="review-item"><span>${esc(p.full_name)}<small>${esc(p.kind)}</small></span><b>${esc(p.versions.join(", "))}</b></div>`).join("")}</div>` : ""}${plan.preview ? `<div class="command-preview"><h3>Homebrew preview</h3><pre>${esc(plan.preview)}</pre></div>` : ""}${backup ? '<label class="check-label"><input type="checkbox" id="diskBackupAck">I have backed up everything I need from this disk.</label>' : ""}<p class="note">This review expires in five minutes.${plan.changes && S.scanning ? " Wait for the storage scan to finish before running it." : ""}</p><details class="command-preview"><summary>Command details</summary><pre>${esc(plan.commands.map(c => c.map(v => JSON.stringify(v)).join(" ")).join("\n"))}</pre></details>`});
    if (!answer.confirmed) return;
    submissionPending = true;
    try {
      const job = await api("/api/tools/run", {token: plan.token, confirmed: true, phrase: answer.phrase, backup_ack: answer.backupAck});
      jobs.push(job);
    } catch (e) {
      statusUncertain = true;
      throw e;
    } finally {
      submissionPending = false;
      loadJobs();
    }
    if (["toolkit", "homebrew"].includes(detailKind)) await closeDetail();
    draw(); loadJobs();
    toast(`${plan.title} started. Results will appear below.`);
  }
  async function dispatch(action, el) {
    if (action === "toolkit-refresh") return refresh(el.dataset.kind);
    if (action === "toolkit-open") {
      const r = await api("/api/tools/open", {action: el.dataset.tool});
      return toast(`${r.title} opened.`);
    }
    if (action === "toolkit-plan") return prepare("tool", {action: el.dataset.tool});
    if (action === "toolkit-system-disks") { showSystemDisks = !showSystemDisks; return draw(); }
    if (action === "toolkit-disk-select") { selectedDisk = el.dataset.target; return draw(); }
    if (action === "toolkit-disk-action") {
      if (["rename", "add-volume", "erase", "partition"].includes(el.dataset.tool)) return diskForm(el.dataset.tool, el.dataset.target);
      return prepare("disk", {action: el.dataset.tool, target: el.dataset.target});
    }
    if (action === "toolkit-part-add") {
      const rows = $("partitionRows");
      if (rows.children.length < 4) rows.insertAdjacentHTML("beforeend", partitionRow(rows.children.length));
      return updatePartitionSizes();
    }
    if (action === "toolkit-part-remove") {
      const rows = $("partitionRows");
      if (rows.children.length > 2) rows.lastElementChild.remove();
      return updatePartitionSizes();
    }
    if (action === "toolkit-disk-review") {
      const form = $("diskOperationForm");
      if (!form.reportValidity()) return;
      const body = {action: form.dataset.operation, target: form.dataset.target,
        name: form.elements['volume-name']?.value, format: form.elements['volume-format']?.value};
      if (body.action === "partition") body.partitions = [...form.querySelectorAll('.partition-fields')].map(row => ({name: row.querySelector('[name="part-name"]').value, format: row.querySelector('[name="part-format"]').value, size_gb: Number(row.querySelector('[name="part-size"]').value)}));
      return prepare("disk", body);
    }
    if (action === "toolkit-dev-files") { navigate("clean"); mode = "normal"; cat = "Developer & Pro Tools"; minmb = 0; return draw(); }
    if (action === "toolkit-export") {
      const blob = new Blob([JSON.stringify({version: S.version, ...health}, null, 2)], {type:"application/json"});
      const url = URL.createObjectURL(blob), a = document.createElement("a");
      a.href = url; a.download = "mac-health-report.json"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  }
  document.addEventListener("submit", event => {
    if (event.target.id === "diskOperationForm") {
      event.preventDefault();
      dispatch("toolkit-disk-review").catch(e => toast(e.message, true));
    }
  });
  window.addEventListener("beforeunload", event => {
    if (isRunning()) { event.preventDefault(); event.returnValue = ""; }
  });
  return {optimizeView, diskView, enter, dispatch, isRunning, locked, prepare, history};
})();
