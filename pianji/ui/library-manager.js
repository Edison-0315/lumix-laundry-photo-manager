import {api} from './api.js';
import {state,el,button,resetLibrarySelection,toast} from './store.js';
import {modal} from './dialogs.js';
import {invalidateLibraryPreviews} from './previews.js';
import {clearChoices} from './choice-list.js';

export async function libraryDialog(refresh){
  if(state.busy){toast('请等待当前任务完成');return false}
  const recent=await api('list_libraries'),m=modal('管理照片库');let done=false,working=false;
  const preventCancel=e=>{if(working)e.preventDefault()};m.dialog.addEventListener('cancel',preventCancel);
  const result=new Promise(resolve=>{
    m.dialog.addEventListener('close',()=>{m.dialog.removeEventListener('cancel',preventCancel);if(!done)resolve(false)},{once:true});
    const activate=async choice=>{
      if(!choice)return;
      resetLibrarySelection();clearChoices();state.browse='folders';state.activity=null;state.person='all';state.stage='all';state.date='all';state.format='all';invalidateLibraryPreviews();
      await refresh();done=true;resolve(true);if(m.content.isConnected&&m.dialog.open)m.dialog.close();
      if(choice.recovery?.errors?.length)toast('有文件需要恢复，请关闭占用程序后在设置中重试');
    };
    const run=(fn,propagate=false)=>async()=>{
      if(working)return;working=true;m.err.textContent='';const disabled=new Map([...m.dialog.querySelectorAll('button')].map(b=>[b,b.disabled]));disabled.forEach((_,b)=>b.disabled=true);
      try{await fn()}catch(e){m.err.textContent=e.message;if(propagate)throw e}finally{working=false;disabled.forEach((value,b)=>{if(b.isConnected)b.disabled=value})}
    };
    const showCreate=()=>{
      m.content.replaceChildren(el('p','','填写名称并选择保存位置，会在该位置创建独立的照片库文件夹。'));
      const label=el('label','','照片库名称'),name=el('input');name.value='我的照片库';label.append(name);
      const location=el('p','path','尚未选择保存位置');let parent=null;
      const pick=button('选择保存位置',run(async()=>{const p=await api('choose_library_parent');if(p){parent=p;location.textContent=p.path}}),'outline');
      m.content.append(label,pick,location);m.buttons.replaceChildren(button('返回',showHome));
      m.submit('创建并打开',run(async()=>{if(!parent)throw new Error('请先选择保存位置');await activate(await api('create_library',parent.token,name.value.trim()))},true));
      name.focus();name.select();
    };
    const showHome=()=>{
      m.content.replaceChildren(el('p','','每个照片库独立保存照片、人物和活动。可以按年份或项目分库。'));
      const actions=el('div','manager-actions');actions.append(button('新建照片库',showCreate,'primary'),button('打开已有照片库',run(async()=>activate(await api('choose_library'))),'outline'));m.content.append(actions,el('h3','','最近照片库'));
      for(const item of recent){
        const row=el('div','library-row'),text=el('div');text.append(el('strong','',item.name+(item.current?' · 当前':'')),el('div','path',item.path));if(!item.available)text.append(el('div','warning small','磁盘未连接或照片库已移动'));
        row.append(text);
        if(!item.current){const open=button('打开',run(async()=>activate(await api('open_library',item.path))),'outline');open.disabled=!item.available;row.append(open,button('移除记录',run(async()=>{await api('remove_recent_library',item.path);recent.splice(recent.indexOf(item),1);showHome()}),'small muted'))}
        m.content.append(row);
      }
      if(!recent.length)m.content.append(el('p','muted','还没有照片库，可以新建或打开已有照片库。'));
      m.buttons.replaceChildren(button('关闭',()=>m.dialog.close()));
    };
    showHome();
  });
  return result;
}
