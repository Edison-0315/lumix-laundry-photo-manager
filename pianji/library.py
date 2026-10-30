from pathlib import Path
from dataclasses import asdict
import hashlib
import json
import threading
from .catalog import Catalog
from .domain import uid,PhotoGroup,FileAsset
from .paths import safe_name,inside
from .fileops import FileJournal,digest
from .locking import LibraryLock

class Library:
    def __init__(self,root):
        self._root_lock=LibraryLock(Path(root).resolve());self._closed=False
        self.catalog=Catalog(root); self.root=self.catalog.root
        self.journal=FileJournal(self.catalog); self.lock=threading.RLock()
        self.recovery=self.recover_pending()

    def close(self):
        with self.lock:
            if not self._closed:self._closed=True;self._root_lock.close()

    def recover_pending(self): return self.journal.recover_pending()

    def _ready(self):
        if self._closed: raise ValueError('照片库已关闭')
        if self.catalog.rows("SELECT id FROM operations WHERE phase!='committed'"):
            raise ValueError('有文件操作尚待恢复，请先关闭占用程序并重试恢复')

    def _folder(self,activity_id,person_id,edited,kind,person_folder=None):
        activity=self.catalog.rows('SELECT * FROM activities WHERE id=?',(activity_id,))[0]
        person=self.catalog.person(person_id)
        if person['activity_id']!=activity_id: raise ValueError('不能将照片放入其他活动的人物')
        base=self.root/activity['folder']/(person_folder or person['folder'])
        return base/'成片' if kind=='export' else base/('已修原片' if edited else '选出原片')/('JPEG' if kind=='jpeg' else 'RAW')

    def _destinations(self,assets,activity_id,person_id,edited,stem,person_folder=None,reserved=None):
        # Reserve one suffix for the entire group, across every format/version.
        safe_name(stem)
        old={str(Path(a['path']).resolve()) for a in assets}
        for n in range(10000):
            candidate=stem if n==0 else f'{stem}_{n+1}'
            paths=[]; seen=set()
            for a in assets:
                suffix=Path(a['path']).suffix
                filename=(candidate+('_'+a['id'][:8] if a['kind']=='export' else '')+suffix)
                dst=inside(self.root,self._folder(activity_id,person_id,edited,a['kind'],person_folder)/filename)
                if str(dst) in seen: filename=candidate+'_'+a['id'][:8]+suffix; dst=dst.with_name(filename)
                seen.add(str(dst)); paths.append(str(dst))
            if all((not Path(p).exists() or p in old) and p.casefold() not in (reserved or set()) for p in paths): return paths
        raise ValueError('同名照片过多，请更换名称')

    def import_groups(self,groups,activity,formats='both',cancel=lambda:False,progress=lambda n,t,m:None):
        with self.lock:
            self._ready()
            if formats not in ('both','jpeg','raw'): raise ValueError('未知照片格式')
            act=self.catalog.activity(activity)
            unclassified=next(p for p in self.catalog.people(act['id']) if p['role']=='unclassified')
            report={'imported':[],'updated':[],'skipped':0,'errors':[],'cancelled':False,'activity_id':act['id']}
            for n,g in enumerate(groups):
                if cancel(): report['cancelled']=True; break
                try:
                    safe_name(g.stem)
                    files=[a for a in g.files if a.kind in (('jpeg','raw','xmp') if formats=='both' else ('raw','xmp') if formats=='raw' else ('jpeg',))]
                    if not any(a.kind in ('jpeg','raw') for a in files):
                        report['skipped']+=1; continue
                    ident=uid(); assets=[]
                    for a in files:
                        source=Path(a.path).resolve()
                        if source.is_relative_to(self.root): raise ValueError('来源位于照片库内，请选择SD卡或库外文件夹')
                        assets.append({'id':uid(),'photo_id':ident,'kind':a.kind,'path':str(source),'sha256':digest(source)})
                    sig=hashlib.sha256(repr(sorted((a['kind'],a['sha256']) for a in assets)).encode()).hexdigest()
                    existing=self._matching_photo(act['id'],assets)
                    if existing:
                        if self._supplement(existing,assets):report['updated'].append(existing['id'])
                        else:report['skipped']+=1
                        continue
                    if self.catalog.rows('SELECT id FROM photos WHERE activity_id=? AND signature=?',(act['id'],sig)):
                        report['skipped']+=1; continue
                    destinations=self._destinations(assets,act['id'],unclassified['id'],False,g.stem)
                    changes=[{'src':a['path'],'dst':d,'sha256':a['sha256'],'move':False} for a,d in zip(assets,destinations)]
                    sql=[('INSERT INTO photos(id,activity_id,person_id,stem,captured_at,signature) VALUES(?,?,?,?,?,?)',(ident,act['id'],unclassified['id'],g.stem,g.captured_at,sig))]
                    sql += [('INSERT INTO assets VALUES(?,?,?,?,?)',(a['id'],ident,a['kind'],d,a['sha256'])) for a,d in zip(assets,destinations)]
                    sql += self._import_member_sql(act['id'],ident,assets)
                    self.journal.execute('import',changes,sql,{'photo_id':ident})
                    report['imported'].append(ident)
                except Exception as e: report['errors'].append({'name':g.stem,'message':str(e)})
                finally: progress(n+1,len(groups),'复制并校验照片')
            return report

    @staticmethod
    def _import_member_sql(activity_id,photo_id,assets):
        return [('INSERT OR IGNORE INTO import_members VALUES(?,?,?,?)',(activity_id,a['kind'],a['sha256'],photo_id)) for a in assets if a['kind'] in ('jpeg','raw')]

    def _matching_photo(self,activity_id,assets):
        candidates=set()
        for a in assets:
            if a['kind'] in ('jpeg','raw'):
                candidates.update(r['photo_id'] for r in self.catalog.rows('SELECT photo_id FROM import_members WHERE activity_id=? AND kind=? AND sha256=?',(activity_id,a['kind'],a['sha256'])))
        if len(candidates)>1:raise ValueError('相同内容对应多个已有照片，请先核对照片库，未自动合并')
        if not candidates:return None
        ident=next(iter(candidates))
        for a in assets:
            if a['kind'] not in ('jpeg','raw'):continue
            prior=self.catalog.rows('SELECT sha256 FROM import_members WHERE photo_id=? AND kind=?',(ident,a['kind']))
            if prior and a['sha256'] not in {r['sha256'] for r in prior}:return None
        return self.catalog.photo(ident)

    def _supplement(self,photo,incoming):
        originals=self._fresh_assets(photo);kinds={a['kind'] for a in originals}
        extra=[{**a,'id':uid(),'photo_id':photo['id'],'_new':True,'_copy':True} for a in incoming if a['kind'] not in kinds]
        if not extra:return False
        all_assets=originals+extra
        # Existing group metadata and even locally edited JPEG bytes survive.
        destinations=self._destinations(all_assets,photo['activity_id'],photo['person_id'],photo['edited'],photo['stem'])
        changes=[];sql=[]
        for a,d in zip(all_assets,destinations):
            if str(Path(a['path']).resolve())!=d:
                changes.append({'src':a['path'],'dst':d,'sha256':a['sha256'],'move':not bool(a.get('_copy'))})
            sql.append(self._asset_sql(a,d))
        sql+=self._import_member_sql(photo['activity_id'],photo['id'],incoming)
        self.journal.execute('supplement',changes,sql,{'photo_id':photo['id']})
        return True

    def _move(self,photo,person_id=None,edited=None,manual=None,person_folder=None,extra_sql=None):
        person_id=person_id or photo['person_id']; edited=bool(photo['edited']) if edited is None else bool(edited)
        assets=self._fresh_assets(photo); destinations=self._destinations(assets,photo['activity_id'],person_id,edited,photo['stem'],person_folder)
        changes=[]; sql=[]
        for a,d in zip(assets,destinations):
            if str(Path(a['path']).resolve())!=d:
                changes.append({'src':a['path'],'dst':d,'sha256':a['sha256'],'move':True})
            sql.append(self._asset_sql(a,d))
        manual=photo['manual_person'] if manual is None else manual
        sql.append(('UPDATE photos SET person_id=?,edited=?,manual_person=? WHERE id=?',(person_id,int(edited),int(manual),photo['id'])))
        sql+=extra_sql or []
        return self.journal.execute('move',changes,sql,{'photo_id':photo['id'],'before':{k:photo[k] for k in ('person_id','edited','manual_person')},'after':{'person_id':person_id,'edited':int(edited),'manual_person':int(manual)}})

    def _fresh_assets(self,photo):
        assets=[dict(a) for a in photo['assets']]
        known={str(Path(a['path']).resolve()).casefold() for a in assets}
        for raw in [a for a in assets if a['kind']=='raw']:
            path=Path(raw['path'])
            for sidecar in (path.with_suffix('.xmp'),path.with_suffix('.XMP'),Path(str(path)+'.xmp')):
                resolved=str(sidecar.resolve())
                if sidecar.is_file() and resolved.casefold() not in known:
                    inside(self.root,sidecar)
                    if self.catalog.rows('SELECT id FROM assets WHERE path=?',(resolved,)): continue
                    assets.append({'id':uid(),'photo_id':photo['id'],'kind':'xmp','path':resolved,'sha256':'','_new':True});known.add(resolved.casefold())
        for a in assets:
            inside(self.root,a['path']);a['sha256']=digest(a['path'])
        return assets

    @staticmethod
    def _asset_sql(asset,destination):
        if asset.get('_new'): return ('INSERT INTO assets VALUES(?,?,?,?,?)',(asset['id'],asset['photo_id'],asset['kind'],destination,asset['sha256']))
        return ('UPDATE assets SET path=?,sha256=? WHERE id=?',(destination,asset['sha256'],asset['id']))

    def _batch(self,ids,fn,cancel=lambda:False,progress=lambda n,t,m:None):
        with self.lock:
            self._ready(); result={'operations':[],'errors':[],'cancelled':False}
            unique=list(dict.fromkeys(ids))
            for n,ident in enumerate(unique):
                if cancel():result['cancelled']=True;break
                try: result['operations'].append(fn(self.catalog.photo(ident)))
                except Exception as e: result['errors'].append({'id':ident,'message':str(e)})
                finally:progress(n+1,len(unique),'整理照片文件')
            return result

    def set_person(self,ids,person_id,manual=True,cancel=lambda:False,progress=lambda n,t,m:None):
        self.catalog.person(person_id)
        return self._batch(ids,lambda p:self._move(p,person_id=person_id,manual=manual),cancel,progress)

    def set_edited(self,ids,value,cancel=lambda:False,progress=lambda n,t,m:None): return self._batch(ids,lambda p:self._move(p,edited=value),cancel,progress)

    def link_export(self,photo_id,file):
        with self.lock:
            self._ready(); p=self.catalog.photo(photo_id); source=Path(file).resolve()
            if source.suffix.lower() not in ('.jpg','.jpeg','.png','.tif','.tiff','.webp'): raise ValueError('请选择导出的图片文件')
            from PIL import Image
            with Image.open(source) as im: im.verify()
            ident=uid(); sha=digest(source)
            asset={'id':ident,'photo_id':photo_id,'kind':'export','path':str(source),'sha256':sha}
            dst=self._destinations([asset],p['activity_id'],p['person_id'],True,p['stem'])[0]
            originals=self._fresh_assets(p)
            destinations=self._destinations(originals,p['activity_id'],p['person_id'],True,p['stem'])
            changes=[]; sql=[]
            for a,d in zip(originals,destinations):
                if str(Path(a['path']).resolve())!=d:
                    changes.append({'src':a['path'],'dst':d,'sha256':a['sha256'],'move':True})
                sql.append(self._asset_sql(a,d))
            changes.append({'src':str(source),'dst':dst,'sha256':sha,'move':False})
            sql += [('INSERT INTO assets VALUES(?,?,?,?,?)',(ident,photo_id,'export',dst,sha)),('UPDATE photos SET edited=1,primary_export_id=? WHERE id=?',(ident,photo_id))]
            return self.journal.execute('export',changes,sql,{'photo_id':photo_id,'export_id':ident})

    def undo_operation(self,opid):
        with self.lock:
            self._ready(); op=self.catalog.operation(opid)
            if op['kind']!='move' or op['phase']!='committed' or op['error']: raise ValueError('此操作不能撤销')
            data=op['payload']; p=self.catalog.photo(data['photo_id'])
            if any(p[k]!=v for k,v in data['after'].items()): raise ValueError('照片后来已变更，请手动调整，避免覆盖新状态')
            return self._move(p,**{'person_id':data['before']['person_id'],'edited':data['before']['edited'],'manual':data['before']['manual_person']})

    def rename_person(self,person_id,name):
        with self.lock:
            self._ready(); safe_name(name); person=self.catalog.person(person_id)
            if person['role']: raise ValueError('合照和待分类名称固定')
            if any(p['name'].casefold()==name.casefold() and p['id']!=person_id for p in self.catalog.people(person['activity_id'])): raise ValueError('同名人物已存在，请使用合并')
            # One journal for the entire rename, so no mixed-name partial result.
            changes=[]; sql=[];reserved=set()
            for p in self.catalog.photos(person['activity_id']):
                if p['person_id']!=person_id: continue
                originals=self._fresh_assets(p)
                destinations=self._destinations(originals,p['activity_id'],person_id,p['edited'],p['stem'],name,reserved)
                reserved.update(d.casefold() for d in destinations)
                for a,d in zip(originals,destinations):
                    if str(Path(a['path']).resolve())!=d:
                        changes.append({'src':a['path'],'dst':d,'sha256':a['sha256'],'move':True})
                    sql.append(self._asset_sql(a,d))
            sql.append(('UPDATE people SET name=?,folder=? WHERE id=?',(name,name,person_id)))
            return self.journal.execute('rename',changes,sql)

    def merge_people(self,source_id,target_id,cancel=lambda:False,progress=lambda n,t,m:None):
        with self.lock:
            self._ready(); src=self.catalog.person(source_id); target=self.catalog.person(target_id)
            if source_id==target_id or src['activity_id']!=target['activity_id'] or src['role']: raise ValueError('请选择同活动内不同的普通人物')
            ids=[p['id'] for p in self.catalog.photos(src['activity_id']) if p['person_id']==source_id]
            result=self.set_person(ids,target_id,cancel=cancel,progress=progress)
            if not result['errors'] and not result['cancelled']:
                with self.catalog.connect() as db: db.execute('DELETE FROM people WHERE id=?',(source_id,))
            return result

    def group(self,photo_id,prefer_export=False):
        p=self.catalog.photo(photo_id); assets=p['assets']
        if prefer_export and p['primary_export_id']:
            assets=[a for a in assets if a['id']==p['primary_export_id']]
        else: assets=[a for a in assets if a['kind']!='export']
        return PhotoGroup(p['id'],'',p['stem'],p['captured_at'],[FileAsset(**a) for a in assets])
