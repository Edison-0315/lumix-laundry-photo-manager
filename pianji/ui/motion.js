// Small, independent springs: retarget from presentation values and velocity.
export const reducedMotion=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
export function spring(initial,paint){
  let value={...initial},target={...initial},velocity={},frame=0,last=0;
  const keys=Object.keys(initial);
  function stop(){cancelAnimationFrame(frame);frame=0;last=0}
  function jump(next){stop();value={...value,...next};target={...value};velocity={};paint({...value})}
  function tick(time){
    const dt=Math.min((time-last)/1000||1/60,.032);last=time;
    const steps=Math.ceil(dt*120),step=dt/steps;
    for(let i=0;i<steps;i++)for(const key of keys){
      velocity[key]=(velocity[key]||0)+(300*(target[key]-value[key])-34*(velocity[key]||0))*step;
      value[key]+=velocity[key]*step;
    }
    const moving=keys.some(key=>Math.abs(target[key]-value[key])>(key==='scale'?.0001:.01)||Math.abs(velocity[key]||0)>(key==='scale'?.001:.05));
    if(!moving){value={...target};velocity={}}
    paint({...value});frame=moving?requestAnimationFrame(tick):0;if(!moving)last=0;
  }
  function to(next,releaseVelocity={}){
    target={...target,...next};velocity={...velocity,...releaseVelocity};
    if(reducedMotion()){jump(target);return}
    if(!frame){last=performance.now();frame=requestAnimationFrame(tick)}
  }
  return {get value(){return {...value}},get target(){return {...target}},jump,to,stop};
}
