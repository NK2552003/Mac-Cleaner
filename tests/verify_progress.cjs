/* Hold real fixture responses to verify shared loading indicators and completion. */
const {chromium} = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true});
  const errors=[], evidence=[];
  let checked=0;
  try {
    const workspace=fs.readFileSync('/tmp/mdc-care-check/launch-url','utf8');
    async function start(url=workspace){
      const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
      const page=await context.newPage();
      page.on('pageerror',e=>errors.push(e.message));
      await page.goto(url);
      await page.waitForFunction(()=>typeof ready!=='undefined'&&ready);
      return page;
    }
    async function inspect(page,label){
      const indicator=page.locator('#main .scan-indicator').first();
      await indicator.waitFor();
      assert.notEqual(await page.locator('#status').innerText(),'Scan complete',`${label} must update the shared activity status`);
      assert.equal(await indicator.getAttribute('role'),'status');
      assert.equal(await indicator.locator('.scan-indicator-row > .i').count(),1);
      assert.equal(await indicator.locator('.scan-track > i').count(),1);
      assert.equal(await page.locator('.ghost-spinner,.ghost-progress progress,.scan-pill').count(),0);
      for(const theme of ['dark','light']) for(const width of [1440,390,320]){
        await page.setViewportSize({width,height:900});
        await page.evaluate(theme=>applyTheme(theme),theme);
        assert(await indicator.evaluate(el=>el.scrollWidth<=el.clientWidth+1),`${label} overflow at ${width}`);
        const box=await indicator.boundingBox();
        assert(box.width>100 && box.x>=0 && box.x+box.width<=width+1);
        if(width===390) await page.screenshot({path:`/tmp/mdc-care-check/progress-${label}-${theme}.png`});
        checked++;
      }
      const result=await new AxeBuilder({page}).include('.scan-indicator').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      evidence.push({label,violations:result.violations});
      assert.deepEqual(result.violations,[],`${label} accessibility`);
    }
    for(const view of ['clean','dups']){
      const page=await start();
      await page.evaluate(view=>{S.scanning=true;S.progress='Scanning in progress';navigate(view);},view);
      await inspect(page,view);
      await page.evaluate(()=>{S.scanning=false;draw();});
      assert.equal(await page.locator('#main .scan-indicator').count(),0);
      await page.close();
    }
    for(const [view,endpoint,refresh] of [
      ['apps','/api/apps',null],['big','/api/biggest',null],
      ['optimize','/api/health','[data-action="toolkit-refresh"]'],
      ['disks','/api/disks','[data-action="toolkit-refresh"]'],
      ['homebrew','/api/brew','[data-action="brew-refresh"]'],
      ['care','/api/care','[data-action="care-refresh"]']]){
      const page=await start();
      let release;
      let gate=new Promise(resolve=>{release=resolve});
      const hold=async route=>{await gate;await route.continue();};
      await page.route(`**${endpoint}`,hold);
      if(view==='homebrew') await page.route('**/api/brew/refresh',hold);
      await page.evaluate(view=>{navigate(view);},view);
      await inspect(page,view);
      release();
      await page.waitForFunction(()=>!document.querySelector('#main .scan-indicator'));
      if(refresh){
        gate=new Promise(resolve=>{release=resolve});
        await page.locator(refresh).first().click();
        await inspect(page,`${view}-refresh`);
        release();
        await page.waitForFunction(()=>!document.querySelector('#main .scan-indicator'));
      }
      // Fail a fresh inventory request and verify the loading state stops.
      if(refresh){
        await page.unroute(`**${endpoint}`,hold);
        await page.route(`**${endpoint}`,route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'Fixture inventory unavailable'})}));
        if(view==='homebrew'){
          await page.unroute('**/api/brew/refresh',hold);
          await page.route('**/api/brew/refresh',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'Fixture inventory unavailable'})}));
        }
        await page.locator(refresh).first().click();
        await page.locator('#main .error-banner').waitFor();
        assert.equal(await page.locator('#main .scan-indicator').count(),0);
      }
      await page.close();
    }
    const page=await start(fs.readFileSync('/tmp/mdc-ghost-check/launch-url','utf8'));
    await page.getByRole('switch',{name:'Ghost Files',exact:true}).click();
    await page.getByRole('button',{name:'Open Ghost Files',exact:true}).click();
    await page.locator('.ghost-heading').waitFor();
    const state=await page.evaluate(()=>api('/api/ghosts/state'));
    await page.route('**/api/ghosts/state',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({...state,scan:{...state.scan,done:false,msg:'Scanning in progress',pct:42}})}));
    await page.evaluate(()=>GhostUI.enter(true));
    await inspect(page,'ghosts');
    assert.equal(await page.locator('.scan-indicator [data-action="ghost-cancel"]').count(),1);
    assert.match(await page.locator('.scan-indicator').innerText(),/42%/);
    assert.equal(await page.locator('.scan-track i').first().evaluate(el=>el.style.width),'42%');
    await page.unroute('**/api/ghosts/state');
    await page.evaluate(()=>GhostUI.enter(true));
    await page.waitForFunction(()=>!document.querySelector('#main .scan-indicator'));
    await page.close();
    fs.writeFileSync('/tmp/mdc-care-check/progress-report.json',JSON.stringify(evidence,null,2));
    assert.deepEqual(errors,[]);
    console.log(`Progress passed: ${checked} theme/window checks across loading, report refreshes, Ghost percentage/cancel controls, completion and error states.`);
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
