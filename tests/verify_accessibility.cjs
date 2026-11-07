/* WCAG checks on loaded features, forms and review dialogs in both themes. */
const {chromium}=require('playwright');
const AxeBuilder=require('@axe-core/playwright').default;
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true});
  try{
    const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    const page=await context.newPage();const errors=[],reports=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(fs.readFileSync('/tmp/mdc-workspace-check/launch-url','utf8'));
    await page.waitForFunction(()=>typeof ready!=='undefined'&&ready);
    async function audit(name){
      const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      reports.push({name,violations:result.violations.map(v=>({id:v.id,impact:v.impact,
        nodes:v.nodes.map(n=>({target:n.target,message:n.failureSummary}))}))});
    }
    for(const theme of ['dark','light']){
      await page.evaluate(theme=>applyTheme(theme),theme);
      for(const view of ['clean','apps','big','dups','optimize','disks','homebrew','settings']){
        await page.evaluate(view=>navigate(view),view);
        await page.waitForTimeout(150);
        await audit(`${theme}/${view}`);
      }
      await page.evaluate(()=>HistoryUI.open());
      await page.locator('.history-row').waitFor();
      await audit(`${theme}/cleanup-history`);
      await page.keyboard.press('Escape');
      await page.evaluate(()=>navigate('apps'));
      await page.locator('.app-card').first().click();
      await audit(`${theme}/application-details`);
      await page.locator('[data-action="app-clean"][data-mode="uninstall"]').click();
      await audit(`${theme}/uninstall-review`);
      await page.locator('#confirmDialog [data-action="cancel-confirm"]').last().click();
      await page.keyboard.press('Escape');
      await page.evaluate(()=>{navigate('clean');S.warnings=['/Users/example/Documents'];draw();});
      await page.locator('.scan-limits summary').click();
      await audit(`${theme}/scan-permissions`);
      await page.evaluate(()=>{S.warnings=[];});
    }
    fs.writeFileSync('/tmp/mdc-workspace-check/accessibility-report.json',JSON.stringify(reports,null,2));
    assert.deepEqual(reports.filter(r=>r.violations.length),[]);
    assert.deepEqual(errors,[]);
    console.log(`Accessibility passed: ${reports.length} WCAG audits across all workspaces, cleanup history, application details, uninstall reviews and permission notices in both themes.`);
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
