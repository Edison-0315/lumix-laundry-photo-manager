const paths={
  image:'M4 4h16v16H4z M4 15l5-5 6 6 3-3 2 2 M16 8h.01',
  library:'M5 3h14v18H5z M8 7h8 M8 11h8 M8 15h5',
  folder:'M3 7V5h7l2 2h9v13H3z',
  calendar:'M4 5h16v16H4z M8 3v4 M16 3v4 M4 10h16 M8 14h2 M14 14h2',
  person:'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M5 21v-2a7 7 0 0 1 14 0v2',
  users:'M15 7a3 3 0 1 1-6 0 3 3 0 0 1 6 0 M6 20v-2a6 6 0 0 1 12 0v2 M18 4a3 3 0 0 1 0 6 M20 14a5 5 0 0 1 2 4 M6 4a3 3 0 0 0 0 6 M4 14a5 5 0 0 0-2 4',
  inbox:'M4 4h16v16H4z M4 14h5l1 3h4l1-3h5',
  back:'M19 12H5 M11 6l-6 6 6 6',
  plus:'M12 5v14 M5 12h14',minus:'M5 12h14',
  check:'m5 12 4 4 10-10',select:'M4 4h16v16H4z m4 8 3 3 5-6',
  trash:'M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7',
  clean:'m4 17 8-8 6 6-8 8z M13 10l6-7 M5 22h15',
  close:'m6 6 12 12 M6 18 18 6',more:'M5 12h.01 M12 12h.01 M19 12h.01',
  scan:'M8 3H3v5 M16 3h5v5 M3 16v5h5 M21 16v5h-5 M8 10h.01 M16 10h.01 M8 15q4 4 8 0',
  import:'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5',
  export:'M12 16V3 M7 8l5-5 5 5 M4 15v6h16v-6',
  restore:'M3 9V3 M3 9h6 M3 9a9 9 0 1 1 1 9',
  edit:'m4 16 12-12 4 4-12 12H4z M13 7l4 4',
  link:'m10 14 4-4 M8 16l-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0 M16 8l1-1a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0',
  chevron:'m9 5 7 7-7 7',zoom:'M15 15l6 6 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0',
};
export function icon(name){
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');svg.setAttribute('stroke-width','1.65');svg.setAttribute('stroke-linecap','round');svg.setAttribute('stroke-linejoin','round');svg.setAttribute('aria-hidden','true');svg.classList.add('ui-icon');
  const p=document.createElementNS(svg.namespaceURI,'path');p.setAttribute('d',paths[name]||paths.folder);svg.append(p);return svg;
}
const labels={'返回':'back','关闭':'close','取消':'close','确认':'check','全选':'select','取消全选':'select','选片':'image','照片库':'library','管理照片库':'library','选择来源':'folder','识别人脸':'scan','平铺照片':'image','人物文件夹':'folder','导入所选':'import','开始导入':'import','新建活动':'plus','创建活动':'plus','新建照片库':'plus','创建并打开':'plus','打开已有照片库':'folder','清理空文件夹':'clean','删除照片库…':'trash','移到系统回收站':'trash','移除记录':'close','调整人物':'users','添加人物':'plus','管理人物':'users','更多操作':'more','标为已修':'check','恢复待修':'restore','标为成片':'image','取消成片':'close','删除照片…':'trash','删除活动…':'trash','删除人物分类…':'trash','恢复':'restore','恢复所选':'restore','永久删除所选':'trash','清空回收站':'trash','确认永久删除':'trash','查看大图':'zoom','用 Photoshop 打开':'edit','选择导出图片并关联':'link','打开成片文件夹':'folder','选择保存位置':'folder','打开':'folder','保存':'check'};
const ids={'new-activity':'plus','new-person':'plus','back':'back','thumb-smaller':'minus','thumb-larger':'plus','viewer-prev':'back','viewer-next':'chevron','viewer-out':'minus','viewer-in':'plus','viewer-close':'close'};
export function decorateButton(b){
  if(b.querySelector(':scope > .ui-icon'))return;
  const name=ids[b.id]||labels[b.textContent.trim()];if(!name)return;
  if(ids[b.id]){if(b.id==='back')b.textContent='返回';else b.textContent=''}
  b.prepend(icon(name));
}
export function decorateControls(){document.querySelectorAll('.appbar button,.sidebar button,.pagehead button,.toolbar button,footer button,.viewer-toolbar button').forEach(decorateButton);const all=document.querySelector('#people-all');if(all&&!all.querySelector('svg'))all.prepend(icon('users'))}
