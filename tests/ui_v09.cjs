const artifact=require('./helpers/artifact.cjs');
const {chromium}=require('playwright'),{PNG}=require('pngjs');
const http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{const file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return}try{res.setHeader('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file))}catch{res.writeHead(404).end()}});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true});let failed=0;
 async function check(name,fn,options={}){
  const p=await browser.newPage({viewport:{width:1440,height:960},...options});p.setDefaultTimeout(4000);const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.addInitScript(()=>{
   const url='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1600"><rect width="1200" height="1600" fill="#535e72"/><path d="M0 400H1200M0 800H1200M0 1200H1200M400 0V1600M800 0V1600" stroke="#c7ad7d" stroke-width="40"/></svg>');
   const photos=Array.from({length:60},(_,i)=>({id:'p'+i,activity_id:'a',person_id:'u',stem:'漫展照片_'+i,captured_at:'2026-11-01T10:00:00',edited:i%2,assets:[{id:'f'+i,kind:'jpeg',path:'C:/测试库/'+i+'.jpg'}]}));const ok=data=>({ok:true,data});
   window.pywebview={api:{get_settings:async()=>ok({library_available:true,library:'C:/测试库'}),list_activities:async()=>ok([{id:'a',name:'秋日漫展'}]),list_people:async()=>ok([{id:'u',name:'待分类',role:'unclassified'},{id:'g',name:'合照',role:'group'}]),list_photos:async()=>ok(photos),get_preview:async()=>ok({url}),get_photo_details:async()=>ok({files:[],total_bytes:12345}),save_settings:async()=>ok({})}};
  });
  try{await p.goto(`http://127.0.0.1:${server.address().port}/index.html`);await p.locator('#choose-source:not([disabled])').waitFor();await fn(p);assert.deepEqual(errors,[]);console.log('PASS '+name)}catch(e){failed++;console.error('FAIL '+name+': '+e.message);await p.screenshot({path:artifact('v09-'+name.replace(/[^a-z0-9]/gi,'-')+'.png')})}finally{await p.close()}
 }
 await check('actual rim refraction',async p=>{
  await p.evaluate(async()=>{
   const {attachGlass}=await import('./glass.js');const bg=document.createElement('div');bg.style.cssText='position:fixed;left:80px;top:80px;width:400px;height:200px;background:repeating-linear-gradient(90deg,#fff 0px,#fff 4px,#202020 4px,#202020 8px);z-index:999';
   const probe=document.createElement('div');probe.id='optical-probe';probe.style.cssText='position:absolute;left:40px;top:30px;width:320px;height:104px;border-radius:20px;background:transparent';
   const label=document.createElement('button');label.textContent='前景文字保持清晰';probe.append(label);bg.append(probe);document.body.append(bg);window.lensProbe=attachGlass(probe,{radius:20,strength:14,blur:0});
  });
  await p.waitForFunction(()=>document.querySelector('#optical-probe .lens-backdrop')?.style.backdropFilter.includes('url'));
  await p.locator('#optical-probe .lens-backdrop').evaluate(layer=>layer.style.background='transparent');await p.waitForTimeout(100);
  const active=PNG.sync.read(await p.locator('#optical-probe').screenshot());await p.locator('#optical-probe .lens-backdrop').evaluate(layer=>layer.style.backdropFilter='none');
  const plain=PNG.sync.read(await p.locator('#optical-probe').screenshot());let changed=0;for(let y=12;y<active.height-12;y++)for(let x=2;x<24;x++){const i=(y*active.width+x)*4;if(Math.abs(active.data[i]-plain.data[i])>20)changed++}assert(changed>150,'a real sampled background must bend at the rim, not just change tint');
  assert.equal(await p.locator('#optical-probe button').evaluate(b=>getComputedStyle(b).filter),'none');
 });
 await check('glass map lifetime and resize',async p=>{
  await p.evaluate(async()=>{const {attachGlass}=await import('./glass.js');const h=document.createElement('div');h.id='lifetime-probe';h.style.cssText='position:fixed;left:20px;top:100px;width:300px;height:80px';document.body.append(h);window.probeGlass=attachGlass(h,{strength:12})});
  await p.waitForFunction(()=>document.querySelector('#lifetime-probe .lens-backdrop')?.style.backdropFilter.includes('url'));const before=await p.locator('#glass-definitions filter').count();const map=await p.locator('#glass-definitions feImage').last().getAttribute('href');
  await p.mouse.move(100,120);await p.mouse.move(150,130);assert.equal(await p.locator('#glass-definitions feImage').last().getAttribute('href'),map);
  await p.locator('#lifetime-probe').evaluate(h=>h.style.width='420px');await p.waitForFunction(old=>[...document.querySelectorAll('#glass-definitions feImage')].at(-1).getAttribute('href')!==old,map);assert.equal(await p.locator('#glass-definitions filter').count(),before);
  await p.evaluate(()=>{probeGlass.destroy();document.querySelector('#lifetime-probe').remove()});assert.equal(await p.locator('#glass-definitions filter').count(),before-1);
 });
 await check('floating actions preserve last row',async p=>{
  await p.locator('[data-view=library]').click();await p.locator('#toggle-browse').click();await p.locator('.photo').first().click();
  assert.equal(await p.locator('footer').evaluate(f=>getComputedStyle(f).position),'absolute');await p.locator('#gallery').evaluate(g=>g.scrollTop=g.scrollHeight);const last=await p.locator('.photo').last().boundingBox(),bar=await p.locator('footer').boundingBox();assert(last.y+last.height<=bar.y-4,'last photo row must scroll above floating actions');assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 },{viewport:{width:1040,height:720}});
 await check('stage spring rapid retarget',async p=>{
  await p.locator('[data-view=library]').click();const indicator=p.locator('.stage-indicator');await indicator.waitFor({state:'visible'});
  await p.locator('[data-stage=pending]').click();await p.locator('[data-stage=edited]').click();await p.locator('[data-stage=all]').click();await p.locator('[data-stage=edited]').click();
  await p.waitForFunction(()=>{const active=document.querySelector('#stage-tabs button.active').getBoundingClientRect(),lens=document.querySelector('.stage-indicator').getBoundingClientRect();return Math.abs(active.x-lens.x)<1&&Math.abs(active.width-lens.width)<1});assert.equal(await p.locator('.photo').count(),30);assert.equal(await indicator.getAttribute('aria-hidden'),'true');
 });
 await check('glass preference fallback',async p=>{
  const session=await p.context().newCDPSession(p);await session.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'}]});await p.locator('#settings').click();await p.waitForTimeout(100);
  assert.equal(await p.locator('#modal .lens-backdrop').evaluate(l=>getComputedStyle(l).display),'none');assert.equal(await p.locator('#modal').evaluate(d=>getComputedStyle(d).backdropFilter),'none');await p.keyboard.press('Escape');
  await session.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-contrast',value:'more'}]});await p.waitForTimeout(100);assert.equal(await p.locator('footer .lens-backdrop').evaluate(l=>getComputedStyle(l).display),'none');
 });
 await check('preview flight interruption',async p=>{
  await p.locator('[data-view=library]').click();await p.locator('#toggle-browse').click();await p.locator('.photo').first().dblclick();await p.locator('#viewer-image:not([hidden])').waitFor();
  assert(await p.locator('#viewer-image').evaluate(im=>new DOMMatrix(getComputedStyle(im).transform).a<Math.min(document.querySelector('#viewer-canvas').clientWidth/im.naturalWidth,document.querySelector('#viewer-canvas').clientHeight/im.naturalHeight,1)*.95),'pointer preview must expand from its thumbnail');
  await p.locator('#viewer-canvas').dispatchEvent('wheel',{deltaY:-100,clientX:700,clientY:400});await p.keyboard.press('ArrowRight');await p.waitForFunction(()=>document.querySelector('#viewer-name').textContent==='漫展照片_1'&&!document.querySelector('#viewer-image').hidden);await p.keyboard.press('Space');await p.keyboard.press('Escape');assert.equal(await p.locator('.photo.checked').count(),1);
 });
 await check('keyboard preview has no flight',async p=>{await p.locator('[data-view=library]').click();await p.locator('#toggle-browse').click();await p.locator('.photo').first().click();await p.locator('#gallery').focus();await p.keyboard.press('Shift+F10');await p.keyboard.press('Enter');await p.locator('#viewer-image:not([hidden])').waitFor();assert(await p.locator('#viewer-image').evaluate(im=>Math.abs(new DOMMatrix(getComputedStyle(im).transform).a-Math.min(document.querySelector('#viewer-canvas').clientWidth/im.naturalWidth,document.querySelector('#viewer-canvas').clientHeight/im.naturalHeight,1))<.001))});
 await check('scrolling modal keeps its material',async p=>{
  await p.locator('#settings').click();await p.locator('#modal-content').evaluate(body=>{for(let i=0;i<40;i++){const line=document.createElement('p');line.textContent='长列表中的照片库记录 '+i;line.style.padding='12px';body.append(line)}});await p.evaluate(()=>{document.querySelector('#modal').scrollTop=300;document.querySelector('#modal-content').scrollTop=300});await p.waitForTimeout(100);assert(await p.evaluate(()=>Math.max(document.querySelector('#modal').scrollTop,document.querySelector('#modal-content').scrollTop)>100));
  const dialog=await p.locator('#modal').boundingBox(),layer=await p.locator('#modal .lens-backdrop').boundingBox();assert(Math.abs(layer.y-dialog.y)<3,'glass must stay anchored to the dialog scrollport');await p.keyboard.press('Escape');assert(!await p.locator('#modal').evaluate(d=>d.open));
 });
 await check('inspector source flight',async p=>{await p.locator('[data-view=library]').click();await p.locator('#toggle-browse').click();await p.locator('.photo').first().click();await p.locator('.large-thumb img').waitFor();await p.locator('.large-thumb').click();await p.locator('#viewer-image:not([hidden])').waitFor();assert(await p.locator('#viewer-image').evaluate(im=>new DOMMatrix(getComputedStyle(im).transform).a<Math.min(document.querySelector('#viewer-canvas').clientWidth/im.naturalWidth,document.querySelector('#viewer-canvas').clientHeight/im.naturalHeight,1)*.95))});
 await check('reduced motion stage direct',async p=>{await p.locator('[data-view=library]').click();await p.locator('[data-stage=edited]').click();const a=await p.locator('#stage-tabs button.active').boundingBox(),b=await p.locator('.stage-indicator').boundingBox();assert(Math.abs(a.x-b.x)<1&&Math.abs(a.width-b.width)<1);assert.equal(await p.locator('#stage-tabs').evaluate(n=>n.getAnimations({subtree:true}).length),0)},{reducedMotion:'reduce'});
 await browser.close();server.close();assert.equal(failed,0,failed+' v0.9 checks failed');console.log('PASS all v0.9 glass and motion checks');
})().catch(e=>{console.error(e.message);server.close();process.exitCode=1});
