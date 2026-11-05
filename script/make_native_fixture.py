"""Create an isolated UI fixture; never target a user's photo library."""
from pathlib import Path
import sys
import json
import uuid
import shutil
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'macos/Backend'))
from managed import ManagedLibrary
fixture = root / 'build/fixtures/NativeWorkflow'
if not fixture.exists():
    library = ManagedLibrary.create(fixture)
    library.close()
(fixture / 'Fixture Ready').mkdir(exist_ok=True)

recovery = root / 'build/fixtures/NativeRecovery'
library = ManagedLibrary.open(recovery) if recovery.exists() else ManagedLibrary.create(recovery)
try:
    if not library.catalog.rows("SELECT id FROM operations WHERE phase!='committed'"):
        payload = {'format': 'lumix-macos-journal-1', 'library_id': library.marker['library_id'],
                   'changes': [], 'sql': [['DROP TABLE photos', []]]}
        with library.catalog.connect() as db:
            db.execute('INSERT INTO operations VALUES(?,?,?,?,NULL)', (uuid.uuid4().hex, 'fixture', 'planned', json.dumps(payload)))
finally:
    library.close()
(recovery / 'Fixture Ready').mkdir(exist_ok=True)

from pianji.domain import PhotoGroup, FileAsset
exports = root / 'build/fixtures/NativeExports'
library = ManagedLibrary.open(exports) if exports.exists() else ManagedLibrary.create(exports)
try:
    sources = root / 'build/fixtures/ExportSources';sources.mkdir(exist_ok=True)
    shutil.copyfile(root/'build/fixtures/UITestSource/JPEG/A.JPG', sources/'A.JPG')
    shutil.copyfile(root/'build/fixtures/UITestSource/Other/B.JPG', sources/'Version 2.JPG')
    (sources/'R.RW2').write_bytes(b'synthetic raw')
    groups = [PhotoGroup(n, '', n, None, [FileAsset(n,n,k,str(sources/f))]) for n,k,f in [('A','jpeg','A.JPG'),('R','raw','R.RW2')]]
    report = library.import_groups(groups,'Exports-'+uuid.uuid4().hex[:8])
    (root/'build/fixtures/export-ui.json').write_text(json.dumps({'root':str(exports),'photo':report['imported'][0],'raw':report['imported'][1],'version':str(sources/'Version 2.JPG')}))
finally:
    library.close()
(exports/'Fixture Ready').mkdir(exist_ok=True)

trash = root / 'build/fixtures/NativeTrash'
library = ManagedLibrary.open(trash) if trash.exists() else ManagedLibrary.create(trash)
try:
    file = root/'build/fixtures/UITestSource/JPEG/A.JPG'
    group = PhotoGroup('t','','Trash Test',None,[FileAsset('t','t','jpeg',str(file))])
    report = library.import_groups([group],'Trash-'+uuid.uuid4().hex[:8])
    (root/'build/fixtures/trash-ui.json').write_text(json.dumps({'root':str(trash),'photo':report['imported'][0],'source':str(file)}))
finally:
    library.close()
(trash/'Fixture Ready').mkdir(exist_ok=True)

purge = root / 'build/fixtures/NativePurge'
library = ManagedLibrary.open(purge) if purge.exists() else ManagedLibrary.create(purge)
try:
    pending = library.catalog.rows('SELECT photo_id FROM purges')
    if pending:
        ident = pending[0]['photo_id']
    else:
        from unittest.mock import patch
        file = root/'build/fixtures/UITestSource/JPEG/A.JPG'
        report = library.import_groups([PhotoGroup('p','','Purge Resume',None,[FileAsset('p','p','jpeg',str(file))])],'Purge-'+uuid.uuid4().hex[:8])
        ident = report['imported'][0];library.trash_photos([ident])
        with patch.object(library.journal.root,'unlink_verified',side_effect=OSError('synthetic UI fixture interruption')):
            library.purge_trash([ident])
    (root/'build/fixtures/purge-ui.json').write_text(json.dumps({'root':str(purge),'photo':ident}))
finally:
    library.close()
(purge/'Fixture Ready').mkdir(exist_ok=True)

recycle = root / ('build/fixtures/整库回收-'+uuid.uuid4().hex[:8])
library = ManagedLibrary.create(recycle)
try:
    file = root/'build/fixtures/UITestSource/JPEG/A.JPG'
    report = library.import_groups([PhotoGroup('recycle','','A',None,[FileAsset('r','recycle','jpeg',str(file))])],'活动')
    (root/'build/fixtures/recycle-ui.json').write_text(json.dumps({'root':str(recycle),'photo':report['imported'][0],'source':str(file)}))
finally:
    library.close()
(recycle/'Fixture Ready').mkdir()
