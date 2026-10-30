import {ready,api} from './api.js';
import {state,$,selected,basePhotos,visible,current,assets,el,button,toast,error} from './store.js';
import {renderGallery,syncSelection,setThumbnailSize,onInspector,openViewer,setupViewer} from './gallery.js';
import {setupSelection} from './selection.js';
import {settingsDialog,importDialog,assignDialog,newPersonDialog,managePeopleDialog,confirmAction,resultDialog} from './dialogs.js';

let taskId=null,inspectorRevision=0;
const safe=fn=>(...args)=>Promise.resolve().then(()=>fn(...args)).catch(error);

async function refresh(){
  state.settings=await api('get_settings');
  if(state.settings.library_available){
    state.activities=await api('list_activities');
    if(!state.activities.some(a=>a.id===state.activity))state.activity=state.activities[0]?.id||null;
    state.people=state.activity?await api('list_people',state.activity):[];
    state.photos=await api('list_photos',{});
    if(state.person!=='all'&&!state.people.some(p=>p.id===state.person))state.person='all';
    const valid=new Set(state.photos.map(p=>p.id));for(const id of state.selected.library)if(!valid.has(id))state.selected.library.delete(id);
  }else{state.activities=[];state.people=[];state.photos=[]}
  render();
}
function sideButton(label,active,fn,count){const b=button('',safe(fn),'side-item'+(active?' active':''));b.append(el('span','',label));if(count!==undefined)b.append(el('span','count',String(count)));return b}
function render(){
  const isSD=state.view==='sd';
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===state.view));
  $('#title').textContent=isSD?'SD 卡选片':state.activities.find(a=>a.id===state.activity)?.name||'照片库';
  $('#subtitle').textContent=isSD?(state.source?.path||'选择SD卡或照片文件夹，在这里查看和选片'):'原片与成片关联管理 · 人物和修图阶段分别整理';
  $('#context').textContent=isSD?'浏览来源 · 选择后导入':'照片库 · '+(state.people.find(p=>p.id===state.person)?.name||'全部人物');
  $('#choose-source').hidden=!isSD;$('#classify').hidden=isSD;$('#classify').disabled=!state.activity||state.busy;
  $('#stage-tabs').hidden=isSD;$('#people-section').hidden=isSD;$('#import').hidden=!isSD;$('#library-actions').hidden=isSD;
  $('#library-path').textContent=state.settings.library||'尚未选择照片库';$('#choose-library').textContent=state.settings.library?'更换照片库':'选择照片库';
  $('#activities').replaceChildren(...state.activities.map(a=>sideButton(a.name,a.id===state.activity,async()=>{state.activity=a.id;state.person='all';state.view='library';state.current=null;await refresh()})));
  $('#people').replaceChildren(sideButton('全部人物',state.person==='all',()=>{state.person='all';render()},basePhotos().length),...state.people.map(p=>sideButton(p.name,state.person===p.id,()=>{state.person=p.id;state.current=null;render()},state.photos.filter(row=>row.activity_id===state.activity&&row.person_id===p.id).length)));
  document.querySelectorAll('[data-stage]').forEach(b=>b.classList.toggle('active',b.dataset.stage===state.stage));
  const dates=[...new Set(basePhotos().map(p=>p.captured_at?.slice(0,10)||'unknown'))].sort();
  const date=$('#date-filter');date.replaceChildren();for(const value of ['all',...dates]){const o=el('option','',value==='all'?'所有日期':value==='unknown'?'拍摄日期未知':value);o.value=value;date.append(o)}if(!dates.includes(state.date))state.date='all';date.value=state.date;
  $('#only-selected').checked=state.onlySelected;
  if(!visible().some(p=>p.id===state.current))state.current=visible().find(p=>selected().has(p.id))?.id||null;
  renderGallery();renderInspector();
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
    box.append(el('h3','','Photoshop'));
    const options=el('div','format-options');const available=new Set(assets(p).map(a=>a.kind));
    if(!available.has(state.psFormat))state.psFormat=available.has('raw')?'raw':'jpeg';
    for(const format of ['jpeg','raw']){const b=button(format==='jpeg'?'JPEG':'RAW',()=>{state.psFormat=format;renderInspector()},state.psFormat===format?'active':'');b.disabled=!available.has(format);options.append(b)}box.append(options);
    const ps=button('用 Photoshop 打开',safe(async()=>{await api('open_photoshop',p.id,state.psFormat);toast('已请求Photoshop打开；修完后请手动标记');await refresh()}),'primary wide');ps.disabled=state.busy;box.append(ps,el('p','small muted','打开不会自动标记已修。'));
    box.append(el('div','divider'),el('h3','','关联成片'));
    box.append(button('选择导出图片并关联',safe(()=>start('choose_and_link_export',p.id)),'outline wide'));
    const exports=assets(p).filter(a=>a.kind==='export');
    if(exports.length){
      box.append(button('打开成片文件夹',safe(()=>api('open_export_folder',p.id)),'wide'));
      for(const a of exports){const row=el('div','export-version');row.append(el('div','',a.path.split(/[\\/]/).pop()),el('div','small muted',a.id===p.primary_export_id?'当前封面':'导出版本'));if(a.id!==p.primary_export_id)row.append(button('设为封面',safe(async()=>{await api('set_export_cover',p.id,a.id);await refresh()})));box.append(row)}
    }else box.append(el('p','small muted','选一张修好后导出的图片，保留原片关联。'));
    if(p.missing)box.append(button('定位缺失文件',safe(()=>start('relink_missing',p.id)),'outline wide'));
    if(state.lastOperation)box.append(button('撤销最近一次归档',safe(()=>start('undo_operation',state.lastOperation)),'wide'));
  }
  const details=el('details');details.append(el('summary','muted small','文件位置'));for(const a of assets(p))details.append(el('p','path',a.path));box.append(el('div','divider'),details);
  try{const result=await api('get_preview',p.id,state.view==='library'&&state.stage==='exports'?'export-thumb':'thumb',state.view==='sd'?state.scanId:null);if(rev!==inspectorRevision)return;thumb.replaceChildren();if(result.url){const im=el('img');im.src=result.url;im.alt=p.stem;thumb.append(im)}else thumb.append(el('span','muted small','无法预览'))}catch{if(rev===inspectorRevision)thumb.textContent='无法预览'}
}
async function start(name,...args){
  if(state.busy)throw new Error('请等待当前任务完成');
  const result=await api(name,...args);if(!result)return;
  if(!result.task_id)return result;
  if($('#modal').open)$('#modal').close();
  taskId=result.task_id;state.busy=true;syncSelection();$('#taskbar').hidden=false;$('#cancel-task').disabled=false;$('#classify').disabled=true;
  try{
    while(taskId){
      const snap=await api('get_task',taskId);$('#task-message').textContent=snap.message||'处理中';$('#task-progress').textContent=snap.total?`${snap.done} / ${snap.total}`:'请稍候';
      const meter=$('#task-meter');if(snap.total){meter.max=snap.total;meter.value=snap.done}else meter.removeAttribute('value');
      if(['succeeded','partial','failed','cancelled'].includes(snap.status)){
        if(name==='scan'&&snap.result){state.scanId=snap.result.scan_id;state.sourcePhotos=snap.result.photos;state.selected.sd.clear();state.current=null}
        if(name==='import_selected'&&snap.result?.activity_id){state.activity=snap.result.activity_id;state.view='library';state.person='all';state.stage='all';state.selected.sd.clear()}
        if(snap.result?.operations?.length)state.lastOperation=snap.result.operations.at(-1);
        taskId=null;state.busy=false;await refresh();
        if(snap.status!=='succeeded')resultDialog(snap);
        else toast(name==='scan'?`已读取 ${snap.result.photos.length} 张照片`:name==='import_selected'?`导入 ${snap.result.imported.length} 张，补充 ${snap.result.updated?.length||0} 张，跳过 ${snap.result.skipped} 张`:'操作已完成');
        break;
      }
      await new Promise(resolve=>setTimeout(resolve,250));
    }
  }finally{taskId=null;state.busy=false;$('#taskbar').hidden=true;syncSelection();$('#classify').disabled=!state.activity}
}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{state.view=b.dataset.view;state.current=null;state.date='all';state.onlySelected=false;render()});
document.querySelectorAll('[data-stage]').forEach(b=>b.onclick=()=>{state.stage=b.dataset.stage;state.current=null;render()});
$('#choose-source').onclick=safe(async()=>{if(state.busy)return;const result=await api('choose_source');if(!result)return;state.source=result;await start('scan',result.token)});
$('#choose-library').onclick=safe(async()=>{const result=await api('choose_library');if(result){state.selected.library.clear();state.current=null;await refresh();if(result.recovery?.errors?.length)toast('有文件需要恢复，请关闭占用程序后在设置中重试')}});
$('#settings').onclick=safe(()=>settingsDialog(start));$('#import').onclick=()=>importDialog(start);
$('#classify').onclick=safe(()=>confirmAction('识别人脸','在本机按当前活动分人物。多人照片进入合照，不确定的保留待分类；手动确认过的照片将跳过。',()=>start('classify_activity',state.activity)));
$('#assign').onclick=()=>assignDialog([...selected()],start,refresh);
$('#new-person').onclick=()=>newPersonDialog(async()=>{await refresh();toast('人物已创建')});$('#manage-people').onclick=()=>managePeopleDialog(start);
$('#mark-edited').onclick=safe(()=>start('set_edited',[...selected()],true));
$('#mark-pending').onclick=safe(()=>{const ids=[...selected()];if(state.photos.some(p=>ids.includes(p.id)&&p.primary_export_id))confirmAction('恢复待修','这些照片已有成片，恢复待修会移动原片并保留全部成片关联。',()=>start('set_edited',ids,false));else return start('set_edited',ids,false)});
$('#date-filter').onchange=e=>{state.date=e.target.value;renderGallery()};$('#only-selected').onchange=e=>{state.onlySelected=e.target.checked;renderGallery()};
$('#select-all').onclick=()=>{const rows=visible();if(rows.length&&rows.every(p=>selected().has(p.id)))rows.forEach(p=>selected().delete(p.id));else rows.forEach(p=>selected().add(p.id));if(state.onlySelected)renderGallery();else syncSelection()};
$('#thumb-size').oninput=e=>setThumbnailSize(e.target.value);$('#thumb-smaller').onclick=()=>setThumbnailSize(state.thumbSize-40);$('#thumb-larger').onclick=()=>setThumbnailSize(state.thumbSize+40);
$('#gallery').addEventListener('wheel',e=>{if(e.ctrlKey){e.preventDefault();setThumbnailSize(state.thumbSize+(e.deltaY<0?40:-40))}},{passive:false});
$('#cancel-task').onclick=safe(async()=>{if(taskId){await api('cancel_task',taskId);$('#cancel-task').disabled=true;$('#task-message').textContent='正在等待当前照片安全结束…'}});
setupSelection(renderInspector);setupViewer();onInspector(renderInspector);
ready().then(async()=>{state.settings=await api('get_settings');state.thumbSize=state.settings.thumbnail_size||240;$('#thumb-size').value=state.thumbSize;await refresh()}).catch(error);
