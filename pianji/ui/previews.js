import {api} from './api.js';
const cache=new Map();
export function preview(photo,kind,scanId=null){
  const key=JSON.stringify([scanId,photo.id,kind]);
  if(cache.has(key))return cache.get(key);
  // Merge in-flight reads only. Completed reads must reach the backend again,
  // where the actual file mtime/size determines whether disk cache is current.
  const request=api('get_preview',photo.id,kind,scanId).finally(()=>{if(cache.get(key)===request)cache.delete(key)});
  cache.set(key,request);if(cache.size>128)cache.delete(cache.keys().next().value);return request;
}
export function invalidateLibraryPreviews(){for(const key of cache.keys())if(JSON.parse(key)[0]===null)cache.delete(key)}
