const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const base = process.env.FLANEUR_URL || 'http://127.0.0.1:8765/map/index.html';

async function openMobile(browser, width = 390) {
  const page = await browser.newPage({viewport: {width, height: 844}, hasTouch: true, isMobile: true});
  await page.goto(base, {waitUntil: 'domcontentloaded'});
  await page.waitForSelector('.sphere');
  return page;
}

async function visibleCountryPoint(page) {
  return page.locator('.country').evaluateAll(nodes => {
    const node=nodes.find(n=>{const b=n.getBoundingClientRect();return b.width>20&&b.height>20});
    if(!node)throw new Error('No visible country hit point');
    const b=node.getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2,code:node.dataset.code};
  });
}

function touch(x, y, id) { return {x, y, id, radiusX: 5, radiusY: 5, force: 1}; }

async function drag(client, from, to, id = 1, steps = 14) {
  await client.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [touch(from.x, from.y, id)]});
  for (let i = 1; i <= steps; i++) await client.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [touch(from.x + (to.x-from.x)*i/steps, from.y + (to.y-from.y)*i/steps, id)]});
  await client.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
}

test('mobile globe silhouette fits and country taps show complete metrics', async () => {
  const browser = await chromium.launch({headless: true});
  try {
    for (const width of [390, 600, 760]) {
      const page = await openMobile(browser, width);
      const geometry = await page.evaluate(() => {
        const sphere = document.querySelector('.sphere').getBBox();
        const svg = document.querySelector('#map').viewBox.baseVal;
        return {x:sphere.x,y:sphere.y,width:sphere.width,height:sphere.height,svgWidth:svg.width,svgHeight:svg.height};
      });
      assert.ok(geometry.x >= 0 && geometry.x + geometry.width <= geometry.svgWidth, `${width}px globe fits horizontally`);
      assert.ok(geometry.y >= 50 && geometry.y + geometry.height <= geometry.svgHeight - 40, `${width}px globe leaves legend and hint room`);
      if (width === 390) assert.ok(Math.abs(geometry.width - 374) < 0.1, '390px approved diameter remains exactly 374px');

      const point = await visibleCountryPoint(page);
      await page.touchscreen.tap(point.x, point.y);
      const tip = page.locator('.tooltip.show');
      await tip.waitFor({timeout: 1500});
      const text = await tip.innerText();
      for (const label of ['Capital:', 'Population:', 'GDP:']) assert.match(text, new RegExp(label));
      assert.match(text,/Capital: .+/);
      assert.match(text,/Population: .+ \(\d{4}\) · #\d+/);
      assert.match(text,/GDP: .+ \(\d{4}\) · #\d+/);
      const box = await tip.boundingBox();
      assert.ok(box.x >= 0 && box.y >= 0 && box.x + box.width <= width && box.y + box.height <= 844, `${width}px complete tooltip is within viewport`);
      await page.close();
    }
  } finally { await browser.close(); }
});

test('real CDP drag and pinch remain continuous and suppress pinch taps', async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await openMobile(browser);
    const client = await page.context().newCDPSession(page);
    const b = await page.locator('#map').boundingBox(), cy=b.y+b.height/2;
    const initial = await page.locator('.country[data-code="CN"]').getAttribute('d');
    await drag(client, {x:b.x+105,y:cy}, {x:b.x+250,y:cy+20});
    await page.waitForTimeout(100);
    const dragged = await page.locator('.country[data-code="CN"]').getAttribute('d');
    assert.notEqual(dragged, initial, 'real touch drag rotates globe');

    const beforePinch = await page.locator('.sphere').evaluate(n => n.getBBox().width);
    await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch(b.x+145,cy,11),touch(b.x+245,cy,12)]});
    for(let i=1;i<=10;i++) await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[touch(b.x+145-i*5,cy,11),touch(b.x+245+i*5,cy,12)]});
    await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[touch(b.x+95,cy,11)]});
    await page.waitForTimeout(50);
    const afterLift = await page.locator('.country[data-code="CN"]').getAttribute('d');
    await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[touch(b.x+125,cy+12,11)]});
    await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await page.waitForTimeout(100);
    const afterPinch = await page.locator('.sphere').evaluate(n => n.getBBox().width);
    const afterContinue = await page.locator('.country[data-code="CN"]').getAttribute('d');
    assert.ok(afterPinch > beforePinch * 1.5, 'pinch zooms in');
    assert.notEqual(afterContinue, afterLift, 'remaining finger continues rotation without a dead gesture');
    assert.equal(await page.locator('.tooltip.show').count(), 0, 'pinch does not create an unintended country tap');

    const zoomed = afterPinch;
    await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch(b.x+90,cy,21),touch(b.x+300,cy,22)]});
    for(let i=1;i<=10;i++) await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[touch(b.x+90+i*6,cy,21),touch(b.x+300-i*6,cy,22)]});
    await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await page.waitForTimeout(100);
    const zoomedOut = await page.locator('.sphere').evaluate(n => n.getBBox().width);
    assert.ok(zoomedOut < zoomed * .8, 'pinch zooms back out');
  } finally { await browser.close(); }
});

