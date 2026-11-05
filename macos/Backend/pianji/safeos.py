"""Darwin file primitives. No overwrite rename and no following source symlinks."""
import contextlib
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import stat
import sys
import uuid

NOFOLLOW_ANY = 0x20000000  # Darwin SDK sys/fcntl.h, macOS 11+
RENAME_EXCL = 4
_libc = ctypes.CDLL(None, use_errno=True)
if sys.platform == 'darwin':
    _rename = _libc.renameatx_np
    _rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    _rename.restype = ctypes.c_int

class OwnershipError(ValueError): pass
class ParentChangedError(OwnershipError):
    def __init__(self, path, identity):
        self.directory = str(absolute(path).parent); self.identity = identity
        super().__init__('照片库父目录已变化，停止写入并保留现场')

class _Attributes(ctypes.Structure):
    _fields_=[('count',ctypes.c_ushort),('reserved',ctypes.c_ushort),('common',ctypes.c_uint32),('volume',ctypes.c_uint32),('directory',ctypes.c_uint32),('file',ctypes.c_uint32),('fork',ctypes.c_uint32)]

def volume_uuid_fd(fd):
    # Darwin sys/attr.h: ATTR_VOL_INFO | ATTR_VOL_UUID, returned as length + uuid_t.
    attributes=_Attributes(5,0,0,0x80040000,0,0,0);buffer=ctypes.create_string_buffer(20)
    function=_libc.fgetattrlist
    function.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint]
    function.restype=ctypes.c_int
    if function(fd,ctypes.byref(attributes),buffer,20,0):
        code=ctypes.get_errno();raise OSError(code,'无法读取稳定卷身份：'+os.strerror(code))
    if int.from_bytes(buffer.raw[:4],'little')!=20 or not any(buffer.raw[4:20]):
        raise ValueError('文件系统未提供有效的稳定卷身份')
    return uuid.UUID(bytes=buffer.raw[4:20]).hex

def fd_identity(fd, legacy=False):
    info=os.fstat(fd)
    return [info.st_dev if legacy else volume_uuid_fd(fd),info.st_ino]

def fd_matches_identity(fd, expected, named=None):
    if not isinstance(expected,(list,tuple)) or len(expected)!=2:return False
    info=named if named is not None else os.fstat(fd)
    actual=[info.st_dev if isinstance(expected[0],int) else volume_uuid_fd(fd),info.st_ino]
    return actual==list(expected)

def matches_identity(path, expected):
    fd=open_regular(path)
    try:return fd_matches_identity(fd,expected)
    finally:os.close(fd)

def absolute(path):
    raw = os.fspath(path)
    if not os.path.isabs(raw) or any(part in ('.', '..') for part in raw.split('/')) or '\0' in raw:
        raise ValueError('需要不含跳转的绝对路径')
    return Path(raw)

def open_regular(path, writable=False):
    if sys.platform != 'darwin': raise RuntimeError('此文件引擎仅支持 macOS')
    fd = os.open(absolute(path), (os.O_RDWR if writable else os.O_RDONLY) | NOFOLLOW_ANY | os.O_NONBLOCK | os.O_CLOEXEC)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd); raise ValueError('不是普通文件')
    return fd

def identity(path, legacy=False):
    fd = open_regular(path)
    try:return fd_identity(fd,legacy)
    finally: os.close(fd)

def digest(path):
    fd = open_regular(path)
    try:
        before = os.fstat(fd); sha = hashlib.sha256()
        while True:
            block = os.read(fd, 1024 * 1024)
            if not block: break
            sha.update(block)
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('源文件在读取期间发生变化')
        return sha.hexdigest()
    finally: os.close(fd)

