const artifact=require('./helpers/artifact.cjs');
const {chromium}=require('playwright'),http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{const p=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(!p.startsWith(root+path.sep)){res.writeHead(403).end();return}try{res.setHeader('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css'}[path.extname(p)]||'text/plain');res.end(fs.readFileSync(p))}catch{res.writeHead(404).end()}});
(async()=>{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1440,height:960}});page.setDefaultTimeout(6000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    const ok=data=>({ok:true,data}),file=(id,kind)=>({id:id+kind,kind,path:'C:/'+id+'.'+kind,photo_id:id});
    const photos=['a','b','c'].map(id=>({id,stem:id,activity_id:'act',person_id:'u',edited:0,primary_export_id:null,assets:[file(id,'jpeg'),file(id,'raw')]}));
    window.test={library:'C:/旧库',photos,trash:[],calls:[],created:[],recent:[{path:'C:/旧库',name:'旧库',current:true,available:true}]};
    const api=window.pywebview={api:{
      get_settings:async()=>ok({library_available:!!test.library,library:test.library}),save_settings:async()=>ok({}),
      list_activities:async()=>ok([{id:'act',name:'活动'}]),list_people:async()=>ok([{id:'u',name:'待分类'}]),list_photos:async f=>ok(f.trashed?test.trash:test.photos),
      get_preview:async()=>ok({url:null,error:'fixture RAW'}),choose_source:async()=>ok({token:'s',name:'SD',path:'C:/SD'}),scan:async()=>ok({task_id:'scan'}),
      get_task:async id=>ok({id,status:'succeeded',errors:[],result:id==='scan'?{scan_id:'scan',photos:[{id:'pair',stem:'pair',relative_dir:'JPEG',relative_dirs:['JPEG','RAW'],files:[file('pair','jpeg'),file('pair','raw')]},{id:'j',stem:'j',relative_dir:'JPEG',files:[file('j','jpeg')]},{id:'r',stem:'r',relative_dir:'RAW',files:[file('r','raw')]}]}:{photo_ids:[],operations:[]}}),
      set_finished:async(ids,value)=>{test.calls.push({ids,value});return ok({task_id:'finish'})},
      trash_photos:async ids=>{test.calls.push({trash:ids});test.trash.push(...test.photos.filter(p=>ids.includes(p.id)));test.photos=test.photos.filter(p=>!ids.includes(p.id));return ok({task_id:'trash'})},
      restore_photos:async ids=>{test.photos.push(...test.trash.filter(p=>ids.includes(p.id)));test.trash=test.trash.filter(p=>!ids.includes(p.id));return ok({task_id:'restore'})},
      list_libraries:async()=>ok(test.recent),choose_library_parent:async()=>ok({token:'parent',path:'C:/照片'}),
      create_library:async(token,name)=>{if(test.delayCreate)await new Promise(resolve=>test.releaseCreate=resolve);test.created.push({token,name});test.library='C:/照片/'+name;test.recent.push({path:test.library,name,current:true,available:true});return ok({path:test.library})},
      choose_library:async()=>ok(null),open_library:async p=>{test.library=p;return ok({path:p})},remove_recent_library:async p=>{test.recent=test.recent.filter(r=>r.path!==p);return ok(true)}
    }};
  });
  try{
    await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);await page.locator('[data-view=library]').click();await page.locator('#toggle-browse').click();await page.locator('.photo').first().waitFor();
    await page.locator('.photo[data-id=a]').click();await page.locator('.photo[data-id=b]').click();await page.locator('.photo[data-id=a]').click({button:'right'});
    await page.getByRole('menuitem',{name:'标为成片',exact:true}).click();await page.waitForFunction(()=>test.calls.length===1);assert.deepEqual(await page.evaluate(()=>test.calls[0].ids),['a','b']);
    await page.locator('.photo[data-id=c]').click({button:'right'});assert.equal(await page.locator('.photo.checked').count(),1);await page.keyboard.press('Escape');assert.equal(await page.getByRole('menu').count(),0);
    await page.locator('#gallery').focus();await page.keyboard.press('Shift+F10');await page.getByRole('menuitem',{name:'删除照片…',exact:true}).click();await page.getByRole('button',{name:'确认',exact:true}).click();await page.waitForFunction(()=>test.trash.length===1);await page.locator('#taskbar[hidden]').waitFor({state:'attached'});assert.equal(await page.locator('.photo').count(),2);
    await page.getByRole('button',{name:'回收站',exact:true}).click();await page.getByRole('button',{name:'恢复',exact:true}).click();await page.waitForFunction(()=>test.trash.length===0);await page.locator('#taskbar[hidden]').waitFor({state:'attached'});assert.equal(await page.locator('.photo').count(),3);await page.getByRole('button',{name:'关闭',exact:true}).click();
    await page.getByRole('button',{name:'管理照片库',exact:true}).click();await page.getByRole('button',{name:'新建照片库',exact:true}).click();await page.getByLabel('照片库名称').fill('漫展库');await page.getByRole('button',{name:'创建并打开',exact:true}).click();assert.equal(await page.locator('#modal').evaluate(e=>e.open),true,'validation failure keeps creation form open');assert.match(await page.locator('.field-error').textContent(),/保存位置/);await page.getByRole('button',{name:'选择保存位置',exact:true}).click();await page.evaluate(()=>test.delayCreate=true);await page.getByRole('button',{name:'创建并打开',exact:true}).click();await page.waitForFunction(()=>typeof test.releaseCreate==='function');await page.keyboard.press('Escape');assert.equal(await page.locator('#modal').evaluate(e=>e.open),true,'pending library creation cannot close and interfere with another dialog');assert.equal(await page.locator('#modal').getByRole('button',{name:'返回',exact:true}).isDisabled(),true);await page.evaluate(()=>test.releaseCreate());await page.waitForFunction(()=>test.created.length===1);await page.locator('#modal:not([open])').waitFor({state:'attached'});assert.deepEqual(await page.evaluate(()=>test.created[0]),{token:'parent',name:'漫展库'});assert.equal(await page.locator('.photo.checked').count(),0);
    await page.locator('[data-view=sd]').click();await page.locator('#choose-source').click();await page.getByRole('button',{name:'文件夹 RAW',exact:true}).click();assert.equal(await page.locator('.photo').count(),2);
    await page.locator('#format-filter').selectOption('jpeg');assert.equal(await page.locator('.photo').count(),1);await page.locator('#format-filter').selectOption('raw');assert.equal(await page.locator('.photo').count(),2);
    await page.locator('.photo').first().click({button:'right'});assert.equal(await page.getByRole('menuitem',{name:'删除照片…',exact:true}).count(),0);await page.keyboard.press('Escape');assert.deepEqual(errors,[]);
    await page.screenshot({path:artifact('v03-ui.png')});console.log('PASS v0.3: context group/unselected/keyboard; trash restore; create library; split folders and filters; SD protected');
  }catch(e){await page.screenshot({path:artifact('v03-ui-failure.png')});throw e}finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
