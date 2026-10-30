"""Keep recovery and all library mutations under a lifetime OS file lock."""
from pathlib import Path
import os
import weakref

def _release(stream):
    try:
        stream.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
    finally: stream.close()

class LibraryLock:
    def __init__(self,root):
        meta=Path(root)/'.片集';meta.mkdir(parents=True,exist_ok=True)
        stream=open(meta/'library.lock','a+b')
        try:
            stream.seek(0,2)
            if stream.tell()==0:stream.write(b'\0');stream.flush()
            stream.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as e:
            stream.close();raise ValueError('此照片库已在另一个片集窗口中打开，请关闭该窗口后重试') from e
        self._finalizer=weakref.finalize(self,_release,stream)

    def close(self): self._finalizer()
