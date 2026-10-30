from pathlib import Path
import pytest
from PIL import Image
from pianji.library import Library
from pianji.discovery import scan_source

@pytest.fixture
def library(tmp_path):
    source=tmp_path/'SD';source.mkdir();Image.new('RGB',(60,80),'red').save(source/'a.jpg');(source/'a.rw2').write_bytes(b'raw')
    lib=Library(tmp_path/'library');lib.import_groups(scan_source(source),'活动')
    yield lib
    lib.close()

def test_mark_jpeg_finished_and_cancel_keeps_originals_and_files(library):
    p=library.catalog.photos()[0];before={a['id']:Path(a['path']).read_bytes() for a in p['assets']}
    report=library.set_finished([p['id']],True)
    assert not report['errors']
    after=library.catalog.photo(p['id']);assert after['edited'] and after['primary_export_id']
    export=next(a for a in after['assets'] if a['kind']=='export')
    assert Path(export['path']).read_bytes()==next(v for k,v in before.items() if k==next(a['id'] for a in p['assets'] if a['kind']=='jpeg'))
    assert library.set_finished([p['id']],True)['skipped']==1
    report=library.set_finished([p['id']],False);assert not report['errors']
    after=library.catalog.photo(p['id']);assert after['edited'] and not after['primary_export_id']
    assert {a['id']:Path(a['path']).read_bytes() for a in after['assets']}==before
    detached=library.catalog.rows('SELECT * FROM detached_exports')
    assert len(detached)==1 and Path(detached[0]['path']).read_bytes()==Path(next(a['path'] for a in after['assets'] if a['kind']=='jpeg')).read_bytes()
    assert not Path(export['path']).exists()

def test_unlink_one_version_preserves_other_cover_and_editing_state(library,tmp_path):
    p=library.catalog.photos()[0];out=tmp_path/'export.jpg';Image.new('RGB',(10,10),'blue').save(out)
    library.link_export(p['id'],out);first=library.catalog.photo(p['id'])['primary_export_id']
    Image.new('RGB',(10,10),'green').save(out);library.link_export(p['id'],out);second=library.catalog.photo(p['id'])['primary_export_id']
    library.unlink_export(p['id'],second)
    after=library.catalog.photo(p['id']);assert after['primary_export_id']==first and after['edited']
    assert len([a for a in after['assets'] if a['kind']=='export'])==1

def test_unlink_failure_rolls_back_metadata_and_file(library,monkeypatch):
    from pianji import fileops
    p=library.catalog.photos()[0];library.set_finished([p['id']],True);before=library.catalog.photo(p['id'])
    def locked(*args):raise PermissionError('locked')
    monkeypatch.setattr(fileops,'transfer',locked)
    report=library.set_finished([p['id']],False)
    assert report['errors'] and library.catalog.photo(p['id'])['primary_export_id']==before['primary_export_id']
    assert all(Path(a['path']).exists() for a in library.catalog.photo(p['id'])['assets'])

def test_raw_only_cannot_be_mislabeled_as_export(tmp_path):
    src=tmp_path/'sd';src.mkdir();(src/'a.rw2').write_bytes(b'raw')
    lib=Library(tmp_path/'lib');lib.import_groups(scan_source(src),'活动')
    p=lib.catalog.photos()[0];result=lib.set_finished([p['id']],True)
    assert result['errors'] and not lib.catalog.photo(p['id'])['primary_export_id']
    lib.close()

def test_missing_export_can_still_be_unlinked(library):
    photo=library.catalog.photos()[0];library.set_finished([photo['id']],True)
    export=next(a for a in library.catalog.photo(photo['id'])['assets'] if a['kind']=='export');Path(export['path']).unlink()
    result=library.set_finished([photo['id']],False)
    assert not result['errors'] and not library.catalog.photo(photo['id'])['primary_export_id']
