const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(fs.readFileSync('/tmp/mdc-care-check/launch-url','utf8'));
 await page.getByRole('heading',{name:'Large files map',exact:true}).waitFor();
 assert.equal(await page.locator('.care-treemap .tile').count(),6);
 await page.screenshot({path:'/tmp/mdc-care-check/overview-desktop.png'});
 await page.locator('[data-action="care-map-file"]').first().click();
 await page.getByRole('dialog').filter({has:page.getByText('Design archive.zip',{exact:true})}).waitFor();
 await page.locator('#confirmDialog [data-action="confirm"]').click();
 await page.locator('[data-action="care-profile"][data-profile="minimal"]').click();
 await page.waitForFunction(()=>selected.size===1&&view==='clean');
 await page.locator('[data-action="navigate"][data-view="care"]').click();
 await page.locator('[data-action="care-tab"][data-tab="history"]').click();
 await page.getByRole('button',{name:'Restore',exact:true}).click();
 await page.waitForFunction(()=>CareUI.isRunning()===false);
 await page.waitForFunction(()=>document.querySelector('.care-row small')?.textContent.toLowerCase().includes('restored'));
 await page.locator('[data-action="care-tab"][data-tab="startup"]').click();
 await page.locator('[data-action="care-inventory"]').click();
 await page.getByRole('heading',{name:'org.example.sync'}).waitFor();
 await page.locator('[data-action="care-startup"][data-enabled="false"]').click();
 await page.locator('#confirmDialog').getByText(/future launches/).waitFor();
 await page.locator('#confirmDialog').getByRole('button',{name:'Cancel',exact:true}).click();
 for(const tab of ['browsers','slimming','rules']) {
   await page.locator(`[data-action="care-tab"][data-tab="${tab}"]`).click();
   await page.screenshot({path:`/tmp/mdc-care-check/${tab}-desktop.png`});
 }
 const draft='{"rules": []}';await page.locator('#careRules').fill(draft);await page.evaluate(()=>draw());assert.equal(await page.locator('#careRules').inputValue(),draft);
 await page.locator('[data-action="care-rules"]').click();
 await page.waitForFunction(()=>!CareUI.isRunning());
 await page.locator('[data-action="navigate"][data-view="settings"]').click();
 assert.equal(await page.locator('#languageSelect option').count(),43);
 assert(await page.locator('#languageSelect').isVisible());
 await page.locator('#languageSelect').selectOption('ar');await page.locator('[data-action="locale-apply"]').click();
 await page.waitForFunction(()=>document.documentElement.dir==='rtl');
 await page.locator('[data-action="navigate"][data-view="care"]').click();
 await page.getByRole('heading',{name:'مركز الصيانة',exact:true}).waitFor();
 await page.locator('[data-action="care-tab"][data-tab="overview"]').click();
 await page.screenshot({path:'/tmp/mdc-care-check/arabic-desktop.png'});
 await page.locator('[data-action="navigate"][data-view="settings"]').click();
 await page.locator('#languageSelect').selectOption('ja');await page.locator('[data-action="locale-apply"]').click();
 await page.waitForFunction(()=>document.documentElement.lang==='ja'&&document.documentElement.dir==='ltr');
 await page.screenshot({path:'/tmp/mdc-care-check/japanese-settings.png'});
 await page.locator('#languageSelect').selectOption('en');await page.locator('[data-action="locale-apply"]').click();
 await page.waitForFunction(()=>document.documentElement.lang==='en');
 await page.locator('[data-action="navigate"][data-view="care"]').click();
 await page.locator('[data-action="care-tab"][data-tab="overview"]').click();
 const download=page.waitForEvent('download');await page.getByRole('link',{name:'Download HTML report'}).click();await (await download).saveAs('/tmp/mdc-care-check/report.html');
 assert(fs.readFileSync('/tmp/mdc-care-check/report.html','utf8').includes('v3.0.0'));
 for(const width of [900,700,390]){
  await page.setViewportSize({width,height:900});
  await page.screenshot({path:`/tmp/mdc-care-check/overview-${width}.png`});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`overflow at ${width}`);
 }
 assert.deepEqual(errors,[]);console.log('Care UI passed: profiles, restore, reviewed startup, rules, report, Arabic/Japanese localization, responsive layouts.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
