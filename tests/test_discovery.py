from pathlib import Path
from PIL import Image
from pianji.discovery import scan_source

def jpg(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (80, 100), 'red').save(path)

def test_pairs_same_stem_case_insensitive(tmp_path):
    jpg(tmp_path/'A.JPG'); (tmp_path/'a.RW2').write_bytes(b'raw')
    (tmp_path/'a.xmp').write_text('metadata')
    groups = scan_source(tmp_path)
    assert len(groups) == 1
    assert {f.kind for f in groups[0].files} == {'jpeg','raw','xmp'}
    assert groups[0].captured_at is None

def test_different_directories_do_not_pair(tmp_path):
    jpg(tmp_path/'a'/'A.JPG'); jpg(tmp_path/'b'/'A.JPG')
    assert len(scan_source(tmp_path)) == 2

def test_corrupt_photo_does_not_stop_scan(tmp_path):
    jpg(tmp_path/'good.jpg'); (tmp_path/'bad.jpg').write_bytes(b'broken')
    groups = scan_source(tmp_path)
    assert len(groups) == 2
    assert next(g for g in groups if g.stem=='bad').error
