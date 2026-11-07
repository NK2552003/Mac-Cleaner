/* Uses --deletion workspace fixture only. Verify real bytes, not just UI success. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    const page=await context.newPage();
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(fs.readFileSync('/tmp/mdc-workspace-check/launch-url','utf8'));
    await page.waitForFunction(()=>typeof ready!=='undefined'&&ready);
    const items=await page.evaluate(()=>S.items);
    for(const item of items) assert.match(item.path,/\/mdc-workspace-ui-[^/]+\//,'Only disposable fixture files are permitted');
    const find=name=>{const item=items.find(item=>item.name===name);assert(item,name);return item;};
    const submit=async()=>{
      const response=page.waitForResponse(r=>['/api/clean','/api/app/clean'].includes(new URL(r.url()).pathname)&&r.request().method()==='POST');
      await page.locator('#confirmDialog [data-action="confirm"]').click();
      const result=await response;assert.equal(result.status(),200);
      await page.waitForFunction(()=>!busy);
      assert.equal(await page.locator('#toasts .toast:not(.error)').count(),0,
        'Outdated success notices must not cover the persistent cleanup report');
      return result.json();
    };
    const review=async item=>{
      await page.evaluate(()=>{selected.clear();navigate('clean',{reset:true,minmb:0});});
      await page.locator(`#main input[data-select="${item.id}"]`).check();
      await page.locator('#selection [data-action="review"]').click();
      await page.locator('#confirmDialog').waitFor();
    };
    const trash=find('Trash');
    await page.locator('[data-action="select-safe"]').click();
    assert(!await page.evaluate(id=>selected.has(id),trash.id),'Select safe must exclude Trash');
    await review(trash);
    assert(await page.locator('#confirmDialog [data-action="confirm"]').isDisabled());
    await page.locator('#confirmPhrase').fill('wrong');
    assert(await page.locator('#confirmDialog [data-action="confirm"]').isDisabled());
    await page.locator('#confirmDialog [data-action="cancel-confirm"]').last().click();
    assert(fs.readdirSync(trash.path).length>0,'Cancel must preserve Trash');
    await review(trash);await page.locator('#confirmPhrase').fill('DELETE');
    assert.deepEqual((await submit()).fails,[]);
    assert.deepEqual(fs.readdirSync(trash.path),[],'Trash contents must actually be gone');

    const cache=find('Build cache');const content=fs.readFileSync(cache.path);
    await review(cache);
    await page.locator('#confirmDialog [data-action="cancel-confirm"]').last().click();
    assert.deepEqual(fs.readFileSync(cache.path),content,'Cancel must preserve file bytes');
    await review(cache);const cleaned=await submit();assert.deepEqual(cleaned.fails,[]);
    assert(!fs.existsSync(cache.path));
    assert.equal(cleaned.results.filter(r=>r.ok).length,1);
    await page.locator('.cleanup-result').getByRole('link',{name:'Cleanup history',exact:true}).click();
    await page.locator('[data-action="history-restore"]:enabled').click();
    await page.waitForFunction(()=>!HistoryUI.isRunning());
    assert.deepEqual(fs.readFileSync(cache.path),content,'Restore must return identical bytes');

    const duplicate=find('Copy.txt');const original=duplicate.keep;
    const originalContent=fs.readFileSync(original);
    await review(duplicate);assert.deepEqual((await submit()).fails,[]);
    assert(!fs.existsSync(duplicate.path));assert.deepEqual(fs.readFileSync(original),originalContent);

    await page.evaluate(()=>navigate('apps'));
    await page.locator('.app-card').first().click();
    const application=await page.evaluate(()=>A.apps[0]);
    const appFile=application.path+'/Contents/executable';
    const appContent=fs.readFileSync(appFile),appCache=application.parts[0].path;
    await page.locator('[data-action="app-clean"][data-mode="caches"]').click();
    assert.deepEqual((await submit()).fails,[]);
    assert(!fs.existsSync(appCache));assert.deepEqual(fs.readFileSync(appFile),appContent);
    await page.locator('.app-card').first().click();
    await page.locator('[data-action="app-clean"][data-mode="uninstall"]').click();
    assert.deepEqual((await submit()).fails,[]);
    assert(!fs.existsSync(application.path));
    const appHistory=await page.evaluate(async path=>(await api('/api/history')).history.find(r=>r.original===path),application.path);
    assert(appHistory.available);assert.deepEqual(fs.readFileSync(appHistory.trash+'/Contents/executable'),appContent);

    const permanent=find('Installer.dmg');
    await review(permanent);await page.locator('#permanent').check();
    assert(await page.locator('#confirmDialog [data-action="confirm"]').isDisabled());
    await page.locator('#confirmPhrase').fill('DELETE');
    assert.deepEqual((await submit()).fails,[]);assert(!fs.existsSync(permanent.path));
    assert(!await page.evaluate(async path=>(await api('/api/history')).history.some(r=>r.original===path),permanent.path));

    const changed=find('Vacation photo.jpg');
    await review(changed);fs.writeFileSync(changed.path,'New content after review: preserve this.');
    const failure=await submit();assert.equal(failure.fails.length,1);
    assert.equal(fs.readFileSync(changed.path,'utf8'),'New content after review: preserve this.');
    await page.locator('.cleanup-result.has-failures').waitFor();
    assert.match(await page.locator('.cleanup-result.has-failures').innerText(),/item changed since the scan/);
    await page.screenshot({path:'/tmp/mdc-workspace-check/cleanup-failure-desktop.png'});
    for(const theme of ['dark','light'])for(const width of [1440,390,320]){
      await page.setViewportSize({width,height:900});await page.evaluate(theme=>applyTheme(theme),theme);
      assert(await page.locator('.cleanup-result').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
      if(width===390)await page.screenshot({path:`/tmp/mdc-workspace-check/cleanup-results-${theme}-mobile.png`});
    }
    assert.deepEqual(errors,[]);
    console.log('Deletion passed: cancel/typed Trash emptying, exact-byte Trash/restore, duplicate keeper, actual app-cache cleanup/uninstall, permanent deletion, changed-file refusal and durable failure feedback.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
