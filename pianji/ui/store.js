export const state={view:'sd',source:null,scanId:null,sourcePhotos:[],photos:[],activities:[],people:[],activity:null,person:'all',stage:'all',date:'all',onlySelected:false,selected:{sd:new Set(),library:new Set()},anchor:{sd:null,library:null},current:null,thumbSize:240,settings:{},busy:false,psFormat:'raw',lastOperation:null};
export const $=s=>document.querySelector(s);
export function selected(){return state.selected[state.view]}
export function basePhotos(){return state.view==='sd'?state.sourcePhotos:state.photos.filter(p=>p.activity_id===state.activity)}
export function visible(){return basePhotos().filter(p=>(state.view==='sd'||state.person==='all'||p.person_id===state.person)&&(state.view==='sd'||state.stage==='all'||state.stage==='pending'&&!p.edited||state.stage==='edited'&&p.edited||state.stage==='exports'&&p.primary_export_id)&&(state.date==='all'||(p.captured_at?.slice(0,10)||'unknown')===state.date)&&(!state.onlySelected||selected().has(p.id)))}
export function current(){return basePhotos().find(p=>p.id===state.current)}
export function assets(p){return p.assets||p.files||[]}
export function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
export function button(text,fn,cls=''){const b=el('button',cls,text);b.type='button';b.addEventListener('click',fn);return b}
let timer;
export function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(timer);timer=setTimeout(()=>$('#toast').hidden=true,4500)}
export function error(e){toast(e.message||String(e))}
