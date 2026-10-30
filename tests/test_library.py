import hashlib
from pathlib import Path
import pytest
from PIL import Image
from pianji.catalog import Catalog
from pianji.discovery import scan_source
from pianji.library import Library

@pytest.fixture
def setup(tmp_path):
    src=tmp_path/'SD'; src.mkdir()
    Image.new('RGB',(80,100),'red').save(src/'A.JPG')
    (src/'A.RW2').write_bytes(b'original RAW')
    (src/'A.xmp').write_text('original xmp')
    lib=Library(tmp_path/'library')
    return src,lib

def test_import_keeps_source_bytes_and_is_idempotent(setup):
    src,lib=setup
    before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in src.iterdir()}
    r=lib.import_groups(scan_source(src),'中文 漫展', 'both')
    assert len(r['imported'])==1 and not r['errors']
    assert before=={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in src.iterdir()}
    assert lib.import_groups(scan_source(src),'中文 漫展','both')['skipped']==1
    assert len(lib.catalog.photos())==1
    assert {a['kind'] for a in lib.catalog.photos()[0]['assets']}=={'jpeg','raw','xmp'}

def test_format_selection(setup):
    src,lib=setup
    lib.import_groups(scan_source(src),'activity','jpeg')
    assert {a['kind'] for a in lib.catalog.photos()[0]['assets']}=={'jpeg'}

def test_collision_never_overwrites(setup):
    src,lib=setup
    lib.import_groups(scan_source(src),'event','both')
    (src/'A.RW2').write_bytes(b'different RAW')
    Image.new('RGB',(80,100),'blue').save(src/'A.JPG')
    lib.import_groups(scan_source(src),'event','both')
    photos=lib.catalog.photos()
    assert len(photos)==2
    paths=[a['path'] for p in photos for a in p['assets']]
    assert len(set(paths))==6 and all(Path(p).is_file() for p in paths)

def test_stage_person_export_and_undo_preserve_links(setup,tmp_path):
    src,lib=setup
    lib.import_groups(scan_source(src),'event','both')
    p=lib.catalog.photos()[0]; person=lib.catalog.add_person(p['activity_id'],'模特 一')
    lib.set_person([p['id']],person['id'])
    op=lib.set_edited([p['id']],True)
    p=lib.catalog.photo(p['id'])
    assert p['edited'] and p['manual_person']
    assert all('已修原片' in a['path'] for a in p['assets'])
    out=tmp_path/'finish.jpg'; Image.new('RGB',(10,10)).save(out)
    lib.link_export(p['id'],out)
    lib.undo_operation(op['operations'][0])
    p=lib.catalog.photo(p['id'])
    assert not p['edited'] and p['primary_export_id']
    assert any(a['kind']=='export' and Path(a['path']).exists() for a in p['assets'])

@pytest.mark.parametrize('name',['../outside','CON','bad.','bad ','a/b'])
def test_path_escape_rejected(setup,name):
    src,lib=setup
    with pytest.raises(ValueError): lib.import_groups(scan_source(src),name,'both')

def test_rename_reserves_destinations_for_duplicate_stems(tmp_path):
    src=tmp_path/'sd';src.mkdir()
    for directory,color in [('a','red'),('b','blue')]:
        folder=src/directory;folder.mkdir();Image.new('RGB',(10,10),color).save(folder/'A.jpg')
    lib=Library(tmp_path/'lib');lib.import_groups(scan_source(src),'event')
    rows=lib.catalog.photos();person=lib.catalog.add_person(rows[0]['activity_id'],'原人物')
    assert not lib.set_person([p['id'] for p in rows],person['id'])['errors']
    lib.rename_person(person['id'],'新人物')
    paths=[Path(a['path']) for p in lib.catalog.photos() for a in p['assets']]
    assert len(set(paths))==2 and all(p.exists() and '新人物' in str(p) for p in paths)
    assert len({p.read_bytes() for p in paths})==2

def test_format_upgrade_preserves_photo_state_and_changed_local_jpeg(setup,tmp_path):
    src,lib=setup
    lib.import_groups(scan_source(src),'event','jpeg')
    photo=lib.catalog.photos()[0];person=lib.catalog.add_person(photo['activity_id'],'模特')
    lib.set_person([photo['id']],person['id']);lib.set_edited([photo['id']],True)
    out=tmp_path/'export.jpg';Image.new('RGB',(20,20),'green').save(out);lib.link_export(photo['id'],out)
    old=lib.catalog.photo(photo['id']);jpeg=next(a for a in old['assets'] if a['kind']=='jpeg');Image.new('RGB',(30,30),'blue').save(jpeg['path'])
    edited_bytes=Path(jpeg['path']).read_bytes()
    report=lib.import_groups(scan_source(src),'event','both')
    rows=lib.catalog.photos()
    assert not report['errors'] and len(rows)==1
    after=rows[0]
    assert after['id']==photo['id'] and after['edited'] and after['manual_person'] and after['person_id']==person['id']
    assert after['primary_export_id']==old['primary_export_id']
    assert {a['kind'] for a in after['assets']}=={'jpeg','raw','xmp','export'}
    assert Path(next(a['path'] for a in after['assets'] if a['kind']=='jpeg')).read_bytes()==edited_bytes
    assert all('已修原片' in a['path'] for a in after['assets'] if a['kind']!='export')
    assert lib.import_groups(scan_source(src),'event','raw')['skipped']==1

def test_cancel_batch_stops_between_photo_groups(tmp_path):
    src=tmp_path/'sd';src.mkdir()
    for i in range(3):Image.new('RGB',(10,10),(i*60,0,0)).save(src/f'{i}.jpg')
    lib=Library(tmp_path/'lib');lib.import_groups(scan_source(src),'event')
    done=[0]
    report=lib.set_edited([p['id'] for p in lib.catalog.photos()],True,cancel=lambda:done[0]>=1,progress=lambda n,t,m:done.__setitem__(0,n))
    assert report['cancelled'] and len(report['operations'])==1
    assert sum(p['edited'] for p in lib.catalog.photos())==1
