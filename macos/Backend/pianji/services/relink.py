"""Find missing assets by stored digest; copy into the managed path only."""
import os
from pathlib import Path
from ..safeos import RootAccess, digest
from ..paths import inside


def relink_missing(library, photo_id, root, cancel=lambda: False, progress=lambda n,t,m: None):
    with library.lock:
        library._ready()
        photo=library.catalog.photo(photo_id)
        report={'relinked':[],'errors':[],'cancelled':False}
        source=RootAccess(root)
        try:
            candidates={}
            for parent,dirs,files in os.walk(source.root,followlinks=False):
                if cancel():report['cancelled']=True;return report
                dirs[:]=[d for d in dirs if not (Path(parent)/d).is_symlink() and d!='.片集']
                for name in files:
                    file=Path(parent)/name
                    if not file.is_symlink():candidates.setdefault(file.suffix.lower(),[]).append(file)
            missing=[]
            for asset in photo['assets']:
                path=inside(library.root,asset['path'])
                if not os.path.lexists(path):missing.append(asset)
            checksums={}
            for n,asset in enumerate(missing):
                if cancel():report['cancelled']=True;break
                try:
                    matched=None
                    for file in candidates.get(Path(asset['path']).suffix.lower(),[]):
                        if cancel():report['cancelled']=True;return report
                        source.verify()
                        if file not in checksums:
                            try:checksums[file]=digest(file)
                            except (OSError,ValueError):checksums[file]=None
                        if checksums[file]==asset['sha256']:matched=file;break
                    if matched is None:raise ValueError('未找到内容匹配的文件：'+Path(asset['path']).name)
                    library.journal.execute('relink',[{'src':str(matched),'dst':asset['path'],'sha256':asset['sha256'],'move':False}],[])
                    report['relinked'].append(asset['id'])
                except Exception as error:report['errors'].append({'id':asset['id'],'message':str(error)})
                progress(n+1,len(missing),'找回缺失文件')
            return report
        finally:source.close()
