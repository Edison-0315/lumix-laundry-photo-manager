"""Private newline JSON protocol over stdio. No HTTP server or dynamic method dispatch."""
import contextlib
import json
from pathlib import Path
import platform
import signal
import sys
import threading
sys.path.insert(0,str(Path(__file__).resolve().parent))
from managed import ManagedLibrary
from pianji.domain import PhotoGroup, FileAsset
from pianji.safeos import RootAccess, absolute
from pianji.paths import safe_name
from source_protection import reject_source_overlap

_output=sys.stdout
_cancelled=threading.Event()
signal.signal(signal.SIGINT,lambda *_:_cancelled.set())

def send(value):
    _output.write(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n');_output.flush()

class Session:
    def __init__(self):self.library=None;self.recycle=None;self.face_engine=None;self.protected_sources=set()
    def close(self):
        self.recycle=None
        if self.library:self.library.close();self.library=None
    def state(self):
        if self.library is None:return {'root':None,'writable':False,'pending':[]}
        self.library._guard()
        pending=self.library.catalog.rows("SELECT id,kind,phase,error FROM operations WHERE phase!='committed'")
        pending+=self.library.catalog.rows("SELECT photo_id AS id,'purge' AS kind,'needs_attention' AS phase,error FROM purges")
        count=self.library.catalog.rows('SELECT COUNT(*) AS count FROM photos p WHERE NOT EXISTS(SELECT 1 FROM trashed_photos t WHERE t.photo_id=p.id)')[0]['count']
        return {'root':str(self.library.root),'library_id':self.library.marker['library_id'],'writable':not pending,'pending':pending,
                'activities':self.library.catalog.activities(),'photo_count':count}
    def dispatch(self,method,params,progress):
        self.protected_sources.update(str(absolute(p)) for p in params.get('protected_roots', []))
        if method=='import': self.protected_sources.add(str(absolute(params['source_root'])))
        if method in ('create','open'):
            root=absolute(params['root'])
            if method=='open': reject_source_overlap(root, self.protected_sources)
            if method=='open' and self.library is not None and root==self.library.root:return self.state()
            candidate=ManagedLibrary.create(root,self.protected_sources) if method=='create' else ManagedLibrary.open(root)
            self.close();self.library=candidate
            return self.state()
        if method=='close':self.close();return self.state()
        if method=='state':return self.state()
        if self.library is None:raise ValueError('请先新建或打开本机照片库')
        reject_source_overlap(self.library.root, self.protected_sources)
        self.library._guard()
        if method=='recover':return self.library.recover_pending()
        if method=='purge_trash':return self.library.purge_trash(params['ids'],cancel=_cancelled.is_set,progress=progress)
        self.library._ready()
        if method=='inspect_recycle':
            from pianji.library_recycle import LibraryRecycleInspector
            self.recycle=LibraryRecycleInspector(self.library)
            return self.recycle.inspect(params.get('protected_roots',[]),params.get('blocked_paths',[]),_cancelled.is_set)
        if method=='validate_recycle':
            if self.recycle is None:raise ValueError('请先预览要回收的照片库')
            return self.recycle.validate(params['token'],params['name'],params.get('protected_roots',[]),params.get('blocked_paths',[]),_cancelled.is_set)
        if method=='create_activity':return self.library.create_activity(params['name'])
        if method=='create_person':
            activity=params['activity_id'];name=params['name']
            if not any(a['id']==activity for a in self.library.catalog.activities()):raise ValueError('活动不存在')
            if any(p['name'].casefold()==name.casefold() for p in self.library.catalog.people(activity)):raise ValueError('同名人物已存在')
            return self.library.catalog.add_person(activity,name)
        if method=='set_person':return self.library.set_person(params['ids'],params['person_id'],cancel=_cancelled.is_set,progress=progress)
        if method=='set_edited':return self.library.set_edited(params['ids'],bool(params['value']),cancel=_cancelled.is_set,progress=progress)
        if method=='rename_person':return self.library.rename_person(params['person_id'],params['name'])
        if method=='merge_people':return self.library.merge_people(params['source_id'],params['target_id'],cancel=_cancelled.is_set,progress=progress)
        if method=='set_finished':return self.library.set_finished(params['ids'],bool(params['value']),cancel=_cancelled.is_set,progress=progress)
        if method=='link_export':return self.library.link_export(params['photo_id'],params['path'])
        if method=='unlink_export':return self.library.unlink_export(params['photo_id'],params['asset_id'])
        if method=='set_export_cover':return self.library.set_export_cover(params['photo_id'],params['asset_id'])
        if method=='undo_operation':return self.library.undo_operation(params['operation_id'])
        if method=='relink_missing':return self.library.relink_missing(params['photo_id'],params['root'],cancel=_cancelled.is_set,progress=progress)
        if method=='record_opened':return self.library.record_opened(params['photo_id'])
        if method=='trash_photos':return self.library.trash_photos(params['ids'],cancel=_cancelled.is_set,progress=progress)
        if method=='restore_photos':return self.library.restore_photos(params['ids'],cancel=_cancelled.is_set,progress=progress)
        if method=='delete_people':return self.library.delete_people(params['ids'],cancel=_cancelled.is_set,progress=progress)
        if method=='delete_activity':return self.library.delete_activity(params['activity_id'],cancel=_cancelled.is_set,progress=progress)
        if method=='classify_activity':
            activity=params['activity_id']
            if not any(a['id']==activity for a in self.library.catalog.activities()):raise ValueError('活动不存在')
            from pianji.faces import FaceEngine,classify_activity
            if self.face_engine is None:self.face_engine=FaceEngine(Path(__file__).resolve().parent.parent/'Models')
            return classify_activity(self.library,activity,self.face_engine,cancel=_cancelled.is_set,progress=progress)
        if method=='import':
            source=RootAccess(params['source_root'])
            try:
                activity=safe_name(params['activity'])
                matches=[row for row in self.library.catalog.rows('SELECT * FROM activities') if row['name'].casefold()==activity.casefold()]
                if len(matches)>1:raise ValueError('活动名称存在歧义，请先检查照片库')
                if matches:activity=matches[0]['name']
                if not any(row['name']==activity for row in self.library.catalog.activities()):self.library.create_activity(activity)
                groups=[]
                for group in params['groups']:
                    files=[]
                    for item in group['files']:
                        if item['kind'] not in ('jpeg','raw','xmp'):raise ValueError('未知来源格式')
                        path=absolute(item['path'])
                        if not path.is_relative_to(source.root):raise ValueError('来源路径超出所选文件夹')
                        files.append(FileAsset(item.get('id',''),group['id'],item['kind'],str(path)))
                    groups.append(PhotoGroup(group['id'],str(source.root),group['stem'],group.get('captured_at'),files))
                return self.library.import_groups(groups,activity,params.get('formats','both'),cancel=_cancelled.is_set,progress=progress)
            finally:source.close()
        raise ValueError('未知后台方法：'+str(method))

def main():
    session=Session()
    send({'type':'ready','protocol':1,'architecture':platform.machine(),'python':platform.python_version()})
    try:
        for line in sys.stdin:
            request_id=None
            try:
                packet=json.loads(line);request_id=packet['id']
                if packet.get('cancelled'):_cancelled.set()
                def progress(done,total,message):send({'type':'progress','id':request_id,'done':done,'total':total,'message':message})
                with contextlib.redirect_stdout(sys.stderr):result=session.dispatch(packet['method'],packet.get('params',{}),progress)
                send({'type':'result','id':request_id,'ok':True,'value':result})
            except Exception as error:
                send({'type':'result','id':request_id,'ok':False,'error':str(error)})
            finally:_cancelled.clear()
    except BrokenPipeError:pass
    finally:session.close()

if __name__=='__main__':main()
