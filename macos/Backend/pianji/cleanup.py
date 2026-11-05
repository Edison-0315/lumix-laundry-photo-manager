"""Remove only empty, known managed paths, through directory descriptors."""
from pathlib import Path
import errno
import json
from .safeos import RootAccess
from .fileops import FORMAT


def checked_path(root,path):
    access=RootAccess(root)
    try:return access.inside(path)
    finally:access.close()


def prune_empty(root,directories):
    access=RootAccess(root);root=access.root
    protected={root,root/'.片集',root/'.片集/staging'};candidates=set()
    report={'removed':[],'errors':[]}
    try:
        for directory in directories:
            try:path=access.inside(directory)
            except (ValueError,OSError):continue
            while path not in protected and path.is_relative_to(root):
                candidates.add(path);path=path.parent
        for path in sorted(candidates,key=lambda p:len(p.parts),reverse=True):
            try:access.remove_empty_directory(path);report['removed'].append(str(path))
            except FileNotFoundError:pass
            except OSError as error:
                if error.errno not in (errno.ENOTEMPTY,errno.EEXIST):report['errors'].append({'path':str(path),'message':str(error)})
            except ValueError as error:report['errors'].append({'path':str(path),'message':str(error)})
        return report
    finally:access.close()


def cleanup_library(library,within=None):
    with library.lock,library.journal.access:
        library._ready();catalog=library.catalog
        paths=[library.root/a['folder'] for a in catalog.rows('SELECT folder FROM activities')]
        paths += [catalog.meta/'回收站',catalog.meta/'取消关联保留']
        for row in catalog.rows("SELECT payload FROM operations WHERE phase='committed' AND error IS NULL"):
            try:data=json.loads(row['payload'])
            except (ValueError,TypeError):continue
            if not isinstance(data,dict) or data.get('format')!=FORMAT or data.get('library_id')!=library.marker['library_id']:continue
            for change in data.get('changes',[]):
                paths.extend(Path(change[key]).parent for key in ('src','dst') if change.get(key))
            paths.extend(Path(path) for path in data.get('cleanup_dirs',[]))
        if within:
            scope=checked_path(library.root,within)
            paths=[p for p in paths if Path(p).is_relative_to(scope)]
        return prune_empty(library.root,paths)
