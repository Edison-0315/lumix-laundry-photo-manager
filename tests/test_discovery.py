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

def test_cancel_stops_metadata_reads_between_files(tmp_path):
    for n in range(12):jpg(tmp_path/f'{n:02}.jpg')
    processed=[]
    scan_source(tmp_path,cancel=lambda:len(processed)>=1,progress=lambda n,t,m:processed.append(n) if n>0 else None)
    assert processed==[1]

def test_format_subfolders_pair_but_remain_readable_independently(tmp_path):
    jpg(tmp_path/'DCIM'/'JPEG'/'A.JPG')
    raw=tmp_path/'DCIM'/'RAW';raw.mkdir();(raw/'a.RW2').write_bytes(b'raw');(raw/'a.xmp').write_text('xmp')
    groups=scan_source(tmp_path)
    assert len(groups)==1
    assert {a.kind for a in groups[0].files}=={'jpeg','raw','xmp'}
    assert len(scan_source(raw))==1 and {a.kind for a in scan_source(raw)[0].files}=={'raw','xmp'}
    assert {a.kind for a in scan_source(tmp_path/'DCIM'/'JPEG')[0].files}=={'jpeg'}

def test_unrelated_or_ambiguous_split_names_are_not_paired(tmp_path):
    jpg(tmp_path/'first'/'A.JPG');(tmp_path/'second').mkdir();(tmp_path/'second'/'A.RW2').write_bytes(b'raw')
    assert len(scan_source(tmp_path))==2
    jpg(tmp_path/'JPEG'/'B.jpg');jpg(tmp_path/'JPG'/'B.jpg');(tmp_path/'RAW').mkdir();(tmp_path/'RAW'/'B.rw2').write_bytes(b'raw')
    assert len(scan_source(tmp_path))==5
