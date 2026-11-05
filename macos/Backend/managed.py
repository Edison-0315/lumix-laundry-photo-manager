"""Only app-created, identity-bound macOS libraries can reach writable services."""
import json
import errno
import os
from pathlib import Path
import threading
import uuid
from contextlib import ExitStack
from pianji.catalog import Catalog
from pianji.library import Library
from pianji.locking import LibraryLock
from pianji.fileops import FileJournal
from pianji.paths import safe_name
from pianji.safeos import RootAccess, absolute, open_regular, identity, fd_identity, volume_uuid_fd, NOFOLLOW_ANY

MARKER = '.片集/macos-library.json'
FORMAT = 'lumix-macos-1'

def read_json(path):
    fd = open_regular(path)
    with os.fdopen(fd, 'r', encoding='utf-8') as stream: return json.load(stream)

def validate_marker(marker, root, root_identity, catalog_identity, volume_uuid=None):
    if not isinstance(marker,dict):raise ValueError('本机库标记无效；请先只读检查')
    recorded_root=marker.get('root_identity');recorded_catalog=marker.get('catalog_identity')
    same=recorded_root==root_identity and recorded_catalog==catalog_identity
    if 'volume_uuid' in marker:
        same=(marker['volume_uuid']==volume_uuid and volume_uuid is not None
              and isinstance(recorded_root,list) and len(recorded_root)==2
              and isinstance(recorded_catalog,list) and len(recorded_catalog)==2
              and recorded_root[0]==recorded_catalog[0] and root_identity[0]==catalog_identity[0]
              and recorded_root[1]==root_identity[1] and recorded_catalog[1]==catalog_identity[1])
    if marker.get('format')!=FORMAT or marker.get('root')!=str(root) or not same:
        raise ValueError('本机库位置、身份或格式已变化；请先只读检查')
    ident=marker.get('library_id')
    if not isinstance(ident,str) or len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident):
        raise ValueError('本机库标记无效；请先只读检查')

class OwnedCatalog(Catalog):
    def __init__(self, root, create, guard):
        self.guard = guard
        if create: super().__init__(root)
        else:
            self.root=Path(root); self.meta=self.root/'.片集'; self.lock=threading.RLock()
            tables={row['name'] for row in self.rows("SELECT name FROM sqlite_master WHERE type='table'")}
            expected={'activities','people','photos','assets','operations','detached_exports','import_members','trashed_photos','purges','deleted_activities'}
            if not expected.issubset(tables): raise ValueError('本机库结构不完整，未执行建表或迁移')

