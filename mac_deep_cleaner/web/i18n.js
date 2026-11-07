"use strict";
const I18n = (() => {
  let language = 'en';
  try {
    const saved = localStorage.getItem('mdc_language');
    if (saved && /^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8}){0,3}$/.test(saved)) language = saved;
  } catch {}

  let pack = {}, metadata = null, failure = '', observer, pending = false;
  let importing = false, jobError = '';
  const originals = new WeakMap();

  let templates = [], sources = new Map(), persistence = Promise.resolve();
  const escapePattern = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  function indexPack() {
    sources = new Map(Object.entries(pack).map(([source, translated]) => [translated, source]));
    templates = Object.entries(pack).filter(([key]) => /\{\w+\}/.test(key)).map(([key, translated]) => {
      const names = [...key.matchAll(/\{(\w+)\}/g)].map(m => m[1]);
      const parts = key.split(/\{\w+\}/);
      return { pattern: new RegExp('^' + parts.map(escapePattern).join('(.*?)') + '$'), names, translated,
        weight: parts.join('').length };
    }).sort((a, b) => b.weight - a.weight);
  }
  function t(value, values) {
    if (typeof value !== 'string' || !value) return value;
    let translated = language === 'en' ? value : pack[value];
    if (!translated && language !== 'en') {
      for (const entry of templates) {
        const match = entry.pattern.exec(value);
        if (match) {
          const params = Object.fromEntries(entry.names.map((name, i) => [name, match[i + 1]]));
          translated = entry.translated.replace(/\{(\w+)\}/g, (token, key) => params[key] ?? token);
          break;
        }
      }
    }
    if (!translated && language !== 'en') {
      const parts = value.split(/( · |(?<=[.!?])\s+)/);
      if (parts.length > 1) translated = parts.map(part => /\S/.test(part) && part !== ' · ' ? t(part) : part).join('');
    }
    translated ||= value;
    return values ? translated.replace(/\{(\w+)\}/g, (token, key) => values[key] ?? token) : translated;
  }

  function direction(value) {
    return /^(ar|he|fa|ur|ps|sd|ug|yi|dv|ckb)(-|$)/.test(value) || value.includes('-Arab') ? 'rtl' : 'ltr';
  }

  function set(value) {
    if (!/^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8}){0,3}$/.test(value)) return;
    language = value;
    document.documentElement.lang = value;
    document.documentElement.dir = direction(value);
    try { localStorage.setItem('mdc_language', value); } catch {}
  }

  function activate(value, persist = true) {
    // Serialize the whole switch: failed downloads never change the server language,
    // and successful saves update both UI and AI before the next switch begins.
    persistence = persistence.catch(() => {}).then(async () => {
      const response = await api('/api/i18n/pack?locale=' + encodeURIComponent(value));
      if (persist) await api('/api/settings', { language: response.locale || value });
      set(response.locale || value);
      pack = response.messages || {};
      indexPack();
      failure = '';
      const picker = document.getElementById('languageSelect');
      if (picker) picker.value = language;
      if (typeof draw === 'function') draw();
      translateDOM();
      try { window.webkit?.messageHandlers?.languageChange?.postMessage({language, messages: pack}); } catch {}
      document.dispatchEvent(new CustomEvent('languagechange', {detail: {language}}));
    });
    return persistence;
  }

  function name(code) {
    try {
      const english = new Intl.DisplayNames([language], { type: 'language' }).of(code);
      const native = new Intl.DisplayNames([code], { type: 'language' }).of(code);
      return `${native} — ${english} (${code})`;
    } catch {
      return code;
    }
  }

  function translateDOM() {
    observer?.disconnect();
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walk.nextNode())) {
      if (node.parentElement?.closest('script,style,textarea,pre,code,.path,.ghost-path,[data-no-translate]')) continue;
      let record = originals.get(node);
      if (!record || node.nodeValue !== record.rendered) record = { source: sources.get(node.nodeValue.trim()) || node.nodeValue };
      const trimmed = record.source.trim();
      if (!trimmed) continue;
      const translated = t(trimmed);
      if (translated && translated !== trimmed) {
        const idx = record.source.indexOf(trimmed);
        if (idx !== -1) {
          const next = record.source.slice(0, idx) + translated + record.source.slice(idx + trimmed.length);
          if (node.nodeValue !== next) node.nodeValue = next;
          record.rendered = next;
        }
      } else {
        if (node.nodeValue !== record.source) node.nodeValue = record.source;
        record.rendered = record.source;
      }
      originals.set(node, record);
    }
    for (const el of document.querySelectorAll('[aria-label],[title],[placeholder]')) {
      if (el.closest('[data-no-translate],pre,code')) continue;
      let record = originals.get(el) || {};
      for (const attr of ['aria-label', 'title', 'placeholder']) {
        const value = el.getAttribute(attr);
        if (value === null) continue;
        if (!record[attr] || value !== record[attr].rendered) record[attr] = { source: sources.get(value) || value };
        const next = t(record[attr].source);
        if (value !== next) el.setAttribute(attr, next);
        record[attr].rendered = next;
      }
      originals.set(el, record);
    }
    observer?.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['aria-label', 'title', 'placeholder'] });
  }

  function settings() {
    const codes = [...new Set([...(metadata?.installed || ['en']), language])];
    const quickList = [
      ['en', 'English'],
      ['es', 'Español'],
      ['hi', 'हिन्दी'],
      ['fr', 'Français'],
      ['de', 'Deutsch'],
      ['ja', '日本語'],
      ['ar', 'العربية'],
      ['zh-CN', '简体中文']
    ];

    const currentTranslated = Object.entries(pack).filter(([source, value]) => source !== value).length;

    return `<section class="settings-section language-settings">
      ${importing ? scanIndicator('Working…', {feature:'settings',key:'translation'}) : ''}
      ${jobError ? `<div class="error-banner" role="alert">${esc(jobError)}</div>` : ''}
      <div class="settings-section-head">
        <div class="head-with-badge">
          <h2>${icon("file")} ${esc(t("Language / भाषा / Idioma"))}</h2>
          <span class="badge ${direction(language) === 'rtl' ? 'rtl-badge' : ''}">${direction(language).toUpperCase()}</span>
        </div>
        <p>${esc(t("Bundled language packs work offline. Import additional languages as JSON."))}</p>
      </div>

      <div class="quick-languages">
        <span class="quick-languages-label">${esc(t("Quick switch"))} / ${esc(t("Test language pack"))}:</span>
        <div class="chip-group">
          ${quickList.map(([c, n]) => `<button type="button" class="chip ${c === language ? 'active' : ''}" data-action="quick-language" data-code="${c}" data-no-translate>${n}</button>`).join('')}
        </div>
      </div>

      <div class="settings-row language-picker-row">
        <div>
          <h3>${esc(t("Interface language"))}</h3>
          <p>${language === 'en' ? esc(t("English source interface.")) : `${esc(t("Local pack"))}: ${currentTranslated}/${metadata?.messages || Object.keys(pack).length} · ${esc(t("Active language"))}: <strong>${esc(name(language))}</strong>`}</p>
        </div>
        <div class="language-dropdown-wrap">
          <select id="languageSelect" aria-label="${esc(t("Interface language"))}">
            ${codes.map(code => `<option value="${esc(code)}" ${code === language ? 'selected' : ''}>${esc(name(code))}${metadata?.installed.includes(code) ? ' · ' + esc(t('Local pack')) : ''}</option>`).join('')}
          </select>
          ${button(t('Apply language'), 'locale-apply', { style: 'primary' })}
        </div>
      </div>

      <details class="settings-accordion">
        <summary>${esc(t("Import or share an offline language pack"))}</summary>
        <p><span dir="ltr" data-no-translate style="font-family:ui-monospace,monospace;font-size:12px;opacity:0.8">JSON: &#123;&quot;locale&quot;:&quot;fr&quot;,&quot;messages&quot;:&#123;&quot;Settings&quot;:&quot;Paramètres&quot;&#125;&#125;</span><br>${esc(t("Only known interface messages are accepted; no HTML or code."))}</p>
        <input id="languagePackFile" type="file" accept=".json,application/json" aria-label="${esc(t("Language pack JSON"))}">
        <div class="language-actions" style="margin-top:10px">
          ${button(t('Import language pack'), 'locale-import')}
          ${button(t('Export current pack'), 'locale-export')}
          ${button(t('Download English template'), 'locale-template')}
        </div>
      </details>

    </section>`;
  }

  async function dispatch(action, el) {
    if (action === 'locale-import' && importing) return;
    if (action === 'quick-language') {
      const code = el?.dataset?.code;
      if (code) return activate(code);
      return;
    }
    const code = $('languageSelect')?.value || language;
    if (action === 'locale-apply') return activate(code);
    if (action === 'locale-import') {
      const file = $('languagePackFile').files[0];
      if (!file) throw new Error('Choose a JSON language pack.');
      if (file.size > 1500000) throw new Error('Language packs must be smaller than 1.5 MB.');
      const document = JSON.parse(await file.text());
      importing = true; jobError = '';
      try {
        const result = await api('/api/i18n/import', document);
        await refresh(result.locale);
      } finally { importing = false; draw(); updateActivityStatus(); }
      return;
    }
    const data = await api(action === 'locale-template' ? '/api/i18n/catalog' : '/api/i18n/pack?locale=' + encodeURIComponent(language));
    const blob = new Blob([JSON.stringify({ locale: data.locale, messages: data.messages }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url;
    link.download = `mac-cleaner-${data.locale}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function refresh(locale) {
    try { metadata = await api('/api/i18n'); } catch {}
    if (locale) await activate(locale);
  }

  async function init() {
    try { metadata = await api('/api/i18n'); } catch (e) { failure = e.message; }
    observer = new MutationObserver(() => {
      if (!pending) {
        pending = true;
        requestAnimationFrame(() => {
          pending = false;
          translateDOM();
        });
      }
    });
    try { await activate(metadata?.language || language, false); }
    catch (e) { failure = e.message; translateDOM(); }
  }

  document.addEventListener('input', event => {
    if (event.target.id !== 'languageSearch') return;
    const query = event.target.value.toLocaleLowerCase();
    for (const option of document.querySelectorAll('#languageSelect option')) {
      option.hidden = !option.textContent.toLocaleLowerCase().includes(query);
    }
  });

  set(language);
  return { t, set, activate, init, refresh, settings, dispatch, isRunning:() => importing, locale: () => language, translateDOM };
})();
