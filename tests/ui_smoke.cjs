const {chromium}=require('playwright');
const http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{
  const p=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
  if(!p.startsWith(root+path.sep)){res.writeHead(403).end();return}
  const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css'};
  try{res.setHeader('Content-Type',mime[path.extname(p)]||'application/octet-stream');res.end(fs.readFileSync(p))}
  catch{res.writeHead(404).end()}
});
(async()=>{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:960}});
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    const pixels='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="260"><rect width="200" height="260" fill="#62646a"/></svg>');
    const photos=Array.from({length:200},(_,i)=>({id:'p'+i,activity_id:'a',person_id:'u',stem:i===0?'<img src=x onerror=alert(1)>':'照片'+i,captured_at:null,edited:0,manual_person:0,primary_export_id:null,missing:false,assets:[{id:'f'+i,photo_id:'p'+i,kind:'jpeg',path:'C:/test/'+i+'.jpg',sha256:'0'}]}));
    const ok=data=>Promise.resolve({ok:true,data});
    window.pywebview={api:{get_settings:()=>ok({library:'C:/test',library_available:true}),list_activities:()=>ok([{id:'a',name:'测试活动'}]),list_people:()=>ok([{id:'u',name:'待分类',role:'unclassified'},{id:'g',name:'合照',role:'group'}]),list_photos:()=>ok(photos),get_preview:()=>ok({url:pixels,error:null}),choose_source:()=>ok({token:'grant',name:'SD测试',path:'C:/SD'}),scan:()=>ok({task_id:'scan'}),get_task:id=>ok({id,status:'succeeded',errors:[],result:{scan_id:'s',photos:photos.map(p=>({...p,files:p.assets})),cancelled:false}}),save_settings:()=>ok({}),cancel_task:()=>ok({})}};
  });
  try{
    await page.goto('http://127.0.0.1:'+server.address().port+'/index.html');
    await page.getByRole('button',{name:'照片库',exact:true}).click();
    await page.locator('.photo').first().waitFor();
    assert.equal(await page.locator('.photo').count(),200);
    const initial=await page.locator('.photo').first().boundingBox();
    assert(initial.height>initial.width*.65,'thumbnail card must retain its photo area and labels');
    assert.equal(await page.locator('.photo .name').first().textContent(),'<img src=x onerror=alert(1)>');
    await page.locator('.photo').nth(0).click(); assert.equal(await page.locator('.photo.checked').count(),1);
    await page.locator('.photo').nth(2).click(); assert.equal(await page.locator('.photo.checked').count(),2);
    await page.locator('.photo').nth(0).click(); assert.equal(await page.locator('.photo.checked').count(),1);
    await page.locator('.photo').nth(4).click({modifiers:['Shift']}); assert.equal(await page.locator('.photo.checked').count(),5);
    const beforeDouble=await page.locator('.photo.checked').count();
    await page.locator('.photo').nth(4).dblclick(); await page.locator('#viewer[open]').waitFor();
    assert.equal(await page.locator('.photo.checked').count(),beforeDouble);
    await page.getByRole('button',{name:'关闭大图'}).click();
    await page.locator('#thumb-size').fill('80'); await page.locator('#thumb-size').dispatchEvent('input');
    assert.equal(await page.locator('#gallery').evaluate(el=>getComputedStyle(el).getPropertyValue('--thumb-size').trim()),'80px');
    await page.locator('#thumb-size').fill('720'); await page.locator('#thumb-size').dispatchEvent('input');
    assert.equal(await page.locator('#gallery').evaluate(el=>getComputedStyle(el).getPropertyValue('--thumb-size').trim()),'720px');
    await page.locator('#thumb-size').fill('200'); await page.locator('#thumb-size').dispatchEvent('input');
    const box=await page.locator('.photo').first().boundingBox();
    await page.evaluate(()=>{window.layoutReads=0;const original=Element.prototype.getBoundingClientRect;Element.prototype.getBoundingClientRect=function(){if(this.matches('.photo'))window.layoutReads++;return original.call(this)}});
    await page.mouse.move(box.x+5,box.y+5);await page.mouse.down();await page.mouse.move(box.x+box.width*2.4,box.y+box.height*.7,{steps:12});await page.mouse.up();
    assert((await page.locator('.photo.checked').count())>=2);
    assert.equal(await page.locator('.selection-marquee').count(),0);
    assert((await page.evaluate(()=>layoutReads))<=400,'drag must cache card geometry instead of remeasuring every pointer event');
    const gallery=await page.locator('#gallery').boundingBox();
    await page.mouse.move(gallery.x+8,gallery.y+8);await page.mouse.down();
    await page.mouse.move(gallery.x+100,gallery.y+gallery.height-3,{steps:10});
    await page.waitForTimeout(250);assert((await page.locator('#gallery').evaluate(el=>el.scrollTop))>0,'rubber-band edge scrolling');await page.keyboard.press('Escape');await page.mouse.up();
    assert.equal(await page.locator('.selection-marquee').count(),0);
    await page.locator('#gallery').evaluate(el=>el.scrollTop=0);
    await page.mouse.move(gallery.x+100,gallery.y+100);await page.keyboard.down('Control');await page.mouse.wheel(0,-80);await page.keyboard.up('Control');
    assert.equal(await page.locator('#thumb-size').inputValue(),'240');
    const libraryCount=await page.locator('.photo.checked').count();
    await page.getByRole('button',{name:'SD 卡选片',exact:true}).click();
    await page.getByRole('button',{name:'选择来源',exact:true}).click();
    await page.locator('.photo').first().waitFor();
    assert.equal(await page.locator('.photo.checked').count(),0);
    await page.locator('.photo').first().click();
    await page.getByRole('button',{name:'照片库',exact:true}).click();
    assert.equal(await page.locator('.photo.checked').count(),libraryCount);
    assert.deepEqual(errors,[]);
    if(process.env.PIANJI_SCREENSHOT)await page.screenshot({path:process.env.PIANJI_SCREENSHOT});
    console.log('UI PASS: real modules; literal filenames; click/Ctrl/Shift/double-click; 80–720 zoom; marquee; isolated selections');
  }finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