class ManagedLibrary(Library):
    @classmethod
    def create(cls, root, protected_roots=()):
        root=absolute(root); safe_name(root.name)
        protected=[absolute(path) for path in protected_roots]
        if any(root.is_relative_to(path) for path in protected): raise ValueError('新照片库不能放在只读来源目录内')
        protected_ids=set()
        for path in protected:
            try: access=RootAccess(path)
            except FileNotFoundError: continue
            try: protected_ids.add(tuple(access.identity))
            finally: access.close()
        for ancestor in root.parents:
            if os.path.lexists(ancestor/'.片集/catalog.sqlite3'):
                raise ValueError('新照片库不能嵌套在现有照片库内')
            access=RootAccess(ancestor)
            try:
                if tuple(access.identity) in protected_ids: raise ValueError('新照片库不能放在只读来源目录内')
            finally: access.close()
        if os.path.lexists(root): raise FileExistsError(errno.EEXIST,'照片库目标已经存在',str(root))
        with ExitStack() as stack:
            parent=RootAccess(root.parent);stack.callback(parent.close)
            preparation=root.parent/('.lumix-create-'+uuid.uuid4().hex)
            parent.verify();os.mkdir(preparation.name,mode=0o700,dir_fd=parent.fd)
            published=False
            try:
                staged=RootAccess(preparation);stack.callback(staged.close)
                os.mkdir('.片集',mode=0o700,dir_fd=staged.fd)
                meta_fd=os.open('.片集',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=staged.fd)
                stack.callback(os.close,meta_fd)
                os.mkdir('staging',mode=0o700,dir_fd=meta_fd)
                database_fd=os.open('catalog.sqlite3',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=meta_fd)
                stack.callback(os.close,database_fd)
                staged.verify()
                instance=cls.__new__(cls)
                instance._initialize(preparation,create=True,marker_root=root,expected_root=staged.identity,
                                     expected_catalog=fd_identity(database_fd,legacy=True),meta_fd=meta_fd)
                stack.callback(instance.close)
                instance.close()
                os.fsync(database_fd);os.fsync(meta_fd);os.fsync(staged.fd)
                parent.rename(preparation,root,fd_identity(staged.fd),directory=True)
                published=True
                return cls.open(root)
            except Exception as error:
                location=root if published else preparation
                raise ValueError('新建照片库未完成，已保留现场。'+('照片库路径：' if published else '准备目录原位置：')+str(location)+'；'+str(error)) from error
    @classmethod
    def open(cls, root):
        root=absolute(root)
        try: marker=read_json(root/MARKER)
        except (OSError, ValueError) as error:
            raise ValueError('此库不是本 macOS 应用创建的库；请使用只读浏览') from error
        access=RootAccess(root)
        try:
            validate_marker(marker,root,access.identity,identity(root/'.片集/catalog.sqlite3',legacy=True),volume_uuid_fd(access.fd))
        finally: access.close()
        instance=cls.__new__(cls); instance._initialize(root, create=False, marker=marker)
        return instance
    def _initialize(self, root, create, marker=None, *, marker_root=None,expected_root=None,expected_catalog=None,meta_fd=None):
        self.root=root; self._closed=False; self.lock=threading.RLock()
        self._access=RootAccess(root)
        self._root_lock=None
        try:
            if expected_root is not None and self._access.identity!=expected_root:raise ValueError('新库准备目录已被替换，停止初始化')
            self._catalog_identity=identity(root/'.片集/catalog.sqlite3',legacy=True)
            if expected_catalog is not None and self._catalog_identity!=expected_catalog:raise ValueError('新库准备数据库已被替换，停止初始化')
            self._volume_uuid=self._access._volume_uuid or volume_uuid_fd(self._access.fd)
            self._access._volume_uuid=self._volume_uuid
            if not create: validate_marker(marker,root,self._access.identity,self._catalog_identity,self._volume_uuid)
            self._root_lock=LibraryLock(root,meta_fd=meta_fd)
            self.catalog=OwnedCatalog(root, create, self._guard)
            if create:
                self._guard()
                marker={'format':FORMAT,'library_id':uuid.uuid4().hex,'root':str(marker_root or root),'root_identity':self._access.identity,'catalog_identity':self._catalog_identity,'volume_uuid':self._volume_uuid}
                flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|NOFOLLOW_ANY|os.O_CLOEXEC
                fd=os.open(root/MARKER,flags,0o600) if meta_fd is None else os.open('macos-library.json',flags,0o600,dir_fd=meta_fd)
                with os.fdopen(fd,'w',encoding='utf-8') as stream:
                    json.dump(marker,stream,ensure_ascii=False,sort_keys=True);stream.flush();os.fsync(stream.fileno())
                if meta_fd is None:
                    own_meta=os.open(root/'.片集',os.O_RDONLY|os.O_DIRECTORY|NOFOLLOW_ANY|os.O_CLOEXEC)
                    try: os.fsync(own_meta)
                    finally: os.close(own_meta)
                else: os.fsync(meta_fd)
                os.fsync(self._access.fd)
                self._guard()
            self.marker=marker
            self.journal=FileJournal(self.catalog,marker['library_id'])
            self.recovery={'recovered':[],'errors':[]}  # Opening never runs journal recovery.
        except BaseException:
            self._closed=True
            if self._root_lock is not None: self._root_lock.close()
            self._access.close()
            raise
    def _guard(self):
        if self._closed: raise ValueError('照片库已关闭')
        self._access.verify()
        if identity(self.root/'.片集/catalog.sqlite3',legacy=True)!=self._catalog_identity: raise ValueError('数据库文件被替换，已停止写入')
        if self._root_lock is not None and identity(self.root/'.片集/library.lock',legacy=True)!=self._root_lock.identity: raise ValueError('库锁文件被替换，已停止写入')
    def _ready(self):
        self._guard(); super()._ready()
        if self.catalog.rows('SELECT photo_id FROM purges LIMIT 1'):
            raise ValueError('有永久删除尚未完成；普通写入已停止，请先检查库状态')
    def close(self):
        if self._closed: return
        super().close()
        self.journal.root.close(); self._access.close()
