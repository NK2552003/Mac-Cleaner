"use strict";
const CareUI = (() => {
  let report = null, error = '', fetching = false, tab = 'overview', timer, announced = false, submitting = false;
  const tabs = ['overview', 'history', 'media', 'startup', 'browsers', 'slimming', 'rules'];
  const names = {overview:'Overview', history:'Cleanup history', media:'Similar media', startup:'Startup items', browsers:'Browsers', slimming:'App slimming', rules:'Custom rules'};
  const text = (value) => esc(I18n.t(value));
  const action = (label, name, data = {}, disabled = false) => button(I18n.t(label), 'care-' + name, {data, disabled: disabled || submitting || S.busy || !!report?.job && !report.job.done});
  const section = (title, body) => `<section class="care-section"><div class="care-section-head"><h2>${text(title)}</h2></div>${body}</section>`;
  const notice = (message) => `<p class="note">${icon('shield')}${text(message)}</p>`;
  const date = (value) => new Date(value * 1000).toLocaleString(I18n.locale());

  async function enter() {
    clearTimeout(timer);
    if (fetching) return;
    fetching = true;
    if (view === 'care') draw();
    try {
      report = await api('/api/care');
      error = '';
      if (!report.job.done) announced = false;
      if (report.job.done && !announced && (report.job.error || report.job.result)) {
        announced = true;
        toast(report.job.error || report.job.result?.message || 'Operation finished. Refresh the storage scan to update findings.', !!report.job.error);
        if (report.job.result?.locale) await I18n.refresh(report.job.result.locale);
        await load();
      }
    } catch(e) {
      error = e.message;
    } finally {
      fetching = false;
      if (view === 'care') draw();
      if (report && !report.job.done) timer = setTimeout(enter, 1500);
    }
  }

  function treemap() {
    const files = (report.map || []).filter(f => f.size > 0).slice(0, 40);
    if (!files.length) return notice('Finish a storage scan to see large files here.');
    const maxSize = Math.max(...files.map(f => f.size), 1);
    const boxes = [];
    function split(items, x, y, w, h) {
      if (items.length === 1) {
        boxes.push({...items[0], x: Math.min(x, 99.5), y: Math.min(y, 99.5), w: Math.max(0.5, Math.min(w, 100 - x)), h: Math.max(0.5, Math.min(h, 100 - y))});
        return;
      }
      const total = items.reduce((n, f) => n + f.size, 0);
      let pivot = 1, subtotal = items[0].size;
      while (pivot < items.length - 1 && subtotal < total / 2) subtotal += items[pivot++].size;
      let ratio = total > 0 ? subtotal / total : 0.5;
      ratio = Math.max(0.08, Math.min(0.92, ratio));
      if (w >= h) {
        split(items.slice(0, pivot), x, y, w * ratio, h);
        split(items.slice(pivot), x + w * ratio, y, w * (1 - ratio), h);
      } else {
        split(items.slice(0, pivot), x, y, w, h * ratio);
        split(items.slice(pivot), x, y + h * ratio, w, h * (1 - ratio));
      }
    }
    split(files, 0, 0, 100, 100);

    return `
      <div class="heatmap-header">
        <div class="heatmap-legend" aria-label="Heat map scale">
          <span class="legend-title">${text('Heat scale')}:</span>
          <span class="legend-chip heat-5">${text('Very large')}</span>
          <span class="legend-chip heat-4"></span>
          <span class="legend-chip heat-3">${text('Moderate')}</span>
          <span class="legend-chip heat-2"></span>
          <span class="legend-chip heat-1">${text('Smaller')}</span>
        </div>
      </div>
      <div class="care-treemap" aria-label="Large file treemap">
        ${boxes.map((f, i) => {
          const itemIdx = report.map.indexOf(report.map.find(r => r.path === f.path));
          const heatRatio = f.size / maxSize;
          const tier = heatRatio >= 0.60 ? 5 : heatRatio >= 0.30 ? 4 : heatRatio >= 0.12 ? 3 : heatRatio >= 0.04 ? 2 : 1;
          const showTitle = f.w >= 11 && f.h >= 9;
          const showSize = f.w >= 6 && f.h >= 5;
          const compact = !showTitle && showSize;
          const tiny = !showSize && !showTitle;
          return `<button data-action="care-map-file" data-index="${itemIdx}" style="left:${f.x}%;top:${f.y}%;width:${f.w}%;height:${f.h}%;" class="tile heat-${tier} ${compact ? 'compact' : ''} ${tiny ? 'tiny' : ''}" title="${esc(f.name)} · ${fmt(f.size)}" aria-label="${esc(f.name)} · ${fmt(f.size)}">
            ${showTitle ? `<span data-no-translate>${esc(f.name)}</span>` : ''}
            ${showSize ? `<b>${fmt(f.size)}</b>` : ''}
          </button>`;
        }).join('')}
      </div>
      <p class="note" style="margin-top:12px">${icon('shield')}${text('Area represents allocated bytes in the 40 largest scanned files. Excluded folders and files below the scan threshold are not included.')}</p>
      <details class="settings-accordion">
        <summary>${text('Accessible file list')}</summary>
        <div class="care-table-wrap">
          <table class="care-table">
            <thead><tr><th>${text('Name')}</th><th>${text('Size')}</th><th>${text('Date modified')}</th><th>${text('Action')}</th></tr></thead>
            <tbody>
              ${files.map((f, i) => `<tr>
                <td><strong data-no-translate>${esc(f.name)}</strong><br><small class="path">${esc(f.path)}</small></td>
                <td>${fmt(f.size)}</td>
                <td>${date(f.mtime)}</td>
                <td>${button('Show in Finder', 'reveal', {data:{path:f.path}, style:'link'})}</td>
              </tr>`).join('')}
            </tbody>
          </table>
        </div>
      </details>`;
  }

  function trend() {
    const values = report.samples || [];
    if (!values.length) return notice('Disk samples will appear as you use the app.');
    const step = Math.max(1, Math.ceil(values.length / 90));
    const points = values.filter((_, i) => i % step === 0 || i === values.length - 1);
    const total = Math.max(...points.map(p => p.total), 1);
    const first = points[0].time, span = Math.max(1, points.at(-1).time - first);
    const polyline = points.map(p => `${10 + (p.time - first) / span * 780},${150 - p.used / total * 140}`).join(' ');

    return `
      <div class="trend-card-content">
        <svg class="care-trend" viewBox="0 0 800 170" role="img" aria-label="Disk used over time; values available in the table below">
          <path d="M10 10V150H790" fill="none" stroke="currentColor" opacity=".2"/>
          <polyline points="${polyline}" fill="none" stroke="#69bbf5" stroke-width="2.5"/>
          ${points.length === 1 ? `<circle cx="10" cy="${150 - points[0].used / total * 140}" r="5" fill="#69bbf5"/>` : ''}
        </svg>
        <div class="trend-legend">
          <span>${date(first)}</span>
          <span style="color:#69bbf5">● ${text('Disk Used')}</span>
          <span>${date(points.at(-1).time)}</span>
        </div>
      </div>
      <p class="note" style="margin-top:12px">${icon('shield')}${text('One local sample per hour while this workspace is open, plus scheduled runs. Missing hours are not interpolated measurements. Trash moves do not free disk space.')}</p>
      <details class="settings-accordion">
        <summary>${text('View data table')}</summary>
        <div class="care-table-wrap">
          <table class="care-table">
            <thead><tr><th>${text('Time')}</th><th>${text('Used')}</th><th>${text('Free')}</th></tr></thead>
            <tbody>
              ${points.map(p => `<tr><td>${date(p.time)}</td><td>${fmt(p.used)}</td><td>${fmt(p.free)}</td></tr>`).join('')}
            </tbody>
          </table>
        </div>
      </details>`;
  }

  function overview() {
    const schedule = report.schedule;
    const timeLabel = new Intl.DateTimeFormat(I18n.locale(), {hour:'2-digit', minute:'2-digit', hourCycle:'h23', timeZone:'UTC'});
    return `
      <div class="care-overview-minimal">
        <section class="care-minimal-row">
          <div class="care-row-info">
            <div class="care-row-title">
              ${icon("check")}
              <h3>${text('Cleanup profiles')}</h3>
            </div>
            <p>${text('Choose a preset, then review every selected item.')}</p>
          </div>
          <div class="care-actions">
            ${Object.entries(report.profiles).map(([key, value]) => action(value.name, 'profile', {profile:key}, !canSelect())).join('')}
          </div>
        </section>

        <section class="care-minimal-row">
          <div class="care-row-info">
            <div class="care-row-title">
              ${icon("refresh")}
              <h3>${text('Weekly cleanup')}</h3>
              <span class="badge ${schedule.enabled ? '' : 'rtl-badge'}">
                ${schedule.enabled ? text('Enabled') : text('Off by default')}
              </span>
            </div>
            <p>${text('Old cache and log files only. Moves to Trash with restore history.')}</p>
          </div>
          <div class="care-schedule-inline">
            <div class="schedule-field">
              <select id="careWeekday" aria-label="${text('Day')}" ${schedule.enabled ? 'disabled' : ''}>
                ${['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'].map((d, i) => `<option value="${i}" ${i === (schedule.calendar?.Weekday ?? 0) ? 'selected' : ''}>${text(d)}</option>`).join('')}
              </select>
            </div>
            <div class="schedule-field">
              <select id="careHour" aria-label="${text('Hour')}" ${schedule.enabled ? 'disabled' : ''}>
                ${Array.from({length:24}, (_, hour) => `<option value="${hour}" ${hour === (schedule.calendar?.Hour ?? 10) ? 'selected' : ''}>${esc(timeLabel.format(new Date(Date.UTC(2020, 0, 1, hour))))}</option>`).join('')}
              </select>
            </div>
            ${action(schedule.enabled ? 'Disable schedule' : 'Review schedule', 'schedule', {}, !schedule.supported)}
          </div>
        </section>

        <section class="care-minimal-row">
          <div class="care-row-info">
            <div class="care-row-title">
              ${icon("download")}
              <h3>${text('Share a report')}</h3>
            </div>
            <p>${text('Export findings as HTML. Print the report to save a PDF.')}</p>
            <p class="note">${icon("shield")}${text('Full paths are omitted; filenames can still be personal. Review before sharing.')}</p>
          </div>
          <div class="care-actions">
            <a class="button primary download-report-btn" href="/api/care/report" download="mac-cleaner-report.html">
              ${icon("download")}${text('Download HTML report')}
            </a>
          </div>
        </section>
      </div>

      ${section('Large files map', treemap())}
      ${section('Space over time', trend())}
    `;
  }

  function history() {
    return section('Cleanup history',
      notice('Up to 1,000 recent Trash moves. Restore is available while the recorded item is unchanged and its original location is free. Permanent deletion and command-based cleanup cannot be undone.') +
      (!report.history.length
        ? `<div class="empty">${icon("file")}<h3>${text('No recorded cleanup yet.')}</h3><p>${text('Cleaned items will appear here for one-click restore.')}</p></div>`
        : `<div class="care-list">${report.history.map(h => `
            <article class="care-row">
              <div class="care-row-main">
                <span class="file-icon">${icon("file")}</span>
                <div>
                  <h3 data-no-translate>${esc(h.original.split('/').pop())}</h3>
                  <p class="path">${esc(h.original)}</p>
                  <small>${date(h.created)} · ${text(h.status === 'moved' && !h.available ? 'Trash entry unavailable' : ({moved:'Moved to Trash',restored:'Restored',interrupted:'Interrupted operation'}[h.status] || h.status))}${h.conflict ? ' · ' + text('Original location occupied') : ''}</small>
                </div>
              </div>
              <div class="care-row-actions">
                ${action('Restore', 'restore', {id:h.id}, !h.available || h.conflict)}
              </div>
            </article>`).join('')}</div>`
      )
    );
  }

  function media() {
    const result = report.media;
    return section('Similar media',
      `<p>${text('Review visually similar photos and videos. Similarity is not proof that files are duplicates.')}</p>
       <div class="care-actions">${action('Find similar media', 'media', {}, S.scanning)}${button(I18n.t('Duplicates'), 'navigate', {style:'link', data:{view:'dups'}})}</div>
       ${result ? `<p class="note">${esc(result.notice || '')}</p>
         <div class="care-list">${(result.pairs || []).map(pair => `<article class="media-pair"><div><strong>${Number(pair.score).toFixed(0)}%</strong><span>${text('Similarity')}</span></div><div class="media-pair-files">${[['left','Show first'],['right','Show second']].map(([side,label]) => `<div><p class="path" data-no-translate>${esc(pair[side])}</p>${button(I18n.t(label), 'reveal', {style:'link', data:{path:pair[side]}})}</div>`).join('')}</div></article>`).join('') || empty('No similar media found', 'Try again after scanning more photos or videos.', 'file')}</div>
         ${(result.errors || []).length ? `<details class="tool-warning"><summary>${text('Some files could not be analyzed')}</summary>${result.errors.map(value => `<p>${esc(value)}</p>`).join('')}</details>` : ''}` : notice('Finish a storage scan, then compare media. Originals are never selected for deletion automatically.')}`);
  }

  function inventoryHeader() {
    return `<div class="inventory-head"><p>${text('Inspect local applications, startup definitions, and browser extensions.')}</p>${action('Refresh inventory', 'inventory', {}, !canSelect())}</div>`;
  }

  function startup() {
    return section('Startup items',
      inventoryHeader() +
      notice('Only user LaunchAgents can be changed here. Disabling affects future launches; it does not kill running apps. Manage modern login/background items in System Settings.') +
      `<div class="care-actions" style="margin-bottom:16px">${button(text('Open Login Items'), 'toolkit-open', {data:{action:'login-items'}, symbol:'arrow'})}</div>` +
      `<div class="care-list">${(report.inventory?.startup || []).map(i => `
        <article class="care-row">
          <div class="care-row-main">
            <span class="file-icon">${icon("code")}</span>
            <div>
              <h3 data-no-translate>${esc(i.label)}</h3>
              <p>${esc(i.explanation)}</p>
              <p class="path">${esc(i.program)}</p>
            </div>
          </div>
          <div class="care-row-actions">
            ${action('Enable', 'startup', {path:i.path, enabled:'true'}, !i.editable)}
            ${action('Disable', 'startup', {path:i.path, enabled:'false'}, !i.editable)}
          </div>
        </article>`).join('')}</div>`
    );
  }

  function browsers() {
    return section('Browsers',
      inventoryHeader() +
      `<div class="browsers-grid">${(report.inventory?.browsers || []).map(b => `
        <article class="care-browser">
          <div class="care-browser-head">
            <h3>${esc(b.name)}</h3>
            <span class="badge">${b.installed ? `${b.extensions.length} ${text('extension records')}` : text('Not found')}</span>
          </div>
          ${notice(b.notice)}
          <div style="margin:12px 0">${action('Manage extensions', 'browser', {browser:b.name})}</div>
          <ul class="extensions-list">${b.extensions.slice(0, 100).map(e => `<li><strong data-no-translate>${esc(e.name)}</strong> <small>${esc(e.version)} · ${esc(e.profile)}</small></li>`).join('')}</ul>
        </article>`).join('')}</div>`
    );
  }

  function slimming() {
    return section('App slimming',
      inventoryHeader() +
      notice('Creates a separate ad-hoc signed copy in Downloads. Your installed app is retained. Keep English/Base plus the languages below. Compatibility, notarization, entitlements, and updates may be affected; test the copy before using it.') +
      `<div class="slimming-options"><label>${text('Additional languages to keep')}<input id="careLanguages" value="${esc(I18n.locale())}" placeholder="hi, es, fr"></label></div>` +
      `<div class="care-list">${(report.inventory?.apps || []).map(a => `
        <article class="care-row">
          <div class="care-row-main">
            <span class="file-icon">${icon("apps")}</span>
            <div>
              <h3>${esc(a.name)} · ${fmt(a.size)}</h3>
              <p>${a.languages.map(l => esc(l.name)).join(', ') || 'No top-level language packs'}</p>
            </div>
          </div>
          <div class="care-row-actions">
            ${action('Review slim copy', 'slim', {path:a.path})}
          </div>
        </article>`).join('')}</div>`
    );
  }

  function rules() {
    return section('Custom rules',
      `<p>${text('Add review-only rules for children of one named app cache directory.')}</p>` +
      notice('JSON only; no executable commands. Every match is caution-level and excluded from profiles and scheduling. Save, rescan, then review matching files in Storage cleanup.') +
      `<label for="careRules" class="field-label">JSON</label>` +
      `<textarea dir="ltr" id="careRules" rows="12" spellcheck="false">${esc(JSON.stringify(report.rules, null, 2))}</textarea>` +
      `<details class="settings-accordion"><summary>${text('Example rule')}</summary><pre>${esc(JSON.stringify({rules:[{name:'Preview cache',path:'~/Library/Caches/com.example.editor/previews/*',reason:'Generated previews; rebuilt by the editor.'}]},null,2))}</pre></details>` +
      `<div style="margin-top:14px">${action('Save rules', 'rules')}</div>`
    ) +
    section('Ghost allowlist',
      notice('Dismissed Ghost Files stay off future Ghost scans. Remove an entry to reconsider it.') +
      (report.allowlist.length
        ? `<div class="care-list">${report.allowlist.map(path => `
            <article class="care-row">
              <p class="path">${esc(path)}</p>
              ${action('Remove from allowlist', 'allowlist', {path})}
            </article>`).join('')}</div>`
        : `<p>${text('No dismissed ghosts.')}</p>`
      )
    );
  }

  function render() {
    return `<div class="care">
      <div class="pagehead care-pagehead">
        <div>
          <h1>${text('Care center')}</h1>
          <p>${text('Automate carefully. See what changed. Keep control.')}</p>
        </div>
        <div class="head-actions">
          ${action('Refresh', 'refresh')}
        </div>
      </div>
      <div class="care-tabs-wrap">
        <div class="care-tabs" role="navigation" aria-label="Care tools">
          ${tabs.map(t => `<button class="care-tab-btn ${tab === t ? 'active' : ''}" data-action="care-tab" data-tab="${t}" ${tab === t ? 'aria-current="page"' : ''}>${text(names[t])}</button>`).join('')}
        </div>
      </div>
      ${error ? `<div class="error-banner" role="alert">${icon('alert')}<span>${esc(error)}</span></div>` : ''}
      ${report?.job && !report.job.done ? scanIndicator(report.job.message, {feature:['media','startup','slimming'].includes(tab) ? 'care-'+tab : 'care'}) : fetching ? scanIndicator('Loading local care tools…') : ''}
      ${report ? ({overview, history, media, startup, browsers, slimming, rules}[tab]()) : ''}
    </div>`;
  }

  async function review(body) {
    const plan = await api('/api/care/plan', body);
    const answer = await ask({
      title: 'Review ' + plan.action,
      body: `<p>${esc(plan.summary)}</p>`,
      confirm: 'Run reviewed operation',
      danger: plan.action === 'slim',
      phrase: plan.action === 'slim' ? 'CREATE COPY' : ''
    });
    if (answer.confirmed) await api('/api/care/run', {token: plan.token, confirmed: true});
  }

  async function perform(name, el) {
    const kind = name.slice(5);
    if (kind === 'tab') {
      navigate('care', {tab:el.dataset.tab});
      return;
    }
    if (kind === 'refresh') {
      announced = false;
      return enter();
    }
    if (kind === 'map-file') {
      const f = report.map[Number(el.dataset.index)];
      if (!f) return;
      return ask({
        title: f.name,
        body: `<p class="path">${esc(f.path)}</p><p>${fmt(f.size)} · Last changed ${date(f.mtime)}</p>${button('Show in Finder', 'reveal', {data:{path:f.path}})}`,
        confirm: 'Done'
      });
    }
    if (kind === 'profile') {
      const result = await api('/api/care/profile', {profile: el.dataset.profile, scan_id: S.scan_id, revision: S.revision});
      selected = new Set(result.ids);
      navigate('clean', {reset:true, minmb:0});
      toast(`${result.ids.length} items selected for review.`);
      return;
    }
    if (kind === 'schedule') {
      if (!$('careHour').reportValidity()) return;
      await review({
        action: 'schedule',
        enabled: !report.schedule.enabled,
        weekday: Number($('careWeekday').value),
        hour: Number($('careHour').value)
      });
    }
    else if (kind === 'startup') await review({action: 'startup', path: el.dataset.path, enabled: el.dataset.enabled === 'true'});
    else if (kind === 'slim') await review({action: 'slim', path: el.dataset.path, keep: $('careLanguages').value.split(',').map(v => v.trim()).filter(Boolean)});
    else if (kind === 'restore') await api('/api/care/restore', {id: el.dataset.id});
    else if (kind === 'inventory' || kind === 'media') await api('/api/care/' + kind, {});
    else if (kind === 'browser') await api('/api/care/browser', {browser: el.dataset.browser});
    else if (kind === 'rules') {
      let rules;
      try { rules = JSON.parse($('careRules').value); }
      catch { throw new Error(I18n.t('Enter valid JSON before saving custom rules.')); }
      await api('/api/care/rules', rules);
      formDrafts.delete('careRules');
    }
    else if (kind === 'allowlist') await api('/api/care/allowlist/remove', {path: el.dataset.path});

    announced = false;
    await enter();
  }

  async function dispatch(name, el) {
    if (['care-tab','care-refresh','care-map-file','care-browser'].includes(name)) return perform(name, el);
    if (submitting || S.busy || report?.job && !report.job.done || pendingAsk) return;
    submitting = true;
    try { await perform(name, el); }
    finally { submitting = false; draw(); }
  }

  return {render, enter, dispatch, tab:() => tab, selectTab:next => {if (tabs.includes(next)) tab = next;},
    isRunning: () => submitting || !!report?.job && !report.job.done};
})();
