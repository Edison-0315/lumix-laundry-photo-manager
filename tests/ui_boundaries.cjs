const {chromium}=require('playwright'),http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{const p=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(!p.startsWith(root+path.sep)){res.writeHead(403).end();return}try{res.setHeader('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css'}[path.extname(p)]||'text/plain');res.end(fs.readFileSync(p))}catch{res.writeHead(404).end()}});
function fixture(){
  window.test={color:'red',previews:[],unlinks:[]};const ok=data=>({ok:true,data});
  const photo=(id,activity,person)=>({id,activity_id:activity,person_id:person,stem:id,captured_at:null,edited:1,primary_export_id:'e'+id,assets:[{id:'f'+id,photo_id:id,kind:'jpeg',path:'C:/'+id+'.jpg',sha256:'0'},{id:'e'+id,photo_id:id,kind:'export',path:'C:/'+id+'-finish.jpg',sha256:'0'}]});
  const photos=[photo('a','one','u'),photo('b','one','v'),photo('c','two','q')];
  window.pywebview={api:{get_settings:async()=>ok({library_available:true,library:'C:/库',photoshop:'C:/Photoshop.exe'}),save_settings:async()=>ok({}),
    list_activities:async()=>ok([{id:'one',name:'活动一'},{id:'two',name:'活动二'}]),list_people:async activity=>ok(activity==='one'?[{id:'u',name:'人物一'},{id:'v',name:'人物二'}]:[{id:'q',name:'人物三'}]),list_photos:async()=>ok(photos),
    get_preview:async(id,kind)=>{test.previews.push({id,kind,color:test.color});return ok({url:'data:image/svg+xml,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><rect width="120" height="80" fill="${test.color}"/></svg>`),error:null})},
    open_photoshop:async()=>ok({requested:true}),unlink_export:async(id,asset)=>{test.unlinks.push({id,asset});const p=photos.find(p=>p.id===id);p.primary_export_id=null;p.assets=p.assets.filter(a=>a.id!==asset);return ok({task_id:'unlink'})},get_task:async id=>ok({id,status:'succeeded',errors:[],result:'operation'})
  }};
}
(async()=>{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true});const failures=[];
  async function scenario(name,fn){const page=await browser.newPage({viewport:{width:1440,height:960}});page.setDefaultTimeout(5000);try{await page.addInitScript(fixture);await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);await page.locator('[data-view=library]').click();await page.locator('#toggle-browse').click();await page.locator('.photo').first().waitFor();await fn(page);console.log('PASS',name)}catch(e){failures.push(name+': '+e.message);console.log('FAIL',name,e.message.split('\n')[0])}finally{await page.close()}}
  try{
    await scenario('external save revalidates thumbnail and big preview',async p=>{
      await p.locator('.photo[data-id=a]').click();await p.getByRole('button',{name:'用 Photoshop 打开',exact:true}).click();
      await p.waitForTimeout(100);await p.evaluate(()=>test.color='blue');await p.locator('.photo[data-id=b]').click();await p.locator('.photo[data-id=a]').click();
      await p.waitForFunction(()=>document.querySelector('#inspector .large-thumb img')?.src.includes('blue'));
      await p.locator('.photo[data-id=a]').dblclick();await p.waitForFunction(()=>document.querySelector('#viewer-image').src.includes('blue'));await p.locator('#viewer-close').click();
      await p.evaluate(()=>test.color='green');await p.locator('.photo[data-id=a]').dblclick();await p.waitForFunction(()=>document.querySelector('#viewer-image').src.includes('green'));
    });
    await scenario('filtered inspector cannot act on hidden photo',async p=>{
      await p.locator('#select-all').click();await p.locator('#only-selected').check();await p.locator('.photo[data-id=a]').click();await p.waitForTimeout(650);
      assert.equal(await p.locator('.photo[data-id=a]').count(),0);assert.notEqual(await p.locator('#inspector .file-title').textContent(),'a');
      const unlink=p.getByRole('button',{name:'解除此版本关联',exact:true});if(await unlink.count()){await unlink.click();await p.getByRole('button',{name:'确认',exact:true}).click();await p.waitForFunction(()=>test.unlinks.length===1);assert.equal(await p.evaluate(()=>test.unlinks[0].id),'b')}
    });
    await scenario('double preview does not cancel another pending deselection',async p=>{
      await p.locator('#select-all').click();await p.locator('#only-selected').check();await p.locator('.photo[data-id=a]').click();await p.locator('.photo[data-id=b]').dblclick();await p.waitForTimeout(650);
      assert.equal(await p.locator('.photo[data-id=a]').count(),0);assert.equal(await p.locator('.photo.checked').count(),1);
    });
    await scenario('person and activity changes reset selected-only filter',async p=>{
      await p.locator('#select-all').click();await p.locator('#only-selected').check();await p.locator('#people button').filter({hasText:'人物一'}).click();
      assert.equal(await p.locator('#only-selected').isChecked(),false);assert.equal(await p.locator('.photo').count(),1);
      await p.locator('.photo').click();await p.locator('#only-selected').check();await p.locator('#activities button').filter({hasText:'活动二'}).click();await p.locator('#toggle-browse').click();
      assert.equal(await p.locator('#only-selected').isChecked(),false);assert.equal(await p.locator('.photo').count(),1);
    });
    assert.deepEqual(failures,[]);
  }finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
