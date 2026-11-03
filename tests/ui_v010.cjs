const artifact=require('./helpers/artifact.cjs');
const {chromium}=require('playwright'),{PNG}=require('pngjs'),http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{const f=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(!f.startsWith(root+path.sep)){res.writeHead(403).end();return}try{res.setHeader('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[path.extname(f)]||'application/octet-stream');res.end(fs.readFileSync(f))}catch{res.writeHead(404).end()}});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true});let failed=0;
 async function check(name,fn,options={}){
  const p=await browser.newPage({viewport:{width:1440,height:960},...options});p.setDefaultTimeout(4000);const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.addInitScript(()=>{
   const url=id=>'data:image/svg+xml,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1600"><rect width="1200" height="1600" fill="${id==='p0'?'#cf7593':'#67b6cf'}"/><path d="M0 500H1200M300 0V1600" stroke="#fff" stroke-width="100"/></svg>`);
   const people=[{id:'u',name:'待分类',role:'unclassified'},{id:'g',name:'合照',role:'group'},...Array.from({length:30},(_,i)=>({id:'m'+i,name:'人物_'+i}))];
   const photos=Array.from({length:32},(_,i)=>({id:'p'+i,activity_id:'a',person_id:i<2?'u':'m'+(i-2),stem:'照片_'+i,edited:0,assets:[{id:'f'+i,kind:'jpeg',path:'C:/库/'+i+'.jpg'}]}));const ok=data=>({ok:true,data});window.test={saved:[],delayed:false,resolve:null};
   window.pywebview={api:{get_settings:async()=>ok({library_available:true,library:'C:/非常长的父目录/漫展照片库',thumbnail_size:240}),list_activities:async()=>ok([{id:'a',name:'秋日漫展'}]),list_people:async()=>ok(people),list_photos:async()=>ok(photos),get_preview:async(id,kind)=>{if(test.delayed&&id==='p0'&&kind==='thumb')return new Promise(resolve=>test.resolve=()=>resolve(ok({url:url(id)})));return ok({url:url(id)})},get_photo_details:async()=>ok({files:[]}),save_settings:async values=>{test.saved.push(values);return ok({})},choose_source:async()=>ok({token:'source',path:'E:/DCIM'}),scan:async()=>ok({task_id:'scan'}),get_task:async()=>ok({status:'succeeded',result:{scan_id:'scan',photos:photos.map((p,i)=>({...p,relative_dir:'f'+i,files:p.assets}))}})}};
  });
  try{await p.goto(`http://127.0.0.1:${server.address().port}/index.html`);await p.locator('#choose-source:not([disabled])').waitFor();await fn(p);assert.deepEqual(errors,[]);console.log('PASS '+name)}catch(e){failed++;console.error('FAIL '+name+': '+e.message);await p.screenshot({path:artifact('v010-'+name.replace(/[^a-z0-9]/gi,'-')+'.png')})}finally{await p.close()}
 }
 const library=async p=>{await p.locator('[data-view=library]').click();await p.locator('#people [data-person=u]').click();await p.locator('.photo').first().waitFor()};
 await check('dark glass material and neutral workspace',async p=>{
  await library(p);assert.equal(await p.locator('#library-path').textContent(),'漫展照片库');assert.match(await p.locator('#library-path').getAttribute('title'),/非常长的父目录/);
  await p.locator('.sidebar>.lens-backdrop').waitFor();const color=await p.locator('.sidebar').evaluate(n=>getComputedStyle(n).color);const numbers=color.match(/\d+/g).map(Number);assert(numbers[0]>200&&numbers[1]>200&&numbers[2]>200,'dark sidebar uses light text');
  const bg=await p.locator('main').evaluate(n=>getComputedStyle(n).backgroundColor);assert(+bg.match(/\d+/g)[0]<50,'photo workspace stays dark');assert.equal(await p.locator('.photo .picture').first().evaluate(n=>getComputedStyle(n).filter),'none');await p.waitForFunction(()=>[...document.querySelectorAll('.sidebar-photo')].some(n=>n.style.backgroundImage.includes('data:image/')));
  const bar=PNG.sync.read(await p.locator('footer').screenshot()),pixel=(Math.floor(bar.height/2)*bar.width+Math.floor(bar.width/2))*4;assert((bar.data[pixel]+bar.data[pixel+1]+bar.data[pixel+2])/3<120,'floating controls must stay dark behind light labels');
 });
 await check('sidebar lens follows single navigation',async p=>{
  await library(p);await p.locator('#people [data-person=m4]').click();await p.locator('#people [data-person=m8]').click();await p.locator('#people [data-person=m3]').click();
  await p.waitForFunction(()=>{const row=document.querySelector('#people .side-item.active'),host=document.querySelector('#people-body .sidebar-selection');if(!row||!host)return false;const a=row.getBoundingClientRect(),b=host.getBoundingClientRect();return Math.abs(a.y-b.y)<1&&Math.abs(a.height-b.height)<1});
  assert.equal(await p.locator('#people .side-item.active').count(),1);assert.equal(await p.locator('.photo').count(),1);assert.equal(await p.locator('.sidebar .checked').count(),0);
  await p.locator('#people [data-person=m3]').click({button:'right'});assert.equal(await p.getByRole('menu',{name:'人物分类'}).count(),1);
 });
 await check('long sidebar and collapse remain reachable',async p=>{
  await library(p);await p.locator('#people [data-person=m29]').scrollIntoViewIfNeeded();await p.locator('#people [data-person=m29]').click();assert(await p.locator('#choose-library').isVisible());assert(await p.locator('#trash').isVisible());
  const sidebar=await p.locator('.sidebar').boundingBox(),bar=await p.locator('.sidebar-bottom').boundingBox();assert(bar.y+bar.height<=sidebar.y+sidebar.height);await p.locator('#people-collapse').click();assert.equal(await p.locator('#people-collapse').getAttribute('aria-expanded'),'false');await p.locator('#people-body').waitFor({state:'hidden'});assert(await p.locator('#people-body').evaluate(n=>n.inert));await p.locator('#people-collapse').click();await p.locator('#people-body').waitFor({state:'visible'});assert(!await p.locator('#people-body').evaluate(n=>n.inert));
 },{viewport:{width:1040,height:720}});
 await check('glass slider native range and keyboard',async p=>{
  const input=p.locator('#thumb-size');await input.fill('720');await input.dispatchEvent('input');assert.equal(await p.locator('#thumb-size-label').textContent(),'720');assert.equal(await input.evaluate(n=>n.style.getPropertyValue('--thumb-progress')),'100%');
  await input.focus();await p.keyboard.press('Home');assert.equal(await input.inputValue(),'80');assert.equal(await p.locator('#thumb-size-label').textContent(),'80');await p.keyboard.press('ArrowRight');assert.equal(await input.inputValue(),'100');await p.locator('#thumb-larger').click();assert.equal(await input.inputValue(),'140');await p.locator('#thumb-smaller').click();assert.equal(await input.inputValue(),'100');assert(await p.locator('.thumbnail-control .lens-backdrop').count());assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 },{viewport:{width:1040,height:720}});
 await check('reduced motion sidebar is immediate',async p=>{await library(p);await p.locator('#people [data-person=m2]').click();const a=await p.locator('#people .active').boundingBox(),b=await p.locator('#people-body .sidebar-selection').boundingBox();assert(Math.abs(a.y-b.y)<1)},{reducedMotion:'reduce'});
 await check('opaque dark fallback is readable',async p=>{
  const session=await p.context().newCDPSession(p);await session.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'}]});assert.equal(await p.locator('.sidebar>.lens-backdrop').evaluate(n=>getComputedStyle(n).display),'none');assert.equal(await p.locator('#sidebar-scene').evaluate(n=>getComputedStyle(n).display),'none');const bg=await p.locator('.sidebar').evaluate(n=>getComputedStyle(n).backgroundColor);assert(+bg.match(/\d+/g)[0]<65);await p.locator('#settings').click();assert(await p.locator('#modal').evaluate(n=>parseInt(getComputedStyle(n).color.match(/\d+/)[0])>160));
 });
 await check('late scene cannot repaint another person',async p=>{
  await p.evaluate(()=>test.delayed=true);await p.locator('[data-view=library]').click();await p.waitForFunction(()=>test.resolve);await p.locator('#people [data-person=m1]').click();await p.waitForFunction(()=>[...document.querySelectorAll('.sidebar-photo')].some(n=>n.style.opacity==='1'&&n.style.backgroundImage.includes('67b6cf')));await p.evaluate(()=>test.resolve());await p.waitForTimeout(100);assert(await p.evaluate(()=>[...document.querySelectorAll('.sidebar-photo')].find(n=>n.style.opacity==='1')?.style.backgroundImage.includes('67b6cf')));
 });
 await check('rapid collapse restores controls and focus',async p=>{
  await library(p);await p.locator('#people-collapse').click();await p.locator('#people-collapse').click();await p.locator('#people-body').waitFor({state:'visible'});await p.waitForTimeout(250);assert.equal(await p.locator('#people-body').evaluate(n=>n.inert),false);await p.locator('#people [data-person=m2]').click();assert.equal(await p.locator('.photo').count(),1);await p.locator('#people-collapse').click();await p.keyboard.press('Tab');assert(!await p.evaluate(()=>document.querySelector('#people-body').contains(document.activeElement)));
 });
 await check('source selection stays aligned while scrolling',async p=>{
  await p.locator('#choose-source').click();const row=p.getByRole('button',{name:'文件夹 f20',exact:true});await row.click();
  const aligned=()=>{const row=document.querySelector('#source-folders .active'),lens=document.querySelector('#source-section .sidebar-selection');return row&&lens&&Math.abs(row.getBoundingClientRect().y-lens.getBoundingClientRect().y)<1};await p.waitForFunction(aligned);
  await row.evaluate(n=>{let parent=n.parentElement;while(parent&&!(parent.scrollHeight>parent.clientHeight&&/auto|scroll/.test(getComputedStyle(parent).overflowY)))parent=parent.parentElement;if(!parent)throw Error('missing navigation scroll area');parent.scrollTop-=80});
  await p.waitForFunction(aligned);
 },{viewport:{width:1040,height:720}});
 await check('active navigation keeps visible keyboard focus',async p=>{
  await p.keyboard.press('Tab');await p.keyboard.press('Tab');const focus=await p.locator('[data-view=sd]').evaluate(n=>({visible:n.matches(':focus-visible'),style:getComputedStyle(n).outlineStyle,width:parseFloat(getComputedStyle(n).outlineWidth)}));assert(focus.visible,'Tab must focus selected navigation');assert(focus.style!=='none'&&focus.width>=2,'selected navigation needs a visible focus ring');
  await library(p);await p.keyboard.press('Tab');await p.locator('#people .active').focus();assert(await p.locator('#people .active').evaluate(n=>n.matches(':focus-visible')&&getComputedStyle(n).outlineStyle!=='none'));
  const session=await p.context().newCDPSession(p);await session.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-contrast',value:'more'}]});assert(await p.locator('#people .active').evaluate(n=>parseFloat(getComputedStyle(n).outlineWidth)>=2),'high contrast must distinguish keyboard focus from ordinary active outline');
 });
 await browser.close();server.close();assert.equal(failed,0,failed+' v0.10 checks failed');console.log('PASS all v0.10 sidebar/material/range checks');
})().catch(e=>{console.error(e.message);server.close();process.exitCode=1});
