// Source-sampling offsets in logical CSS pixels, encoded for an SVG lens map.
const smooth=t=>{t=Math.max(0,Math.min(1,t));return t*t*(3-2*t)};
export function makeLensMap(width,height,{radius=20,strength=12,band=16}={}){
  if(![width,height,radius,strength,band].every(Number.isFinite)||width<=0||height<=0||strength<0||band<=0)throw new RangeError('Invalid glass geometry');
  const density=Math.min(1,512/Math.max(width,height)),w=Math.max(1,Math.ceil(width*density)),h=Math.max(1,Math.ceil(height*density));
  const r=Math.max(0,Math.min(radius,width/2,height/2)),power=Math.min(strength,32),offsets=new Float32Array(w*h*2);
  let maximum=0;
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    const px=(x+.5)*width/w-width/2,py=(y+.5)*height/h-height/2;
    const qx=Math.abs(px)-width/2+r,qy=Math.abs(py)-height/2+r,ax=Math.max(qx,0),ay=Math.max(qy,0),length=Math.hypot(ax,ay);
    const distance=length+Math.min(Math.max(qx,qy),0)-r;
    let nx=0,ny=0;
    if(length>0){nx=ax/length*Math.sign(px);ny=ay/length*Math.sign(py)}
    else if(qx>qy)nx=Math.sign(px);else ny=Math.sign(py);
    const amplitude=distance<=0?power*smooth(1+distance/band):0,index=(y*w+x)*2;
    offsets[index]=nx*amplitude;offsets[index+1]=ny*amplitude;maximum=Math.max(maximum,Math.abs(offsets[index]),Math.abs(offsets[index+1]));
  }
  const scale=maximum*2,data=new Uint8ClampedArray(w*h*4);
  for(let i=0;i<w*h;i++){
    data[i*4]=scale?Math.round((.5+offsets[i*2]/scale)*255):128;
    data[i*4+1]=scale?Math.round((.5+offsets[i*2+1]/scale)*255):128;
    data[i*4+2]=0;data[i*4+3]=255;
  }
  return {width:w,height:h,data,scale};
}
