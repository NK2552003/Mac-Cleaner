/* Isolated fixture checks: locale switching mechanics, dynamic text and overlays. */
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1200, height: 900}, reducedMotion: 'reduce'});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(fs.readFileSync('/tmp/mdc-workspace-check/launch-url', 'utf8'));
    await page.waitForFunction(() => typeof I18n !== 'undefined' && typeof S !== 'undefined' && S !== null);
    const directory = path.join(__dirname, '../mac_deep_cleaner/web/locales');
    const locales = fs.readdirSync(directory).filter(name => name.endsWith('.json')).map(name => name.slice(0, -5));
    assert.equal(locales.length, 42);
    for (const locale of locales) {
      const actual = await page.evaluate(async locale => {
        await I18n.activate(locale);
        const pack = await api('/api/i18n/pack?locale=' + locale);
        return {locale: I18n.locale(), lang: document.documentElement.lang,
          dir: document.documentElement.dir, expected: pack.messages.Settings,
          label: I18n.t('Settings'), saved: (await api('/api/i18n')).language};
      }, locale);
      assert.equal(actual.locale, locale);
      assert.equal(actual.lang, locale);
      assert.equal(actual.saved, locale);
      assert.equal(actual.label, actual.expected);
      assert.notEqual(actual.label, 'Settings');
      assert.equal(actual.dir, /^(ar|fa|he|ur)$/.test(locale) ? 'rtl' : 'ltr');
    }
    await page.evaluate(() => navigate('settings'));
    await page.evaluate(() => I18n.activate('fr'));
    assert.equal(await page.locator('#languageSelect').inputValue(), 'fr');
    await page.evaluate(() => I18n.activate('ja'));
    assert.equal(await page.locator('#languageSelect').inputValue(), 'ja');
    // Use deterministic test translations to isolate engine bugs from pack coverage.
    const packs = {
      fr: {Settings: 'Paramètres', 'Files inside folder ({0})': 'Fichiers dans le dossier ({0})',
        'Showing {count} files for {name}.': '{name} : {count} fichiers.', 'Close details': 'Fermer les détails'},
      ja: {Settings: '設定', 'Files inside folder ({0})': 'フォルダー内のファイル（{0}）', 'Close details': '詳細を閉じる'}
    };
    await page.route('**/api/i18n/pack?locale=*', async route => {
      const locale = new URL(route.request().url()).searchParams.get('locale');
      if (!packs[locale]) return route.continue();
      await route.fulfill({json: {locale, messages: packs[locale]}});
    });
    await page.evaluate(async () => {
      await I18n.activate('fr');
      const dialog = document.createElement('dialog');
      dialog.id = 'localizationTest';
      dialog.innerHTML = '<p id="dynamicMessage">Files inside folder (12)</p><button id="attrMessage" aria-label="Close details">Settings</button><code>Settings</code><span data-no-translate>Settings</span>';
      document.body.append(dialog); dialog.showModal(); I18n.translateDOM();
    });
    assert.equal(await page.locator('#dynamicMessage').textContent(), 'Fichiers dans le dossier (12)');
    assert.equal(await page.locator('#attrMessage').getAttribute('aria-label'), 'Fermer les détails');
    assert.equal(await page.evaluate(() => I18n.t('Showing {count} files for {name}.', {count: 12, name: 'My App'})), 'My App : 12 fichiers.');
    await page.evaluate(() => I18n.activate('ja'));
    assert.equal(await page.locator('#dynamicMessage').textContent(), 'フォルダー内のファイル（12）');
    assert.equal(await page.locator('#attrMessage').textContent(), '設定');
    assert.equal(await page.locator('#localizationTest code').textContent(), 'Settings');
    assert.equal(await page.locator('#localizationTest [data-no-translate]').textContent(), 'Settings');
    await page.evaluate(() => I18n.activate('en'));
    assert.equal(await page.locator('#dynamicMessage').textContent(), 'Files inside folder (12)');
    assert.equal(await page.locator('#attrMessage').getAttribute('aria-label'), 'Close details');
    await page.evaluate(() => { document.querySelector('#localizationTest').remove(); });
    await page.evaluate(async () => { await Promise.all([I18n.activate('fr'), I18n.activate('ja')]); });
    assert.equal(await page.evaluate(async () => [I18n.locale(), (await api('/api/i18n')).language].join(':')), 'ja:ja');
    await page.evaluate(() => I18n.activate('en'));

    await page.route('**/api/i18n/pack?locale=de', route => route.fulfill({status: 503, json: {error: 'Fixture pack failure'}}));
    assert.equal(await page.evaluate(async () => {
      try { await I18n.activate('de'); return false; } catch { return true; }
    }), true);
    assert.equal(await page.evaluate(async () => [I18n.locale(), (await api('/api/i18n')).language].join(':')), 'en:en');
    await page.goto(fs.readFileSync('/tmp/mdc-ghost-check/launch-url', 'utf8'));
    await page.waitForFunction(() => typeof S !== 'undefined' && S !== null);
    await page.evaluate(async () => {
      await I18n.activate('en');
      await api('/api/ghosts/config', {level: 1});
      await load(); navigate('ghosts');
    });
    await page.locator('.ghost-heading [data-action="ghost-scan"]').click();
    await page.locator('.ghost-card').first().waitFor();
    await page.waitForFunction(() => !S.busy);
    await page.locator('.ghost-card [data-action="ghost-inspect"]').first().click();
    await page.locator('#ghostDrawerContent .ghost-detail-section').first().waitFor();
    assert.equal(await page.locator('#ghostDrawerContent .ghost-drawer-card').count(), 0);
    const style = await page.locator('.ghost-detail-section').first().evaluate(element => {
      const css = getComputedStyle(element);
      return {shadow: css.boxShadow, background: css.backgroundColor, radius: css.borderRadius,
        gap: getComputedStyle(element.parentElement).gap};
    });
    assert.equal(style.shadow, 'none'); assert.equal(style.radius, '0px');
    assert.equal(style.background, 'rgba(0, 0, 0, 0)'); assert.equal(style.gap, '24px');
    for (const width of [1200, 390]) {
      await page.setViewportSize({width, height: 900});
      await page.screenshot({path: `/tmp/mdc-ghost-check/inspector-cardless-${width}.png`});
      assert(await page.locator('#detailDialog').evaluate(el => el.scrollWidth <= el.clientWidth + 1));
    }
    assert.deepEqual(errors, []);
    console.log('Passed: all 42 locale selections/persistence/directions; dynamic placeholders; live overlay switching; English restoration; language races; cardless Ghost inspector.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
