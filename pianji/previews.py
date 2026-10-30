from pathlib import Path
from io import BytesIO
import hashlib
import threading
import weakref
import os
from PIL import Image,ImageOps
from .domain import PreviewResult

def _image_preview(im,size=None):
    if size:
        im.draft('RGB',(size,size))
        im.thumbnail((size,size),Image.Resampling.LANCZOS,reducing_gap=3.0)
    return ImageOps.exif_transpose(im).convert('RGB')

def decode(group,size=None):
    errors=[]
    for asset in sorted(group.files,key=lambda a: a.kind!='jpeg'):
        try:
            if asset.kind=='jpeg' or asset.kind=='export':
                with Image.open(asset.path) as im: return _image_preview(im,size)
            if asset.kind=='raw':
                import rawpy
                with open(asset.path,'rb') as source,rawpy.imread(source) as raw:
                    try:
                        t=raw.extract_thumb()
                        if t.format==rawpy.ThumbFormat.JPEG:
                            with Image.open(BytesIO(t.data)) as im: return _image_preview(im,size)
                        return _image_preview(Image.fromarray(t.data),size)
                    except (rawpy.LibRawNoThumbnailError,rawpy.LibRawUnsupportedThumbnailError):
                        return _image_preview(Image.fromarray(raw.postprocess(use_camera_wb=True,half_size=True,output_bps=8)),size)
        except Exception as e: errors.append(str(e))
    raise ValueError('无法预览此照片；可保留原文件并用Photoshop打开')

class PreviewCache:
    def __init__(self,root,limit=512*1024*1024):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.limit=limit; self.lock=threading.RLock()
        self._keys=weakref.WeakValueDictionary()
        self._bytes=sum(p.stat().st_size for p in self.root.glob('*.jpg'))

    def get(self,group,size=640):
        try:
            size=max(80,min(int(size),4096))
            fingerprints=[]
            for a in group.files:
                if a.kind=='xmp':continue
                try:
                    stat=Path(a.path).stat();fingerprints.append((a.path,stat.st_mtime_ns,stat.st_size))
                except OSError:fingerprints.append((a.path,None,None))
            key=hashlib.sha256(repr((fingerprints,size)).encode()).hexdigest()
            path=self.root/(key+'.jpg')
            with self.lock:
                key_lock=self._keys.get(key)
                if key_lock is None:key_lock=threading.Lock();self._keys[key]=key_lock
            with key_lock:
                if not path.exists() or path.stat().st_size==0:
                    im=decode(group,size=size)
                    temp=path.with_suffix('.tmp'); im.save(temp,'JPEG',quality=88); temp.replace(path)
                    with self.lock:
                        self._bytes+=path.stat().st_size
                        if self._bytes>self.limit:self._prune()
                os.utime(path,None)
                content=path.read_bytes()
                with self.lock:
                    if self._bytes>self.limit:self._prune()
            return PreviewResult(str(path),content=content)
        except Exception as e: return PreviewResult(error=str(e))

    def _prune(self):
        entries=sorted(self.root.glob('*.jpg'),key=lambda p:p.stat().st_mtime)
        total=sum(p.stat().st_size for p in entries)
        for p in entries:
            if total<=self.limit: break
            if p.stem in self._keys:continue
            total-=p.stat().st_size; p.unlink(missing_ok=True)
        self._bytes=total
