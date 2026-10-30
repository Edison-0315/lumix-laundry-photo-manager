from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import threading
import logging
from .domain import TaskSnapshot,uid

class JobManager:
    def __init__(self):
        self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='pianji-work')
        self._tasks={}; self._events={}; self._lock=threading.RLock()

    def submit(self,kind,fn):
        ident=uid(); event=threading.Event()
        with self._lock: self._tasks[ident]=TaskSnapshot(ident,message=kind); self._events[ident]=event
        def progress(done,total,message):
            with self._lock:
                s=self._tasks[ident]; s.done=done; s.total=total; s.message=message
        def run():
            if event.is_set():
                with self._lock:self._tasks[ident].status='cancelled';self._tasks[ident].result={'cancelled':True}
                return
            with self._lock: self._tasks[ident].status='running'
            try:
                result=fn(event.is_set,progress)
                with self._lock:
                    s=self._tasks[ident]; s.result=result
                    s.errors=result.get('errors',[]) if isinstance(result,dict) else []
                    cancelled=event.is_set() or (isinstance(result,dict) and result.get('cancelled'))
                    s.status='cancelled' if cancelled else ('partial' if s.errors else 'succeeded')
            except Exception as e:
                logging.exception('Background task failed: %s',kind)
                with self._lock:
                    s=self._tasks[ident]; s.status='failed'; s.errors=[{'message':str(e)}]; s.message=str(e)
        self._executor.submit(run)
        return ident

    def get_task(self,ident):
        with self._lock:
            if ident not in self._tasks: raise ValueError('任务不存在')
            return asdict(self._tasks[ident])

    def cancel_task(self,ident):
        with self._lock:
            if ident not in self._tasks: raise ValueError('任务不存在')
            self._events[ident].set()
            if self._tasks[ident].status in ('running','queued'): self._tasks[ident].status='cancelling'
        return self.get_task(ident)

    def close(self):
        for event in self._events.values(): event.set()
        self._executor.shutdown(wait=True,cancel_futures=False)
