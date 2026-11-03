import {$,selected,state} from './store.js';
import {attachGlass} from './glass.js';
import {spring,reducedMotion} from './motion.js';
import {setupSidebar,syncSidebar} from './sidebar-motion.js';
let indicator,slide,seen=false,input='pointer',lastWidth=0,lastView,viewAnimation;
export const spatialMotion=()=>input==='pointer'&&!reducedMotion();
export function setupChrome(){
  setupSidebar();
  attachGlass($('footer'),{radius:20,strength:14,blur:8});
  attachGlass($('#modal'),{radius:22,strength:16,blur:12});
  attachGlass($('.viewer-toolbar'),{radius:18,strength:12,blur:10});
  const rail=$('#stage-tabs');indicator=document.createElement('div');indicator.className='stage-indicator';indicator.setAttribute('aria-hidden','true');rail.prepend(indicator);
  attachGlass(indicator,{radius:13,strength:10,blur:5});
  slide=spring({x:0},value=>indicator.style.transform=`translateX(${value.x}px)`);
  document.addEventListener('pointerdown',()=>{input='pointer';document.body.dataset.inputMode=input},true);
  document.addEventListener('keydown',()=>{input='keyboard';document.body.dataset.inputMode=input},true);
  new ResizeObserver(()=>syncChrome(true)).observe(rail);
  new ResizeObserver(()=>{
    const height=$('footer').offsetHeight;
    $('main').style.setProperty('--floating-footer-height',height+'px');
  }).observe($('footer'));
}
export function syncChrome(resize=false){
  if(!indicator)return;
  syncViewTransition();
  // A stage rail appearing/resizing must not snap an unrelated sidebar spring.
  syncSidebar();
  $('footer').classList.toggle('has-selection',selected().size>0);
  const rail=$('#stage-tabs'),active=rail.querySelector('button.active');
  if(rail.hidden||!active||!active.offsetWidth){seen=false;return}
  const width=active.offsetWidth;
  if(width!==lastWidth){indicator.style.width=width+'px';lastWidth=width}
  const target={x:active.offsetLeft};
  if(!seen||resize||reducedMotion()||input==='keyboard')slide.jump(target);else slide.to(target);
  seen=true;
}
function syncViewTransition(){
  if(lastView===state.view)return;
  const first=lastView===undefined;lastView=state.view;
  const gallery=$('#gallery'),running=viewAnimation?.playState==='running';
  const presentation=running?getComputedStyle(gallery):null;
  const opacity=running?presentation.opacity:.78,transform=running?presentation.transform:'translateY(4px)';
  viewAnimation?.cancel();
  if(first||reducedMotion()||input==='keyboard')return;
  const tokens=getComputedStyle(document.documentElement);
  viewAnimation=gallery.animate([{opacity,transform},{opacity:1,transform:'translateY(0)'}],{
    duration:parseFloat(tokens.getPropertyValue('--motion-layer'))||200,easing:tokens.getPropertyValue('--ease-fluid').trim(),
  });
}
