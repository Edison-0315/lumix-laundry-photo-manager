"""macOS journal adapter for reused business services; no legacy SQL recovery."""
from pathlib import Path
import copy
import json
import os
import threading
from .domain import uid
from .locking import FileAccess
from .safeos import RootAccess, OwnershipError, ParentChangedError, digest, identity, matches_identity, fd_matches_identity

FORMAT = 'lumix-macos-journal-1'

class FileJournal:
    def __init__(self, catalog, library_id):
        self.catalog = catalog; self.library_id = library_id
        self.root = RootAccess(catalog.root)
        self.lock = threading.RLock(); self.access = FileAccess()
    def _save(self, opid, data):
        with self.catalog.connect() as db:
            db.execute('UPDATE operations SET payload=? WHERE id=?', (json.dumps(data, ensure_ascii=False), opid))
    def execute(self, kind, changes, sql, payload=None):
        with self.lock, self.access:
            self.catalog.guard()
            if self.catalog.rows("SELECT id FROM operations WHERE phase!='committed'"):
                raise ValueError('有操作尚未处理，未开始新的文件事务')
            opid = uid(); changes = copy.deepcopy(changes)
            for change in changes:
                self.root.inside(change['dst'])
                if change['move']: self.root.inside(change['src'])
                if os.path.lexists(change['dst']): raise FileExistsError('目标已存在，未覆盖')
                change['temp'] = change['dst'] + '.' + opid + '.partial'
                change['identity'] = identity(change['src']) if change['move'] else None
            data = {**(payload or {}), 'format':FORMAT, 'library_id':self.library_id, 'changes':changes, 'sql':sql}
            with self.catalog.connect() as db:
                db.execute('INSERT INTO operations VALUES(?,?,?,?,NULL)', (opid, kind, 'planned', json.dumps(data, ensure_ascii=False)))
            try:
                with self.catalog.connect() as db: db.execute("UPDATE operations SET phase='running' WHERE id=?", (opid,))
                for change in changes:
                    if digest(change['src']) != change['sha256']: raise ValueError('源文件在操作前发生变化')
                    if change['move']:
                        self.root.rename(change['src'], change['dst'], change['identity'])
                    else:
                        def owned(ident):
                            change['identity'] = ident; self._save(opid, data)
                        self.root.copy_stage(change['src'], change['temp'], change['sha256'], owned)
                        self.root.rename(change['temp'], change['dst'], change['identity'])
                    if identity(change['dst']) != change['identity'] or digest(change['dst']) != change['sha256']:
                        raise OwnershipError('目标文件发生变化，保留现场')
                with self.catalog.connect() as db:
                    for statement, args in sql: db.execute(statement, args)
                    db.execute("UPDATE operations SET phase='committed' WHERE id=?", (opid,))
            except Exception as error:
                if isinstance(error, ParentChangedError):
                    data['directory_checks'] = [{'path':error.directory,'identity':error.identity}]
                    self._save(opid, data)
                failures = self.rollback(data)
                with self.catalog.connect() as db:
                    db.execute('UPDATE operations SET phase=?,error=? WHERE id=?', ('needs_attention' if failures or isinstance(error, ParentChangedError) else 'committed', str(error) + ('; '+str(failures) if failures else ''), opid))
                raise
            return opid
    def rollback(self, data):
        with self.access:
            if data.get('format') != FORMAT or data.get('library_id') != self.library_id:
                return ['不是本 macOS 库的操作日志；未执行文件恢复或历史 SQL']
            for check in data.get('directory_checks', []):
                try:
                    # Reopen under the managed root, never an arbitrary logged directory.
                    with self.root.parent(Path(check['path'])/'directory-identity-check') as (fd, _):
                        info = os.fstat(fd)
                        if not fd_matches_identity(fd,check['identity']):
                            return ['父目录仍被替换，请先只读检查并恢复原目录，已保留现场']
                except (OSError, ValueError, KeyError, TypeError) as error:
                    return ['父目录身份无法确认，已保留现场：'+str(error)]
            errors = []
            for change in reversed(data['changes']):
                try:
                    destination = self.root.inside(change['dst']); temporary = self.root.inside(change['temp'])
                    if os.path.lexists(temporary): self.root.remove_owned(temporary, change.get('identity'))
                except Exception as error: errors.append(str(error))
                try:
                    destination = self.root.inside(change['dst'])
                    if not os.path.lexists(destination):
                        if change['move'] and (not os.path.lexists(change['src']) or not matches_identity(change['src'],change.get('identity'))):
                            raise OwnershipError('原位置或文件身份缺失，保留记录')
                        continue
                    if not matches_identity(destination,change.get('identity')):
                        if not change['move']: continue  # Copy never removed its source; keep an unrelated destination.
                        if os.path.lexists(change['src']) and matches_identity(change['src'],change.get('identity')): continue
                        raise OwnershipError('目标归属不明且原文件尚未恢复，保留文件')
                    if digest(destination) != change['sha256']: raise OwnershipError('目标内容改变，保留文件')
                    if change['move']: self.root.rename(destination, change['src'], change['identity'])
                    else: self.root.remove_owned(destination, change['identity'])
                except Exception as error: errors.append(str(error))
            return errors
    def recover_pending(self):
        with self.lock, self.access:
            recovered = []; errors = []
            for row in self.catalog.rows("SELECT * FROM operations WHERE phase!='committed'"):
                try: failures = self.rollback(json.loads(row['payload']))
                except Exception as error: failures = [str(error)]
                with self.catalog.connect() as db:
                    db.execute('UPDATE operations SET phase=?,error=? WHERE id=?', ('needs_attention' if failures else 'committed', str(failures) if failures else '已恢复至操作前状态', row['id']))
                if failures: errors.append({'id':row['id'], 'errors':failures})
                else: recovered.append(row['id'])
            return {'recovered':recovered, 'errors':errors}
