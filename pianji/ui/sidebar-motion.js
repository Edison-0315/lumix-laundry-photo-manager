import {$,state} from './store.js';
import {attachGlass} from './glass.js';
import {spring,reducedMotion} from './motion.js';
let groups=[],sceneURL='',front=0;
export function setupSidebar(){
  attachGlass($('.sidebar'),{radius:22,strength:12,blur:20});
  attachGlass($('.thumbnail-control'),{radius:22,strength:10,blur:8});
  for(const selector of ['.sidebar nav','#activities-section','#people-body','#source-section']){
    const host=$(selector),lens=document.createElement('div');lens.className='sidebar-selection';lens.setAttribute('aria-hidden','true');host.prepend(lens);
    const motion=spring({x:0,y:0},value=>lens.style.transform=`translate3d(${value.x}px,${value.y}px,0)`);
    const group={host,lens,motion,seen:false,width:0,height:0};groups.push(group);
    new ResizeObserver(()=>{
      const width=host.clientWidth,height=host.clientHeight;
      if(width===group.width&&height===group.height)return;
      group.width=width;group.height=height;syncGroup(group,true);
    }).observe(host);
  }
}
export function syncThumbnailControl(value=state.thumbSize){
  const input=$('#thumb-size');input.style.setProperty('--thumb-progress',((value-80)/640*100)+'%');$('#thumb-size-label').textContent=value;
}
export function syncSidebar(resize=false){
  syncThumbnailControl();
  for(const group of groups)syncGroup(group,resize);
}
function syncGroup(group,resize=false){
    const {host,lens,motion}=group,active=host.querySelector('.nav.active,.side-item.active');
    if(!active||!host.getClientRects().length||host.hidden){lens.hidden=true;motion.stop();group.seen=false;return}
    // Use layout geometry: the button's brief press scale is foreground feedback.
    // Sampling its transformed bounds would leave the selection film undersized.
    lens.hidden=false;lens.style.width=active.offsetWidth+'px';lens.style.height=active.offsetHeight+'px';
    let node=active,x=0,y=0;
    while(node&&node!==host){x+=node.offsetLeft;y+=node.offsetTop;node=node.offsetParent}
    const target={x,y};
    if(!group.seen||resize||reducedMotion()||document.body.dataset.inputMode==='keyboard')motion.jump(target);else motion.to(target);
    group.seen=true;
}
export function setSidebarScene(url){
  if(url===sceneURL)return;sceneURL=url;
  const layers=[...document.querySelectorAll('.sidebar-photo')];if(!layers.length)return;
  if(!url){layers.forEach(layer=>{layer.style.opacity=0;layer.style.backgroundImage='none'});return}
  front=1-front;layers[front].style.backgroundImage='url("'+url.replaceAll('"','%22')+'")';
  layers.forEach((layer,i)=>layer.style.opacity=i===front?'1':'0');
}
