"""Read-only whole-library preview. Native FileManager performs system recycling."""
import hashlib
import fcntl
import json
import os
from pathlib import Path
import stat
import unicodedata
from .domain import uid
from .safeos import absolute, RootAccess

class LibraryRecycleInspector:
    def __init__(self,library):self.library=library;self.plan=None
    def _scope(self,protected,blocked):
        library=self.library;library._ready();root=library.root
        def physical(access):
            # Darwin SDK F_GETPATH = 50; resolve the opened directory without
            # reading its ancestors or trusting case-sensitive string prefixes.
            raw=fcntl.fcntl(access.fd,50,b'\0'*1024).split(b'\0',1)[0]
            return Path(os.fsdecode(raw))
        actual=physical(library._access)
        if root==root.parent or root==Path.home():raise ValueError('不能回收磁盘根目录或用户目录')
        for value in protected:
            path=absolute(value)
            if root.is_relative_to(path) or path.is_relative_to(root):
                raise ValueError('照片库与只读来源重叠，不能整库回收')
            try:access=RootAccess(path)
            except FileNotFoundError:continue
            try:
                source=physical(access)
                if access.identity==library._access.identity or actual.is_relative_to(source) or source.is_relative_to(actual):
                    raise ValueError('照片库与只读来源重叠，不能整库回收')
            finally:access.close()
        for value in [*blocked,str(Path(__file__).absolute())]:
            if absolute(value).is_relative_to(root):raise ValueError('照片库包含应用或设置目录，不能整库回收')
    def _snapshot(self,cancel):
        root=self.library.root;entries=[];count=0;total=0
        def unreadable(error):raise error
        for parent,dirs,files in os.walk(root,followlinks=False,onerror=unreadable):
            if cancel():raise ValueError('统计已取消')
            directory=Path(parent)
            if directory!=root and '.片集' in dirs and os.path.lexists(directory/'.片集/catalog.sqlite3'):
                raise ValueError('此目录包含其他照片库，不能整库回收')
            for name in [*dirs,*files]:
                if cancel():raise ValueError('统计已取消')
                path=directory/name;info=path.lstat()
                if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                    raise ValueError('照片库含链接或特殊文件，请先移出后回收')
                # SQLite readers may create/remove WAL auxiliaries and touch
                # the metadata directory timestamp. Track directory identity
                # and membership; file content stamps still invalidate plans.
                regular=stat.S_ISREG(info.st_mode)
                relative=path.relative_to(root)
                # SHM is a derived WAL index; SQLite readers can modify it
                # without changing database contents. DB and WAL stay covered.
                if relative.parts!=('.片集','catalog.sqlite3-shm'):
                    entries.append((str(relative),info.st_dev,info.st_ino,info.st_mode,info.st_size if regular else 0,info.st_mtime_ns if regular else 0))
                if stat.S_ISREG(info.st_mode):count+=1;total+=info.st_size
        digest=hashlib.sha256(json.dumps(sorted(entries),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        return {'fingerprint':digest,'file_count':count,'bytes':total}
    def inspect(self,protected,blocked,cancel=lambda:False):
        self._scope(protected,blocked)
        before=self._snapshot(cancel);after=self._snapshot(cancel)
        if before!=after:raise ValueError('照片库正在变化，请稍后重新预览')
        library=self.library
        self.plan={**after,'token':uid(),'name':library.root.name,'root':str(library.root),
                   'root_identity':library._access.identity,'catalog_identity':library._catalog_identity,
                   'photo_count':library.catalog.rows('SELECT COUNT(*) AS count FROM photos')[0]['count']}
        return {k:v for k,v in self.plan.items() if k!='fingerprint'}
    def validate(self,token,name,protected,blocked,cancel=lambda:False):
        if not self.plan or token!=self.plan['token'] or unicodedata.normalize('NFC',name)!=unicodedata.normalize('NFC',self.plan['name']):
            raise ValueError('预览已失效或照片库名称不匹配，请重新确认')
        self._scope(protected,blocked)
        current=self._snapshot(cancel)
        if current['fingerprint']!=self.plan['fingerprint']:raise ValueError('照片库内容已变化，请重新预览后确认')
        return {k:v for k,v in self.plan.items() if k!='fingerprint'}
