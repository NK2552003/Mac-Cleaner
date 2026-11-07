/* Shared history and language controls survive removal of the Care workspace. */
const {chromium,webkit}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await (process.env.MDC_TEST_BROWSER==='webkit'?webkit:chromium).launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1200,height:900},reducedMotion:'reduce'});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(fs.readFileSync('/tmp/mdc-workspace-check/launch-url','utf8'));
    await page.waitForFunction(()=>typeof ready!=='undefined'&&ready);
    await page.evaluate(()=>navigate('settings'));
    await page.getByText('Import or share an offline language pack',{exact:true}).click();
    await page.locator('#languagePackFile').setInputFiles({name:'fixture-fr.json',mimeType:'application/json',
      buffer:Buffer.from(JSON.stringify({locale:'fr',messages:{Settings:'Options de test'}}))});
    const imported=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/i18n/import');
    await page.locator('[data-action="locale-import"]').click();
    assert.equal((await imported).status(),200);
    await page.waitForFunction(()=>!I18n.isRunning()&&I18n.locale()==='fr');
    assert.equal(await page.evaluate(()=>view),'settings');
    assert.equal(await page.evaluate(()=>I18n.t('Settings')),'Options de test');
    await page.evaluate(()=>I18n.activate('en'));
    assert.equal(await page.locator('#translationKey,[data-action="locale-generate"]').count(),0);
    assert.equal(await page.locator('[data-view="care"]').count(),0);
    await page.locator('#automationIntervalControl').click();
    await page.getByRole('option',{name:'12 hours',exact:true}).click();
    await page.locator('[data-action="background-interval"]').click();
    await page.waitForFunction(()=>S.settings.automation_hours===12);
    await page.locator('[data-action="background-toggle"][data-setting="automation_enabled"]').click();
    await page.waitForFunction(()=>S.settings.automation_enabled);
    assert(await page.evaluate(()=>S.settings.automation_next_run > Date.now()/1000));
    await page.locator('[data-action="background-toggle"][data-setting="automation_enabled"]').click();
    await page.waitForFunction(()=>!S.settings.automation_enabled);
    let checks=0, updateState=null;
    await page.route('**/api/background',async route=>{
      const response=await route.fetch();const body=await response.json();
      return route.fulfill({json:updateState?{...body,updates:updateState}:body});
    });
    await page.route('**/api/updates/check',route=>{checks++;updateState={checking:false,checked_at:Date.now()/1000,available:true,latest:'v9.0.0',url:'https://github.com/NK2552003/Mac-Cleaner/releases/tag/v9.0.0'};return route.fulfill({json:updateState});});
    await page.locator('[data-action="background-update"]').click();
    await page.getByText('Update available',{exact:false}).waitFor();
    assert.equal(checks,1);
    assert.equal(await page.getByRole('link',{name:'View release on GitHub'}).getAttribute('href'),'https://github.com/NK2552003/Mac-Cleaner/releases/tag/v9.0.0');
    // Exercise the native permission/message contract without requesting host permissions.
    await page.evaluate(()=>{
      window.nativeMessages=[];
      Object.defineProperty(window,'webkit',{configurable:true,value:{messageHandlers:{notifications:{postMessage:payload=>nativeMessages.push(payload)}}}});
      draw();
    });
    await page.locator('[data-action="background-notifications"]').click();
    assert(await page.evaluate(()=>nativeMessages.some(m=>m.action==='authorize')));
    await page.evaluate(()=>BackgroundUI.authorization('Disabled in System Settings',true));
    assert.equal(await page.evaluate(()=>S.settings.notifications),false);
    await page.evaluate(()=>BackgroundUI.authorization('Enabled',true));
    assert.equal(await page.evaluate(()=>S.settings.notifications),true);
    await page.locator('[data-action="background-test"]').click();
    assert(await page.evaluate(()=>nativeMessages.some(m=>m.action==='test')));
    await page.evaluate(()=>MDCNative.safeClean());
    const job=await page.evaluate(async()=>{
      for(let attempt=0;attempt<100;attempt++) {
        const job=(await api('/api/background')).automation;
        if(!job.running&&job.last_run>0) return job;
        await new Promise(resolve=>setTimeout(resolve,100));
      }
      throw new Error('Cleanup did not complete');
    });
    assert.equal(job.error,'');
    assert(job.result, JSON.stringify({job,toasts:await page.locator('#toasts').innerText()}));
    assert(job.result.results.some(r=>r.ok&&r.name==='Idle cache'));
    assert.equal(await page.evaluate(()=>selected.size),0);
    await page.evaluate(()=>BackgroundUI.poll());
    await page.waitForFunction(()=>nativeMessages.some(m=>m.action==='deliver'&&m.title==='Cleanup'));
    await page.evaluate(()=>BackgroundUI.poll());
    assert.equal(await page.evaluate(()=>nativeMessages.filter(m=>m.action==='deliver').length),1);
    await page.screenshot({path:'/tmp/mdc-workspace-check/storage-without-care.png'});
    await page.evaluate(()=>{applyTheme('light');document.querySelector('#main').scrollTop=350;});
    await page.screenshot({path:'/tmp/mdc-workspace-check/automation-light.png'});
    await page.evaluate(()=>HistoryUI.open());
    await page.locator('.history-row').first().waitFor();
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'/tmp/mdc-workspace-check/history-mobile.png'});
    assert.deepEqual(errors,[]);
    console.log('Support passed: offline language import, saved interval and schedule toggle, GitHub release link, actual safe Trash cleanup, native notification permission/test/completion bridge, no cloud controls.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
