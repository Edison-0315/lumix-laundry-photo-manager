import {state,libraryFolderMode,libraryFolders,childFolders} from './store.js';
const groups=new Map();
export function choices(scope){if(!groups.has(scope))groups.set(scope,new Set());return groups.get(scope)}
export function clearChoices(){groups.clear()}
export function syncChoices(scope){for(const node of document.querySelectorAll('[data-select-scope]'))if(node.dataset.selectScope===scope){const yes=choices(scope).has(node.dataset.selectKey);node.classList.toggle('checked',yes);node.setAttribute('aria-pressed',String(yes))}}
export function bindChoice(node,scope,key,open,change=()=>{}){
  let before=null;node.dataset.selectScope=scope;node.dataset.selectKey=key;node.setAttribute('aria-pressed',String(choices(scope).has(key)));node.classList.toggle('checked',choices(scope).has(key));
  node.addEventListener('click',e=>{if(e.detail>1)return;if(e.detail===1)before=new Set(choices(scope));const set=choices(scope);set.has(key)?set.delete(key):set.add(key);syncChoices(scope);change()});
  node.addEventListener('dblclick',e=>{e.preventDefault();if(before){groups.set(scope,before);syncChoices(scope);change()}before=null;open()});
  node.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();open()}});
  return node;
}
export function folderScope(){return state.view==='sd'?'folders:sd:'+state.scanId+':'+state.sourceFolder:'folders:library:'+state.activity+':'+state.person+':'+state.stage}
export function selectableFolderKeys(){const keys=libraryFolderMode()?libraryFolders().map(p=>p.key):state.view==='sd'?childFolders():[];return state.onlySelected?keys.filter(key=>choices(folderScope()).has(key)):keys}
