/* Hold real fixture responses to verify shared loading indicators and completion. */
const {chromium,webkit} = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async()=>{
  const engine=process.env.MDC_TEST_BROWSER || 'chromium';
  assert(['chromium','webkit'].includes(engine));
  const browser=await ({chromium,webkit}[engine]).launch({headless:true});
  const errors=[], evidence=[];
  let checked=0;
  try {
    const workspace=fs.readFileSync('/tmp/mdc-workspace-check/launch-url','utf8');
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
      assert.equal(await page.locator('#main .brand-loader').count(),1,`${label} must have one loader`);
      assert.equal(await indicator.locator('svg.loader-visual').count(),1);
      assert.equal(await indicator.getAttribute('data-feature'),label.replace('-refresh',''));
      assert.equal(await page.locator('.scan-track,.scan-banner,.ghost-spinner,.ghost-progress progress,.scan-pill,.skeleton').count(),0);
      await page.emulateMedia({reducedMotion:'no-preference'});
      const before=await page.evaluate(()=>{
        LoaderUI.sync();
        const animation=document.querySelector('#main .loader-orbit').getAnimations()[0];
        const blink=document.querySelector('#main .loader-blink').getAnimations()[0];
        return {start:animation.startTime,time:animation.currentTime,state:animation.playState,blinkStart:blink.startTime,blinkTime:blink.currentTime};
      });
      assert.equal(before.state,'running');
      await page.waitForTimeout(100);
      const after=await page.evaluate(()=>{
        draw();
        const animation=document.querySelector('#main .loader-orbit').getAnimations()[0];
        const blink=document.querySelector('#main .loader-blink').getAnimations()[0];
        return {start:animation.startTime,time:animation.currentTime,blinkStart:blink.startTime,blinkTime:blink.currentTime};
      });
      assert.equal(after.start,before.start,`${label} must retain its animation clock across redraws`);
      assert(after.time>before.time+50,`${label} animation must keep advancing`);
      assert.equal(after.blinkStart,before.blinkStart,`${label} blinking must retain its clock across redraws`);
      assert(after.blinkTime>before.blinkTime+50,`${label} blinking must keep advancing`);
      const eyes=await indicator.locator('.loader-blink').evaluate(el=>{
        const animation=el.getAnimations()[0];
        animation.pause();
        const sample=fraction=>{
          animation.currentTime=animation.effect.getTiming().duration*fraction;
          return new DOMMatrix(getComputedStyle(el).transform).d;
        };
        const result={open:sample(0),closed:sample(.16),reopened:sample(.5)};
        animation.play();
        return result;
      });
      assert(eyes.open>.99 && eyes.closed<.1 && eyes.reopened>.99,'Eyes must close briefly and reopen');
      assert.equal(await indicator.locator('.loader-nose').evaluate(el=>getComputedStyle(el).transform),'none','Blinking must not squash the nose');
      assert.equal(await indicator.locator('.loader-orbit').evaluate(el=>getComputedStyle(el).animationTimingFunction),'linear');
      if(label==='clean') {
        // Observe a real blink under repeated polling, then compare rendered frames.
        await page.evaluate(()=>{ draw(); window.blinkRedraw=setInterval(()=>draw(),140); });
        try {
          await page.waitForFunction(()=>Number(getComputedStyle(document.querySelector('.loader-eyelids')).opacity)>.9, null, {timeout:1800});
        } finally { await page.evaluate(()=>clearInterval(window.blinkRedraw)); }
        const avatar=indicator.locator('.loader-visual');
        await avatar.evaluate(el=>el.getAnimations({subtree:true}).forEach(a=>{a.pause();a.currentTime=0;}));
        const opened=await avatar.screenshot({path:`/tmp/mdc-workspace-check/blink-${engine}-open.png`});
        await avatar.evaluate(el=>el.querySelectorAll('.loader-blink,.loader-eyelids').forEach(g=>{const a=g.getAnimations()[0];a.currentTime=a.effect.getTiming().duration*.16;}));
        const closed=await avatar.screenshot({path:`/tmp/mdc-workspace-check/blink-${engine}-closed.png`});
        assert(!opened.equals(closed),'Blinking must visibly change rendered SVG pixels');
        await avatar.evaluate(el=>el.querySelectorAll('.loader-blink,.loader-eyelids').forEach(g=>{const a=g.getAnimations()[0];a.currentTime=a.effect.getTiming().duration*.5;}));
        const reopened=await avatar.screenshot();
        assert(opened.equals(reopened),'Eyes must render fully open again after a blink');
      }
      await page.emulateMedia({reducedMotion:'reduce'});
      assert.equal(await indicator.locator('.loader-orbit').evaluate(el=>el.getAnimations().length),0,'Reduced motion must stop decorative animation');
      assert.equal(await indicator.locator('.loader-blink').evaluate(el=>el.getAnimations().length),0,'Reduced motion must stop blinking');
      for(const theme of ['dark','light']) for(const width of [1440,390,320]){
        await page.setViewportSize({width,height:900});
        await page.evaluate(theme=>applyTheme(theme),theme);
        assert(await indicator.evaluate(el=>el.scrollWidth<=el.clientWidth+1),`${label} overflow at ${width}`);
        if(await indicator.evaluate(el=>el.classList.contains('is-centered'))) {
          const visual=await indicator.locator('.loader-visual').boundingBox();
          const copy=await indicator.locator('.loader-copy').boundingBox();
          assert(copy.y>=visual.y+visual.height,`${label} content must sit below the mascot`);
          assert(Math.abs((visual.x+visual.width/2)-(copy.x+copy.width/2))<2,`${label} content must be centered`);
          assert.equal(await indicator.evaluate(el=>getComputedStyle(el).textAlign),'center');
        }
        const box=await indicator.boundingBox();
        assert(box.width>100 && box.x>=0 && box.x+box.width<=width+1);
        if(width===390) await page.screenshot({path:`/tmp/mdc-workspace-check/progress-${engine}-${label}-${theme}.png`});
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
      if(view==='clean'){
        assert.equal(await page.locator('.overview .brand-loader').count(),1,'Storage loader belongs inside its overview card');
        await page.evaluate(()=>{S.items=[];draw();});
        assert.equal(await page.locator('#main .brand-loader').count(),1,'An empty scan must not add a second loader');
        assert.equal(await page.locator('.overview .brand-loader.is-centered').count(),1);
      }
      if(view==='dups') {
        await page.evaluate(()=>{S.items=[];draw();});
        assert.equal(await page.locator('#main .brand-loader.is-centered').count(),1);
      }
      await page.evaluate(()=>{S.scanning=false;draw();});
      assert.equal(await page.locator('#main .scan-indicator').count(),0);
      await page.emulateMedia({reducedMotion:'no-preference'});
      const emptyMascot=page.locator('#main .empty > .loader-visual.is-still');
      assert.equal(await emptyMascot.count(),1,'Completed empty results must retain the mascot');
      assert.equal(await emptyMascot.evaluate(el=>el.getAnimations({subtree:true}).length),0,'Completed empty results must not look like an ongoing scan');
      const visual=await emptyMascot.boundingBox();
      const title=await page.locator('#main .empty > h3').boundingBox();
      assert(title.y>=visual.y+visual.height);
      assert(Math.abs((visual.x+visual.width/2)-(title.x+title.width/2))<2,'Empty-state text must be centered below its mascot');
      await page.close();
    }
    for(const [view,endpoint,refresh] of [
      ['apps','/api/apps',null],['big','/api/biggest',null],
      ['optimize','/api/health','[data-action="toolkit-refresh"]'],
      ['disks','/api/disks','[data-action="toolkit-refresh"]'],
      ['homebrew','/api/brew','[data-action="brew-refresh"]']]){
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
    assert.equal(await page.locator('.loader-value').innerText(),'42%');
    await page.unroute('**/api/ghosts/state');
    await page.route('**/api/ghosts/state',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({...state,ghosts:[],scan:{...state.scan,done:false,msg:'Scanning in progress',pct:42}})}));
    await page.evaluate(()=>GhostUI.enter(true));
    assert.equal(await page.locator('#main .brand-loader').count(),1);
    assert.equal(await page.locator('#main .brand-loader.is-centered').count(),1,'An empty Ghost scan must center its mascot');
    assert.equal(await page.locator('#ghostCardsContainer .empty').count(),0,'Ghost scans must not show a second empty state');
    await page.unroute('**/api/ghosts/state');
    await page.evaluate(()=>GhostUI.enter(true));
    await page.waitForFunction(()=>!document.querySelector('#main .scan-indicator'));
    await page.close();
    fs.writeFileSync(`/tmp/mdc-workspace-check/progress-${engine}-report.json`,JSON.stringify(evidence,null,2));
    assert.deepEqual(errors,[]);
    console.log(`Progress (${engine}) passed: ${checked} theme/window checks across loading, report refreshes, Ghost percentage/cancel controls, single-loader placement, uninterrupted orbit/blink clocks, visible blinking frames, centered empty states, reduced motion, completion and error states.`);
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
