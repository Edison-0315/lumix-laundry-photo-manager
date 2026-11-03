import {state,$,selected,visible,current,button,el,error} from './store.js';
import {syncSelection,openViewer} from './gallery.js';
import {reducedMotion} from './motion.js';
let menu=null,origin=null;
const close=(focus=false)=>{
  const outgoing=menu;menu=null;
  if(outgoing){
    if(reducedMotion())outgoing.remove();
    else{
      const style=getComputedStyle(outgoing),opacity=style.opacity,transform=style.transform;
      outgoing.inert=true;outgoing.setAttribute('aria-hidden','true');outgoing.removeAttribute('role');
      outgoing.querySelectorAll('[role]').forEach(node=>node.removeAttribute('role'));
      outgoing.style.pointerEvents='none';outgoing.style.animation='none';
      const exit=outgoing.animate([{opacity,transform},{opacity:0,transform:'scale(.97)'}],{duration:100,easing:'ease-in',fill:'forwards'});
      exit.finished.then(()=>outgoing.remove(),()=>outgoing.remove());
    }
  }
  if(focus)origin?.focus();
};
export function commandMenu(x,y,title,entries){
  close();origin=document.activeElement;menu=el('div','context-menu');menu.setAttribute('role','menu');menu.setAttribute('aria-label',title);menu.append(el('div','menu-heading',title));
  for(const item of entries){const b=button(item.name,()=>{close();Promise.resolve().then(item.fn).catch(error)},item.danger?'danger':'');b.disabled=Boolean(item.disabled);b.setAttribute('role','menuitem');menu.append(b)}
  placeMenu(x,y);menu.querySelector('button:not(:disabled)')?.focus();
}
function placeMenu(x,y){
  document.body.append(menu);const width=menu.offsetWidth,height=menu.offsetHeight;
  const left=Math.max(8,Math.min(x,innerWidth-width-8)),top=Math.max(8,Math.min(y,innerHeight-height-8));
  menu.style.left=left+'px';menu.style.top=top+'px';menu.style.transformOrigin=`${Math.max(0,Math.min(width,x-left))}px ${Math.max(0,Math.min(height,y-top))}px`;
}

export function setupContextMenu(actions,inspect){
  const show=(x,y)=>{
    close();const rows=visible().filter(p=>selected().has(p.id));if(!rows.length)return;
    origin=document.activeElement;menu=el('div','context-menu');menu.setAttribute('role','menu');menu.setAttribute('aria-label',`已选 ${rows.length} 张照片`);
    menu.append(el('div','menu-heading',`已选 ${rows.length} 张照片`));
    const add=(name,fn,disabled=false,danger=false)=>{const b=button(name,()=>{close();Promise.resolve().then(fn).catch(error)},danger?'danger':'');b.setAttribute('role','menuitem');b.disabled=disabled;menu.append(b)};
    add('查看大图',()=>openViewer(current()?.id||rows[0].id),rows.length!==1);
    if(state.view==='sd'){
      add('导入所选',()=>$('#import').click(),state.busy);
      add('取消选择',()=>{selected().clear();syncSelection();inspect()});
    }else{
      add('调整人物',()=>$('#assign').click(),state.busy);
      for(const [id,label]of [['mark-edited','标为已修'],['mark-pending','恢复待修'],['mark-finished','标为成片'],['unmark-finished','取消成片']]){
        const source=$('#'+id);if(!source.hidden)add(label,()=>source.click(),source.disabled);
      }
      add('删除照片…',actions.trash,state.busy,true);
    }
    placeMenu(x,y);menu.querySelector('button:not(:disabled)')?.focus();
  };
  $('#gallery').addEventListener('contextmenu',e=>{
    e.preventDefault();const card=e.target.closest('.photo');if(!card)return;
    if(!selected().has(card.dataset.id)){selected().clear();selected().add(card.dataset.id)}
    state.current=card.dataset.id;state.anchor[state.view]=card.dataset.id;syncSelection();inspect();show(e.clientX,e.clientY);
  });
  $('#more-actions').onclick=()=>{const r=$('#more-actions').getBoundingClientRect();show(r.left,r.top)};
  document.addEventListener('pointerdown',e=>{if(menu&&!menu.contains(e.target))close()});
  document.addEventListener('scroll',()=>close(),true);window.addEventListener('resize',()=>close());
  document.addEventListener('keydown',e=>{
    if(menu){
      if(e.key==='Escape'||e.key==='Tab'){e.preventDefault();close(true);return}
      if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();const items=[...menu.querySelectorAll('button:not(:disabled)')],at=items.indexOf(document.activeElement);items[e.key==='Home'?0:e.key==='End'?items.length-1:(at+(e.key==='ArrowDown'?1:-1)+items.length)%items.length]?.focus()}
      return;
    }
    if($('#modal').open||$('#viewer').open||!e.target.closest('#gallery'))return;
    if(e.key==='ContextMenu'||e.shiftKey&&e.key==='F10'){e.preventDefault();const r=$('#gallery').getBoundingClientRect();show(r.left+32,r.top+32)}
    if(e.key==='Delete'&&state.view==='library'&&!state.busy){e.preventDefault();Promise.resolve().then(actions.trash).catch(error)}
  });
}
