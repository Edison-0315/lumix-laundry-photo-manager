import {state,$,assets,el,button,error,toast} from './store.js';
import {api} from './api.js';

export function modal(title){
  const dialog=$('#modal'),body=$('#modal-content');body.replaceChildren(el('h2','',title));
  const content=el('div'),err=el('div','field-error'),buttons=el('div','buttons');body.append(content,err,buttons);
  buttons.append(button('取消',()=>dialog.close()));
  if(!dialog.open)dialog.showModal();
  const submit=(text,fn)=>{
    const b=button(text,async()=>{b.disabled=true;err.textContent='';try{await fn();if(content.isConnected&&dialog.open)dialog.close()}catch(e){if(!dialog.open&&content.isConnected)dialog.showModal();err.textContent=e.message}finally{b.disabled=false}},'primary');buttons.append(b);return b;
  };
  return {dialog,content,err,buttons,submit};
}
function field(parent,label,value='',type='text'){
  const row=el('label','',label),input=el('input');input.type=type;input.value=value;row.append(input);parent.append(row);return input;
}
export function confirmAction(title,message,fn){const m=modal(title);m.content.append(el('p','',message));m.submit('确认',fn)}
export async function settingsDialog(refresh){
  const settings=await api('get_settings');const m=modal('设置');
  const path=field(m.content,'Photoshop 程序路径',settings.photoshop||'');path.placeholder='例如 C:\\Program Files\\Adobe\\…\\Photoshop.exe';
  m.content.append(button('选择 Photoshop.exe',async()=>{try{const p=await api('choose_photoshop');if(p)path.value=p}catch(e){m.err.textContent=e.message}},'outline'));
  m.content.append(el('p','','可手动填写自定义位置；打开照片后仍需手动标记已修。'));
  m.content.append(el('div','notice','照片库：'+(settings.library||'尚未选择')+'\n照片保存在你选择的文件夹中；设置与缩略图缓存保存在本机AppData。'));
  m.content.append(button('重试未完成的文件恢复',async()=>{try{m.dialog.close();await refresh('recover_pending')}catch(e){error(e)}},'outline'));
  m.submit('保存',async()=>{state.settings=await api('save_settings',{photoshop:path.value.trim()});toast('设置已保存')});
}
export function importDialog(start){
  if(!state.settings.library_available){toast('请先选择照片库');return}
  const ids=[...state.selected.sd];if(!ids.length)return;
  const m=modal('导入所选照片');const name=field(m.content,'活动名称',state.activities.find(a=>a.id===state.activity)?.name||new Date().toLocaleDateString('sv-SE')+'_漫展');
  const list=el('datalist');list.id='activity-names';state.activities.forEach(a=>{const o=el('option');o.value=a.name;list.append(o)});m.content.append(list);name.setAttribute('list','activity-names');
  const label=el('label','','导入格式'),select=el('select');for(const [value,text]of[['both','JPEG 和 RAW'],['jpeg','仅 JPEG'],['raw','仅 RAW']]){const o=el('option','',text);o.value=value;select.append(o)}label.append(select);m.content.append(label);
  const summary=el('div','notice');const update=()=>{const groups=state.sourcePhotos.filter(p=>ids.includes(p.id)),files=groups.flatMap(assets).filter(a=>select.value==='both'||a.kind===select.value||select.value==='raw'&&a.kind==='xmp');summary.textContent=`已选 ${ids.length} 张照片，预计 ${files.length} 个文件。\n目标：${state.settings.library}\\${name.value}\\待分类\\选出原片\n从来源复制，源文件保留；导入后可识别人脸。`};name.oninput=update;select.onchange=update;update();m.content.append(summary);
  m.submit('开始导入',()=>start('import_selected',state.scanId,ids,name.value,select.value));
}
export function assignDialog(ids,start,refresh){
  const m=modal('调整人物');m.content.append(el('p','',`将 ${ids.length} 张照片及关联文件整理到所选人物文件夹。`));
  const select=el('select');for(const p of state.people){const o=el('option','',p.name);o.value=p.id;select.append(o)}m.content.append(select);
  m.content.append(button('新建人物',()=>newPersonDialog(async person=>{await refresh();await start('set_person',ids,person.id)}),'outline'));
  m.submit('移动到此人物',()=>start('set_person',ids,select.value));
}
export function newPersonDialog(done){
  if(!state.activity){toast('请先选择活动');return}
  const m=modal('新建人物'),name=field(m.content,'人物名称');
  m.submit('创建',async()=>{const person=await api('create_person',state.activity,name.value);await done(person)});name.focus();
}
export function managePeopleDialog(start){
  const normal=state.people.filter(p=>!p.role);if(!normal.length){toast('还没有普通人物，可以先识别人脸或新建人物');return}
  const m=modal('管理人物'),select=el('select');normal.forEach(p=>{const o=el('option','',p.name);o.value=p.id;select.append(o)});m.content.append(select);
  const name=field(m.content,'新名称',normal[0].name);select.onchange=()=>name.value=normal.find(p=>p.id===select.value).name;
  m.submit('重命名',()=>start('rename_person',select.value,name.value));
  const target=el('select');state.people.forEach(p=>{const o=el('option','',p.name);o.value=p.id;target.append(o)});
  const label=el('label','','或合并到');label.append(target);m.content.append(label,el('p','','合并会移动全部原片和成片，人工归属将保留。'));
  m.buttons.prepend(button('合并人物',async()=>{try{if(select.value===target.value)throw new Error('请选择另一个人物');m.dialog.close();confirmAction('合并人物','确认将所选人物的全部照片移到目标人物？',()=>start('merge_people',select.value,target.value))}catch(e){m.err.textContent=e.message}},'outline'));
}
export function resultDialog(snapshot){
  const m=modal(snapshot.status==='failed'?'任务未完成':snapshot.status==='cancelled'?'任务已取消':'部分文件需要处理');
  const result=snapshot.result||{};
  m.content.append(el('p','',snapshot.status==='cancelled'?'已经完整完成的照片保留，未完成的文件已尝试恢复；可重新执行。':'已完成的照片保留，请检查下面的文件后重试。'));
  const list=el('div','notice');list.style.maxHeight='300px';list.style.overflow='auto';
  for(const e of snapshot.errors||[])list.append(el('p','',(e.name||e.id||'')+' '+(e.message||JSON.stringify(e))));
  if(!list.children.length)list.textContent=`完成 ${result.imported?.length??result.classified??snapshot.done??0} 项。`;
  m.content.append(list);m.buttons.replaceChildren(button('知道了',()=>m.dialog.close(),'primary'));
}
