"""Remove only empty, known managed directories. Never traverse reparse points."""
from pathlib import Path
import errno
import json
import logging
import os


def checked_path(root,path):
    root=Path(root).resolve();path=Path(os.path.abspath(path))
    if not path.is_relative_to(root):raise ValueError('路径超出了照片库范围')
    cursor=path
    while cursor!=root:
        if cursor.is_symlink() or cursor.is_junction():raise ValueError('不能通过符号链接或目录联接清理或删除')
        cursor=cursor.parent
    return path


def prune_empty(root,directories):
    root=Path(root).resolve();protected={root,root/'.片集'};candidates=set();result={'removed':[],'errors':[]}
    for directory in directories:
        try:path=checked_path(root,directory)
        except (ValueError,OSError):continue
        while path not in protected and path.is_relative_to(root):
            candidates.add(path);path=path.parent
    for path in sorted(candidates,key=lambda p:len(p.parts),reverse=True):
        try:
            checked_path(root,path);path.rmdir();result['removed'].append(str(path))
        except FileNotFoundError:pass
        except OSError as e:
            if e.errno in (errno.ENOTEMPTY,errno.EEXIST) or getattr(e,'winerror',None)==145:continue
            result['errors'].append({'path':str(path),'message':str(e)})
        except ValueError:continue
    if result['errors']:logging.warning('Empty directory cleanup incomplete: %s',result['errors'])
    return result


def cleanup_library(library,within=None):
    with library.lock,library.journal.access:
        library._ready();catalog=library.catalog
        paths=[library.root/a['folder'] for a in catalog.rows('SELECT folder FROM activities')]
        paths += [catalog.meta/'回收站',catalog.meta/'取消关联保留']
        for row in catalog.rows('SELECT payload FROM operations'):
            for change in json.loads(row['payload']).get('changes',[]):
                paths.extend(Path(change[key]).parent for key in ('src','dst') if change.get(key))
            paths.extend(Path(path) for path in json.loads(row['payload']).get('cleanup_dirs',[]))
        if within:
            scope=checked_path(library.root,within)
            paths=[p for p in paths if Path(p).is_relative_to(scope)]
        return prune_empty(library.root,paths)
