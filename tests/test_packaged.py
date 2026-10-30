import os
import json
import hashlib
from pathlib import Path
import pytest

@pytest.mark.skipif(not os.environ.get('PIANJI_BUNDLE'),reason='packaged artifact is checked explicitly after building')
def test_packaged_manifest():
    root=Path(os.environ['PIANJI_BUNDLE'])
    assert (root/'片集.exe').is_file()
    resources=root/'_internal'
    assert (resources/'pianji/ui/index.html').is_file()
    assert (resources/'THIRD-PARTY-NOTICES.md').is_file()
    assert (resources/'licenses').is_dir()
    manifest=json.loads((resources/'models/manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['models']:
        assert hashlib.sha256((resources/'models'/entry['filename']).read_bytes()).hexdigest()==entry['sha256']
        assert (resources/'models'/entry['license']).is_file()
    forbidden={'.venv','venv','photo-manager-venv','tests','__pycache__','.git','portrait-a.jpg','catalog.sqlite3','settings.json'}
    assert not any(p.name in forbidden for p in root.rglob('*'))
