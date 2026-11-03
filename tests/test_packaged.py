import os
import json
import hashlib
from pathlib import Path
import pytest

@pytest.mark.skipif(not os.environ.get('PIANJI_BUNDLE'),reason='packaged artifact is checked explicitly after building')
def test_packaged_manifest():
    root=Path(os.environ['PIANJI_BUNDLE'])
    assert (root/'洗衣机管理器.exe').is_file()
    resources=root/'_internal'
    assert (resources/'pianji/ui/index.html').is_file()
    assert (resources/'pianji/ui/lumix.ico').is_file()
    assert (resources/'pianji/ui/glass.css').is_file() and (resources/'pianji/ui/icons.js').is_file()
    assert (resources/'pianji/ui/viewer.js').is_file() and (resources/'pianji/ui/motion.js').is_file()
    assert all((resources/'pianji/ui'/name).is_file() for name in ('glass.js','glass-optics.js','chrome-motion.js'))
    assert all((resources/'pianji/ui'/name).is_file() for name in ('pearl.css','sidebar-motion.js'))
    assert (resources/'pianji/ui/workspace-motion.js').is_file()
    # Every nested module must be delivered, with the exact verified source bytes.
    source_ui=Path(__file__).resolve().parents[1]/'pianji/ui'
    for source in source_ui.rglob('*'):
        if source.is_file():
            bundled=resources/'pianji/ui'/source.relative_to(source_ui)
            assert bundled.is_file(),f'Missing UI resource: {bundled}'
            assert bundled.read_bytes()==source.read_bytes(),f'Stale UI resource: {bundled}'
    assert (resources/'THIRD-PARTY-NOTICES.md').is_file()
    assert (resources/'licenses').is_dir()
    manifest=json.loads((resources/'models/manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['models']:
        assert hashlib.sha256((resources/'models'/entry['filename']).read_bytes()).hexdigest()==entry['sha256']
        assert (resources/'models'/entry['license']).is_file()
    forbidden={'.venv','venv','photo-manager-venv','tests','__pycache__','.git','portrait-a.jpg','catalog.sqlite3','settings.json'}
    assert not any(p.name in forbidden for p in root.rglob('*'))
