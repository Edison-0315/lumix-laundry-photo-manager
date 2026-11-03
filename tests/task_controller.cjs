// Exercise the task boundary against real UI modules and DOM; only native API is substituted.
const {chromium}=require('playwright'),http=require('http'),fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../pianji/ui');
const server=http.createServer((req,res)=>{
 const file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
 if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return}
 try{let data=fs.readFileSync(file);if(file.endsWith('index.html'))data=Buffer.from(data.toString().replace(/<script[^>]*src="app.js"[^>]*><\/script>/,''));res.setHeader('Content-Type',{'.html':'text/html','.js':'text/javascript','.css':'text/css'}[path.extname(file)]||'application/octet-stream');res.end(data)}catch{res.writeHead(404).end()}
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await chromium.launch({channel:'msedge',headless:true});const p=await browser.newPage();
  await p.goto(`http://127.0.0.1:${server.address().port}/index.html`);
  const result=await p.evaluate(async()=>{
   const {createTaskController}=await import('./features/tasks.js'),{state}=await import('./store.js');
   const ok=data=>({ok:true,data});let refreshes=0,inspections=0,release;
   state.scanId='old';state.source={path:'E:/old'};state.sourcePhotos=[{id:'old',files:[]}];state.selected.sd.add('old');
   window.pywebview={api:{choose_source:async()=>ok({path:'E:/new',token:'new'}),scan:async()=>ok({task_id:'scan'}),get_task:async()=>new Promise(resolve=>release=()=>resolve(ok({status:'cancelled',result:{cancelled:true}}))),cancel_task:async()=>ok(true),broken:async()=>{throw new Error('offline')}}};
   const tasks=createTaskController({refresh:async()=>refreshes++,renderInspector:()=>inspections++});
   const running=tasks.scanSource();while(!release)await new Promise(r=>setTimeout(r,0));
   let blocked=false;try{await tasks.start('broken')}catch(e){blocked=e.message.includes('等待')}
   await tasks.cancel();const cancelling=document.querySelector('#cancel-task').disabled&&document.querySelector('#task-message').textContent.includes('安全结束');
   release();await running;
   const cancelled=state.scanId==='old'&&state.source.path==='E:/old'&&state.selected.sd.has('old')&&document.querySelector('#modal-title').textContent==='读取已取消';
   let failed=false;try{await tasks.start('broken')}catch(e){failed=e.message==='offline'}
   return {blocked,cancelling,cancelled,failed,busy:state.busy,hidden:document.querySelector('#taskbar').hidden,refreshes,inspections};
  });
  assert.deepEqual(result,{blocked:true,cancelling:true,cancelled:true,failed:true,busy:false,hidden:true,refreshes:1,inspections:2});
  console.log('PASS task cancellation retains scan/selection; duplicate work rejected; failures release busy UI');
 }finally{if(browser)await browser.close();await new Promise(r=>server.close(r))}
})().catch(e=>{console.error(e);process.exitCode=1});
