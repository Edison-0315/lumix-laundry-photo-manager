import {state,$,resetLibrarySelection} from './store.js';
const fields=['view','activity','person','stage','browse','sourceFolder','date','format'];
state.history=[];
export function clearHistory(){state.history=[]}
export function remember(){
  const entry=Object.fromEntries(fields.map(key=>[key,state[key]]));entry.library=state.settings.library;entry.scan=state.scanId;entry.scroll=$('#gallery')?.scrollTop||0;
  const last=state.history.at(-1);
  if(!last||fields.some(key=>last[key]!==entry[key])||last.library!==entry.library||last.scan!==entry.scan)state.history.push(entry);
  if(state.history.length>80)state.history.shift();
}
export async function goBack(refresh){
  if(state.busy)return;
  while(state.history.length){
    const entry=state.history.pop();
    if(entry.library!==state.settings.library||entry.view==='sd'&&entry.scan!==state.scanId)continue;
    if(entry.view==='library'&&entry.activity&&!state.activities.some(a=>a.id===entry.activity))continue;
    resetLibrarySelection();for(const key of fields)state[key]=entry[key];
    await refresh();requestAnimationFrame(()=>{if($('#gallery'))$('#gallery').scrollTop=entry.scroll});return;
  }
  $('#back').disabled=true;
}
