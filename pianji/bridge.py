"""Only methods without an underscore are exposed by pywebview."""
from pathlib import Path
from dataclasses import asdict
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
import base64
import json
import os
import logging
from .domain import uid
from .discovery import scan_source
from .library import Library
from .previews import PreviewCache
from .jobs import JobManager
from .photoshop import validate_executable,open_in_photoshop
from .paths import safe_name,inside

class PathNotGranted(ValueError): pass

def api(fn):
    @wraps(fn)
    def wrapper(*args,**kwargs):
        try: return {'ok':True,'data':fn(*args,**kwargs)}
        except Exception as e:
            logging.info('API %s failed: %s',fn.__name__,e)
            return {'ok':False,'error':{'code':'PATH_NOT_GRANTED' if isinstance(e,PathNotGranted) else 'OPERATION_FAILED','message':str(e)}}
    return wrapper

class Bridge:
    def __init__(self,config_root,dialog=None,model_root=None):
        self._config=Path(config_root); self._config.mkdir(parents=True,exist_ok=True)
        self._settings_file=self._config/'settings.json'
        try: self._settings=json.loads(self._settings_file.read_text(encoding='utf-8'))
        except (FileNotFoundError,ValueError): self._settings={}
        self._dialog=dialog; self._window=None; self._grants={}; self._scans={};self._library_parents={}
        self._jobs=JobManager(); self._previews=ThreadPoolExecutor(max_workers=2)
        self._cache=PreviewCache(self._config/'cache'); self._lib=None
        self._model_root=model_root or Path(__file__).resolve().parents[1]/'models'
        if self._settings.get('library'):
            # Stored library comes only from a prior native folder selection.
            if Path(self._settings['library']).is_dir(): self._lib=Library(self._settings['library'])

    def _persist(self):
        temp=self._settings_file.with_suffix('.tmp')
        temp.write_text(json.dumps(self._settings,ensure_ascii=False,indent=2),encoding='utf-8'); temp.replace(self._settings_file)

    def _pick(self,kind):
        if self._dialog: return self._dialog(kind)
        if not self._window: raise ValueError('桌面窗口尚未就绪')
        import webview
        dialog_type=webview.FileDialog.FOLDER if kind in ('source','library','library_parent') else webview.FileDialog.OPEN
        types=('程序 (*.exe)',) if kind=='photoshop' else ('图片 (*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.webp)',) if kind=='export' else ()
        result=self._window.create_file_dialog(dialog_type,allow_multiple=False,file_types=types)
        return result[0] if result else None

    def _library(self):
        if not self._lib: raise ValueError('请先选择照片库文件夹')
        return self._lib

    def _submit(self,name,fn): return {'task_id':self._jobs.submit(name,fn)}

    @api
    def choose_source(self):
        path=self._pick('source')
        if not path: return None
        root=Path(path).resolve()
        if not root.is_dir(): raise ValueError('来源文件夹不存在')
        if self._lib and (root.is_relative_to(self._lib.root) or self._lib.root.is_relative_to(root)):
            raise ValueError('来源和照片库须使用互不包含的文件夹')
        token=uid(); self._grants[token]=root
        return {'token':token,'name':root.name,'path':str(root)}

    @api
    def scan(self,source_token,formats='both'):
        if source_token not in self._grants: raise PathNotGranted('请通过文件夹选择窗口指定来源')
        root=self._grants[source_token]
        def work(cancel,progress):
            errors=[];groups=scan_source(root,cancel,progress,errors=errors,formats=formats)
            if cancel():return {'cancelled':True}
            if not groups and errors:return {'photos':[],'errors':errors,'cancelled':False}
            scan_id=uid(); self._scans[scan_id]={g.id:g for g in groups}
            def relative(path):
                p=Path(path).relative_to(root);return '' if p==Path('.') else p.as_posix()
            return {'scan_id':scan_id,'photos':[{**asdict(g),'relative_dir':relative(g.source_dir),'relative_dirs':sorted({relative(Path(a.path).parent) for a in g.files})} for g in groups],'errors':errors,'cancelled':False}
        return self._submit('扫描照片',work)

    @api
    def choose_library(self):
        self._check_switch()
        path=self._pick('library')
        if not path: return None
        return self._switch_library(Path(path).resolve())

    def _check_switch(self):
        if any(s.status in ('running','queued','cancelling') for s in self._jobs._tasks.values()):raise ValueError('请等待当前任务完成后切换照片库')

    def _check_library_root(self,root):
        if any(root.is_relative_to(source) or source.is_relative_to(root) for source in self._grants.values()): raise ValueError('来源和照片库须使用互不包含的文件夹')
        paths=self._settings.get('recent_libraries',[])+([self._settings['library']] if self._settings.get('library') else [])
        if any(root!=Path(p).resolve() and (root.is_relative_to(Path(p).resolve()) or Path(p).resolve().is_relative_to(root)) for p in paths):raise ValueError('照片库之间须使用互不包含的文件夹，请选择其他保存位置')

    def _switch_library(self,root):
        self._check_switch();self._check_library_root(root)
        if not self._lib or self._lib.root!=root:
            new_library=Library(root)
            if self._lib:self._lib.close()
            self._lib=new_library
        prior=self._settings.get('recent_libraries',[])
        if self._settings.get('library'):prior=[self._settings['library'],*prior]
        seen={str(root).casefold()};recent=[str(root)]
        for path in prior:
            key=str(Path(path).resolve()).casefold()
            if key not in seen:seen.add(key);recent.append(str(Path(path).resolve()))
        self._settings['library']=str(root);self._settings['recent_libraries']=recent;self._persist()
        return {'path':str(root),'recovery':self._lib.recovery}

    @api
    def choose_library_parent(self):
        self._check_switch();path=self._pick('library_parent')
        if not path:return None
        root=Path(path).resolve()
        if not root.is_dir():raise ValueError('保存位置不存在')
        token=uid();self._library_parents[token]=root
        return {'token':token,'path':str(root)}

    @api
    def create_library(self,parent_token,name):
        self._check_switch();safe_name(name)
        if parent_token not in self._library_parents:raise PathNotGranted('请先选择照片库的保存位置')
        root=inside(self._library_parents[parent_token],self._library_parents[parent_token]/name)
        self._check_library_root(root)
        # Exclusive creation prevents adopting or overwriting an existing folder.
        root.mkdir(exist_ok=False)
        return self._switch_library(root)

    @api
    def list_libraries(self):
        paths=list(dict.fromkeys(([self._settings['library']] if self._settings.get('library') else [])+self._settings.get('recent_libraries',[])))
        return [{'path':p,'name':Path(p).name,'available':(Path(p)/'.片集'/'catalog.sqlite3').is_file(),'current':bool(self._lib and self._lib.root==Path(p).resolve())} for p in paths]

    @api
    def open_library(self,path):
        root=Path(path).resolve();known=self.list_libraries()['data']
        if not any(Path(p['path']).resolve()==root for p in known):raise PathNotGranted('请通过文件夹选择窗口打开其他照片库')
        if not (root/'.片集'/'catalog.sqlite3').is_file():raise ValueError('照片库不可用，请连接磁盘或重新选择位置')
        return self._switch_library(root)

    @api
    def remove_recent_library(self,path):
        root=Path(path).resolve()
        if self._lib and self._lib.root==root:raise ValueError('当前照片库不能从最近记录移除，请先切换')
        self._settings['recent_libraries']=[p for p in self._settings.get('recent_libraries',[]) if Path(p).resolve()!=root]
        if self._settings.get('library') and Path(self._settings['library']).resolve()==root:self._settings.pop('library')
        self._persist()
        return True

    @api
    def get_settings(self):
        return {**self._settings,'library_available':bool(self._lib)}

    @api
    def choose_photoshop(self):
        path=self._pick('photoshop')
        if not path: return None
        exe=validate_executable(path); self._settings['photoshop']=str(exe); self._persist(); return str(exe)

    @api
    def save_settings(self,values):
        if set(values)-{'photoshop','thumbnail_size'}: raise PathNotGranted('照片库须通过文件夹选择窗口设置')
        if 'photoshop' in values: self._settings['photoshop']=str(validate_executable(values['photoshop'])) if values['photoshop'] else ''
        if 'thumbnail_size' in values: self._settings['thumbnail_size']=max(80,min(720,int(values['thumbnail_size'])))
        self._persist(); return self._settings

    @api
    def list_activities(self): return self._library().catalog.activities()

    @api
    def create_activity(self,name):
        self._check_switch();return self._library().create_activity(name)

    @api
    def list_people(self,activity_id): return self._library().catalog.people(activity_id)

    @api
    def list_photos(self,filters):
        lib=self._library(); photos=lib.catalog.photos(filters.get('activity_id'),trashed=bool(filters.get('trashed')))
        for p in photos: p['missing']=any(not Path(a['path']).is_file() for a in p['assets'])
        return photos

    @api
    def trash_photos(self,photo_ids):
        lib=self._library();return self._submit('移到回收站',lambda c,p:lib.trash_photos(photo_ids,c,p))

    @api
    def restore_photos(self,photo_ids):
        lib=self._library();return self._submit('恢复照片',lambda c,p:lib.restore_photos(photo_ids,c,p))

    @api
    def get_preview(self,photo_id,kind='thumb',scan_id=None):
        if kind not in ('thumb','preview','export','export-thumb'): raise ValueError('未知预览类型')
        if scan_id:
            group=self._scans.get(scan_id,{}).get(photo_id)
            if not group: raise ValueError('来源照片已失效，请重新扫描')
            read=lambda:self._cache.get(group,640 if kind in ('thumb','export-thumb') else 4096)
        else:
            lib=self._library()
            def read():
                # Keep the snapshot paths and their file handles under one read
                # lease. Journal writers wait, while other previews run in parallel.
                with lib.journal.access.read():
                    lib._ready()
                    group=lib.group(photo_id,prefer_export=kind in ('export','export-thumb'))
                    return self._cache.get(group,640 if kind in ('thumb','export-thumb') else 4096)
        result=self._previews.submit(read).result()
        if result.error: return {'url':None,'error':result.error}
        return {'url':'data:image/jpeg;base64,'+base64.b64encode(result.content).decode(),'error':None}

    @api
    def import_selected(self,scan_id,photo_ids,activity,formats):
        lib=self._library(); scanned=self._scans.get(scan_id)
        if not scanned or any(i not in scanned for i in photo_ids): raise ValueError('来源照片已失效，请重新扫描')
        groups=[scanned[i] for i in dict.fromkeys(photo_ids)]
        return self._submit('导入照片',lambda c,p:lib.import_groups(groups,activity,formats,c,p))

    @api
    def classify_activity(self,activity_id):
        lib=self._library()
        def work(cancel,progress):
            from .faces import FaceEngine,classify_activity
            return classify_activity(lib,activity_id,FaceEngine(self._model_root),cancel,progress)
        return self._submit('人物分类',work)

    @api
    def set_person(self,photo_ids,person_id):
        lib=self._library(); return self._submit('调整人物',lambda c,p:lib.set_person(photo_ids,person_id,cancel=c,progress=p))

    @api
    def create_person(self,activity_id,name):
        lib=self._library()
        with lib.lock:
            lib._ready()
            if not any(a['id']==activity_id for a in lib.catalog.activities()):raise ValueError('活动不存在')
            return lib.catalog.add_person(activity_id,name)

    @api
    def delete_people(self,person_ids):
        lib=self._library();return self._submit('删除人物分类',lambda c,p:lib.delete_people(person_ids,c,p))

    @api
    def rename_person(self,person_id,name):
        lib=self._library(); return self._submit('重命名人物',lambda c,p:lib.rename_person(person_id,name))

    @api
    def merge_people(self,source_id,target_id):
        lib=self._library(); return self._submit('合并人物',lambda c,p:lib.merge_people(source_id,target_id,cancel=c,progress=p))

    @api
    def set_edited(self,photo_ids,value):
        lib=self._library(); return self._submit('整理修图阶段',lambda c,p:lib.set_edited(photo_ids,value,cancel=c,progress=p))

    @api
    def set_finished(self,photo_ids,value):
        lib=self._library();return self._submit('标为成片' if value else '取消成片',lambda c,p:lib.set_finished(photo_ids,value,cancel=c,progress=p))

    @api
    def unlink_export(self,photo_id,asset_id):
        lib=self._library();return self._submit('解除成片关联',lambda c,p:lib.unlink_export(photo_id,asset_id))

    @api
    def choose_and_link_export(self,photo_id):
        lib=self._library(); lib.catalog.photo(photo_id); path=self._pick('export')
        if not path: return None
        return self._submit('关联成片',lambda c,p:lib.link_export(photo_id,path))

    @api
    def set_export_cover(self,photo_id,asset_id):
        lib=self._library()
        with lib.lock:
            lib._ready();lib.catalog.photo(photo_id)
            if not any(a['id']==asset_id and a['kind']=='export' for a in lib.catalog.assets(photo_id)): raise ValueError('成片不存在')
            with lib.catalog.connect() as db: db.execute('UPDATE photos SET primary_export_id=? WHERE id=?',(asset_id,photo_id))
        return True

    @api
    def open_photoshop(self,photo_id,format):
        return open_in_photoshop(self._library(),photo_id,format,self._settings.get('photoshop',''))

    @api
    def open_export_folder(self,photo_id):
        lib=self._library(); p=lib.catalog.photo(photo_id)
        asset=next((a for a in p['assets'] if a['id']==p['primary_export_id']),None)
        if not asset or not Path(asset['path']).is_file(): raise ValueError('此照片尚无可用成片')
        os.startfile(str(Path(asset['path']).parent)); return True

    @api
    def relink_missing(self,photo_id):
        lib=self._library(); photo=lib.catalog.photo(photo_id)
        root=self._pick('source')
        if not root: return None
        def work(cancel,progress):
            from .fileops import digest
            candidates={}
            for parent,dirs,files in os.walk(root,followlinks=False):
                dirs[:]=[d for d in dirs if not (Path(parent)/d).is_symlink() and not (Path(parent)/d).is_junction()]
                for name in files:
                    if cancel(): return {'cancelled':True}
                    f=Path(parent)/name
                    if f.is_file() and not f.is_symlink(): candidates.setdefault(f.suffix.lower(),[]).append(f)
            recovered=[]
            with lib.lock:
                for a in photo['assets']:
                    if Path(a['path']).is_file(): continue
                    matched=next((f for f in candidates.get(Path(a['path']).suffix.lower(),[]) if digest(f)==a['sha256']),None)
                    if matched:
                        # Copy into the old managed location, never adopt/move an external source.
                        lib.journal.execute('relink',[{'src':str(matched),'dst':a['path'],'move':False,'sha256':a['sha256']}],[])
                        recovered.append(a['id'])
            remaining=[a for a in photo['assets'] if not Path(a['path']).is_file()]
            return {'recovered':recovered,'errors':[{'id':a['id'],'message':'仍未找到：'+Path(a['path']).name} for a in remaining]}
        return self._submit('定位缺失文件',work)

    @api
    def undo_operation(self,operation_id):
        lib=self._library(); return self._submit('撤销归档',lambda c,p:lib.undo_operation(operation_id))

    @api
    def recover_pending(self):
        lib=self._library(); return self._submit('恢复文件操作',lambda c,p:lib.recover_pending())

    @api
    def get_task(self,task_id): return self._jobs.get_task(task_id)

    @api
    def cancel_task(self,task_id): return self._jobs.cancel_task(task_id)

    def _close(self):
        self._jobs.close(); self._previews.shutdown(wait=True)
        if self._lib:self._lib.close()
