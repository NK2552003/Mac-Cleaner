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
    await page.goto(fs.readFileSync('/tmp/mdc-care-check/launch-url','utf8'));
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
    await page.getByRole('link',{name:'Similar media',exact:true}).click();
    await page.locator('.media-pair').waitFor();
    assert.equal(new URL(page.url()).hash,'#care/media');
    // Direct Care links survive loading and another reload without losing the tab.
    const direct=await page.context().newPage();
    await direct.goto(page.url());
    await direct.locator('.media-pair').waitFor();
    assert.equal(new URL(direct.url()).hash,'#care/media');
    await direct.reload();
    await direct.locator('.media-pair').waitFor();
    await direct.close();
    const reveal = page.waitForResponse(r => new URL(r.url()).pathname === '/api/reveal');
    await page.getByRole('button',{name:'Show first',exact:true}).click();
    assert.equal((await reveal).status(),200);
    await page.locator('[data-tab="rules"]').click();
    const draft='{"rules": []}\n';
    await page.locator('#careRules').fill(draft);
    await page.locator('[data-tab="overview"]').click();
    await page.locator('#careHour').selectOption('17');
    await page.locator('#careWeekday').selectOption('4');
    await page.evaluate(() => navigate('apps'));
    await page.locator('.app-card').waitFor();
    await page.getByRole('link',{name:'App slimming',exact:true}).click();
    await page.locator('#careLanguages').fill('en, fr');
    await page.locator('[data-tab="rules"]').click();
    assert.equal(await page.locator('#careRules').inputValue(),draft);
    await page.locator('[data-tab="overview"]').click();
    assert.equal(await page.locator('#careHour').inputValue(),'17');
    assert.equal(await page.locator('#careWeekday').inputValue(),'4');
    assert.match(await page.locator('#careWeekdayControl').innerText(),/Thursday/);
    assert.match(await page.locator('#careHourControl').innerText(),/17:00/);
    assert.equal(await page.locator('.care-schedule-inline').getByText('Day',{exact:true}).count(),0);
    assert.equal(await page.locator('.care-schedule-inline').getByText('Hour',{exact:true}).count(),0);
    assert.equal(await page.getByRole('combobox',{name:'Day',exact:true}).count(),1);
    assert.equal(await page.getByRole('combobox',{name:'Hour',exact:true}).count(),1);
    await page.locator('[data-action="care-map-file"]').first().click();
    const mapReveal=page.waitForResponse(r => new URL(r.url()).pathname === '/api/reveal');
    await page.locator('#confirmDialog [data-action="reveal"]').click();
    assert.equal((await mapReveal).status(),200);
    const originalTitle=await page.locator('#confirmTitle').innerText();
    assert.equal(await page.evaluate(async () => (await ask({title:'Overlapping review',body:'',confirm:'Confirm'})).confirmed),false);
    assert.equal(await page.locator('#confirmTitle').innerText(),originalTitle);
    await page.locator('#confirmDialog [data-action="confirm"]').click();
    await page.locator('[data-action="care-profile"][data-profile="minimal"]').click();
    await page.waitForFunction(() => view === 'clean' && selected.size === 1);
    assert.equal(await page.locator('#itemSearch').inputValue(),'');
    assert.equal(await page.locator('#sizeFilter').inputValue(),'0');
    assert.equal(await page.locator('#categoryFilter').inputValue(),'');
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
    const views=['clean','apps','big','dups','optimize','disks','homebrew','care','settings'];
    let checks=0;
    for (const locale of ['en','ar']) {
      await page.evaluate(locale => I18n.activate(locale),locale);
      for (const theme of ['dark','light']) for (const [width,height] of [[1440,900],[390,844],[320,740],[740,320]]) {
        await page.setViewportSize({width,height});
        await page.evaluate(theme => applyTheme(theme),theme);
        for (const target of views) {
          await page.evaluate(target => navigate(target,{tab:target==='care'?'overview':undefined}),target);
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
    // Every Care tab has a usable narrow layout, including the accessible table.
    await page.setViewportSize({width:320,height:740});
    for (const tab of ['overview','history','media','startup','browsers','slimming','rules']) {
      await page.evaluate(tab => navigate('care',{tab}),tab);
      await page.locator('#main details').evaluateAll(els => els.forEach(el => el.open=true));
      assert(await page.locator('#main').evaluate(el => el.scrollWidth<=el.clientWidth+1),`Care ${tab} overflow`);
    }
    assert.deepEqual(errors,[]);
    console.log(`Workspace passed: filters/back-forward, drafts, Finder links, review guard, profile handoff, stale inspector, disk visibility/drive actions, dropdown keyboard, ${checks} theme/locale/layout views and seven Care tabs.`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exit(1);});
