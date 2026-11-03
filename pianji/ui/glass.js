import {makeLensMap} from './glass-optics.js';
const ns='http://www.w3.org/2000/svg';
const instances=new Set(),cache=new Map();let serial=0,definitions;
const preferenceQueries=['(prefers-reduced-transparency: reduce)','(prefers-contrast: more)','(forced-colors: active)'].map(q=>matchMedia(q));
const solid=()=>preferenceQueries.some(q=>q.matches);
function svg(tag,attrs={}){const node=document.createElementNS(ns,tag);for(const [key,value]of Object.entries(attrs))node.setAttribute(key,String(value));return node}
function defs(){
  if(definitions)return definitions;
  const root=svg('svg',{id:'glass-definitions',width:0,height:0,'aria-hidden':true,focusable:false});root.style.cssText='position:fixed;left:0;top:0;pointer-events:none';
  definitions=svg('defs');root.append(definitions);document.body.prepend(root);return definitions;
}
function mapFor(width,height,radius,strength){
  const key=[width,height,radius,strength].join(':');if(cache.has(key))return cache.get(key);
  const map=makeLensMap(width,height,{radius,strength}),canvas=document.createElement('canvas');canvas.width=map.width;canvas.height=map.height;
  canvas.getContext('2d').putImageData(new ImageData(map.data,map.width,map.height),0,0);
  const value={url:canvas.toDataURL(),scale:map.scale};cache.set(key,value);while(cache.size>20)cache.delete(cache.keys().next().value);return value;
}
export function attachGlass(host,{radius,strength=12,blur=10}={}){
  const layer=document.createElement('div');layer.className='lens-backdrop';layer.setAttribute('aria-hidden','true');host.classList.add('lens-surface');host.prepend(layer);
  const id='glass-lens-'+(++serial),filter=svg('filter',{id,filterUnits:'userSpaceOnUse',primitiveUnits:'userSpaceOnUse','color-interpolation-filters':'sRGB'});
  const image=svg('feImage',{result:'lensMap',preserveAspectRatio:'none'}),displace=svg('feDisplacementMap',{in:'SourceGraphic',in2:'lensMap',xChannelSelector:'R',yChannelSelector:'G'});filter.append(image,displace);defs().append(filter);
  let frame=0,geometry='',destroyed=false;
  function update(){
    cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{
      frame=0;if(destroyed||!host.isConnected)return;
      if(solid()){layer.style.backdropFilter='none';return}
      const width=host.offsetWidth,height=host.offsetHeight;if(!width||!height)return;
      const corner=radius??(parseFloat(getComputedStyle(host).borderTopLeftRadius)||18),next=[width,height,corner,strength].join(':');
      if(next!==geometry){
        geometry=next;const map=mapFor(width,height,corner,strength),margin=Math.ceil(map.scale);
        for(const [key,value]of Object.entries({x:-margin,y:-margin,width:width+margin*2,height:height+margin*2}))filter.setAttribute(key,value);
        for(const [key,value]of Object.entries({x:0,y:0,width,height,href:map.url}))image.setAttribute(key,value);
        displace.setAttribute('scale',map.scale);
      }
      layer.style.backdropFilter=`url("#${id}") blur(${blur}px) saturate(1.2)`;
    });
  }
  const observer=new ResizeObserver(update);observer.observe(host);
  const instance={update,destroy(){destroyed=true;cancelAnimationFrame(frame);observer.disconnect();filter.remove();layer.remove();host.classList.remove('lens-surface');instances.delete(instance)}};
  instances.add(instance);update();return instance;
}
for(const query of preferenceQueries)query.addEventListener('change',()=>instances.forEach(instance=>instance.update()));
