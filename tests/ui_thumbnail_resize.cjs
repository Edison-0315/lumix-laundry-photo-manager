const {chromium}=require('playwright'),http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const artifact=require('./helpers/artifact.cjs'),root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{
 const file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
 if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return}
 try{res.setHeader('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file))}catch{res.writeHead(404).end()}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true});let failed=0;
 try{
  const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   const ok=data=>({ok:true,data});window.test={saved:[]};
   const people=Array.from({length:200},(_,i)=>({id:'person'+i,name:i===0?'超长名称测试_人物分类_不会把小图标撑开':'人物 '+i}));
   const photos=people.flatMap((p,i)=>Array.from({length:3},(_,n)=>({id:p.id+'-'+n,activity_id:'a',person_id:p.id,stem:'LUMIX_'+i+'_'+n,edited:0,assets:[{id:'asset'+i+'-'+n,kind:'jpeg',path:'C:/库/'+i+'-'+n+'.jpg'}]})));
   const url='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="600"><rect width="400" height="600" fill="#42607b"/><circle cx="200" cy="250" r="120" fill="#d9a87b"/></svg>');
   window.pywebview={api:{get_settings:async()=>ok({library_available:true,library:'C:/测试库',thumbnail_size:240}),list_activities:async()=>ok([{id:'a',name:'漫展'}]),list_people:async()=>ok(people),list_photos:async()=>ok(photos),get_preview:async()=>ok({url}),get_photo_details:async()=>ok({files:[]}),save_settings:async values=>{test.saved.push(values);return ok(values)},choose_source:async()=>ok({token:'src',path:'E:/DCIM'}),scan:async()=>ok({task_id:'s'}),get_task:async()=>ok({status:'succeeded',result:{scan_id:'s',photos:photos.map((p,i)=>({...p,relative_dir:'组'+Math.floor(i/3),files:p.assets}))}})}};
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);await page.locator('#activities button').waitFor();await page.locator('[data-view=library]').click();await page.locator('.folder-card').first().waitFor();await page.waitForTimeout(350);
  const size=async value=>{await page.locator('#thumb-size').fill(String(value));await page.locator('#thumb-size').dispatchEvent('input');await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))};
  const geometry=()=>page.evaluate(()=>{
   const grid=document.querySelector('#gallery'),card=grid.querySelector('.folder-card'),art=card.querySelector('.folder-art'),icon=art.querySelector('.folder-icon');
   const box=n=>{const r=n.getBoundingClientRect();return {width:r.width,height:r.height,x:r.x,y:r.y}};
   return {card:box(card),art:box(art),icon:box(icon),scrollWidth:grid.scrollWidth,clientWidth:grid.clientWidth};
  });
  async function check(name,fn){try{await fn();console.log('PASS '+name)}catch(e){failed++;console.error('FAIL '+name+': '+e.message)}}
  const samples=[];
  await check('long names do not shift artwork below neighboring folders',async()=>{
   await size(240);const tops=await page.locator('.folder-art').evaluateAll(nodes=>nodes.slice(0,3).map(n=>n.getBoundingClientRect().top));
   if(!process.env.PIANJI_DIAGNOSE)assert(Math.max(...tops)-Math.min(...tops)<1,'folder artwork must align at the top of a row');
  });
  await check('folder artwork keeps its proportion throughout 80–720 sizing',async()=>{
   for(const value of [80,120,200,240,320,480,720]){await size(value);const g=await geometry();samples.push({value,...g});if(!process.env.PIANJI_DIAGNOSE){assert(Math.abs(g.art.width/g.art.height-4/3)<.04,`size ${value}: folder art ${g.art.width.toFixed(1)} × ${g.art.height.toFixed(1)}`);assert(Math.abs(g.card.width-value)<2,`size ${value}: card stretched to ${g.card.width}`);assert(g.scrollWidth<=g.clientWidth+1,'gallery overflows horizontally')}}
  });
  await check('dense slider input coalesces gallery writes and retains final value',async()=>{
   const writes=await page.evaluate(async()=>{
    const {setThumbnailSize}=await import('./gallery.js'),grid=document.querySelector('#gallery');let writes=0;
    const observer=new MutationObserver(records=>writes+=records.filter(r=>r.attributeName==='style').length);observer.observe(grid,{attributes:true});
    for(let i=0;i<100;i++)setThumbnailSize(80+(i%32)*20);
    await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));observer.disconnect();
    return {writes,css:grid.style.getPropertyValue('--thumb-size'),input:document.querySelector('#thumb-size').value};
   });
   if(!process.env.PIANJI_DIAGNOSE){assert(writes.writes<=2,`100 inputs produced ${writes.writes} gallery style writes`);assert.equal(writes.css,'140px');assert.equal(writes.input,'140')}
   samples.push({burst:writes});
  });
  const cdp=await page.context().newCDPSession(page);await cdp.send('Performance.enable');
  const before=(await cdp.send('Performance.getMetrics')).metrics;
  const timing=await page.evaluate(async()=>{const {setThumbnailSize}=await import('./gallery.js');const stamps=[];for(let i=0;i<60;i++){await new Promise(r=>requestAnimationFrame(t=>{stamps.push(t);setThumbnailSize(80+i*10);r()}))}await new Promise(r=>requestAnimationFrame(r));return {frames:stamps.length,over32:stamps.slice(1).filter((v,i)=>v-stamps[i]>32).length,maxGap:Math.max(...stamps.slice(1).map((v,i)=>v-stamps[i]))}});
  const after=(await cdp.send('Performance.getMetrics')).metrics;
  const metric=name=>(after.find(m=>m.name===name)?.value||0)-(before.find(m=>m.name===name)?.value||0);
  samples.push({profile:{...timing,layoutMs:metric('LayoutDuration')*1000,styleMs:metric('RecalcStyleDuration')*1000,scriptMs:metric('ScriptDuration')*1000}});
  fs.writeFileSync(artifact(process.env.PIANJI_DIAGNOSE?'thumbnail-resize-before.json':'thumbnail-resize-after.json'),JSON.stringify(samples,null,2));
  await size(240);await page.screenshot({path:artifact(process.env.PIANJI_DIAGNOSE?'folder-size-before.png':'folder-size-after.png')});
  await check('small viewport and SD folders retain selection while sizing',async()=>{
   await page.setViewportSize({width:1040,height:720});await size(80);await page.locator('.folder-card').first().click();
   const selected=await page.locator('.folder-card.checked').getAttribute('data-select-key');await size(720);const g=await geometry();
   if(!process.env.PIANJI_DIAGNOSE){assert(g.scrollWidth<=g.clientWidth+1);assert(g.card.width<=g.clientWidth);assert(Math.abs(g.art.width/g.art.height-4/3)<.04)}
   assert.equal(await page.locator('.folder-card.checked').getAttribute('data-select-key'),selected);
   await page.locator('[data-view=sd]').click();await page.locator('#choose-source').click();await page.locator('.folder-card').first().waitFor();await size(80);const sd=await geometry();
   if(!process.env.PIANJI_DIAGNOSE)assert(Math.abs(sd.art.width/sd.art.height-4/3)<.04);
   await page.waitForTimeout(650);assert.equal(await page.evaluate(()=>test.saved.at(-1).thumbnail_size),80);
  });
  assert.deepEqual(errors,[]);assert.equal(failed,0,`${failed} thumbnail checks failed`);console.log('PASS folder thumbnail resizing; profile '+JSON.stringify(samples.at(-1)));
 }finally{await browser.close();await new Promise(r=>server.close(r))}
})().catch(e=>{console.error(e);process.exitCode=1});
