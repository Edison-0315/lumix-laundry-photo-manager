const {chromium}=require('playwright'),http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{const p=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(!p.startsWith(root+path.sep)){res.writeHead(403).end();return}try{res.setHeader('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[path.extname(p)]||'text/plain');res.end(fs.readFileSync(p))}catch{res.writeHead(404).end()}});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true}),p=await browser.newPage({viewport:{width:1440,height:960}});p.setDefaultTimeout(5000);const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.addInitScript(()=>{
  const ok=data=>({ok:true,data});window.test={available:true,deletes:[],cleaned:0};
  window.pywebview={api:{get_settings:async()=>ok({library_available:test.available,library:test.available?'C:/照片库':null}),list_activities:async()=>ok([]),list_people:async()=>ok([]),list_photos:async()=>ok([]),list_libraries:async()=>ok(test.available?[{path:'C:/照片库',name:'照片库',current:true,available:true}]:[]),
    inspect_library_delete:async path=>ok({path,name:'照片库',token:'token',photo_count:20,file_count:45,bytes:104857600}),cleanup_empty_folders:async()=>{test.cleaned++;return ok({removed:['C:/照片库/旧人物'],errors:[]})},
    delete_library:async(token,name)=>{test.deletes.push({token,name});test.available=false;return ok({recycled:true})}
  }};
 });
 try{
  await p.goto(`http://127.0.0.1:${server.address().port}/index.html`);await p.locator('#choose-library').click();await p.getByRole('button',{name:'清理空文件夹',exact:true}).click();await p.waitForFunction(()=>test.cleaned===1);
  await p.getByRole('button',{name:'删除照片库…',exact:true}).click();assert.match(await p.locator('#modal').innerText(),/Windows 回收站/);assert.match(await p.locator('#modal').innerText(),/C:\/照片库/);assert.match(await p.locator('#modal').innerText(),/20/);
  const confirm=p.getByRole('button',{name:'移到系统回收站',exact:true}),name=p.getByLabel('输入照片库名称确认删除',{exact:true});assert.ok(await confirm.isDisabled());await name.fill('错误');assert.ok(await confirm.isDisabled());await p.locator('#modal').getByRole('button',{name:'返回',exact:true}).click();assert.equal(await p.evaluate(()=>test.deletes.length),0);
  await p.getByRole('button',{name:'删除照片库…',exact:true}).click();await name.fill('照片库');await confirm.click();await p.waitForFunction(()=>test.deletes.length===1);await p.waitForFunction(()=>document.querySelector('#modal')?.innerText.includes('还没有照片库'));assert.deepEqual(await p.evaluate(()=>test.deletes),[{token:'token',name:'照片库'}]);await p.getByRole('button',{name:'关闭',exact:true}).click();
  assert.ok(await p.locator('[data-view=sd] svg').count());assert.ok(await p.locator('#choose-library svg').count());assert.ok(await p.locator('.empty .empty-icon svg').count());
  assert.match(await p.locator('.sidebar').evaluate(el=>getComputedStyle(el).backdropFilter),/blur/);assert.ok(parseInt(await p.locator('.sidebar').evaluate(el=>getComputedStyle(el).borderRadius))>=16);assert.ok(parseInt(await p.locator('#modal').evaluate(el=>getComputedStyle(el).borderRadius))>=18);
  await p.screenshot({path:path.resolve(__dirname,'../../../work/v07-glass-1440.png')});await p.setViewportSize({width:1040,height:720});await p.screenshot({path:path.resolve(__dirname,'../../../work/v07-glass-1040.png')});
  assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);console.log('PASS v0.7: cleanup entry; actual-library delete preview/name gate/cancel/refresh; SVG icons; rounded glass; desktop widths');
 }catch(e){await p.screenshot({path:path.resolve(__dirname,'../../../work/v07-ui-failure.png')});throw e}finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});

