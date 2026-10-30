"""Journal every owned destination before touching files; commit metadata last."""
from pathlib import Path
import hashlib
import os
import json
import threading
import logging
from .domain import uid
from .paths import inside
from .locking import FileAccess

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def identity(path):
    stat=Path(path).stat()
    return [stat.st_dev,stat.st_ino]

def transfer(src,dst,move):
    src=Path(src); dst=Path(dst)
    dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists(): raise FileExistsError(f'目标已存在：{dst.name}')
    if move:
        # os.rename on Windows is exclusive; never use replace for photos.
        os.rename(src,dst)
    else:
        with open(src,'rb') as reader,open(dst,'xb') as writer:
            for block in iter(lambda:reader.read(1024*1024),b''): writer.write(block)
            writer.flush(); os.fsync(writer.fileno())

class FileJournal:
    def __init__(self,catalog): self.catalog=catalog; self.lock=threading.RLock();self.access=FileAccess()

    def execute(self,kind,changes,sql,payload=None):
        with self.lock,self.access:
            opid=uid()
            for c in changes:
                inside(self.catalog.root,c['dst'])
                if c['move']: inside(self.catalog.root,c['src'])
                if Path(c['dst']).exists(): raise FileExistsError('目标文件已存在')
                c['temp']=c['dst']+f'.{opid}.partial'
                c['identity']=identity(c['src']) if c['move'] else None
            data={'changes':changes,'sql':sql,**(payload or {})}
            with self.catalog.connect() as db:
                db.execute('INSERT INTO operations VALUES(?,?,?,?,NULL)',(opid,kind,'planned',json.dumps(data,ensure_ascii=False)))
            try:
                with self.catalog.connect() as db: db.execute("UPDATE operations SET phase='running' WHERE id=?",(opid,))
                for c in changes:
                    if digest(c['src'])!=c['sha256']: raise ValueError('源文件在操作前发生变化')
                    if c['move']: transfer(c['src'],c['dst'],True)
                    else:
                        transfer(c['src'],c['temp'],False)
                        if digest(c['temp'])!=c['sha256']: raise ValueError('文件复制校验失败')
                        c['identity']=identity(c['temp'])
                        # Persist staging identity before publication, making a crash
                        # distinguish our file from an unrelated concurrent writer.
                        with self.catalog.connect() as db:
                            db.execute('UPDATE operations SET payload=? WHERE id=?',(json.dumps(data,ensure_ascii=False),opid))
                        os.rename(c['temp'],c['dst'])
                    if digest(c['dst'])!=c['sha256']: raise ValueError('目标文件校验失败')
                with self.catalog.connect() as db:
                    for statement,args in sql: db.execute(statement,args)
                    db.execute("UPDATE operations SET phase='committed' WHERE id=?",(opid,))
            except Exception as e:
                failures=self.rollback(data)
                with self.catalog.connect() as db:
                    db.execute('UPDATE operations SET phase=?,error=? WHERE id=?',('needs_attention' if failures else 'committed',str(e)+(('; '+str(failures)) if failures else ''),opid))
                raise
            # Metadata is committed. Cleanup must never enter the file rollback
            # path, even if an unexpected filesystem/runtime error escapes it.
            try:
                from .cleanup import prune_empty
                directories=[Path(c['src']).parent for c in changes if c['move']]+data.get('cleanup_dirs',[])
                prune_empty(self.catalog.root,directories)
            except Exception:logging.exception('Committed photo operation succeeded; empty folder cleanup failed')
            return opid

    def rollback(self,data):
        with self.access:return self._rollback(data)

    def _rollback(self,data):
        errors=[]
        for c in reversed(data['changes']):
            try:
                src=Path(c['src']); dst=inside(self.catalog.root,c['dst'])
                temp=inside(self.catalog.root,c['temp'])
                # Only a journal-owned staging file may be incomplete.
                if temp.exists(): temp.unlink()
                if not dst.exists():
                    if c['move'] and not src.exists(): raise FileNotFoundError('原路径与目标路径均缺失')
                    continue
                if c.get('identity')!=identity(dst):
                    if c['move'] and not src.exists(): raise ValueError('目标归属不明，保留现场等待人工恢复')
                    continue
                if digest(dst)!=c['sha256']: raise ValueError('目标内容变化，已保留现场')
                if c['move']:
                    if src.exists(): raise FileExistsError('原位置已有文件，未覆盖')
                    src.parent.mkdir(parents=True,exist_ok=True); os.rename(dst,src)
                else: dst.unlink()
            except Exception as e: errors.append(str(e))
        return errors

    def recover_pending(self):
        recovered=[]; errors=[]
        with self.lock,self.access:
            for op in self.catalog.rows("SELECT id FROM operations WHERE phase!='committed'"):
                data=self.catalog.operation(op['id'])['payload']
                failures=self.rollback(data)
                with self.catalog.connect() as db:
                    db.execute('UPDATE operations SET phase=?,error=? WHERE id=?',('needs_attention' if failures else 'committed',str(failures) if failures else '已恢复至操作前状态',op['id']))
                (errors if failures else recovered).append({'id':op['id'],'errors':failures})
        return {'recovered':recovered,'errors':errors}
