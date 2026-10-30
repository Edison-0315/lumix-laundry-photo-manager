import {ready,api} from './api.js';
import {state,$,selected,basePhotos,visible,current,assets,el,button,toast,error,folderPaths,sourceDirs,resetLibrarySelection,libraryFolderMode,libraryFolders,childFolders} from './store.js';
import {renderGallery,syncSelection,setThumbnailSize,onInspector,onFolder,openViewer,setupViewer,updatePhotoThumbnail} from './gallery.js';
import {preview,invalidateLibraryPreviews} from './previews.js';
import {setupSelection} from './selection.js';
import {settingsDialog,importDialog,assignDialog,newPersonDialog,managePeopleDialog,confirmAction,resultDialog,deleteDialog,trashDialog,newActivityDialog,deletePeopleDialog} from './dialogs.js';
import {libraryDialog} from './library-manager.js';
import {setupContextMenu,commandMenu} from './context-menu.js';
import {bindChoice,choices,syncChoices,clearChoices,folderScope,selectableFolderKeys} from './choice-list.js';
import {remember,goBack,clearHistory} from './navigation.js';

let taskId=null,inspectorRevision=0,proposedSource=null;
const safe=fn=>(...args)=>Promise.resolve().then(()=>fn(...args)).catch(error);

async function refresh(){
  state.settings=await api('get_settings');
  if(state.settings.library_available){
    state.activities=await api('list_activities');
    if(!state.activities.some(a=>a.id===state.activity))state.activity=state.activities[0]?.id||null;
    state.people=state.activity?await api('list_people',state.activity):[];
    state.photos=await api('list_photos',{});
    if(state.person!=='all'&&!state.people.some(p=>p.id===state.person)){state.person='all';state.stage='all';state.browse='folders'}
    const context=state.view==='library'?visible():state.photos.filter(p=>p.activity_id===state.activity);
    const valid=new Set(context.map(p=>p.id));for(const id of state.selected.library)if(!valid.has(id))state.selected.library.delete(id);
  }else{state.activities=[];state.people=[];state.photos=[]}
  render();
}
function sideButton(label,active,fn,count){const b=button('',safe(fn),'side-item'+(active?' active':''));b.append(el('span','',label));if(count!==undefined)b.append(el('span','count',String(count)));return b}
async function openActivity(id){if(state.activity!==id||state.view!=='library'||state.person!=='all'||state.stage!=='all'||state.browse!=='folders')remember();resetLibrarySelection();state.activity=id;state.person='all';state.stage='all';state.browse='folders';state.view='library';await refresh()}
function openPerson(id){const layout=id==='all'?'folders':'photos';if(state.person!==id||state.view!=='library'||state.browse!==layout||state.stage!=='all')remember();resetLibrarySelection();state.person=id;state.stage='all';state.browse=layout;state.date='all';state.view='library';render()}
function openLibraryFolder(folder){if(folder.kind==='person')openPerson(folder.person)}
function createActivity(){if(!state.settings.library_available){toast('请先创建或打开照片库');return}newActivityDialog(async activity=>openActivity(activity.id))}
function render(){
  const isSD=state.view==='sd';
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===state.view));
  $('#title').textContent=isSD?'SD 卡选片':state.activities.find(a=>a.id===state.activity)?.name||'照片库';
  $('#subtitle').textContent=isSD?(state.source?.path||'选择SD卡或照片文件夹，在这里查看和选片'):'原片与成片关联管理 · 人物和修图阶段分别整理';
  $('#context').textContent=isSD?'浏览来源 · 选择后导入':'照片库 · '+(state.people.find(p=>p.id===state.person)?.name||'全部人物');
  $('#choose-source').hidden=!isSD;$('#classify').hidden=isSD;$('#classify').disabled=!state.activity||state.busy;
  $('#source-read-label').hidden=!isSD;$('#toggle-browse').hidden=isSD||state.person!=='all';$('#toggle-browse').textContent=state.browse==='folders'?'平铺照片':'人物文件夹';
  $('#stage-tabs').hidden=isSD;$('#people-section').hidden=isSD;$('#import').hidden=!isSD;$('#library-actions').hidden=isSD;
  $('#library-path').textContent=state.settings.library||'尚未选择照片库';$('#choose-library').textContent='管理照片库';$('#format-filter').value=state.format;
  $('#activities').replaceChildren(...state.activities.map(a=>{const b=sideButton(a.name,a.id===state.activity,()=>openActivity(a.id));b.dataset.activity=a.id;return b}));
  $('#people-all').classList.toggle('active',state.person==='all');$('#people-body').hidden=state.peopleCollapsed;$('#people-collapse').textContent=(state.peopleCollapsed?'▸':'▾')+' 人物';$('#people-collapse').setAttribute('aria-expanded',String(!state.peopleCollapsed));
  $('#people').replaceChildren(...state.people.map(p=>{const b=sideButton(p.name,state.person===p.id,()=>openPerson(p.id),state.photos.filter(row=>row.activity_id===state.activity&&row.person_id===p.id).length);b.dataset.person=p.id;return b}));
  const crumbs=$('#library-breadcrumbs');crumbs.hidden=isSD;crumbs.replaceChildren(button('全部人物',()=>openPerson('all')));if(state.person!=='all'){crumbs.append(el('span','muted','/'),button(state.people.find(p=>p.id===state.person)?.name||'人物',()=>openPerson(state.person)));if(state.stage!=='all')crumbs.append(el('span','muted','/'),el('span','',({pending:'选出原片',edited:'已修原片',exports:'成片'})[state.stage]))}else if(state.browse==='photos')crumbs.append(el('span','small muted','/ 平铺照片'));
  renderFolders();
  document.querySelectorAll('[data-stage]').forEach(b=>b.classList.toggle('active',b.dataset.stage===state.stage));
  const dates=[...new Set(basePhotos().map(p=>p.captured_at?.slice(0,10)||'unknown'))].sort();
  const date=$('#date-filter');date.replaceChildren();for(const value of ['all',...dates]){const o=el('option','',value==='all'?'所有日期':value==='unknown'?'拍摄日期未知':value);o.value=value;date.append(o)}if(!dates.includes(state.date))state.date='all';date.value=state.date;
  $('#only-selected').checked=state.onlySelected;
  if(!visible().some(p=>p.id===state.current))state.current=visible().find(p=>selected().has(p.id))?.id||null;
  renderGallery();renderInspector();
}
function chooseFolder(path){if(state.sourceFolder!==path)remember();state.sourceFolder=path;state.date='all';state.onlySelected=false;state.current=null;render()}
function renderFolders(){
  const show=state.view==='sd'&&Boolean(state.scanId);$('#source-section').hidden=!show;$('#source-breadcrumbs').hidden=!show;
  if(!show)return;
  const rows=folderPaths(),container=$('#source-folders');container.replaceChildren();
  for(const path of rows){const b=sideButton(path||'来源根目录',state.sourceFolder===path,()=>chooseFolder(path),state.sourcePhotos.filter(p=>sourceDirs(p).includes(path)).length);b.setAttribute('aria-label','文件夹 '+(path||'来源根目录'));b.title=path||state.source?.path||'';container.append(b)}
  if(rows.length>1)container.append(sideButton('全部子文件夹',state.sourceFolder==='*',()=>chooseFolder('*'),state.sourcePhotos.length));
  const crumb=$('#source-breadcrumbs');crumb.replaceChildren(button('来源根目录',()=>chooseFolder('')));
  if(state.sourceFolder==='*')crumb.append(el('span','','/ 全部子文件夹'));
  else{let path='';for(const part of state.sourceFolder.split('/').filter(Boolean)){path=path?path+'/'+part:part;const target=path;crumb.append(el('span','muted','/'),button(part,()=>chooseFolder(target)))}}
}
async function renderInspector(){
  const box=$('#inspector'),p=current(),rev=++inspectorRevision;
  box.replaceChildren();
  if(!p){const empty=el('div','empty');empty.append(el('span','','选择一张照片'),el('small','','单击选择 · 双击查看大图\n拖动可批量选择'));box.append(empty);return}
  const thumb=el('div','large-thumb');thumb.append(el('span','muted small','正在读取…'));thumb.onclick=()=>openViewer(p.id);box.append(thumb,el('div','file-title',p.stem));
  const dl=el('dl');const add=(k,v)=>dl.append(el('dt','',k),el('dd','',v));
  add('拍摄日期',p.captured_at?.replace('T',' ')||'未知');add('文件格式',[...new Set(assets(p).filter(a=>a.kind!=='xmp').map(a=>({jpeg:'JPEG',raw:'RAW',export:'成片'}[a.kind])))].join(' / '));
  if(state.view==='library'){add('人物',state.people.find(person=>person.id===p.person_id)?.name||'待分类');add('修图阶段',p.edited?'已修原片':'选出原片');if(p.opened_at)add('PS请求',p.opened_at.slice(0,16).replace('T',' '));}
  box.append(dl);
  if(p.error||p.missing)box.append(el('p','warning small',p.missing?'部分文件缺失，请定位原文件后恢复。':p.error));
  if(state.view==='library'){
    if(state.stage!=='exports'){
    box.append(el('h3','','Photoshop'));
    const options=el('div','format-options');const available=new Set(assets(p).map(a=>a.kind));
    if(!available.has(state.psFormat))state.psFormat=available.has('raw')?'raw':'jpeg';
    for(const format of ['jpeg','raw']){const b=button(format==='jpeg'?'JPEG':'RAW',()=>{state.psFormat=format;renderInspector()},state.psFormat===format?'active':'');b.disabled=!available.has(format);options.append(b)}box.append(options);
    const ps=button('用 Photoshop 打开',safe(async()=>{await api('open_photoshop',p.id,state.psFormat);invalidateLibraryPreviews();toast('已请求Photoshop打开；修完后请手动标记');await refresh()}),'primary wide');ps.disabled=state.busy;box.append(ps,el('p','small muted','打开不会自动标记已修。'));
    }
    box.append(el('div','divider'),el('h3','','关联成片'));
    box.append(button('选择导出图片并关联',safe(()=>start('choose_and_link_export',p.id)),'outline wide'));
    const exports=assets(p).filter(a=>a.kind==='export');
    if(exports.length){
      box.append(button('打开成片文件夹',safe(()=>api('open_export_folder',p.id)),'wide'));
      for(const a of exports){const row=el('div','export-version');row.append(el('div','',a.path.split(/[\\/]/).pop()),el('div','small muted',a.id===p.primary_export_id?'当前封面':'导出版本'));if(a.id!==p.primary_export_id)row.append(button('设为封面',safe(async()=>{await api('set_export_cover',p.id,a.id);invalidateLibraryPreviews();await refresh()})));row.append(button('解除此版本关联',()=>confirmAction('解除成片关联','此版本不再显示为成片，复制文件移入照片库内的“取消关联保留”目录；原片和修图阶段保留。',()=>start('unlink_export',p.id,a.id))));box.append(row)}
    }else box.append(el('p','small muted','选一张修好后导出的图片，保留原片关联。'));
    if(p.missing)box.append(button('定位缺失文件',safe(()=>start('relink_missing',p.id)),'outline wide'));
    if(state.lastOperation?.photoId===p.id)box.append(button('撤销最近一次归档',safe(()=>start('undo_operation',state.lastOperation.id)),'wide'));
    box.querySelectorAll('button').forEach(b=>{b.dataset.mutation='true';if(state.busy)b.disabled=true});
  }
  const details=el('details');details.append(el('summary','muted small','文件位置'));for(const a of assets(p))details.append(el('p','path',a.path));box.append(el('div','divider'),details);
  try{const result=await preview(p,state.view==='library'&&state.stage==='exports'?'export-thumb':'thumb',state.view==='sd'?state.scanId:null);if(rev!==inspectorRevision)return;thumb.replaceChildren();if(result.url){const im=el('img');im.src=result.url;im.alt=p.stem;thumb.append(im);updatePhotoThumbnail(p.id,result.url)}else thumb.append(el('span','muted small','无法预览'))}catch{if(rev===inspectorRevision)thumb.textContent='无法预览'}
}
async function start(name,...args){
  if(state.busy)throw new Error('请等待当前任务完成');
  state.busy=true;syncSelection();$('#inspector').querySelectorAll('[data-mutation]').forEach(b=>b.disabled=true);
  try{
    const result=await api(name,...args);if(!result)return;
    if(!result.task_id)return result;
    if($('#modal').open)$('#modal').close();
    taskId=result.task_id;$('#taskbar').hidden=false;$('#cancel-task').disabled=false;$('#classify').disabled=true;
    while(taskId){
      const snap=await api('get_task',taskId);$('#task-message').textContent=snap.message||'处理中';$('#task-progress').textContent=snap.total?`${snap.done} / ${snap.total}`:'请稍候';
      const meter=$('#task-meter');if(snap.total){meter.max=snap.total;meter.value=snap.done}else meter.removeAttribute('value');
      if(['succeeded','partial','failed','cancelled'].includes(snap.status)){
        if(name==='scan'&&['succeeded','partial'].includes(snap.status)&&snap.result?.scan_id){clearHistory();state.source=proposedSource;state.sourceFolder='';state.format='all';state.scanId=snap.result.scan_id;state.sourcePhotos=snap.result.photos;state.selected.sd.clear();state.current=null;clearChoices()}
        if(name==='import_selected'&&snap.result?.activity_id){remember();state.activity=snap.result.activity_id;state.view='library';state.person='all';state.stage='all';state.selected.sd.clear()}
        if(['set_person','set_edited'].includes(name)&&snap.result?.operations?.length)state.lastOperation={id:snap.result.operations.at(-1),photoId:snap.result.photo_ids?.at(-1)};
        else if(name!=='scan')state.lastOperation=null;
        if(name!=='scan')invalidateLibraryPreviews();
        taskId=null;await refresh();
        if(snap.status!=='succeeded')resultDialog(snap,name);
        else toast(name==='scan'?`已读取 ${snap.result.photos.length} 张照片`:name==='import_selected'?`导入 ${snap.result.imported.length} 张，补充 ${snap.result.updated?.length||0} 张，跳过 ${snap.result.skipped} 张`:'操作已完成');
        return snap;
      }
      await new Promise(resolve=>setTimeout(resolve,250));
    }
  }finally{taskId=null;state.busy=false;$('#taskbar').hidden=true;syncSelection();renderInspector();$('#classify').disabled=!state.activity}
}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{if(state.view!==b.dataset.view)remember();state.view=b.dataset.view;state.current=null;state.date='all';state.onlySelected=false;render()});
document.querySelectorAll('[data-stage]').forEach(b=>b.onclick=()=>{if(state.stage!==b.dataset.stage||state.browse!=='photos')remember();resetLibrarySelection();state.stage=b.dataset.stage;state.browse='photos';state.date='all';state.onlySelected=false;render()});
$('#choose-source').onclick=safe(async()=>{if(state.busy)return;const result=await api('choose_source');if(!result)return;proposedSource=result;await start('scan',result.token,$('#source-read-format').value)});
$('#choose-library').onclick=safe(()=>libraryDialog(refresh));
$('#trash').onclick=safe(()=>trashDialog(start));
$('#settings').onclick=safe(()=>settingsDialog(start));$('#import').onclick=safe(()=>importDialog(start,refresh));
$('#new-activity').onclick=safe(createActivity);
$('#people-all').onclick=()=>openPerson('all');$('#people-collapse').onclick=()=>{state.peopleCollapsed=!state.peopleCollapsed;render()};
$('#toggle-browse').onclick=()=>{remember();resetLibrarySelection();state.browse=state.browse==='folders'?'photos':'folders';render()};
$('#back').onclick=safe(()=>goBack(refresh));
document.addEventListener('keydown',e=>{if(e.altKey&&e.key==='ArrowLeft'&&!e.target.closest('input,select,textarea')&&!$('#modal').open&&!$('#viewer').open){e.preventDefault();safe(()=>goBack(refresh))()}});
$('#classify').onclick=safe(()=>confirmAction('识别人脸','在本机按当前活动分人物。多人照片进入合照，不确定的保留待分类；手动确认过的照片将跳过。',()=>start('classify_activity',state.activity)));
const actionIds=()=>libraryFolderMode()?[]:visible().filter(p=>selected().has(p.id)).map(p=>p.id);
$('#assign').onclick=()=>assignDialog(actionIds(),start,refresh);
$('#new-person').onclick=()=>newPersonDialog(async()=>{await refresh();toast('人物已创建')});$('#manage-people').onclick=()=>managePeopleDialog(start);
$('#mark-edited').onclick=safe(()=>start('set_edited',actionIds(),true));
$('#mark-pending').onclick=safe(()=>{const ids=actionIds();if(state.photos.some(p=>ids.includes(p.id)&&p.primary_export_id))confirmAction('恢复待修','这些照片已有成片，恢复待修会移动原片并保留全部成片关联。',()=>start('set_edited',ids,false));else return start('set_edited',ids,false)});
$('#mark-finished').onclick=safe(()=>start('set_finished',actionIds(),true));
$('#unmark-finished').onclick=()=>{const ids=actionIds();confirmAction('取消成片','取消所选照片的全部成片关联，复制文件移入库内“取消关联保留”目录；原片与修图阶段保留。',()=>start('set_finished',ids,false))};
$('#date-filter').onchange=e=>{if(state.view==='library')resetLibrarySelection();state.date=e.target.value;renderGallery();renderInspector()};$('#only-selected').onchange=e=>{state.onlySelected=e.target.checked;renderGallery()};
$('#format-filter').onchange=e=>{if(state.view==='library')resetLibrarySelection();state.format=e.target.value;renderGallery();renderInspector()};
$('#select-all').onclick=()=>{const folders=selectableFolderKeys(),rows=libraryFolderMode()?[]:visible(),set=choices(folderScope());const all=(folders.length+rows.length)>0&&folders.every(key=>set.has(key))&&rows.every(p=>selected().has(p.id));folders.forEach(key=>all?set.delete(key):set.add(key));rows.forEach(p=>all?selected().delete(p.id):selected().add(p.id));syncChoices(folderScope());if(state.onlySelected)renderGallery();else syncSelection()};
$('#thumb-size').oninput=e=>setThumbnailSize(e.target.value);$('#thumb-smaller').onclick=()=>setThumbnailSize(state.thumbSize-40);$('#thumb-larger').onclick=()=>setThumbnailSize(state.thumbSize+40);
$('#gallery').addEventListener('wheel',e=>{if(e.ctrlKey){e.preventDefault();setThumbnailSize(state.thumbSize+(e.deltaY<0?40:-40))}},{passive:false});
$('#cancel-task').onclick=safe(async()=>{if(taskId){await api('cancel_task',taskId);$('#cancel-task').disabled=true;$('#task-message').textContent='正在等待当前照片安全结束…'}});
setupSelection(renderInspector);setupViewer();onInspector(renderInspector);onFolder(folder=>folder.kind==='source'?chooseFolder(folder.path):openLibraryFolder(folder));
setupContextMenu({trash:()=>deleteDialog(actionIds(),start)},renderInspector);
function sidebarMenu(e){
  const node=e.target.closest('[data-person],[data-activity]'),personArea=e.target.closest('#people-section');
  if(!node&&!personArea&&!e.target.closest('#activities-section'))return;
  e.preventDefault();const scope=node?.dataset.selectScope,key=node?.dataset.selectKey;
  if(scope&&!choices(scope).has(key)){choices(scope).clear();choices(scope).add(key);syncChoices(scope)}
  if(node?.dataset.person||personArea){
    const ids=scope?[...choices(scope)].filter(id=>state.people.some(p=>p.id===id)):node?.dataset.person?[node.dataset.person]:[],people=state.people.filter(p=>ids.includes(p.id));
    commandMenu(e.clientX,e.clientY,'人物分类',[
      {name:'添加人物',fn:()=>$('#new-person').click(),disabled:state.busy||!state.activity},
      {name:'查看人物照片',fn:()=>openPerson(ids[0]),disabled:ids.length!==1},
      {name:'重命名人物',fn:()=>managePeopleDialog(start,ids[0]),disabled:state.busy||people.length!==1||Boolean(people[0]?.role)},
      {name:'删除人物分类…',fn:()=>deletePeopleDialog(ids,start),disabled:state.busy||!people.length||people.some(p=>p.role),danger:true}]);
  }else commandMenu(e.clientX,e.clientY,'活动',[
    {name:'新建活动',fn:createActivity,disabled:state.busy||!state.settings.library_available},
    {name:'打开活动',fn:()=>openActivity(node.dataset.activity),disabled:!node}]);
}
document.addEventListener('contextmenu',sidebarMenu);
document.addEventListener('keydown',e=>{if((e.key==='ContextMenu'||e.shiftKey&&e.key==='F10')&&e.target.closest('#people-section,#activities-section')){const r=e.target.getBoundingClientRect();sidebarMenu({target:e.target,clientX:r.left,clientY:r.bottom,preventDefault:()=>e.preventDefault()})}});
ready().then(async()=>{state.settings=await api('get_settings');state.thumbSize=state.settings.thumbnail_size||240;$('#thumb-size').value=state.thumbSize;await refresh()}).catch(error);
