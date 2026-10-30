export async function ready(){
  if(window.pywebview?.api)return;
  await new Promise(resolve=>window.addEventListener('pywebviewready',resolve,{once:true}));
}
export async function api(name,...args){
  const fn=window.pywebview?.api?.[name];
  if(!fn)throw new Error('桌面连接尚未就绪，请重新启动程序');
  const response=await fn(...args);
  if(!response?.ok)throw new Error(response?.error?.message||'操作未完成');
  return response.data;
}
