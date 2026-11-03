const artifact=require('./helpers/artifact.cjs');
const {chromium}=require('playwright');
const http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{
 const file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
 if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return}
 try{res.setHeader('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file))}catch{res.writeHead(404).end()}
});
const failures=[];
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 async function check(name,fn,options={}){
  const p=await browser.newPage({viewport:{width:1440,height:960},...options});p.setDefaultTimeout(2500);const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.addInitScript(()=>{
   const url=id=>'data:image/svg+xml,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${id==='b'?1200:1800}" height="${id==='b'?1800:1200}"><rect width="1800" height="1800" fill="${id==='a'?'#4d5b66':'#67584c'}"/><path d="M900 0V1800M0 600H1800" stroke="#ddd" stroke-width="4"/><text x="800" y="580" font-size="90" fill="white">${id}</text></svg>`);
   const photos=['a','b','c'].map(id=>({id,stem:'漫展_'+id,files:[{id:'f'+id,kind:'jpeg',path:'C:/测试SD/'+id+'.jpg'}],relative_dir:'',captured_at:'2026-11-01T12:00:00'}));
   const ok=data=>({ok:true,data});window.test={photos,fail:null,delay:null,resolve:null,reject:null,requests:[]};
   window.pywebview={api:{get_settings:async()=>ok({library_available:false}),list_activities:async()=>ok([]),list_people:async()=>ok([]),list_photos:async()=>ok([]),save_settings:async()=>ok({}),
    choose_source:async()=>ok({token:'fixture',path:'C:/测试SD',name:'测试SD'}),scan:async()=>ok({task_id:'scan'}),get_task:async()=>ok({status:'succeeded',errors:[],result:{scan_id:'scan',photos,cancelled:false}}),
    get_preview:async(id,kind)=>{test.requests.push([id,kind]);if(kind==='preview'&&id===test.delay)return new Promise((resolve,reject)=>{test.resolve=()=>resolve(ok({url:url(id)}));test.reject=()=>reject(new Error('迟到的错误'))});return ok({url:kind==='preview'&&id===test.fail?null:url(id),error:'测试图片暂不可读'})},get_photo_details:async()=>ok({files:[],total_bytes:12345})
   }};
  });
  try{await p.goto(`http://127.0.0.1:${server.address().port}/index.html`);await p.locator('#choose-source').click();await p.locator('.photo').first().waitFor();await fn(p);assert.deepEqual(errors,[]);console.log('PASS '+name)}
  catch(e){failures.push(name+': '+e.message);console.error('FAIL '+name+': '+e.message);await p.screenshot({path:artifact('v08-'+name.replace(/[^a-z0-9]/gi,'-')+'.png')})}
  finally{await p.close()}
 }
 const open=async(p,id='a')=>{await p.locator(`.photo[data-id="${id}"]`).dblclick();await p.locator('#viewer-image:not([hidden])').waitFor();await p.waitForTimeout(280)};
 const matrix=p=>p.locator('#viewer-image').evaluate(im=>{const m=new DOMMatrix(getComputedStyle(im).transform);return {scale:m.a,x:m.e,y:m.f}});
 await check('pointer anchored zoom',async p=>{
  await open(p);const before=await p.locator('#viewer-image').boundingBox(),rx=.64,ry=.57,x=before.x+before.width*rx,y=before.y+before.height*ry;
  await p.locator('#viewer-canvas').evaluate(canvas=>canvas.addEventListener('wheel',event=>{const r=document.querySelector('#viewer-image').getBoundingClientRect();window.wheelAnchor={rx:(event.clientX-r.x)/r.width,ry:(event.clientY-r.y)/r.height,x:event.clientX,y:event.clientY}},{capture:true,once:true}));
  await p.mouse.move(x,y);await p.mouse.wheel(0,-120);await p.waitForTimeout(750);
  const after=await p.locator('#viewer-image').boundingBox(),anchor=await p.evaluate(()=>wheelAnchor);assert(after.width>before.width);assert(Math.abs(after.x+after.width*anchor.rx-anchor.x)<2,'zoom must keep the pixel pointed at the actual wheel event under the cursor: '+JSON.stringify({before,after,anchor}));assert(Math.abs(after.y+after.height*anchor.ry-anchor.y)<2);assert.match(await p.locator('#viewer-zoom').textContent(),/%/);
  await p.keyboard.press('ArrowRight');await p.waitForFunction(()=>document.querySelector('#viewer-name').textContent==='漫展_b'&&!document.querySelector('#viewer-image').hidden);await p.waitForTimeout(250);
  const next=await matrix(p);assert(Math.abs(next.x)<1&&Math.abs(next.y)<1);assert(next.scale<1);assert.equal(await p.locator('#viewer-position').textContent(),'2 / 3');
 });
 await check('viewer selection persists',async p=>{
  await p.locator('.photo[data-id="c"]').click();await open(p);assert.equal(await p.locator('.photo.checked').count(),1);
  await p.keyboard.press('Space');assert.equal(await p.locator('#viewer-select').getAttribute('aria-pressed'),'true');assert.equal(await p.locator('.photo.checked').count(),2);
  await p.locator('#viewer-select').click();assert.equal(await p.locator('#viewer-select').getAttribute('aria-pressed'),'false');await p.keyboard.press('Space');assert.equal(await p.locator('#viewer-select').getAttribute('aria-pressed'),'true');
  await p.keyboard.press('ArrowRight');await p.waitForFunction(()=>document.querySelector('#viewer-name').textContent==='漫展_b');await p.locator('#viewer-canvas').focus();await p.keyboard.press('Space');await p.keyboard.press('Escape');await p.locator('#viewer[open]').waitFor({state:'hidden'});assert.equal(await p.locator('.photo.checked').count(),3);assert(await p.evaluate(()=>document.querySelector('#gallery').contains(document.activeElement)));
 });
 await check('selected filter keeps navigation',async p=>{
  await p.locator('.photo[data-id="a"]').click();await p.locator('.photo[data-id="b"]').click();await p.locator('#only-selected').check();await open(p);await p.keyboard.press('Space');await p.keyboard.press('ArrowRight');assert.equal(await p.locator('#viewer-name').textContent(),'漫展_b');await p.keyboard.press('Escape');await p.waitForTimeout(250);assert.equal(await p.locator('.photo').count(),1);assert.equal(await p.locator('.photo').getAttribute('data-id'),'b');
 });
 await check('cancel and late results',async p=>{
  await p.evaluate(()=>test.delay='a');await p.locator('.photo[data-id="a"]').dblclick();await p.waitForFunction(()=>test.reject);await p.keyboard.press('ArrowRight');await p.locator('#viewer-image:not([hidden])').waitFor();await p.evaluate(()=>test.reject());await p.waitForTimeout(100);assert.equal(await p.locator('#viewer-error').textContent(),'');assert.equal(await p.locator('#viewer-name').textContent(),'漫展_b');
  await p.keyboard.press('Escape');await p.evaluate(()=>{test.delay='c';test.resolve=null});await p.locator('.photo[data-id="c"]').dblclick();await p.waitForFunction(()=>test.resolve);await p.keyboard.press('Escape');await p.evaluate(()=>test.resolve());await p.waitForTimeout(100);assert(!await p.locator('#viewer').evaluate(d=>d.open));
 });
 await check('error retry',async p=>{await p.evaluate(()=>test.fail='a');await p.locator('.photo[data-id="a"]').dblclick();await p.locator('#viewer-retry').waitFor({state:'visible'});await p.evaluate(()=>test.fail=null);await p.locator('#viewer-retry').click();await p.locator('#viewer-image:not([hidden])').waitFor();assert.equal(await p.locator('#viewer-error').textContent(),'')});
 await check('drag bounds and interruption',async p=>{
  await open(p);await p.locator('#viewer-actual').click();await p.waitForTimeout(750);const r=await p.locator('#viewer-canvas').boundingBox();
  await p.mouse.move(r.x+r.width/2,r.y+r.height/2);await p.mouse.down();await p.mouse.move(r.x+r.width/2+900,r.y+r.height/2+600,{steps:10});await p.mouse.up();
  await p.waitForTimeout(100);await p.mouse.move(r.x+r.width/2,r.y+r.height/2);await p.mouse.down();const grabbed=await matrix(p);await p.mouse.move(r.x+r.width/2-20,r.y+r.height/2-10);const moved=await matrix(p);assert(Math.abs(moved.x-grabbed.x)<30,'grabbing a settling image must not jump');await p.mouse.up();await p.waitForTimeout(950);
  const m=await matrix(p);assert(Math.abs(m.x)<=Math.max(0,(1800*m.scale-r.width)/2)+1);assert(Math.abs(m.y)<=Math.max(0,(1200*m.scale-r.height)/2)+1);
 });
 await check('reduced motion and small window',async p=>{
  await open(p);await p.locator('#viewer-actual').click();const m=await matrix(p);assert.equal(m.scale,1);assert.equal(await p.locator('#viewer').evaluate(d=>d.getAnimations().length),0);await p.keyboard.press('Escape');await p.locator('#settings').click();await p.locator('#modal[open]').waitFor();await p.keyboard.press('Escape');await p.locator('#settings').click();assert(await p.locator('#modal').evaluate(d=>d.open));assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 },{viewport:{width:1040,height:720},reducedMotion:'reduce'});
 await check('menu focus and modal reopening',async p=>{
  await p.locator('.photo').first().click({button:'right'});await p.getByRole('menu').waitFor();await p.keyboard.press('ArrowDown');assert.equal(await p.evaluate(()=>document.activeElement.getAttribute('role')),'menuitem');await p.keyboard.press('Escape');assert.equal(await p.getByRole('menu').count(),0);await p.locator('#settings').click();await p.keyboard.press('Escape');await p.locator('#settings').click();assert(await p.locator('#modal').evaluate(d=>d.open));
 });
 await check('rapid preview reopen',async p=>{
  await open(p);await p.evaluate(async()=>{const g=await import('./gallery.js');document.querySelector('#viewer').close();g.openViewer('b')});await p.waitForFunction(()=>document.querySelector('#viewer-name').textContent==='漫展_b'&&!document.querySelector('#viewer-image').hidden);assert(await p.locator('#viewer').evaluate(d=>d.open));assert.equal(await p.locator('#viewer-image').evaluate(im=>im.naturalHeight),1800);
 });
 await check('zoom limits and keyboard controls',async p=>{
  await open(p);await p.locator('#viewer-in').evaluate(b=>{for(let i=0;i<50;i++)b.click()});await p.waitForFunction(()=>Math.abs(new DOMMatrix(getComputedStyle(document.querySelector('#viewer-image')).transform).a-16)<.0005,null,{timeout:5000});assert(Math.abs((await matrix(p)).scale-16)<.0005);
  await p.locator('#viewer-out').evaluate(b=>{for(let i=0;i<70;i++)b.click()});await p.waitForFunction(()=>Math.abs(new DOMMatrix(getComputedStyle(document.querySelector('#viewer-image')).transform).a-.02)<.0005,null,{timeout:5000});assert(Math.abs((await matrix(p)).scale-.02)<.0005);
  await p.locator('#viewer-actual').focus();await p.keyboard.press('Space');await p.waitForFunction(()=>Math.abs(new DOMMatrix(getComputedStyle(document.querySelector('#viewer-image')).transform).a-1)<.001,null,{timeout:5000});assert(Math.abs((await matrix(p)).scale-1)<.001);assert.equal(await p.locator('.photo.checked').count(),0,'Space on a zoom button activates only that button');
 });
 await check('pointer cancellation recovers',async p=>{
  await open(p);const r=await p.locator('#viewer-canvas').boundingBox();await p.mouse.move(r.x+100,r.y+100);await p.mouse.down();await p.mouse.move(r.x+500,r.y+300);await p.locator('#viewer-canvas').evaluate(c=>c.dispatchEvent(new PointerEvent('pointercancel',{pointerId:1,bubbles:true})));await p.mouse.up();await p.waitForTimeout(950);const m=await matrix(p);assert(Math.abs(m.x)<1&&Math.abs(m.y)<1);assert(!await p.locator('#viewer-canvas').evaluate(c=>c.classList.contains('panning')));
 });
 await check('selected filter rapid reopen',async p=>{
  await p.locator('.photo[data-id="a"]').click();await p.locator('.photo[data-id="b"]').click();await p.locator('#only-selected').check();await open(p);await p.keyboard.press('Space');
  await p.evaluate(async()=>{const g=await import('./gallery.js');document.querySelector('#viewer').close();g.openViewer('b')});await p.locator('#viewer-image:not([hidden])').waitFor();await p.keyboard.press('Escape');await p.waitForTimeout(250);assert.equal(await p.locator('.photo').count(),1,'reopening must still apply the previous session selection changes');assert.equal(await p.locator('.photo').getAttribute('data-id'),'b');
 });
 await check('letterbox zoom retains photo',async p=>{
  await open(p,'b');const canvas=await p.locator('#viewer-canvas').boundingBox();await p.mouse.move(canvas.x+2,canvas.y+canvas.height/2);for(let i=0;i<20;i++)await p.mouse.wheel(0,-180);await p.waitForTimeout(1000);
  const image=await p.locator('#viewer-image').boundingBox();assert(image.x<canvas.x+canvas.width&&image.x+image.width>canvas.x,'zooming over letterbox must not move the photo entirely offscreen');await p.locator('#viewer-fit').click();const value=await matrix(p);assert.equal(value.x,0);assert.equal(value.y,0);
 });
 await browser.close();server.close();if(failures.length)throw new Error(failures.join('\n'));console.log('PASS all v0.8 interaction checks');
})().catch(e=>{console.error(e.message);server.close();process.exitCode=1});
