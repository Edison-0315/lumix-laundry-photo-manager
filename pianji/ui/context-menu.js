import {state,$,selected,visible,current,button,el,error} from './store.js';
import {syncSelection,openViewer} from './gallery.js';

export function setupContextMenu(actions,inspect){
  let menu=null,origin=null;
  const close=(focus=false)=>{menu?.remove();menu=null;if(focus)origin?.focus()};
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
    document.body.append(menu);const rect=menu.getBoundingClientRect();menu.style.left=Math.max(8,Math.min(x,innerWidth-rect.width-8))+'px';menu.style.top=Math.max(8,Math.min(y,innerHeight-rect.height-8))+'px';menu.querySelector('button:not(:disabled)')?.focus();
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
