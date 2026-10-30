"""Keep recovery and all library mutations under a lifetime OS file lock."""
from pathlib import Path
import os
import weakref
import threading
from contextlib import contextmanager

class FileAccess:
    """Concurrent file readers; a reentrant writer for journal transactions."""
    def __init__(self):
        self._condition=threading.Condition(threading.RLock())
        self._writer=None;self._depth=0;self._readers=0;self._waiting=0

    def __enter__(self):
        ident=threading.get_ident()
        with self._condition:
            if self._writer==ident:self._depth+=1;return self
            self._waiting+=1
            try:
                while self._writer is not None or self._readers:self._condition.wait()
                self._writer=ident;self._depth=1
            finally:self._waiting-=1
        return self

    def __exit__(self,*args):
        with self._condition:
            self._depth-=1
            if self._depth==0:self._writer=None;self._condition.notify_all()

    @contextmanager
    def read(self):
        with self._condition:
            own_writer=self._writer==threading.get_ident()
            if not own_writer:
                while self._writer is not None or self._waiting:self._condition.wait()
                self._readers+=1
        try:yield
        finally:
            if not own_writer:
                with self._condition:self._readers-=1;self._condition.notify_all()

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
            stream.close();raise ValueError('此照片库已在另一个洗衣机管理器窗口中打开，请关闭该窗口后重试') from e
        self._finalizer=weakref.finalize(self,_release,stream)

    def close(self): self._finalizer()
