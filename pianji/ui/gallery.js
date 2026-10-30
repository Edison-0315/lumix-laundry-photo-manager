import {state,$,selected,visible,current,assets,el,button,error} from './store.js';
import {api} from './api.js';
let inspectorHook=()=>{},observer,queue=[],active=0,revision=0;
export function onInspector(fn){inspectorHook=fn}
export function syncSelection(){
  const set=selected();
  document.querySelectorAll('.photo').forEach(card=>{card.classList.toggle('checked',set.has(card.dataset.id));card.setAttribute('aria-selected',String(set.has(card.dataset.id)));const pick=card.querySelector('.pick');pick.textContent=set.has(card.dataset.id)?'✓':'';pick.setAttribute('aria-pressed',String(set.has(card.dataset.id)))});
  $('#selection-count').textContent=`已选 ${set.size} 张`;
  $('#import').disabled=!set.size||state.busy;
  ['assign','mark-edited','mark-pending'].forEach(id=>$('#'+id).disabled=!set.size||state.busy);
  const rows=visible();$('#select-all').textContent=rows.length&&rows.every(p=>set.has(p.id))?'取消全选':'全选';
}
export function selectPhoto(id,event={}){
  if(event.detail>1)return;
  const set=selected(),rows=visible(),anchor=state.anchor[state.view];
  if(event.shiftKey&&anchor&&rows.some(p=>p.id===anchor)){
    const a=rows.findIndex(p=>p.id===anchor),b=rows.findIndex(p=>p.id===id);
    if(!event.ctrlKey&&!event.metaKey)set.clear();rows.slice(Math.min(a,b),Math.max(a,b)+1).forEach(p=>set.add(p.id));
  }else if(event.ctrlKey||event.metaKey){set.has(id)?set.delete(id):set.add(id);state.anchor[state.view]=id}
  else{set.clear();set.add(id);state.anchor[state.view]=id}
  state.current=id;syncSelection();inspectorHook();
  if(state.onlySelected&&!set.has(id))renderGallery();
}
async function pump(){
  while(active<2&&queue.length){
    const {node,p,rev,view,scanId,exported}=queue.shift();
    if(!node.isConnected||rev!==revision)continue;
    active++;
    api('get_preview',p.id,exported?'export-thumb':'thumb',view==='sd'?scanId:null).then(result=>{
      if(!node.isConnected||rev!==revision)return;
      node.replaceChildren();
      if(result.url){const im=el('img');im.src=result.url;im.alt=p.stem;im.draggable=false;node.append(im)}
      else node.append(el('span','placeholder','无法预览'));
    }).catch(()=>{if(node.isConnected)node.replaceChildren(el('span','placeholder','无法预览'))}).finally(()=>{active--;pump()});
  }
}
export function renderGallery(){
  revision++;queue=[];observer?.disconnect();
  const grid=$('#gallery'),rows=visible(),rev=revision;grid.replaceChildren();
  grid.style.setProperty('--thumb-size',state.thumbSize+'px');
  $('#photo-count').textContent=`${rows.length} 张照片`;
  if(!rows.length){
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
  }
  observer=new IntersectionObserver(entries=>{
    for(const entry of entries)if(entry.isIntersecting){observer.unobserve(entry.target);queue.push({node:entry.target,p:targets.get(entry.target),rev,view:state.view,scanId:state.scanId,exported:state.view==='library'&&state.stage==='exports'})}
    pump();
  },{root:grid,rootMargin:'200px'});
  for(const target of targets.keys())observer.observe(target);
  syncSelection();
}
export function setThumbnailSize(value){
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
    const result=await api('get_preview',id,state.stage==='exports'&&state.view==='library'?'export':'preview',state.view==='sd'?state.scanId:null);
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
