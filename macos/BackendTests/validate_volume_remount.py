"""Development-only acceptance for the dedicated mounted disk-image fixture."""
import hashlib
import json
from pathlib import Path
import sys

repository=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repository/'macos/Backend'))
from managed import ManagedLibrary
from pianji.domain import PhotoGroup,FileAsset

host=repository/'build/fixtures/CrossVolumeValidation'
receipt=json.loads((host/'stable-receipt.json').read_text())
root=Path(receipt['root'])
assert root==repository/'build/fixtures/VolumeMount/StableLibrary','Only the dedicated test volume is allowed'
assert not (host/'stable-result.json').exists(),'Already completed; prepare a fresh fixture before repeating'
current=root.stat().st_dev
assert current!=receipt['device_before'],'Remount with a different attachment order first'
library=ManagedLibrary.open(root)
try:
    assert library.marker['volume_uuid']==receipt['volume_uuid']
    recovered=library.recover_pending()
    assert recovered['errors']==[] and len(recovered['recovered'])==1,recovered
    library._ready();assert list(root.rglob('*.partial'))==[]
    purged=library.purge_trash([receipt['trashed_photo']])
    assert purged['errors']==[] and purged['deleted']==[receipt['trashed_photo']],purged
    source=host/'HostSource/Photo.JPG'
    added=library.import_groups([PhotoGroup('c','','AfterRemount',None,[FileAsset('c','c','jpeg',str(source))])],'Stable Volume')
    assert added['errors']==[] and len(added['imported'])==1,added
    for path,(checksum,modified) in receipt['sources'].items():
        file=Path(path)
        assert hashlib.sha256(file.read_bytes()).hexdigest()==checksum and file.stat().st_mtime_ns==modified
    receipt.update(device_after=current,remount_checks='passed')
    (host/'stable-result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Device changed:',receipt['device_before'],'->',current)
    print('Volume reopen, old partial recovery, old trash ownership/purge and new import passed; sources unchanged')
finally:library.close()
