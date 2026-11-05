"""Explicit, resumable purge of files receipted by this macOS library only."""
import json
import os
from pathlib import Path
from .domain import uid
from .fileops import FORMAT as JOURNAL_FORMAT
from .safeos import digest, identity, matches_identity

FORMAT='lumix-macos-purge-1'

def pending(catalog,photo_id):
    return catalog.rows('SELECT * FROM purges WHERE photo_id=?',(photo_id,))

def trash_receipt(library,photo_id):
    for row in library.catalog.rows("SELECT payload FROM operations WHERE kind='trash' AND phase='committed' AND error IS NULL ORDER BY rowid DESC"):
        data=json.loads(row['payload'])
        if data.get('photo_id')==photo_id:
            if data.get('format')!=JOURNAL_FORMAT or data.get('library_id')!=library.marker['library_id']:
                raise ValueError('不是本 macOS 库的回收站记录')
            return {str(Path(c['dst'])):c for c in data['changes'] if c['move']}
    return {}

def purge(library,photo_ids,cancel=lambda:False,progress=lambda n,t,m:None):
    report={'deleted':[],'errors':[],'cancelled':False}
    with library.lock,library.journal.access:
        library._guard()
        if library.catalog.rows("SELECT id FROM operations WHERE phase!='committed'"):
            raise ValueError('请先处理未完成的文件操作')
        catalog=library.catalog;access=library.journal.root;ids=list(dict.fromkeys(photo_ids))
        for n,ident in enumerate(ids):
            if cancel():report['cancelled']=True;break
            try:
                if not catalog.rows('SELECT photo_id FROM trashed_photos WHERE photo_id=?',(ident,)):
                    raise ValueError('只能永久删除本机照片库回收站中的照片')
                trash_root=access.inside(catalog.meta/'回收站'/ident)
                assets=catalog.assets(ident)+catalog.rows('SELECT * FROM detached_exports WHERE photo_id=?',(ident,))
                records=pending(catalog,ident)
                if records:
                    plan=json.loads(records[0]['payload'])
                    if not isinstance(plan,dict) or plan.get('format')!=FORMAT or plan.get('library_id')!=library.marker['library_id']:
                        raise ValueError('永久删除日志来源不明，保留现场')
                else:
                    files=[];receipts=trash_receipt(library,ident)
                    for asset in assets:
                        path=access.inside(asset['path'])
                        # An originally missing asset may later reappear at its
                        # normal location. It never authorizes deleting that file.
                        if not path.is_relative_to(trash_root) or not os.path.lexists(path):continue
                        receipt=receipts.get(str(path));owned=identity(path);sha=digest(path)
                        if not receipt or not matches_identity(path,receipt.get('identity')) or sha!=receipt['sha256'] or sha!=asset['sha256']:
                            raise ValueError('回收站文件与移入时的身份或内容不一致，已保留：'+str(path))
                        files.append({'path':str(path),'identity':owned,'sha256':sha,
                                      'quarantine':str(catalog.meta/'staging'/('purge-'+uid()))})
                    plan={'format':FORMAT,'library_id':library.marker['library_id'],'files':files}
                    # Persist both ownership and the private quarantine name
                    # before the first move/unlink, including for crash resume.
                    with catalog.connect() as db:
                        db.execute('INSERT INTO purges VALUES(?,?,NULL)',(ident,json.dumps(plan,ensure_ascii=False)))
                for file in plan['files']:
                    path=access.inside(file['path']);quarantine=access.inside(file['quarantine'])
                    if not path.is_relative_to(trash_root) or quarantine.parent!=catalog.meta/'staging' or not quarantine.name.startswith('purge-'):
                        raise ValueError('永久删除路径不符合本机日志格式，保留现场')
                    if os.path.lexists(path):
                        if not matches_identity(path,file['identity']) or digest(path)!=file['sha256']:
                            raise ValueError('回收站文件被替换或修改，已保留：'+str(path))
                        if os.path.lexists(quarantine):raise ValueError('原文件和隔离文件同时存在，保留现场')
                        access.rename(path,quarantine,file['identity'])
                    if os.path.lexists(quarantine):access.unlink_verified(quarantine,file['identity'],file['sha256'])
                with catalog.connect() as db:
                    for table in ('assets','detached_exports','import_members','trashed_photos','purges'):
                        db.execute('DELETE FROM '+table+' WHERE photo_id=?',(ident,))
                    db.execute('DELETE FROM photos WHERE id=?',(ident,))
                report['deleted'].append(ident)
                from .cleanup import prune_empty
                cleanup=prune_empty(library.root,[Path(a['path']).parent for a in assets]+[trash_root])
                report['errors'].extend({'id':ident,'message':'照片永久删除已完成；空目录清理需检查：'+issue['path']+'；'+issue['message']}
                                        for issue in cleanup['errors'])
            except Exception as error:
                message=str(error)
                with catalog.connect() as db:db.execute('UPDATE purges SET error=? WHERE photo_id=?',(message,ident))
                report['errors'].append({'id':ident,'message':message})
            finally:progress(n+1,len(ids),'永久删除回收站照片')
    return report
