import {$} from './store.js';
import {reducedMotion} from './motion.js';
let active=null,serial=0,applying=false;
const enabled=()=>typeof document.startViewTransition==='function'&&!reducedMotion()&&document.body.dataset.inputMode!=='keyboard';
export function stopWorkspaceTransition(){
  if(applying)return;
  serial++;active?.transition.skipTransition();active?.clear();active=null;
}
export function folderIdentity(node){return node?{scope:node.dataset.selectScope,key:node.dataset.selectKey}:null}
function currentFolder(identity){return [...document.querySelectorAll('.folder-card')].find(n=>n.dataset.selectScope===identity.scope&&n.dataset.selectKey===identity.key)}
function transition(source,change,destination){
  stopWorkspaceTransition();
  if(!enabled()||!source?.isConnected||!source.getClientRects().length){change();return Promise.resolve()}
  const ticket=serial,marked=new Set();let changed=false;
  const clear=()=>{for(const node of marked)if(node.dataset.transitionTicket===String(ticket)){node.style.removeProperty('view-transition-name');delete node.dataset.transitionTicket}};
  const mark=(node,name='folder-surface')=>{if(node?.isConnected){node.style.viewTransitionName=name;node.dataset.transitionTicket=ticket;marked.add(node)}};
  mark(source);mark($('footer'),'workspace-controls');
  const update=()=>{
    if(ticket!==serial)return;
    clear();applying=true;
    try{changed=true;change();mark(destination());mark($('footer'),'workspace-controls')}finally{applying=false}
  };
  try{
    const motion=document.startViewTransition(update),record={transition:motion,clear};active=record;
    motion.ready.catch(()=>{}); // Unsupported capture/geometry still executes the DOM update.
    motion.finished.catch(()=>{}).finally(()=>{clear();if(active===record)active=null});
    return motion.updateCallbackDone;
  }catch(error){clear();if(!changed)change();return Promise.resolve()}
}
export function enterWorkspaceFolder(source,change){return transition(source,change,()=>$('#gallery'))}
export function leaveWorkspaceFolder(identity,change){return identity?transition($('#gallery'),change,()=>currentFolder(identity)):Promise.resolve(change())}
