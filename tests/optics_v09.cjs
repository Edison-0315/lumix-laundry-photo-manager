const assert=require('assert'),{pathToFileURL}=require('url'),path=require('path');
(async()=>{
 const {makeLensMap}=await import(pathToFileURL(path.resolve(__dirname,'../pianji/ui/glass-optics.js')));
 const zero=makeLensMap(240,80,{radius:18,strength:0});assert.equal(zero.scale,0);assert(zero.data.every((n,i)=>i%4===0||i%4===1?n===128:i%4===2?n===0:n===255));
 const lens=makeLensMap(240,80,{radius:18,strength:14,band:16});assert(lens.width<=512&&lens.height<=512);assert(lens.scale>0&&lens.scale<=28);assert.equal(lens.data.length,lens.width*lens.height*4);
 const sample=(x,y)=>{const i=(y*lens.width+x)*4;return [(lens.data[i]/255-.5)*lens.scale,(lens.data[i+1]/255-.5)*lens.scale]};
 assert(Math.abs(sample(120,40)[0])<.08&&Math.abs(sample(120,40)[1])<.08,'center must remain optically stable');
 assert(sample(2,40)[0]<-8&&sample(237,40)[0]>8,'opposite rims sample opposite directions');
 assert(Math.abs(sample(120,25)[1])<Math.abs(sample(120,3)[1]),'edge displacement must fall smoothly into the center');
 const large=makeLensMap(1700,100,{radius:22,strength:12});assert(large.width<=512&&large.height<=512);assert(large.data.length<=512*512*4);
 for(const args of [[0,20],[20,NaN],[Infinity,20]])assert.throws(()=>makeLensMap(...args),RangeError);
 assert.throws(()=>makeLensMap(30,30,{strength:Infinity}),RangeError);
 const tiny=makeLensMap(.5,.5,{radius:99,strength:10});assert(tiny.data.length>0&&Number.isFinite(tiny.scale));
 console.log('PASS optical math: identity, signed rim field, stable center, encoding, geometry limits and invalid input');
})().catch(e=>{console.error(e);process.exitCode=1});
