import {state,$,selected,visible,current,assets,el,button,error,childFolders} from './store.js';
import {api} from './api.js';
import {preview} from './previews.js';
let inspectorHook=()=>{},folderHook=()=>{},observer,queue=[],active=0,revision=0,cards=new Map(),drawn=new Set(),beforeClick=null,filterTimer;
export function onInspector(fn){inspectorHook=fn}
export function onFolder(fn){folderHook=fn}
export function syncSelection(){
  const set=selected();
  for(const id of new Set([...drawn,...set])){if(drawn.has(id)===set.has(id))continue;const card=cards.get(id);if(!card)continue;const checked=set.has(id);card.classList.toggle('checked',checked);card.setAttribute('aria-selected',String(checked));const pick=card.querySelector('.pick');pick.textContent=checked?'✓':'';pick.setAttribute('aria-pressed',String(checked))}
  drawn=new Set([...set].filter(id=>cards.has(id)));
  const count=`已选 ${set.size} 张`;if($('#selection-count').textContent!==count)$('#selection-count').textContent=count;
  $('#import').disabled=!set.size||state.busy;
  const rows=visible();$('#select-all').textContent=rows.length&&rows.every(p=>set.has(p.id))?'取消全选':'全选';
  const picked=rows.filter(p=>set.has(p.id)),exportView=state.view==='library'&&state.stage==='exports';
  $('#assign').disabled=!picked.length||state.busy;
  $('#mark-edited').hidden=exportView;$('#mark-pending').hidden=exportView;$('#mark-finished').hidden=exportView;
  $('#mark-edited').disabled=!picked.some(p=>!p.edited)||state.busy;$('#mark-pending').disabled=!picked.some(p=>p.edited)||state.busy;
  $('#mark-finished').disabled=!picked.some(p=>!p.primary_export_id&&assets(p).some(a=>a.kind==='jpeg'))||state.busy;
  $('#unmark-finished').hidden=!exportView&&!picked.some(p=>p.primary_export_id);$('#unmark-finished').disabled=!picked.some(p=>p.primary_export_id)||state.busy;
  for(const id of ['choose-source','choose-library','settings','new-person','manage-people'])$('#'+id).disabled=state.busy||(['new-person','manage-people'].includes(id)&&!state.activity);
}
export function selectPhoto(id,event={}){
  if(event.detail>1)return;
  const set=selected(),rows=visible(),anchor=state.anchor[state.view];
  if(event.detail===1)beforeClick={id,view:state.view,selected:new Set(set)};
  if(event.shiftKey&&anchor&&rows.some(p=>p.id===anchor)){
    const a=rows.findIndex(p=>p.id===anchor),b=rows.findIndex(p=>p.id===id);
    if(!event.ctrlKey&&!event.metaKey)set.clear();rows.slice(Math.min(a,b),Math.max(a,b)+1).forEach(p=>set.add(p.id));
  }else{set.has(id)?set.delete(id):set.add(id);state.anchor[state.view]=id}
  state.current=id;syncSelection();inspectorHook();
  clearTimeout(filterTimer);if(state.onlySelected&&!set.has(id))filterTimer=setTimeout(renderGallery,500);
}
export function doubleClickPhoto(id){clearTimeout(filterTimer);if(beforeClick?.id===id&&beforeClick.view===state.view){selected().clear();beforeClick.selected.forEach(value=>selected().add(value));syncSelection()}beforeClick=null;if(state.onlySelected)renderGallery();openViewer(id)}
export function updatePhotoThumbnail(id,url){const picture=cards.get(id)?.querySelector('.picture');if(!picture||picture.querySelector('img')?.src===url)return;const im=el('img');im.src=url;im.alt=cards.get(id).querySelector('.name').textContent;im.draggable=false;picture.replaceChildren(im)}
async function pump(){
  while(active<2&&queue.length){
    const {node,p,rev,view,scanId,exported}=queue.shift();
    if(!node.isConnected||rev!==revision)continue;
    active++;
    preview(p,exported?'export-thumb':'thumb',view==='sd'?scanId:null).then(result=>{
      if(!node.isConnected||rev!==revision)return;
      node.replaceChildren();
      if(result.url){const im=el('img');im.src=result.url;im.alt=p.stem;im.draggable=false;node.append(im)}
      else node.append(el('span','placeholder','无法预览'));
    }).catch(()=>{if(node.isConnected)node.replaceChildren(el('span','placeholder','无法预览'))}).finally(()=>{active--;pump()});
  }
}
export function renderGallery(){
  clearTimeout(filterTimer);beforeClick=null;revision++;queue=[];observer?.disconnect();cards=new Map();drawn=new Set();
  const grid=$('#gallery'),rows=visible(),rev=revision;grid.replaceChildren();
  if(!rows.some(p=>p.id===state.current)){const next=rows.find(p=>selected().has(p.id))?.id||null;if(next!==state.current){state.current=next;queueMicrotask(inspectorHook)}}
  grid.style.setProperty('--thumb-size',state.thumbSize+'px');
  $('#photo-count').textContent=`${rows.length} 张照片`;
  const folders=childFolders();
  for(const path of folders){const b=button('',()=>folderHook(path),'folder-card');b.append(el('strong','',path.split('/').pop()),el('span','small muted','打开文件夹'));b.setAttribute('aria-label',path.split('/').pop());grid.append(b)}
  if(!rows.length&&!folders.length){
    const empty=el('div','empty');empty.append(el('div','empty-icon','▧'),el('span','',state.view==='sd'?(state.source?'没有符合条件的照片':'从SD卡开始选片'):(state.settings.library_available?'当前筛选下没有照片':'先选择照片库')),
      el('small','',state.view==='sd'?'选择来源后，单击选中、双击查看，拖动可批量选择':'导入的照片将在这里按活动、人物与修图阶段整理'));grid.append(empty);
  }
  const targets=new Map();
  for(const p of rows){
    const card=el('article','photo');card.dataset.id=p.id;card.setAttribute('role','option');
    const picture=el('div','picture');picture.append(el('span','placeholder','正在读取…'));targets.set(picture,p);
    const pick=button('',e=>{e.stopPropagation();selectPhoto(p.id,{ctrlKey:true})},'pick');pick.setAttribute('aria-label','选择 '+p.stem);
    const kinds=new Set(assets(p).map(a=>a.kind));const badge=el('span','badge',kinds.has('raw')?(kinds.has('jpeg')?'JPEG + RAW':'RAW'):'JPEG');
    const meta=el('div','meta');meta.append(el('span','',p.captured_at?.slice(0,10)||'日期未知'),el('span',p.missing?'warning':p.edited?'success':'',p.missing?'文件缺失':state.view==='sd'?'':p.primary_export_id?'有成片':p.edited?'已修':'待修'));
    card.append(picture,badge,pick,el('div','name',p.stem),meta);grid.append(card);
    card.setAttribute('aria-selected','false');cards.set(p.id,card);
  }
  observer=new IntersectionObserver(entries=>{
    for(const entry of entries)if(entry.isIntersecting){observer.unobserve(entry.target);queue.push({node:entry.target,p:targets.get(entry.target),rev,view:state.view,scanId:state.scanId,exported:state.view==='library'&&state.stage==='exports'})}
    pump();
  },{root:grid,rootMargin:'200px'});
  for(const target of targets.keys())observer.observe(target);
  syncSelection();
}
export function setThumbnailSize(value){
  $('#gallery').dispatchEvent(new Event('layoutchange'));
  state.thumbSize=Math.max(80,Math.min(720,Number(value)||240));
  $('#thumb-size').value=state.thumbSize;$('#gallery').style.setProperty('--thumb-size',state.thumbSize+'px');
  clearTimeout(setThumbnailSize.timer);setThumbnailSize.timer=setTimeout(()=>api('save_settings',{thumbnail_size:state.thumbSize}).catch(error),500);
}
let viewerScale=1,viewerX=0,viewerY=0,viewerToken=0;
function transform(){const im=$('#viewer-image');im.style.transform=`translate(${viewerX}px,${viewerY}px) scale(${viewerScale})`}
export function fitViewer(){const im=$('#viewer-image'),canvas=$('#viewer-canvas');viewerScale=Math.min(canvas.clientWidth/Math.max(im.naturalWidth,1),canvas.clientHeight/Math.max(im.naturalHeight,1),1);viewerX=0;viewerY=0;transform()}
export async function openViewer(id){
  const p=visible().find(p=>p.id===id);if(!p)return;
  state.current=id;inspectorHook();const token=++viewerToken;
  $('#viewer-name').textContent=p.stem;$('#viewer-image').hidden=true;$('#viewer-error').textContent='正在读取大图…';
  if(!$('#viewer').open)$('#viewer').showModal();
  try{
    const result=await preview(p,state.stage==='exports'&&state.view==='library'?'export':'preview',state.view==='sd'?state.scanId:null);
    if(token!==viewerToken)return;
    if(!result.url){$('#viewer-error').textContent=result.error||'无法预览';return}
    const im=$('#viewer-image');im.onload=()=>{if(token!==viewerToken)return;im.hidden=false;$('#viewer-error').textContent='';fitViewer()};im.src=result.url;
  }catch(e){$('#viewer-error').textContent=e.message}
}
export function setupViewer(){
  const canvas=$('#viewer-canvas');
  $('#viewer-close').onclick=()=>{$('#viewer').close();viewerToken++};
  const zoom=factor=>{viewerScale=Math.max(.02,Math.min(16,viewerScale*factor));transform()};
  $('#viewer-in').onclick=()=>zoom(1.25);$('#viewer-out').onclick=()=>zoom(.8);$('#viewer-fit').onclick=fitViewer;
  $('#viewer-actual').onclick=()=>{viewerScale=1;viewerX=0;viewerY=0;transform()};
  const step=delta=>{const rows=visible(),i=rows.findIndex(p=>p.id===state.current);if(rows[i+delta])openViewer(rows[i+delta].id)};
  $('#viewer-prev').onclick=()=>step(-1);$('#viewer-next').onclick=()=>step(1);
  canvas.addEventListener('wheel',e=>{e.preventDefault();zoom(e.deltaY<0?1.15:1/1.15)},{passive:false});
  let pan=null;canvas.onpointerdown=e=>{if(e.button!==0)return;pan={x:e.clientX,y:e.clientY,ox:viewerX,oy:viewerY};canvas.setPointerCapture(e.pointerId)};
  canvas.onpointermove=e=>{if(!pan)return;viewerX=pan.ox+e.clientX-pan.x;viewerY=pan.oy+e.clientY-pan.y;transform()};
  canvas.onpointerup=()=>pan=null;canvas.onpointercancel=()=>pan=null;
  document.addEventListener('keydown',e=>{if(!$('#viewer').open)return;if(e.key==='ArrowLeft')step(-1);if(e.key==='ArrowRight')step(1)});
  window.addEventListener('resize',()=>{if($('#viewer').open)fitViewer()});
}
