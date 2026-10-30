const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{
  const p=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
  if(!p.startsWith(root+path.sep)){res.writeHead(403).end();return}
  try{res.setHeader('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css'}[path.extname(p)]||'application/octet-stream');res.end(fs.readFileSync(p))}catch{res.writeHead(404).end()}
});
(async()=>{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1440,height:960}});
  page.setDefaultTimeout(10000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    window.test={library:false,chooseCalls:0,cancelled:false,imports:[],calls:[],photos:[],slow:false};
    const sample=(id,relative_dir='')=>({id,stem:id,relative_dir,captured_at:null,files:[{id:'f'+id,photo_id:id,kind:'jpeg',path:'C:/SD/'+relative_dir+'/'+id+'.jpg',sha256:'0'}]});
    const source=[sample('a','DCIM/100'),sample('b','DCIM/200')];
    const url='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><rect width="120" height="80" fill="#555"/></svg>');
    const ok=data=>({ok:true,data});let job=null;
    window.pywebview={api:{
      get_settings:async()=>ok({library_available:test.library,library:test.library?'C:/库':null}),save_settings:async()=>ok({}),
      list_activities:async()=>ok([{id:'act',name:'活动'}]),list_people:async()=>ok([{id:'u',name:'待分类',role:'unclassified'}]),list_photos:async()=>ok(test.photos),
      choose_library:async()=>{test.chooseCalls++;if(test.cancelLibrary)return ok(null);test.library=true;return ok({path:'C:/库'})},choose_source:async()=>ok({token:'t',path:test.slow?'C:/新来源':'C:/SD',name:'SD'}),
      scan:async()=>{test.cancelled=false;job='scan';return ok({task_id:'scan'})},
      cancel_task:async()=>{test.cancelled=true;return ok({})},
      get_task:async id=>{
        if(id==='scan')return ok(test.cancelled?{id,status:'cancelled',errors:[],result:{cancelled:true}}:test.slow?{id,status:'running',done:0,total:2,message:'读取中',errors:[]}:{id,status:'succeeded',errors:[],result:{scan_id:'s',photos:source,cancelled:false}});
        return ok({id,status:'succeeded',errors:[],result:id==='import'?{activity_id:'act',imported:['a'],updated:[],skipped:0}:{operations:['op'],photo_ids:['a']}});
      },
      get_preview:async()=>ok({url,error:null}),
      import_selected:async(...args)=>{test.imports.push(args);test.photos=[{id:'a',stem:'a',activity_id:'act',person_id:'u',edited:0,primary_export_id:null,captured_at:null,assets:[{id:'fa',photo_id:'a',kind:'jpeg',path:'C:/库/a.jpg',sha256:'0'}]}];return ok({task_id:'import'})},
      set_finished:async(ids,value)=>{test.calls.push({ids,value});test.photos[0].primary_export_id=value?'export':null;test.photos[0].edited=1;test.photos[0].assets=test.photos[0].assets.filter(a=>a.kind!=='export');if(value)test.photos[0].assets.push({id:'export',photo_id:'a',kind:'export',path:'C:/库/成片/a.jpg',sha256:'0'});return ok({task_id:'finished'})}
    }};
  });
  try{
    await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);
    await page.getByRole('button',{name:'选择来源',exact:true}).click();
    await page.getByRole('button',{name:'文件夹 DCIM/100',exact:true}).click();
    await page.locator('.photo').first().waitFor();assert.equal(await page.locator('.photo').count(),1);assert.equal(await page.locator('.photo .name').first().textContent(),'a');
    console.log('folders ok');
    await page.locator('.photo').first().click();
    await page.evaluate(()=>test.cancelLibrary=true);await page.getByRole('button',{name:'导入所选',exact:true}).click();await page.waitForFunction(()=>test.chooseCalls===1);
    assert.equal(await page.locator('#modal').evaluate(el=>el.open),false);assert.equal(await page.locator('.photo.checked').count(),1);
    await page.evaluate(()=>test.cancelLibrary=false);
    await page.getByRole('button',{name:'导入所选',exact:true}).click();await page.getByRole('button',{name:'开始导入',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>test.chooseCalls),2,'import must prompt for a library automatically; cancel preserves selection');
    console.log('library prompt ok');
    await page.getByRole('button',{name:'开始导入',exact:true}).click();
    await page.waitForFunction(()=>test.imports.length===1);await page.locator('#taskbar[hidden]').waitFor({state:'attached'});await page.locator('.photo').first().waitFor();
    console.log('import ok');
    await page.locator('.photo').first().click();await page.getByRole('button',{name:'标为成片',exact:true}).click();
    await page.waitForFunction(()=>test.calls.length===1);
    await page.locator('[data-stage=exports]').click();assert.equal(await page.locator('.photo.checked').count(),0,'stage switch clears original selection');
    assert.equal(await page.locator('#mark-pending').isVisible(),false);assert.equal(await page.locator('#mark-edited').isVisible(),false);
    await page.locator('.photo').first().click();await page.getByRole('button',{name:'取消成片',exact:true}).click();await page.getByRole('button',{name:'确认',exact:true}).click();
    await page.waitForFunction(()=>test.calls.length===2);await page.waitForFunction(()=>document.querySelectorAll('.photo').length===0);
    assert.deepEqual(await page.evaluate(()=>test.calls.map(c=>c.value)),[true,false]);
    await page.getByRole('button',{name:'SD 卡选片',exact:true}).click();await page.locator('.photo').first().click();await page.evaluate(()=>test.slow=true);
    await page.getByRole('button',{name:'选择来源',exact:true}).click();await page.locator('#taskbar:not([hidden])').waitFor();await page.locator('#cancel-task').click();
    await page.locator('#taskbar[hidden]').waitFor({state:'attached'});assert(await page.evaluate(()=>test.cancelled));
    assert.equal(await page.locator('#modal h2').textContent(),'读取已取消');
    assert.equal(await page.locator('.photo.checked').count(),1);assert.equal(await page.locator('#subtitle').textContent(),'C:/SD');
    assert.deepEqual(errors,[]);console.log('Feedback UI PASS: folders; implicit library picker; direct finished/unlink; stage scope; cancel scan');
  }catch(e){await page.screenshot({path:path.resolve(__dirname,'../../../work/feedback-failure.png')});console.error('STATE',await page.evaluate(()=>({test,toast:document.querySelector('#toast').textContent,modal:document.querySelector('#modal').innerText})));throw e}finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
