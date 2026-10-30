const {chromium}=require('playwright'),http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{const p=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(!p.startsWith(root+path.sep)){res.writeHead(403).end();return}try{res.setHeader('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.ico':'image/x-icon'}[path.extname(p)]||'text/plain');res.end(fs.readFileSync(p))}catch{res.writeHead(404).end()}});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true}),p=await browser.newPage({viewport:{width:1440,height:960}});p.setDefaultTimeout(5000);const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.addInitScript(()=>{
  const ok=data=>({ok:true,data}),file=(id,kind='jpeg')=>({id:'f'+id+kind,photo_id:id,kind,path:'C:/'+id+(kind==='raw'?'.rw2':'.jpg')}),photo=id=>({id,stem:id,activity_id:'act',person_id:'u',edited:0,assets:[file(id),file(id,'raw')]});
  window.test={activities:[{id:'act',name:'活动一'},{id:'other',name:'活动二'}],photos:[photo('one'),photo('two')],imports:[],deletes:[],trash:[],taskResult:{}};
  window.pywebview={api:{get_settings:async()=>ok({library_available:true,library:'C:/库'}),save_settings:async()=>ok({}),list_activities:async()=>ok(test.activities),list_people:async()=>ok([{id:'u',name:'待分类',role:'unclassified'}]),list_photos:async f=>ok(f.trashed?test.trash:test.photos),
   choose_source:async()=>ok({token:'src',path:'F:/',name:'SD'}),scan:async()=>{test.taskResult={scan_id:'s',photos:[{id:'src',stem:'source',relative_dir:'',files:[file('src')]}]};return ok({task_id:'scan'})},
   get_task:async()=>ok({status:'succeeded',errors:[],result:test.taskResult}),
   get_preview:async()=>ok({url:'data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="#495961"/></svg>')}),
   get_photo_details:async id=>{if(id==='one')await new Promise(r=>setTimeout(r,350));return ok({camera:id==='one'?'Old camera':'Panasonic DC-S5M2',captured_at:'2026-10-28 12:34:56',focal_length:'85 mm',lens:'LUMIX S 85/F1.8',aperture:'f/2.8',shutter:'1/250 s',iso:'640',files:[{kind:'jpeg',name:'a.jpg',bytes:1048576},{kind:'raw',name:'a.rw2',bytes:25165824}],total_bytes:26214400})},
   import_selected:async(scan,ids,activity,format)=>{test.imports.push({scan,ids,activity,format});test.taskResult={activity_id:test.activities.find(a=>a.name===activity).id,imported:[],updated:[],skipped:0};return ok({task_id:'import'})},
   create_activity:async name=>{const a={id:'new',name};test.activities.push(a);return ok(a)},
   delete_activity:async id=>{test.deletes.push(id);test.activities=test.activities.filter(a=>a.id!==id);test.trash=test.photos;test.photos=[];test.taskResult={deleted_activity:id};return ok({task_id:'delete'})}
  }};
 });
 try{
  await p.goto(`http://127.0.0.1:${server.address().port}/index.html`);
  await p.locator('#activities [data-activity=act]').waitFor();await p.locator('#choose-source').click();await p.locator('.photo').click();await p.locator('#import').click();
  const activity=p.getByLabel('活动名称',{exact:true});assert.equal(await activity.evaluate(el=>el.tagName),'SELECT');await activity.selectOption({label:'活动二'});assert.match(await p.locator('#modal .notice').innerText(),/活动二/);
  await p.getByRole('button',{name:'开始导入',exact:true}).click();await p.waitForFunction(()=>test.imports.length===1);assert.equal(await p.evaluate(()=>test.imports[0].activity),'活动二');await p.locator('#taskbar[hidden]').waitFor({state:'attached'});
  await p.locator('[data-view=sd]').click();await p.locator('.photo').click();await p.locator('#import').click();await p.locator('#modal').getByRole('button',{name:'新建活动',exact:true}).click();await p.getByLabel('活动名称',{exact:true}).fill('新漫展');await p.getByRole('button',{name:'创建活动',exact:true}).click();await p.waitForFunction(()=>document.querySelector('#modal select')?.value==='新漫展');await p.getByRole('button',{name:'开始导入',exact:true}).click();await p.waitForFunction(()=>test.imports.length===2);assert.equal(await p.evaluate(()=>test.imports[1].activity),'新漫展');await p.locator('#taskbar[hidden]').waitFor({state:'attached'});
  await p.locator('#activities [data-activity=act]').click();await p.locator('#people [data-person=u]').click();await p.locator('.photo[data-id=one]').click();await p.locator('.photo[data-id=two]').click();await p.waitForFunction(()=>document.querySelector('#inspector')?.innerText.includes('Panasonic DC-S5M2'));await p.waitForTimeout(450);
  const details=await p.locator('#inspector').innerText();for(const text of ['文件大小','拍摄日期','相机型号','镜头焦段','相机参数','85 mm','f/2.8','1/250 s','ISO 640','25 MB'])assert.ok(details.includes(text),text);assert.ok(!details.includes('Old camera'),'late details must not replace new selection');
  const chip=p.locator('.large-thumb .format-chip');assert.match(await chip.innerText(),/JPG.*RAW/);assert.match(await chip.evaluate(el=>getComputedStyle(el).backdropFilter),/blur/);assert.equal(await chip.evaluate(el=>getComputedStyle(el).bottom),'10px');
  assert.equal(await p.title(),'洗衣机管理器');assert.match(await p.locator('.brand').innerText(),/洗衣机管理器/);assert.equal(await p.locator('#settings').innerText(),'');assert.equal(await p.getByRole('button',{name:'设置',exact:true}).count(),1);assert.equal(await p.locator('#settings svg').count(),1);assert.equal(await p.locator('#trash svg').count(),1);assert.equal(await p.locator('[data-view=sd]').innerText(),'选片');
  const red=await p.locator('#trash').evaluate(el=>getComputedStyle(el).color);assert.notEqual(red,'rgb(166, 169, 179)');
  await p.screenshot({path:path.resolve(__dirname,'../../../work/v06-ui-details.png')});
  await p.locator('#activities [data-activity=act]').click({button:'right'});await p.getByRole('menuitem',{name:'删除活动…',exact:true}).click();assert.match(await p.locator('#modal').innerText(),/回收站/);await p.getByRole('button',{name:'取消',exact:true}).click();assert.equal(await p.evaluate(()=>test.deletes.length),0);
  await p.locator('#activities [data-activity=act]').click({button:'right'});await p.getByRole('menuitem',{name:'删除活动…',exact:true}).click();await p.getByRole('button',{name:'确认',exact:true}).click();await p.waitForFunction(()=>test.deletes.length===1);await p.locator('#taskbar[hidden]').waitFor({state:'attached'});assert.deepEqual(await p.evaluate(()=>test.deletes),['act']);assert.equal(await p.locator('#activities [data-activity=act]').count(),0);assert.deepEqual(errors,[]);
  console.log('PASS v0.6: explicit activity chooser/new activity; deletion/cancel; branding/icons; glass formats; EXIF details and stale-response guard');
 }catch(e){await p.screenshot({path:path.resolve(__dirname,'../../../work/v06-ui-failure.png')});throw e}finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});

