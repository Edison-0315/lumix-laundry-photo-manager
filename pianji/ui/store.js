export const state={view:'sd',source:null,sourceFolder:'',format:'all',scanId:null,sourcePhotos:[],photos:[],activities:[],people:[],activity:null,person:'all',stage:'all',date:'all',onlySelected:false,selected:{sd:new Set(),library:new Set()},anchor:{sd:null,library:null},current:null,thumbSize:240,settings:{},busy:false,psFormat:'raw',lastOperation:null};
export const $=s=>document.querySelector(s);
export function selected(){return state.selected[state.view]}
export function basePhotos(){return state.view==='sd'?state.sourcePhotos:state.photos.filter(p=>p.activity_id===state.activity)}
export function sourceDirs(p){return p.relative_dirs||[p.relative_dir||'']}
export function visible(){return basePhotos().filter(p=>(state.view!=='sd'||state.sourceFolder==='*'||sourceDirs(p).includes(state.sourceFolder))&&(state.format==='all'||assets(p).some(a=>a.kind===state.format))&&(state.view==='sd'||state.person==='all'||p.person_id===state.person)&&(state.view==='sd'||state.stage==='all'||state.stage==='pending'&&!p.edited||state.stage==='edited'&&p.edited||state.stage==='exports'&&p.primary_export_id)&&(state.date==='all'||(p.captured_at?.slice(0,10)||'unknown')===state.date)&&(!state.onlySelected||selected().has(p.id)))}
export function folderPaths(){const paths=new Set(['']);for(const p of state.sourcePhotos)for(const dir of sourceDirs(p)){let parent='';for(const part of dir.split('/').filter(Boolean)){parent=parent?parent+'/'+part:part;paths.add(parent)}}return [...paths].sort()}
export function childFolders(){if(state.view!=='sd'||state.sourceFolder==='*'||state.onlySelected)return [];const prefix=state.sourceFolder?state.sourceFolder+'/':'';return folderPaths().filter(p=>p.startsWith(prefix)&&p!==state.sourceFolder&&!p.slice(prefix.length).includes('/'))}
export function resetLibrarySelection(){state.selected.library.clear();state.anchor.library=null;state.current=null;state.lastOperation=null;state.onlySelected=false}
export function current(){return visible().find(p=>p.id===state.current)}
export function assets(p){return p.assets||p.files||[]}
export function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
export function button(text,fn,cls=''){const b=el('button',cls,text);b.type='button';b.addEventListener('click',fn);return b}
let timer;
export function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(timer);timer=setTimeout(()=>$('#toast').hidden=true,4500)}
export function error(e){toast(e.message||String(e))}
