from pathlib import Path
from io import BytesIO
import hashlib
import threading
from PIL import Image,ImageOps
from .domain import PreviewResult

def decode(group):
    errors=[]
    for asset in sorted(group.files,key=lambda a: a.kind!='jpeg'):
        try:
            if asset.kind=='jpeg' or asset.kind=='export':
                with Image.open(asset.path) as im: return ImageOps.exif_transpose(im).convert('RGB')
            if asset.kind=='raw':
                import rawpy
                with rawpy.imread(asset.path) as raw:
                    try:
                        t=raw.extract_thumb()
                        if t.format==rawpy.ThumbFormat.JPEG:
                            with Image.open(BytesIO(t.data)) as im: return ImageOps.exif_transpose(im).convert('RGB')
                        return Image.fromarray(t.data).convert('RGB')
                    except (rawpy.LibRawNoThumbnailError,rawpy.LibRawUnsupportedThumbnailError):
                        return Image.fromarray(raw.postprocess(use_camera_wb=True,half_size=True,output_bps=8))
        except Exception as e: errors.append(str(e))
    raise ValueError('无法预览此照片；可保留原文件并用Photoshop打开')

class PreviewCache:
    def __init__(self,root,limit=512*1024*1024):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.limit=limit; self.lock=threading.RLock()

    def get(self,group,size=640):
        try:
            size=max(80,min(int(size),4096))
            fingerprints=[(a.path,Path(a.path).stat().st_mtime_ns,Path(a.path).stat().st_size) for a in group.files if a.kind!='xmp']
            key=hashlib.sha256(repr((fingerprints,size)).encode()).hexdigest()
            path=self.root/(key+'.jpg')
            with self.lock:
                if not path.exists():
                    im=decode(group); im.thumbnail((size,size))
                    temp=path.with_suffix('.tmp'); im.save(temp,'JPEG',quality=88); temp.replace(path)
                    self._prune()
                path.touch()
            return PreviewResult(str(path))
        except Exception as e: return PreviewResult(error=str(e))

    def _prune(self):
        entries=sorted(self.root.glob('*.jpg'),key=lambda p:p.stat().st_mtime)
        total=sum(p.stat().st_size for p in entries)
        for p in entries:
            if total<=self.limit: break
            total-=p.stat().st_size; p.unlink(missing_ok=True)
