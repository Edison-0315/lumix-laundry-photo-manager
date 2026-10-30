import {state,$,selected,visible} from './store.js';
import {syncSelection,selectPhoto,doubleClickPhoto} from './gallery.js';
export function setupSelection(refreshInspector){
  let drag=null,suppress=false,raf=0;
  function update(){
    if(!drag?.active)return;
    const r=drag.rect,x=drag.x-r.left+drag.grid.scrollLeft,y=drag.y-r.top+drag.grid.scrollTop;
    const left=Math.min(drag.sx,x),right=Math.max(drag.sx,x),top=Math.min(drag.sy,y),bottom=Math.max(drag.sy,y);
    const l=Math.max(r.left,r.left+left-drag.grid.scrollLeft),t=Math.max(r.top,r.top+top-drag.grid.scrollTop);
    Object.assign(drag.box.style,{left:l+'px',top:t+'px',width:Math.max(0,Math.min(r.right,r.left+right-drag.grid.scrollLeft)-l)+'px',height:Math.max(0,Math.min(r.bottom,r.top+bottom-drag.grid.scrollTop)-t)+'px'});
    const chosen=selected();chosen.clear();if(drag.additive)drag.before.forEach(id=>chosen.add(id));
    for(const c of drag.cards)if(c.x<right&&c.x+c.width>left&&c.y<bottom&&c.y+c.height>top)chosen.add(c.id);
    syncSelection();
  }
  function scroll(){
    if(!drag?.active)return;const r=drag.rect,edge=32;
    const delta=drag.y<r.top+edge?-Math.min(20,(r.top+edge-drag.y)/2):drag.y>r.bottom-edge?Math.min(20,(drag.y-r.bottom+edge)/2):0;
    if(delta){const old=drag.grid.scrollTop;drag.grid.scrollTop+=delta;if(old!==drag.grid.scrollTop)drag.dirty=true}
    if(drag.dirty){drag.dirty=false;update()}raf=requestAnimationFrame(scroll);
  }
  function finish(cancel=false){
    if(!drag)return;if(drag.active&&!cancel)update();const d=drag;drag=null;cancelAnimationFrame(raf);d.box?.remove();
    if(d.grid.hasPointerCapture?.(d.id))d.grid.releasePointerCapture(d.id);
    if(!d.active)return;
    if(cancel){selected().clear();d.before.forEach(id=>selected().add(id))}
    else if(!selected().has(state.current))state.current=visible().find(p=>selected().has(p.id))?.id||state.current;
    suppress=true;syncSelection();refreshInspector();
  }
  document.addEventListener('dragstart',e=>{if(e.target.closest('#gallery'))e.preventDefault()});
  document.addEventListener('pointerdown',e=>{
    suppress=false;
    if(e.button!==0||e.pointerType==='touch'||$('#viewer').open||$('#modal').open)return;
    const grid=e.target.closest('#gallery');if(!grid||e.target.closest('button,.empty'))return;
    const r=grid.getBoundingClientRect();drag={grid,rect:r,id:e.pointerId,ox:e.clientX,oy:e.clientY,sx:e.clientX-r.left+grid.scrollLeft,sy:e.clientY-r.top+grid.scrollTop,x:e.clientX,y:e.clientY,before:new Set(selected()),additive:e.ctrlKey||e.metaKey||e.shiftKey,active:false,dirty:false};
  });
  document.addEventListener('pointermove',e=>{
    if(!drag||drag.id!==e.pointerId)return;drag.x=e.clientX;drag.y=e.clientY;
    if(!drag.active){
      if(Math.hypot(e.clientX-drag.ox,e.clientY-drag.oy)<6)return;
      const r=drag.rect,sx=drag.grid.scrollLeft,sy=drag.grid.scrollTop;
      drag.cards=[...drag.grid.querySelectorAll('.photo')].map(card=>{const c=card.getBoundingClientRect();return {id:card.dataset.id,x:c.left-r.left+sx,y:c.top-r.top+sy,width:c.width,height:c.height}});
      drag.active=true;drag.box=document.createElement('div');drag.box.className='selection-marquee';document.body.append(drag.box);drag.grid.setPointerCapture(e.pointerId);raf=requestAnimationFrame(scroll);
    }
    e.preventDefault();drag.dirty=true;
  },{passive:false});
  document.addEventListener('pointerup',e=>{if(drag?.id===e.pointerId)finish()});document.addEventListener('pointercancel',()=>finish(true));
  document.addEventListener('keydown',e=>{
    if(drag&&e.key==='Escape'){e.preventDefault();finish(true)}
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='a'&&e.target.closest('#gallery')&&!$('#viewer').open){e.preventDefault();visible().forEach(p=>selected().add(p.id));syncSelection()}
  });
  document.addEventListener('click',e=>{
    if(suppress){suppress=false;e.preventDefault();e.stopImmediatePropagation();return}
    const card=e.target.closest('#gallery .photo');if(card&&!e.target.closest('button'))selectPhoto(card.dataset.id,e);
    if(e.target.id==='gallery'&&!e.ctrlKey&&!e.metaKey){selected().clear();syncSelection();refreshInspector()}
  },true);
  $('#gallery').addEventListener('dblclick',e=>{const card=e.target.closest('.photo');if(card&&!e.target.closest('button'))doubleClickPhoto(card.dataset.id)});
  $('#gallery').addEventListener('layoutchange',()=>finish(true));window.addEventListener('resize',()=>finish(true));
}
