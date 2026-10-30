from pathlib import Path
from datetime import datetime
import hashlib
import os
from PIL import Image
from .domain import FileAsset,PhotoGroup

KINDS={'.jpg':'jpeg','.jpeg':'jpeg','.rw2':'raw','.dng':'raw','.cr2':'raw','.cr3':'raw','.nef':'raw','.arw':'raw','.raf':'raw','.orf':'raw','.xmp':'xmp'}

def scan_source(root,cancel=lambda:False,progress=lambda n,t,m:None):
    root=Path(root).resolve()
    if not root.is_dir(): raise ValueError('来源文件夹不存在')
    paired={}
    progress(0,0,'正在查找照片')
    for parent,dirs,files in os.walk(root,followlinks=False):
        if cancel(): return []
        dirs[:]=[d for d in dirs if not (Path(parent)/d).is_symlink() and not (Path(parent)/d).is_junction()]
        for name in sorted(files):
            if cancel(): return []
            p=Path(parent)/name
            if p.is_symlink() or not p.resolve().is_relative_to(root): continue
            kind=KINDS.get(p.suffix.lower())
            if not kind: continue
            # Camera sidecars can be A.xmp or A.RW2.xmp.
            stem=p.stem
            if kind=='xmp' and Path(stem).suffix.lower() in KINDS: stem=Path(stem).stem
            key=(str(p.parent).casefold(),stem.casefold())
            ident=hashlib.sha256(('\0'.join(key)).encode()).hexdigest()[:32]
            row=paired.setdefault(key,PhotoGroup(ident,str(p.parent),stem,None,[]))
            row.files.append(FileAsset(hashlib.sha256(str(p).encode()).hexdigest()[:32],ident,kind,str(p)))
    # Only pair explicit sibling format folders. A basename alone is unsafe
    # across separate shoots; multiple candidates stay separate for review.
    siblings={}
    for g in paired.values():
        parent=Path(g.source_dir)
        kinds={a.kind for a in g.files if a.kind!='xmp'}
        expected='jpeg' if parent.name.casefold() in ('jpeg','jpg') else 'raw' if parent.name.casefold() in ('raw','rw2') else None
        if expected and kinds=={expected}:
            siblings.setdefault((str(parent.parent).casefold(),g.stem.casefold()),[]).append(g)
    for candidates in siblings.values():
        if len(candidates)!=2:continue
        if {a.kind for g in candidates for a in g.files if a.kind!='xmp'}!={'jpeg','raw'}:continue
        if any(sum(a.kind!='xmp' for a in g.files)!=1 for g in candidates):continue
        first,second=candidates
        first.files.extend(second.files)
        for a in first.files:a.photo_id=first.id
        paired={key:g for key,g in paired.items() if g is not second}
    return _groups(paired,progress,cancel)

def _groups(paired,progress,cancel=lambda:False):
    groups=[g for g in paired.values() if any(a.kind!='xmp' for a in g.files)]
    for n,g in enumerate(groups,1):
        if cancel(): return groups[:n-1]
        jpg=next((a for a in g.files if a.kind=='jpeg'),None)
        if jpg:
            try:
                with Image.open(jpg.path) as im:
                    exif=im.getexif(); original=exif.get_ifd(34665).get(36867) if 34665 in exif else exif.get(36867)
                    if original:
                        try: g.captured_at=datetime.strptime(str(original),'%Y:%m:%d %H:%M:%S').isoformat()
                        except ValueError: pass
                    im.verify()
            except Exception: g.error='JPEG无法预览，仍可导入原文件'
        else:
            try:
                import exifread
                with open(g.files[0].path,'rb') as f: tags=exifread.process_file(f,details=False,stop_tag='DateTimeOriginal')
                original=tags.get('EXIF DateTimeOriginal')
                if original: g.captured_at=datetime.strptime(str(original),'%Y:%m:%d %H:%M:%S').isoformat()
            except Exception: pass
        progress(n,len(groups),'读取照片信息')
    return groups
