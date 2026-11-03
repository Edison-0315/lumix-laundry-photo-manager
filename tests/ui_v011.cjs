const artifact=require('./helpers/artifact.cjs');
const {chromium}=require('playwright'),http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{const f=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(!f.startsWith(root+path.sep)){res.writeHead(403).end();return}try{res.setHeader('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[path.extname(f)]||'application/octet-stream');res.end(fs.readFileSync(f))}catch{res.writeHead(404).end()}});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true});let failed=0;
 async function check(name,fn,options={}){
  const p=await browser.newPage({viewport:{width:1440,height:960},...options});p.setDefaultTimeout(5000);const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.addInitScript(()=>{
   const ok=data=>({ok:true,data});const people=[{id:'u',name:'待分类',role:'unclassified'},{id:'g',name:'合照',role:'group'},...Array.from({length:12},(_,i)=>({id:'m'+i,name:'人物_'+i}))];
   const photos=Array.from({length:16},(_,i)=>({id:'p'+i,activity_id:'a',person_id:i<4?'u':'m'+(i-4),stem:'LUMIX_'+i,edited:i%2,assets:[{id:'f'+i,kind:'jpeg',path:'C:/测试/'+i+'.jpg'}]}));
   const url='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800"><rect width="600" height="800" fill="#5b869a"/><circle cx="260" cy="250" r="180" fill="#a35b62"/></svg>');
   window.pywebview={api:{get_settings:async()=>ok({library_available:true,library:'C:/测试/漫展照片库',thumbnail_size:240}),list_activities:async()=>ok([{id:'a',name:'秋日漫展'}]),list_people:async()=>ok(people),list_photos:async()=>ok(photos),get_preview:async()=>ok({url}),get_photo_details:async()=>ok({files:[]}),save_settings:async()=>ok({})}};
  });
  try{await p.goto(`http://127.0.0.1:${server.address().port}/index.html`);await p.locator('#choose-source:not([disabled])').waitFor();await p.locator('.sidebar>.lens-backdrop').waitFor();await p.waitForTimeout(500);await fn(p);assert.deepEqual(errors,[]);console.log('PASS '+name)}catch(e){failed++;console.error('FAIL '+name+': '+e.message);await p.screenshot({path:artifact('v011-'+name.replace(/[^a-z0-9]/gi,'-')+'.png')})}finally{await p.close()}
 }
 const trace=async p=>p.evaluate(()=>{window.frames=[];return new Promise(resolve=>{document.querySelector('.sidebar nav').addEventListener('pointerdown',()=>{const start=performance.now();function sample(t){const lens=document.querySelector('.sidebar nav .sidebar-selection'),active=document.querySelector('.sidebar nav .active');frames.push({t:t-start,y:lens.getBoundingClientRect().y,target:active.getBoundingClientRect().y});if(t-start<900)requestAnimationFrame(sample);else resolve(frames)}requestAnimationFrame(sample)},{once:true,capture:true})})});
 await check('nav has continuous intermediate frames',async p=>{
  const before=await p.locator('.sidebar nav .sidebar-selection').boundingBox();const sampling=trace(p);await p.locator('[data-view=library]').click();const frames=await sampling,after=await p.locator('.sidebar nav .active').boundingBox(),distance=after.y-before.y;
  fs.writeFileSync(artifact('v011-nav-before.json'),JSON.stringify(frames));
  const intermediate=frames.filter(f=>f.y>before.y+2&&f.y<after.y-2);assert(intermediate.length>=5,'need at least five visible intermediate frames, got '+intermediate.length);let prior=before.y;for(const frame of frames){assert(Math.abs(frame.y-prior)<Math.abs(distance)*.55,'navigation must not jump to target after layout observer');prior=frame.y}assert(Math.abs(frames.at(-1).y-after.y)<1,'navigation settles at current row');
  const settled=await p.locator('.sidebar nav .sidebar-selection').boundingBox();assert(Math.abs(settled.height-after.height)<.1,'press feedback must not leave a shortened selection film');
 });
 await check('quick reverse starts at presentation position',async p=>{
  const samples=trace(p);await p.locator('[data-view=library]').click();await p.waitForTimeout(90);const before=await p.locator('.sidebar nav .sidebar-selection').boundingBox();await p.locator('[data-view=sd]').click();const frames=await samples;const target=await p.locator('.sidebar nav .active').boundingBox();assert(before.y>target.y+3,'first movement must be visible before reversing');const positions=new Set(frames.map(f=>f.y.toFixed(1)));assert(positions.size>=9,'reverse must preserve continuous movement');assert(Math.abs(frames.at(-1).y-target.y)<1);
 });
 await check('workspace change fades without blocking navigation',async p=>{
  await p.locator('[data-view=library]').click();const opacity=await p.locator('#gallery').evaluate(n=>parseFloat(getComputedStyle(n).opacity));assert(opacity<1&&opacity>=.7,'workspace change needs a light continuity fade');await p.locator('[data-view=sd]').click();assert(await p.locator('[data-view=sd]').evaluate(n=>n.classList.contains('active')));await p.waitForFunction(()=>getComputedStyle(document.querySelector('#gallery')).opacity==='1');
 });
 await check('keyboard and reduced motion stay immediate',async p=>{
  await p.locator('[data-view=library]').focus();await p.keyboard.press('Enter');const a=await p.locator('.sidebar nav .active').boundingBox(),b=await p.locator('.sidebar nav .sidebar-selection').boundingBox();assert(Math.abs(a.y-b.y)<1);assert.equal(await p.locator('#gallery').evaluate(n=>getComputedStyle(n).opacity),'1');await p.emulateMedia({reducedMotion:'reduce'});await p.locator('[data-view=sd]').click();const c=await p.locator('.sidebar nav .active').boundingBox(),d=await p.locator('.sidebar nav .sidebar-selection').boundingBox();assert(Math.abs(c.y-d.y)<1);assert.equal(await p.locator('#gallery').evaluate(n=>getComputedStyle(n).opacity),'1');
 });
 await browser.close();server.close();assert.equal(failed,0,failed+' v0.11 checks failed');console.log('PASS all v0.11 motion checks');
})().catch(e=>{console.error(e.message);server.close();process.exitCode=1});