test('a burst of pointer moves is coalesced to one globe render per frame', async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await openMobile(browser);
    const result = await page.evaluate(async () => {
      const svg=document.querySelector('#map'), b=svg.getBoundingClientRect();
      let writes=0;const original=Element.prototype.setAttribute;
      Element.prototype.setAttribute=function(name,value){if(name==='d'&&this.closest?.('#map'))writes++;return original.call(this,name,value)};
      svg.dispatchEvent(new PointerEvent('pointerdown',{pointerId:91,pointerType:'touch',button:0,clientX:b.left+80,clientY:b.top+220,bubbles:true}));
      for(let i=1;i<=60;i++)svg.dispatchEvent(new PointerEvent('pointermove',{pointerId:91,pointerType:'touch',button:0,clientX:b.left+80+i*3,clientY:b.top+220,bubbles:true}));
      const synchronousWrites=writes;
      await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);
      svg.dispatchEvent(new PointerEvent('pointerup',{pointerId:91,pointerType:'touch',button:0,clientX:b.left+260,clientY:b.top+220,bubbles:true}));
      Element.prototype.setAttribute=original;
      return {synchronousWrites,totalWrites:writes,countries:document.querySelectorAll('.country').length};
    });
    assert.equal(result.synchronousWrites, 0, 'move handlers defer geometry work to animation frames');
    assert.ok(result.totalWrites <= 2*(result.countries + 3), `one coalesced move render plus one full-fidelity settle, got ${result.totalWrites} path writes for ${result.countries} countries`);
  } finally { await browser.close(); }
});

test('desktop globe rotates on mouse drag without a stray click', async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    await page.goto(base, {waitUntil: 'domcontentloaded'});await page.waitForSelector('.sphere');
    const sphere=await page.locator('.sphere').evaluate(n=>{const b=n.getBBox(),v=n.ownerSVGElement.viewBox.baseVal;return {x:b.x,y:b.y,w:b.width,h:b.height,vw:v.width,vh:v.height}});
    assert.ok(sphere.x>=0&&sphere.y>=0&&sphere.x+sphere.w<=sphere.vw&&sphere.y+sphere.h<=sphere.vh,'default desktop globe fully fits canvas');
    assert.ok(Math.abs(sphere.w-sphere.h)<1,'desktop projection is circular');
    const before=await page.locator('.country[data-code="CN"]').getAttribute('d');
    const b=await page.locator('#map').boundingBox(), from={x:b.x+b.width*.42,y:b.y+b.height*.52}, to={x:from.x+180,y:from.y+35};
    await page.mouse.move(from.x,from.y);await page.mouse.down();await page.mouse.move(to.x,to.y,{steps:14});await page.mouse.up();await page.waitForTimeout(100);
    assert.notEqual(await page.locator('.country[data-code="CN"]').getAttribute('d'),before,'real mouse drag rotates projected geometry');
    assert.equal(await page.locator('.tooltip.show').count(),0,'drag release does not create a country click');
  } finally { await browser.close(); }
});

test('desktop wheel and controls zoom both ways, then reset view', async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    await page.goto(base, {waitUntil: 'domcontentloaded'});await page.waitForSelector('.sphere');
    const diameter=()=>page.locator('.sphere').evaluate(n=>n.getBBox().width);
    const initial=await diameter(), b=await page.locator('#map').boundingBox();
    await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.wheel(0,-500);await page.waitForTimeout(100);
    const wheelIn=await diameter();assert.ok(wheelIn>initial*1.1,'wheel up zooms in');
    await page.mouse.wheel(0,700);await page.waitForTimeout(100);assert.ok(await diameter()<wheelIn,'wheel down zooms out');
    await page.locator('#reset-view').dispatchEvent('click');
    await page.locator('#zoom-in').dispatchEvent('click');assert.ok(Math.abs(await diameter()-initial*1.5)<1,'desktop + keeps 1.5 zoom semantics');
    await page.locator('#zoom-out').dispatchEvent('click');assert.ok(Math.abs(await diameter()-initial)<1,'desktop − zooms back out');
    await page.locator('#reset-view').dispatchEvent('click');assert.ok(Math.abs(await diameter()-initial)<1,'reset restores default scale');
  } finally { await browser.close(); }
});

test('desktop hover metrics are complete and directory focus rotates globe', async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    await page.goto(base, {waitUntil: 'domcontentloaded'});await page.waitForSelector('.country');
    await page.locator('.country[data-code="BR"]').dispatchEvent('pointermove',{clientX:600,clientY:420,pointerType:'mouse'});
    const text=await page.locator('.tooltip.show').innerText();
    assert.match(text,/Capital: .+/);assert.match(text,/Population: .+ \(\d{4}\) · #\d+/);assert.match(text,/GDP: .+ \(\d{4}\) · #\d+/);
    const before=await page.locator('.country[data-code="JP"]').getAttribute('d');
    await page.fill('#search','Japan');await page.locator('.country-row[data-code="JP"]').click();await page.waitForTimeout(100);
    assert.notEqual(await page.locator('.country[data-code="JP"]').getAttribute('d'),before,'directory selection rotates country to the front');
  } finally { await browser.close(); }
});
