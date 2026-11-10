"use strict";
const BackgroundUI = (() => {
  let state = {automation:{}, updates:{}}, polling = false, lastEvent = 0;
  let eventSession = '';
  let permission = 'Unknown';
  const text = source => esc(I18n.t(source));
  const native = () => !!window.webkit?.messageHandlers?.notifications;
  const date = value => value ? new Date(value * 1000).toLocaleString(I18n.locale()) : I18n.t('Not recorded');
  const intervals = [1, 6, 12, 24, 48, 72, 168, 336, 720];
  const hoursLabel = hours => new Intl.NumberFormat(I18n.locale(), {style:'unit', unit:'hour', unitDisplay:'long'}).format(hours);
  /** Render automation, notification, and update controls with escaped job failures. */
  function settings() {
    const prefs = S.settings || {}, job = state.automation, update = state.updates;
    const hours = formDrafts.get('automationHours') ?? prefs.automation_hours ?? 168;
    const interval = formDrafts.get('automationInterval') ?? (intervals.includes(Number(hours)) ? String(hours) : 'custom');
    return `<section class="settings-section">
      <div class="settings-section-head"><h2>${text('Automation')}</h2>
      <p>${text('Move safe caches and logs untouched for 7 days to Trash. Restore them from Cleanup history.')}</p>
      <p>${text('Runs while Mac Deep Cleaner is open, including in the menu bar. Quitting pauses automation.')}</p></div>
      <div class="settings-row"><div><h3>${text('Automatic safe cleanup')}</h3>
      <p>${text('Next run')}: ${esc(prefs.automation_enabled ? date(prefs.automation_next_run) : I18n.t('Off'))}</p></div>
      ${button(I18n.t(prefs.automation_enabled ? 'Disable' : 'Enable'), 'background-toggle', {data:{setting:'automation_enabled'}, disabled:!!S.busy})}</div>
      <div class="settings-row"><label for="automationInterval">${text('Interval (hours)')}</label>
      <div class="interval-picker">
        <select id="automationInterval" aria-label="${text('Interval (hours)')}">
          ${intervals.map(value => `<option value="${value}" ${interval === String(value) ? 'selected' : ''}>${esc(hoursLabel(value))}</option>`).join('')}
          <option value="custom" ${interval === 'custom' ? 'selected' : ''}>${text('Custom')}</option>
        </select>
        <div class="interval-stepper" ${interval !== 'custom' ? 'hidden' : ''}>
          <button type="button" data-action="background-step" data-step="-1" aria-label="${text('Decrease interval')}" ${Number(hours) <= 1 ? 'disabled' : ''}><span aria-hidden="true">−</span></button>
          <input id="automationHours" type="number" inputmode="numeric" min="1" max="720" step="1" value="${esc(hours)}" aria-label="${text('Interval (hours)')}">
          <button type="button" data-action="background-step" data-step="1" aria-label="${text('Increase interval')}" ${Number(hours) >= 720 ? 'disabled' : ''}><span aria-hidden="true">+</span></button>
        </div>
        ${button(I18n.t('Save'), 'background-interval', {disabled:!!S.busy})}
      </div></div>
      <div class="settings-row"><div><h3>${text('One-click safe cleanup')}</h3>
      <p>${text('Last run')}: ${esc(date(job.last_run))} · ${text(job.running ? 'Running…' : (job.error || job.result?.fails?.length) ? 'Failed' : job.last_run ? 'Completed' : 'Not recorded')}</p></div>
      ${button(I18n.t('Clean up'), 'background-clean', {disabled:!!S.busy || S.scanning || job.running})}</div>
      ${job.error ? `<p class="error-banner" role="alert">${text(job.error)}</p>` : ''}
      ${job.result?.fails?.length ? `<ul class="error-banner" role="alert">${job.result.fails.map(([name, message]) => `<li>${esc(name)}: ${text(message)}</li>`).join('')}</ul>` : ''}
      ${job.result ? `<p role="status">${esc(fmt(job.result.processed_bytes || 0))} ${text('processed.')} ${text('Moving files to Trash keeps them recoverable; space is freed when you empty it yourself.')}</p>${button(I18n.t('Cleanup history'), 'history-open')}` : ''}
    </section>
    <section class="settings-section"><div class="settings-section-head"><h2>${text('Notifications')}</h2>
    <p>${text('Cleanup results and available updates.')}</p></div>
    <div class="settings-row"><p>${native() ? text(permission) : text('Available in the macOS app.')}</p>
    <div class="language-actions">${button(I18n.t(prefs.notifications ? 'Disable' : 'Enable'), 'background-notifications', {disabled:!native() || !!S.busy})}
    ${button(I18n.t('Test notification'), 'background-test', {disabled:!native() || !prefs.notifications})}
    ${native() ? button(I18n.t('System Settings'), 'background-notification-settings') : ''}</div></div></section>
    <section class="settings-section"><div class="settings-section-head"><h2>${text('Updates')}</h2>
    <p>${text('Check GitHub for new releases.')}</p></div>
    <div class="settings-row"><div><h3>${text('Automatic update checks')}</h3><p>${text('Checks once a day while the app is open.')}</p></div>
    ${button(I18n.t(prefs.automatic_updates ? 'Disable' : 'Enable'), 'background-toggle', {data:{setting:'automatic_updates'}, disabled:!!S.busy})}</div>
    <div class="settings-row"><div><p role="status">${text(update.checking ? 'Checking…' : update.error || (update.checked_at ? update.available ? 'Update available' : 'You are up to date.' : 'Not recorded'))}
    ${update.latest ? `<span data-no-translate> (${esc(update.latest)})</span>` : ''}</p><p>${text('Checked')}: ${esc(date(update.checked_at))}</p></div>
    ${button(I18n.t('Check for updates'), 'background-update', {disabled:update.checking})}</div>
    <a class="button" href="${esc(update.url || 'https://github.com/NK2552003/Mac-Cleaner/releases')}" target="_blank" rel="noopener noreferrer">${text('View release on GitHub')}</a>
    </section>`;
  }
  /** Refresh background state and persist only delivered events for the current service. */
  async function poll() {
    if (polling) return;
    polling = true;
    try {
      const next = await api('/api/background');
      const changed = JSON.stringify(state) !== JSON.stringify(next);
      const finished = next.automation.last_run && next.automation.last_run !== state.automation.last_run;
      state = next;
      if (finished) await load();
      if (eventSession !== next.event_session) {
        eventSession = next.event_session;
        lastEvent = 0;
        try {
          const delivered = JSON.parse(sessionStorage.getItem('mdc-delivered-event'));
          if (delivered?.session === eventSession && Number.isSafeInteger(delivered.id)) lastEvent = delivered.id;
        } catch { /* In-memory deduplication still works when storage is unavailable. */ }
      }
      for (const event of next.events || []) {
        if (event.id <= lastEvent) continue;
        if (!S.settings?.notifications) continue;
        const payload = {action:'deliver', id:String(event.id), title:I18n.t(event.title), body:I18n.t(event.message)};
        if (native()) window.webkit.messageHandlers.notifications.postMessage(payload);
        else toast(payload.title + ': ' + payload.body);
        lastEvent = event.id;
        try { sessionStorage.setItem('mdc-delivered-event', JSON.stringify({session:eventSession, id:lastEvent})); }
        catch { /* Do not interrupt delivery if storage is unavailable. */ }
      }
      if (changed && view === 'settings') draw();
    } catch { /* The main connection banner handles server disconnections. */ }
    finally { polling = false; }
  }
  /** Keep the interval preset and unsaved numeric value synchronized. */
  function changeInterval(value) {
    formDrafts.set('automationInterval', value);
    if (value !== 'custom') {
      formDrafts.set('automationHours', value);
      $('automationHours').value = value;
    }
    draw();
  }
  /** Save the custom interval draft and update step-button bounds. */
  function syncInterval() {
    const input = $('automationHours');
    const hours = Number(input.value);
    formDrafts.set('automationHours', input.value);
    document.querySelector('[data-step="-1"]').disabled = hours <= 1;
    document.querySelector('[data-step="1"]').disabled = hours >= 720;
  }
  /** Handle background settings and cleanup actions through the local service. */
  async function dispatch(action, el) {
    if (action === 'background-step') {
      const input = $('automationHours');
      if (!input.value || !input.validity.valid) input.value = String(Math.max(1, Math.min(720, Math.round(Number(input.value) || 1))));
      Number(el.dataset.step) < 0 ? input.stepDown() : input.stepUp();
      syncInterval();
      return;
    }
    if (action === 'background-clean') { await api('/api/automation/clean', {}); await load(); }
    if (action === 'background-update') { state.updates = await api('/api/updates/check', {}); draw(); }
    if (action === 'background-toggle') {
      const key = el.dataset.setting;
      await api('/api/settings', {[key]:!S.settings[key]}); await load();
    }
    if (action === 'background-interval') {
      const input = $('automationHours');
      if (!input.reportValidity()) return;
      await api('/api/settings', {automation_hours:Number(input.value)}); await load();
    }
    if (action === 'background-notifications') {
      if (S.settings.notifications) { await api('/api/settings', {notifications:false}); await load(); }
      else window.webkit.messageHandlers.notifications.postMessage({action:'authorize'});
    }
    if (action === 'background-test') window.webkit.messageHandlers.notifications.postMessage({action:'test', title:I18n.t('Mac Deep Cleaner'), body:I18n.t('Test notification')});
    if (action === 'background-notification-settings') window.webkit.messageHandlers.notifications.postMessage({action:'settings'});
    await poll();
  }
  /** Apply native notification permission state and optionally enable delivery. */
  async function authorization(status, enable) {
    const changed = permission !== status;
    permission = status;
    if (enable && status === 'Enabled') {
      try { await api('/api/settings', {notifications:true}); await load(); }
      catch (e) { toast(e.message, true); }
    }
    if (changed && view === 'settings') draw();
  }
  setInterval(poll, 3000);
  const menuStatus = () => I18n.t('Safe cleanup') + ' · ' + I18n.t(state.automation.running ? 'Running…' : (state.automation.error || state.automation.result?.fails?.length) ? 'Failed' : state.automation.last_run ? 'Completed' : 'Not recorded');
  return {settings, dispatch, changeInterval, syncInterval, poll, authorization, menuStatus, isRunning:() => !!state.automation.running};
})();
