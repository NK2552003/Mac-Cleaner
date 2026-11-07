/* Run against workspace_fixture.py. All operations use temporary files/fake runners. */
const {chromium} = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(fs.readFileSync('/tmp/mdc-workspace-check/launch-url','utf8'));
    await page.waitForFunction(() => typeof ready !== 'undefined' && ready);
    await page.locator('#itemSearch').fill('Build');
    await page.locator('#sizeFilter').selectOption('100');
    await page.locator('#categoryFilter').selectOption('App Caches');
    const scroll = await page.locator('#main').evaluate(el => {el.scrollTop=300;return el.scrollTop;});
    await page.evaluate(() => navigate('dups'));
    await page.locator('#duplicateSearch').fill('Copy');
    await page.goBack();
    await page.waitForFunction(() => view === 'clean');
    assert.equal(await page.locator('#itemSearch').inputValue(),'Build');
    assert.equal(await page.locator('#sizeFilter').inputValue(),'100');
    assert.equal(await page.locator('#categoryFilter').inputValue(),'App Caches');
    assert.match(await page.locator('#categoryFilterControl').innerText(),/App Caches/);
    assert.equal(await page.locator('#main').evaluate(el => el.scrollTop),scroll);
    await page.goForward();
    await page.waitForFunction(() => view === 'dups');
    assert.equal(await page.locator('#duplicateSearch').inputValue(),'Copy');
    assert.equal(await page.locator('[data-view="care"]').count(),0);
    assert.equal(await page.locator('script[src*="care.js"],link[href*="care.css"]').count(),0);
    const legacy=await page.context().newPage();
    await legacy.goto(page.url().split('#')[0]+'#care/media');
    await legacy.waitForFunction(()=>typeof ready!=='undefined'&&ready);
    assert.equal(new URL(legacy.url()).hash,'#clean');
    await legacy.close();
    await page.evaluate(()=>navigate('settings'));
    await page.locator('details').filter({has:page.locator('#translationKey')}).locator('summary').click();
    await page.locator('#translationKey').fill('fixture-draft');
    await page.locator('#translationLanguage').selectOption('fr');
    await page.evaluate(()=>navigate('apps'));
    await page.locator('.app-card').waitFor();
    await page.evaluate(()=>navigate('settings'));
    assert.equal(await page.locator('#translationKey').inputValue(),'');
    assert.equal(await page.locator('#translationLanguage').inputValue(),'fr');
    await page.evaluate(()=>navigate('clean',{reset:true}));
    await page.getByRole('button',{name:'Cleanup history',exact:true}).click();
    await page.locator('.history-row').waitFor();
    assert.match(await page.locator('.cleanup-history').innerText(),/Restorable cache/);
    await page.keyboard.press('Escape');
    await page.evaluate(() => navigate('homebrew'));
    await page.locator('.brew-package-link').first().waitFor();
    let release, intercepted;
    const held = new Promise(resolve => {release=resolve;});
    const received = new Promise(resolve => {intercepted=resolve;});
    await page.route('**/api/brew/explain?*', async route => {intercepted();await held;await route.continue();});
    const response=page.waitForResponse(r => new URL(r.url()).pathname === '/api/brew/explain');
    await page.locator('.brew-package-link').first().click();
    await received;
    await page.evaluate(() => navigate('disks'));
    release();
    await response;
    await page.locator('.disk-device-list').waitFor();
    assert.equal(await page.locator('#detailDialog').evaluate(el => el.open),false);
    assert.deepEqual(await page.locator('.disk-choice').evaluateAll(els => els.map(el => el.dataset.target).sort()),['disk1s2s1','disk9s1']);
    await page.locator('.disk-choice[data-target="disk9s1"]').click();
    assert.equal(await page.locator('[data-action="toolkit-disk-action"][data-tool="erase"]').getAttribute('data-target'),'disk8');
    assert.equal(await page.getByRole('button',{name:/Show system volumes/}).count(),0);
    await page.getByRole('switch',{name:'Developer mode',exact:true}).click();
    await page.getByRole('button',{name:/Show system volumes/}).click();
    assert(await page.locator('.disk-choice').count() > 2);
    await page.getByRole('switch',{name:'Developer mode',exact:true}).click();
    await page.waitForFunction(() => mode === 'normal');
    assert.equal(await page.locator('.disk-choice').count(),2);
    // Disabled custom-select options must not receive keyboard selection.
    await page.evaluate(() => {
      const select=document.createElement('select');select.id='keyboardFixture';
      select.innerHTML='<option value="a">Alpha</option><option value="b" disabled>Beta</option><option value="c">Gamma</option>';
      document.querySelector('#main').prepend(select);Dropdowns.enhance(document.querySelector('#main'));
    });
    await page.locator('#keyboardFixtureControl').click();
    await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');
    assert.equal(await page.locator('#keyboardFixture').inputValue(),'c');
    await page.evaluate(() => navigate('clean',{reset:true}));
    const views=['clean','apps','big','dups','optimize','disks','homebrew','settings'];
    let checks=0;
    for (const locale of ['en','ar']) {
      await page.evaluate(locale => I18n.activate(locale),locale);
      for (const theme of ['dark','light']) for (const [width,height] of [[1440,900],[390,844],[320,740],[740,320]]) {
        await page.setViewportSize({width,height});
        await page.evaluate(theme => applyTheme(theme),theme);
        for (const target of views) {
          await page.evaluate(target => navigate(target),target);
          const overflow=await page.locator('#main').evaluate(main => {
            const box=main.getBoundingClientRect();
            return [...main.querySelectorAll('*')].filter(el => {
              if (el.closest('details:not([open])') && !el.closest('summary')) return false;
              const r=el.getBoundingClientRect();
              return r.width>0 && getComputedStyle(el).visibility!=='hidden' && (r.right>box.right+1 || r.left<box.left-1);
            }).map(el => el.tagName+'.'+el.className).slice(0,6);
          });
          assert.deepEqual(overflow,[],`${target}, ${locale}, ${theme}, ${width}x${height}`);
          checks++;
        }
      }
    }
    assert.deepEqual(errors,[]);
    console.log(`Workspace passed: filters/back-forward, settings drafts, history access, removed Care links, stale inspector, disk visibility/drive actions, dropdown keyboard, ${checks} theme/locale/layout views.`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exit(1);});
