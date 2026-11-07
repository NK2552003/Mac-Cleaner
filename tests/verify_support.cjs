/* Shared history and language controls survive removal of the Care workspace. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true});
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
    let running=true,submitted=false;
    await page.route('**/api/i18n/generate',route=>{submitted=true;return route.fulfill({json:{started:true}});});
    await page.route('**/api/i18n/job',route=>route.fulfill({json:{done:!running,message:'Working…',error:running?'':'Fixture translation failure',result:null}}));
    await page.locator('details').filter({has:page.locator('#translationKey')}).locator('summary').click();
    await page.locator('#translationKey').fill('fixture-only');
    await page.locator('[data-action="locale-generate"]').click();
    await page.locator('#confirmDialog [data-action="confirm"]').click();
    await page.locator('.language-settings .brand-loader').waitFor();
    assert(submitted);
    assert.equal(await page.evaluate(()=>view),'settings');
    assert.equal(await page.locator('#translationKey').inputValue(),'');
    await page.evaluate(()=>draw());
    assert.equal(await page.locator('.language-settings .brand-loader').count(),1);
    running=false;
    await page.waitForFunction(()=>!I18n.isRunning());
    await page.getByText('Fixture translation failure',{exact:true}).waitFor();
    assert.equal(await page.locator('.language-settings .brand-loader').count(),0);
    assert.equal(await page.locator('[data-view="care"]').count(),0);
    await page.evaluate(()=>navigate('clean'));
    await page.evaluate(()=>MDCNative.safeClean());
    assert(await page.evaluate(()=>selected.size>0));
    assert.equal(await page.evaluate(()=>view),'clean');
    await page.screenshot({path:'/tmp/mdc-workspace-check/storage-without-care.png'});
    await page.evaluate(()=>HistoryUI.open());
    await page.locator('.history-row').waitFor();
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'/tmp/mdc-workspace-check/history-mobile.png'});
    assert.deepEqual(errors,[]);
    console.log('Support passed: language import, Settings-only generation/error feedback, cleared key, single loader, native safe-item selection, no Care navigation.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
