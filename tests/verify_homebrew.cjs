/* Fixture-only UI regressions. No host Homebrew or disk mutations are executed. */
const {chromium} = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(fs.readFileSync('/tmp/mdc-ui-check/launch-url','utf8'));
  await page.getByRole('button',{name:'Homebrew',exact:true}).click();
  await page.locator('.brew-environment').waitFor();
  await page.screenshot({path:'/tmp/mdc-ui-check/homebrew-desktop.png'});
  await page.locator('#brewSearch').fill('shared');
  await page.locator('.brew-package-row .brew-package-link').click();
  await page.locator('#detailDialog').getByRole('heading',{name:'Why it’s installed'}).waitFor();
  assert(await page.locator('#detailDialog').getByRole('button',{name:'Uninstall',exact:true}).isDisabled());
  assert((await page.locator('.brew-reverse-tree').innerText()).includes('ffmpeg'));
  assert((await page.locator('.brew-reverse-tree').innerText()).includes('studio'));
  await page.getByRole('button',{name:'Close package details'}).click();
  await page.getByRole('button',{name:'Dependency groups',exact:true}).click();
  await page.locator('.brew-dependency-group').filter({hasText:'ffmpeg'}).first().locator('summary').click();
  await page.screenshot({path:'/tmp/mdc-ui-check/homebrew-groups.png'});
  await page.locator('[data-action="brew-tab"][data-tab="updates"]').click();
  await page.locator('.brew-package-row .brew-package-link').filter({hasText:'ffmpeg'}).click();
  await page.locator('#detailDialog').getByRole('button',{name:'Upgrade',exact:true}).click();
  await page.locator('#confirmDialog').getByText('Would install dependency: new-runtime',{exact:false}).waitFor();
  await page.locator('#confirmDialog [data-action="confirm"]').click();
  await page.locator('.job-result').filter({hasText:'Upgrade ffmpeg'}).getByText('Completed',{exact:true}).waitFor();
  await page.locator('[data-action="brew-tab"][data-tab="tidy"]').click();
  await page.getByRole('button',{name:'Review removal',exact:true}).click();
  const confirm=page.locator('#confirmDialog [data-action="confirm"]');
  await page.locator('#confirmPhrase').fill('WRONG'); assert(await confirm.isDisabled());
  await page.locator('#confirmPhrase').fill('REMOVE'); assert(await confirm.isEnabled());
  await page.screenshot({path:'/tmp/mdc-ui-check/homebrew-tidy-review.png'});
  await page.locator('#confirmDialog').getByRole('button',{name:'Cancel',exact:true}).click();
  await page.getByRole('button',{name:'Review removal',exact:true}).click();
  await page.locator('#confirmPhrase').fill('REMOVE'); await confirm.click();
  await page.getByText('No eligible unused dependencies were found.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Preview cleanup',exact:true}).click();
  await page.locator('#confirmDialog').getByText('Would remove:',{exact:false}).waitFor();
  await page.locator('#confirmDialog').getByRole('button',{name:'Cancel',exact:true}).click();
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('button',{name:'Export Brewfile',exact:true}).click();
  const download=await downloadPromise; assert.equal(download.suggestedFilename(),'Brewfile');
  await download.saveAs('/tmp/mdc-ui-check/ExportedBrewfile');
  assert(fs.readFileSync('/tmp/mdc-ui-check/ExportedBrewfile','utf8').includes('brew "ffmpeg"'));
  await page.getByRole('button',{name:'Disks & volumes',exact:true}).click();
  await page.locator('.disk-device-list').waitFor();
  assert.equal(await page.locator('.disk-choice[data-target="disk1s1"]').count(),0,'system data hidden by default');
  assert.equal(await page.locator('.disk-choice[data-target="disk0s2"]').count(),0,'partition record hidden by default');
  assert.equal(await page.locator('.disk-choice[data-target="disk1s2s1"]').count(),1,'startup volume remains visible');
  await page.getByRole('button',{name:/Show system volumes/}).click();
  assert.equal(await page.locator('.disk-choice[data-target="disk1s1"]').count(),1,'advanced toggle reveals system records');
  await page.getByRole('button',{name:'Hide system volumes',exact:true}).click();
  await page.screenshot({path:'/tmp/mdc-ui-check/disks-redesigned.png'});
  for (const [width,height] of [[1440,900],[1024,768],[768,1024],[390,844],[320,740],[740,320]]) {
    await page.setViewportSize({width,height});
    for (const view of ['homebrew','disks']) {
      await page.locator(`[data-action="navigate"][data-view="${view}"]`).click();
      await page.locator(view==='homebrew'?'.brew-environment':'.disk-device-list').waitFor();
      if(view==='homebrew') await page.locator('[data-action="brew-tab"][data-tab="overview"]').click();
      const overflow=await page.locator('#main').evaluate(main=>{
        const box=main.getBoundingClientRect();
        return [...main.querySelectorAll('*')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&(r.right>box.right+1||r.left<box.left-1)}).map(e=>`${e.tagName}.${e.className}`).slice(0,6);
      });
      assert.deepEqual(overflow,[],`${view} overflow at ${width}x${height}`);
      if(view==='disks') {
        const nested=await page.locator('.disk-workspace').evaluate(el=>[el,...el.querySelectorAll('*')].filter(x=>['auto','scroll'].includes(getComputedStyle(x).overflowY)&&x.scrollHeight>x.clientHeight+1).map(x=>x.className));
        assert.deepEqual(nested,[],`nested disk scrolling at ${width}x${height}`);
      }
      if(width===390) await page.screenshot({path:`/tmp/mdc-ui-check/${view}-updated-mobile.png`});
    }
  }
  assert.deepEqual(errors,[]);
  console.log('Passed: Homebrew dependency graph, protected uninstall, upgrade preview/run, tidy confirmation/cancel/run, Brewfile export; default-hidden system records and opt-in reveal; no nested disk scrolling or horizontal overflow at six sizes.');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
