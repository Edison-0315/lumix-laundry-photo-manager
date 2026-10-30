"""Explicit, resumable permanent deletion of owned recycle-bin files only."""
from pathlib import Path
import json
from .fileops import digest,identity
from .paths import inside

def pending(catalog,photo_id):
    return catalog.rows('SELECT * FROM purges WHERE photo_id=?',(photo_id,))

def trash_receipt(catalog,photo_id):
    # Existing 0.3/0.4 libraries already have these committed move receipts.
    # File identity survives an NTFS rename and distinguishes replacements.
    for row in catalog.rows("SELECT payload FROM operations WHERE kind='trash' AND phase='committed' AND error IS NULL ORDER BY rowid DESC"):
        data=json.loads(row['payload'])
        if data.get('photo_id')==photo_id:
            return {str(Path(c['dst']).resolve()).casefold():c for c in data['changes'] if c['move']}
    return {}

def purge(library,photo_ids,cancel=lambda:False,progress=lambda n,t,m:None):
    result={'deleted':[],'errors':[],'cancelled':False}
    with library.lock,library.journal.access:
        library._ready();catalog=library.catalog;ids=list(dict.fromkeys(photo_ids))
        for index,ident in enumerate(ids,1):
            if cancel():result['cancelled']=True;break
            try:
                if not catalog.rows('SELECT photo_id FROM trashed_photos WHERE photo_id=?',(ident,)):raise ValueError('只能永久删除当前照片库回收站中的照片')
                trash_root=inside(library.root,catalog.meta/'回收站'/ident)
                records=pending(catalog,ident)
                if records:files=json.loads(records[0]['payload'])
                else:
                    files=[];receipts=trash_receipt(catalog,ident)
                    assets=catalog.assets(ident)+catalog.rows('SELECT * FROM detached_exports WHERE photo_id=?',(ident,))
                    for asset in assets:
                        path=inside(library.root,asset['path'])
                        # Missing originals retain old normal paths. They must
                        # never authorize deleting anything appearing there later.
                        if not path.is_relative_to(trash_root):continue
                        if path.is_file():
                            receipt=receipts.get(str(path).casefold());sha=digest(path);owned=identity(path)
                            if not receipt or owned!=receipt.get('identity') or sha!=receipt['sha256'] or sha!=asset['sha256']:
                                raise ValueError('回收站文件与移入时的记录不一致，已保留该文件，请核对：'+str(path))
                            files.append({'path':str(path),'identity':owned,'sha256':sha})
                    # Persist before the first irreversible action. This also
                    # blocks restore after a partial delete or process crash.
                    with catalog.connect() as db:db.execute('INSERT INTO purges VALUES(?,?,NULL)',(ident,json.dumps(files,ensure_ascii=False)))
                for file in files:
                    path=inside(trash_root,file['path'])
                    if not path.exists():continue
                    if identity(path)!=file['identity'] or digest(path)!=file['sha256']:
                        raise ValueError('回收站文件已被替换或修改，已保留该文件，请核对后处理：'+str(path))
                    path.unlink()
                with catalog.connect() as db:
                    for table in ('assets','detached_exports','import_members','trashed_photos','purges'):
                        db.execute(f'DELETE FROM {table} WHERE photo_id=?',(ident,))
                    db.execute('DELETE FROM photos WHERE id=?',(ident,))
                result['deleted'].append(ident)
            except Exception as e:
                message=str(e)
                with catalog.connect() as db:db.execute('UPDATE purges SET error=? WHERE photo_id=?',(message,ident))
                result['errors'].append({'id':ident,'message':message})
            finally:progress(index,len(ids),'永久删除回收站照片')
    return result
