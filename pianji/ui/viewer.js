import {state,$,selected,visible} from './store.js';
import {preview} from './previews.js';
import {spring,reducedMotion} from './motion.js';
import {spatialMotion} from './chrome-motion.js';

let sequence=[],index=0,token=0,ready=false,pan=null,returnFocus=null,selectionChanged=false;
let hooks={selection:()=>{},closed:()=>{}},motion;
let entryRect=null,entryFromInspector=false;
const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));
const active=()=>sequence[index];
function sourceRect(id,origin=null){
  const source=origin||[...$('#gallery').querySelectorAll('.photo')].find(card=>card.dataset.id===id)?.querySelector('.picture');
  if(!source?.isConnected)return null;
  const rect=source.getBoundingClientRect(),clip=origin?{top:0,left:0,right:innerWidth,bottom:innerHeight}:$('#gallery').getBoundingClientRect();
  if(rect.bottom<=clip.top||rect.top>=clip.bottom||rect.right<=clip.left||rect.left>=clip.right)return null;
  return {x:rect.x,y:rect.y,width:rect.width,height:rect.height};
}
function transformAt(rect){
  const image=$('#viewer-image'),canvas=$('#viewer-canvas').getBoundingClientRect();
  return {scale:Math.min(rect.width/image.naturalWidth,rect.height/image.naturalHeight),x:rect.x+rect.width/2-canvas.x-canvas.width/2,y:rect.y+rect.height/2-canvas.y-canvas.height/2};
}
function bounds(scale){
  const image=$('#viewer-image'),canvas=$('#viewer-canvas');
  return {x:Math.max(0,(image.naturalWidth*scale-canvas.clientWidth)/2),y:Math.max(0,(image.naturalHeight*scale-canvas.clientHeight)/2)};
}
function constrain(value){const b=bounds(value.scale);return {...value,x:clamp(value.x,-b.x,b.x),y:clamp(value.y,-b.y,b.y)}}
function rubber(value,bound,dimension){
  const edge=clamp(value,-bound,bound),over=value-edge;
  return edge+over*dimension*.35/(dimension+.35*Math.abs(over));
}
function unRubber(value,bound,dimension){
  const edge=clamp(value,-bound,bound),over=value-edge;
  return edge+over*dimension/(.35*Math.max(1,dimension-Math.abs(over)));
}
function syncControls(){
  const photo=active(),picked=Boolean(photo&&selected().has(photo.id));
  $('#viewer-prev').disabled=index<=0;$('#viewer-next').disabled=index>=sequence.length-1;
  $('#viewer-position').textContent=sequence.length?`${index+1} / ${sequence.length}`:'';
  const select=$('#viewer-select');select.disabled=!photo;select.textContent=picked?'已选中':'选中照片';select.setAttribute('aria-pressed',String(picked));select.title=picked?'取消选择（空格）':'选中照片（空格）';
  for(const id of ['viewer-in','viewer-out','viewer-fit','viewer-actual'])$('#'+id).disabled=!ready;
}
function setLoading(loading,message=''){
  $('#viewer-canvas').setAttribute('aria-busy',String(loading));$('#viewer-error').textContent=message;
  $('#viewer-retry').hidden=loading||!message;$('#viewer-status').hidden=!loading&&!message;
}
function stopPan(){
  if(!pan)return;const id=pan.id;pan=null;$('#viewer-canvas').classList.remove('panning');
  if($('#viewer-canvas').hasPointerCapture(id))$('#viewer-canvas').releasePointerCapture(id);
}
export function fitViewer(){
  if(!ready)return;
  stopPan();const image=$('#viewer-image'),canvas=$('#viewer-canvas');
  motion.jump({scale:Math.min(canvas.clientWidth/image.naturalWidth,canvas.clientHeight/image.naturalHeight,1),x:0,y:0});
}
async function loadPhoto(){
  const photo=active();if(!photo)return;
  stopPan();motion.stop();$('#viewer-image').getAnimations().forEach(animation=>animation.cancel());ready=false;const request=++token;
  state.current=photo.id;hooks.selection();
  $('#viewer-name').textContent=photo.stem;$('#viewer-image').hidden=true;$('#viewer-zoom').textContent='—';
  setLoading(true,'正在读取大图…');syncControls();
  const valid=()=>request===token&&$('#viewer').open;
  try{
    const result=await preview(photo,state.stage==='exports'&&state.view==='library'?'export':'preview',state.view==='sd'?state.scanId:null);
    if(!valid())return;
    if(!result.url)throw new Error(result.error||'无法预览这张照片');
    // Decode offscreen so an older image's load/error cannot mutate the new one.
    const decoded=new Image();decoded.src=result.url;await decoded.decode();if(!valid())return;
    const image=$('#viewer-image');image.src=result.url;image.alt=photo.stem;image.hidden=false;ready=true;
    fitViewer();
    if(entryRect&&spatialMotion()){
      const target=motion.value;motion.jump(transformAt(entryRect));motion.to(target);
    }
    entryRect=null;setLoading(false);syncControls();
  }catch(error){if(valid()){ready=false;setLoading(false,error.message||'无法预览这张照片');syncControls()}}
}
export function openViewer(id,origin=null){
  if(!$('#viewer').open){
    // Native close dispatches an event later. Flush a previous filtered session
    // before replacing its state if the user reopens within that same task.
    if(selectionChanged){hooks.closed(true);selectionChanged=false}
    sequence=[...visible()];index=sequence.findIndex(p=>p.id===id);if(index<0)return;
    selectionChanged=false;returnFocus=document.activeElement;entryFromInspector=Boolean(origin?.closest('.inspector'));entryRect=spatialMotion()?sourceRect(id,origin):null;
    $('#viewer').showModal();$('#viewer-canvas').focus({preventScroll:true});
  }else{const next=sequence.findIndex(p=>p.id===id);if(next<0)return;index=next;entryRect=null}
  return loadPhoto();
}
export function setupViewer(callbacks){
  hooks=callbacks;const canvas=$('#viewer-canvas'),dialog=$('#viewer');
  motion=spring({scale:1,x:0,y:0},value=>{
    $('#viewer-image').style.transform=`translate(${value.x}px,${value.y}px) scale(${value.scale})`;
    const label=Math.round(value.scale*100)+'%';if($('#viewer-zoom').textContent!==label)$('#viewer-zoom').textContent=label;
  });
  function zoom(factor,clientX,clientY){
    if(!ready)return;stopPan();const r=canvas.getBoundingClientRect(),value=motion.value;
    const targetScale=clamp(motion.target.scale*factor,.02,16),ratio=targetScale/value.scale;
    const px=(clientX??r.left+r.width/2)-r.left-r.width/2,py=(clientY??r.top+r.height/2)-r.top-r.height/2;
    const image=$('#viewer-image');
    const anchorX=clamp(px,value.x-image.naturalWidth*value.scale/2,value.x+image.naturalWidth*value.scale/2);
    const anchorY=clamp(py,value.y-image.naturalHeight*value.scale/2,value.y+image.naturalHeight*value.scale/2);
    // Both translation and scale use the same spring, keeping this image pixel anchored.
    const next={scale:targetScale,x:anchorX-(anchorX-value.x)*ratio,y:anchorY-(anchorY-value.y)*ratio};
    // Preserve the pointed pixel even when a zoom interrupts the entry flight.
    // Keep at least a small photo edge visible without forcing it back to center.
    const width=image.naturalWidth*targetScale,height=image.naturalHeight*targetScale;
    const limitX=(width+r.width)/2-Math.min(48,width/2,r.width/2),limitY=(height+r.height)/2-Math.min(48,height/2,r.height/2);
    next.x=clamp(next.x,-limitX,limitX);next.y=clamp(next.y,-limitY,limitY);
    motion.to(next);
  }
  function step(delta){if(sequence[index+delta]){entryRect=null;index+=delta;loadPhoto()}}
  function toggle(){const photo=active();if(!photo)return;const set=selected();set.has(photo.id)?set.delete(photo.id):set.add(photo.id);state.anchor[state.view]=photo.id;selectionChanged=true;hooks.selection();syncControls()}
  $('#viewer-select').onclick=toggle;$('#viewer-retry').onclick=()=>loadPhoto();
  $('#viewer-in').onclick=()=>zoom(1.25);$('#viewer-out').onclick=()=>zoom(.8);$('#viewer-fit').onclick=fitViewer;
  $('#viewer-actual').onclick=()=>{stopPan();motion.to({scale:1,x:0,y:0})};
  $('#viewer-prev').onclick=()=>step(-1);$('#viewer-next').onclick=()=>step(1);
  $('#viewer-close').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{
    if(dialog.open)return; // A queued close event may arrive after an immediate reopen.
    const destination=ready&&spatialMotion()?(entryFromInspector?sourceRect(active()?.id,$('.inspector .large-thumb')):sourceRect(active()?.id)):null;
    if(destination){
      const value=motion.value,target=transformAt(destination),image=$('#viewer-image');
      image.animate([{transform:`translate(${value.x}px,${value.y}px) scale(${value.scale})`,opacity:1},{transform:`translate(${target.x}px,${target.y}px) scale(${target.scale})`,opacity:.1}],{duration:180,easing:'cubic-bezier(.23,1,.32,1)',fill:'forwards'});
    }
    entryRect=null;
    token++;stopPan();motion.stop();ready=false;setLoading(false);hooks.closed(selectionChanged);selectionChanged=false;
    const card=[...$('#gallery').querySelectorAll('.photo')].find(node=>node.dataset.id===state.current);
    const target=card||(returnFocus?.isConnected&&returnFocus!==document.body?returnFocus:$('#gallery'));
    if(card)card.tabIndex=-1;target.focus({preventScroll:true});
  });
  canvas.addEventListener('wheel',e=>{
    e.preventDefault();const pixels=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?canvas.clientHeight:1);
    zoom(Math.exp(clamp(-pixels*.0018,-.4,.4)),e.clientX,e.clientY);
  },{passive:false});
  canvas.addEventListener('pointerdown',e=>{
    if(e.button!==0||!ready||pan||e.target.closest('button'))return;
    motion.stop();canvas.focus({preventScroll:true});const value=motion.value;
    const b=bounds(value.scale);
    pan={id:e.pointerId,x:e.clientX,y:e.clientY,origin:value,rawX:unRubber(value.x,b.x,canvas.clientWidth),rawY:unRubber(value.y,b.y,canvas.clientHeight),time:e.timeStamp,vx:0,vy:0};
    canvas.setPointerCapture(e.pointerId);canvas.classList.add('panning');
  });
  canvas.addEventListener('pointermove',e=>{
    if(!pan||pan.id!==e.pointerId)return;e.preventDefault();const dt=e.timeStamp-pan.time,b=bounds(pan.origin.scale);
    const next={...pan.origin,x:rubber(pan.rawX+e.clientX-pan.x,b.x,canvas.clientWidth),y:rubber(pan.rawY+e.clientY-pan.y,b.y,canvas.clientHeight)};
    const previous=motion.value;if(dt>0){pan.vx=(next.x-previous.x)/dt*1000;pan.vy=(next.y-previous.y)/dt*1000}pan.time=e.timeStamp;motion.jump(next);
  });
  function release(e,cancel=false){
    if(!pan||pan.id!==e.pointerId)return;
    const value=motion.value,age=e.timeStamp-pan.time;
    const velocity=cancel||age>90?{x:0,y:0}:{x:clamp(pan.vx,-1800,1800),y:clamp(pan.vy,-1800,1800)};
    const next=constrain({...value,x:value.x+velocity.x*.1,y:value.y+velocity.y*.1});
    stopPan();motion.to(next,velocity);
  }
  canvas.addEventListener('pointerup',e=>release(e));canvas.addEventListener('pointercancel',e=>release(e,true));
  canvas.addEventListener('lostpointercapture',e=>release(e,true));
  document.addEventListener('keydown',e=>{
    if(!dialog.open||e.altKey||e.ctrlKey||e.metaKey||e.target.closest('input,select,textarea,[contenteditable=true]'))return;
    if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();step(e.key==='ArrowLeft'?-1:1)}
    if(e.code==='Space'&&(!e.target.closest('button')||e.target.id==='viewer-select')){e.preventDefault();if(!e.repeat)toggle()}
  });
  window.addEventListener('resize',()=>{if(dialog.open)fitViewer()});
  matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',()=>{if(reducedMotion())motion.jump(constrain(motion.target))});
}
