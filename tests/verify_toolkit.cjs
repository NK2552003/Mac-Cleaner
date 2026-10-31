/* Run against tests/toolkit_fixture.py only. All mutation commands use FakeRunner. */
const {chromium} = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const url = fs.readFileSync('/tmp/mdc-ui-check/launch-url','utf8');
  await page.goto(url);
  await page.getByRole('heading',{name:'Your Mac, at a glance'}).waitFor();
  const initialDiskJobs = (await page.evaluate(async () => (await (await fetch('/api/jobs')).json()).jobs)).filter(j => j.kind === 'disk').length;
  await page.screenshot({path:'/tmp/mdc-ui-check/optimize-desktop.png'});
  await page.locator('[data-tool="quicklook-reset"]').click();
  await page.getByRole('dialog',{name:'Rebuild Quick Look thumbnails'}).waitFor();
  await page.locator('#confirmDialog [data-action="confirm"]').click();
  await page.locator('.job-result').filter({hasText:'Rebuild Quick Look thumbnails'}).first().getByText('Completed',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Disks & volumes',exact:true}).click();
  await page.locator('.disk-heading h2').waitFor();
  assert.equal(await page.locator('[data-action="toolkit-disk-action"][data-tool="erase"]').count(),0);
  await page.screenshot({path:'/tmp/mdc-ui-check/disks-desktop.png'});
  await page.locator('.disk-choice[data-target="disk8"]').click();
  await page.locator('[data-action="toolkit-disk-action"][data-tool="erase"]').click();
  await page.getByLabel('Volume name',{exact:true}).fill('My Work SSD');
  await page.getByRole('button',{name:'Review operation',exact:true}).click();
  const confirm = page.locator('#confirmDialog [data-action="confirm"]');
  await page.locator('#confirmPhrase').waitFor();
  assert(await confirm.isDisabled());
  await page.locator('#confirmPhrase').fill('ERASE disk8');
  assert(await confirm.isDisabled());
  await page.locator('#diskBackupAck').check();
  assert(await confirm.isEnabled());
  await page.screenshot({path:'/tmp/mdc-ui-check/erase-review.png'});
  await page.locator('#confirmDialog').getByRole('button',{name:'Cancel',exact:true}).click();
  await page.getByRole('button',{name:'Close disk setup'}).click();
  assert.equal((await page.evaluate(async () => (await (await fetch('/api/jobs')).json()).jobs)).filter(j => j.kind === 'disk').length,initialDiskJobs);
  await page.locator('[data-action="toolkit-disk-action"][data-tool="partition"]').click();
  await page.locator('[name="part-size"]').first().fill('100');
  await page.getByRole('button',{name:'Add partition',exact:true}).click();
  assert.equal(await page.locator('.partition-fields').count(),3);
  await page.getByRole('button',{name:'Remove last',exact:true}).click();
  await page.getByRole('button',{name:'Review operation',exact:true}).click();
  await page.locator('#confirmPhrase').fill('ERASE disk8');
  await page.locator('#diskBackupAck').check();
  await confirm.click(); // Fixture runner only; never executes diskutil.
  await page.locator('.job-result').filter({hasText:'Repartition disk'}).first().getByText('Completed',{exact:true}).waitFor();
  for (const [width,height] of [[1440,900],[1024,768],[768,1024],[390,844],[320,740],[740,320]]) {
    await page.setViewportSize({width,height});
    for (const target of ['optimize','disks']) {
      await page.locator(`[data-action="navigate"][data-view="${target}"]`).click();
      await page.locator(target === 'optimize' ? '.health-overview' : '.disk-workspace').waitFor();
      const overflowing = await page.locator('#main').evaluate(main => {
        const b = main.getBoundingClientRect();
        return [...main.querySelectorAll('*')].filter(e => {
          const r = e.getBoundingClientRect();
          return r.width && (r.right > b.right + 1 || r.left < b.left - 1);
        }).map(e => `${e.tagName}.${e.className}`).slice(0,8);
      });
      assert.deepEqual(overflowing,[],`${target} overflow at ${width}x${height}`);
      if (width === 390) await page.screenshot({path:`/tmp/mdc-ui-check/${target}-mobile.png`});
    }
  }
  // Modal input/confirmation must fit at the narrowest supported width too.
  await page.setViewportSize({width:320,height:740});
  await page.locator('.disk-choice[data-target="disk8"]').click();
  await page.locator('[data-action="toolkit-disk-action"][data-tool="partition"]').click();
  assert(await page.locator('#diskOperationForm').evaluate(e => e.scrollWidth <= e.clientWidth + 1));
  await page.getByRole('button',{name:'Review operation',exact:true}).click();
  await page.locator('#confirmPhrase').waitFor();
  assert(await page.locator('#confirmDialog').evaluate(e => e.scrollWidth <= e.clientWidth + 1));
  await page.screenshot({path:'/tmp/mdc-ui-check/partition-mobile.png'});
  await page.keyboard.press('Escape');
  await page.keyboard.press('Escape');
  assert.deepEqual(errors,[]);
  console.log('Passed: tool execution, protected startup disk, erase acknowledgement/cancel, partition flow, 12 responsive views, mobile dialogs, no browser errors.');
  await browser.close();
})().catch(error => {console.error(error);process.exit(1);});