class RootAccess:
    def __init__(self, root):
        self.root = absolute(root)
        self.fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW_ANY | os.O_CLOEXEC)
        info = os.fstat(self.fd); self.identity = [info.st_dev, info.st_ino]
        try:self._volume_uuid=volume_uuid_fd(self.fd)
        except (OSError,ValueError):self._volume_uuid=None  # Read-only source volumes may lack this attribute.
    def close(self):
        fd=getattr(self,'fd',None);self.fd=None
        if fd is not None:os.close(fd)
    def __del__(self):
        try:self.close()
        except Exception:pass
    def verify(self):
        if self.fd is None: raise ValueError('照片库已关闭')
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW_ANY | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            if [info.st_dev, info.st_ino] != self.identity: raise OwnershipError('照片库目录已被替换')
            if self._volume_uuid is not None and volume_uuid_fd(fd)!=self._volume_uuid:
                raise OwnershipError('照片库所在卷已被替换，已停止写入')
        finally: os.close(fd)
    def inside(self, path):
        path = absolute(path)
        try: relative = path.relative_to(self.root)
        except ValueError: raise ValueError('路径超出了照片库范围')
        if not relative.parts: raise ValueError('文件操作不能以照片库根目录为目标')
        cursor = self.root
        for part in relative.parts:
            cursor /= part
            try:
                if stat.S_ISLNK(os.lstat(cursor).st_mode): raise ValueError('照片库路径不能包含符号链接')
            except FileNotFoundError: break
        return path
    @contextlib.contextmanager
    def parent(self, path, create=False):
        self.verify(); path = self.inside(path); relative = path.relative_to(self.root)
        fd = os.dup(self.fd)
        try:
            for part in relative.parts[:-1]:
                if create:
                    try: os.mkdir(part, mode=0o755, dir_fd=fd)
                    except FileExistsError: pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                os.close(fd); fd = child
            yield fd, relative.name
        finally: os.close(fd)
    def rename(self, source, destination, expected=None, *, directory=False):
        with self.parent(source) as (srcfd, src), self.parent(destination, create=True) as (dstfd, dst):
            self.verify_parent_binding(source, srcfd)
            self.verify_parent_binding(destination, dstfd)
            kind_flag = os.O_DIRECTORY if directory else os.O_NONBLOCK
            held = os.open(src, os.O_RDONLY | os.O_NOFOLLOW | kind_flag | os.O_CLOEXEC, dir_fd=srcfd)
            try:
                info = os.fstat(held)
                correct_kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
                if not correct_kind: raise ValueError('只允许移动目录' if directory else '只允许移动普通文件')
                original = fd_identity(held)
                if expected is not None and not fd_matches_identity(held,expected): raise OwnershipError('源文件归属已变化，保留文件')
                if _rename(srcfd, os.fsencode(src), dstfd, os.fsencode(dst), RENAME_EXCL):
                    code = ctypes.get_errno(); raise OSError(code, os.strerror(code), str(destination))
                moved = os.stat(dst, dir_fd=dstfd, follow_symlinks=False)
                if not fd_matches_identity(dstfd,original,moved):
                    # Put an unrelated replacement back when the original name is still free.
                    _rename(dstfd, os.fsencode(dst), srcfd, os.fsencode(src), RENAME_EXCL)
                    raise OwnershipError('移动时源文件被替换；已保留现场，未删除任何文件')
                try:
                    self.verify_parent_binding(source, srcfd)
                    self.verify_parent_binding(destination, dstfd)
                except ParentChangedError:
                    # Use the held descriptors, never the replacement namespace.
                    # EXCL preserves an unrelated source name if rollback is blocked.
                    if _rename(dstfd, os.fsencode(dst), srcfd, os.fsencode(src), RENAME_EXCL) == 0:
                        try: os.fsync(dstfd); os.fsync(srcfd)
                        except OSError: pass  # The original fault still requires inspection.
                    raise
                os.fsync(dstfd); os.fsync(srcfd)
                self.verify()
                return original
            finally: os.close(held)
    def copy_stage(self, source, destination, expected_hash, owned):
        sourcefd = open_regular(source)
        try:
            before = os.fstat(sourcefd)
            with self.parent(destination, create=True) as (parentfd, name):
                self.verify_parent_binding(destination, parentfd)
                destfd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parentfd)
                try:
                    created = fd_identity(destfd)
                    owned(created)  # Persist ownership before writing the first byte.
                    sha = hashlib.sha256()
                    while True:
                        block = os.read(sourcefd, 1024 * 1024)
                        if not block: break
                        sha.update(block); offset = 0
                        while offset < len(block):
                            written = os.write(destfd, block[offset:])
                            if written <= 0: raise OSError(errno.EIO, '写入未完成')
                            offset += written
                    os.fsync(destfd); os.fsync(parentfd)
                    self.verify_parent_binding(destination, parentfd)
                    after = os.fstat(sourcefd)
                    if sha.hexdigest() != expected_hash or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise ValueError('源文件在复制期间发生变化，未发布副本')
                    return created
                finally: os.close(destfd)
        finally: os.close(sourcefd)
    def verify_parent_binding(self, path, held):
        opened = os.fstat(held); expected = fd_identity(held)
        try:
            with self.parent(path) as (current, _): named = os.fstat(current)
        except (OSError, ValueError) as error:
            raise ParentChangedError(path, expected) from error
        if (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
            raise ParentChangedError(path, expected)
    def remove_owned(self, path, expected):
        if expected is None: raise OwnershipError('未记录文件归属，保留现场')
        # Quarantine under the private metadata directory before unlinking.
        quarantine = self.root/'.片集/staging'/('remove-' + uuid.uuid4().hex)
        self.rename(path, quarantine, expected)
        with self.parent(quarantine) as (parentfd, name):
            info = os.stat(name, dir_fd=parentfd, follow_symlinks=False)
            if not fd_matches_identity(parentfd,expected,info): raise OwnershipError('隔离文件归属变化，保留现场')
            os.unlink(name, dir_fd=parentfd); os.fsync(parentfd)

    def unlink_verified(self, path, expected, checksum):
        # Used only for a persisted private purge quarantine. Keep the regular
        # descriptor open while verifying contents and its directory entry.
        with self.parent(path) as (parentfd, name):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parentfd)
            try:
                before = os.fstat(fd)
                if not stat.S_ISREG(before.st_mode) or not fd_matches_identity(fd,expected):
                    raise OwnershipError('隔离文件身份变化，未删除')
                sha = hashlib.sha256()
                while True:
                    block = os.read(fd, 1024 * 1024)
                    if not block: break
                    sha.update(block)
                after = os.fstat(fd); named = os.stat(name, dir_fd=parentfd, follow_symlinks=False)
                if sha.hexdigest() != checksum or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or not fd_matches_identity(parentfd,expected,named):
                    raise OwnershipError('隔离文件内容或身份变化，未删除')
                self.verify(); os.unlink(name, dir_fd=parentfd); os.fsync(parentfd)
            finally: os.close(fd)

    def remove_empty_directory(self, path):
        with self.parent(path) as (parentfd, name):
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parentfd)
            try:
                expected = fd_identity(fd)
                with os.scandir(fd) as entries:
                    if next(entries, None) is not None: raise OSError(errno.ENOTEMPTY, '目录不是空目录', str(path))
                quarantine = self.root/'.片集/staging'/('empty-' + uuid.uuid4().hex)
                self.rename(path, quarantine, expected, directory=True)
                try:
                    with self.parent(quarantine) as (privatefd, private_name):
                        self.verify_parent_binding(quarantine, privatefd)
                        named = os.stat(private_name, dir_fd=privatefd, follow_symlinks=False)
                        if not fd_matches_identity(privatefd, expected, named):
                            raise OwnershipError('空目录隔离身份变化，未清理')
                        os.rmdir(private_name, dir_fd=privatefd); os.fsync(privatefd)
                except Exception as error:
                    try: self.rename(quarantine, path, expected, directory=True)
                    except Exception as restore_error:
                        raise OwnershipError('空目录清理未完成，已保留现场，请检查隔离路径：'+str(quarantine)+'；'+str(restore_error)) from error
                    raise
            finally: os.close(fd)
