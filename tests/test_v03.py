from pathlib import Path
import pytest
from PIL import Image
from pianji.library import Library
from pianji.discovery import scan_source
from pianji.bridge import Bridge

@pytest.fixture
def fixture(tmp_path):
    src=tmp_path/'SD';(src/'JPEG').mkdir(parents=True);(src/'RAW').mkdir()
    Image.new('RGB',(30,30),'red').save(src/'JPEG'/'a.jpg')
    (src/'RAW'/'a.rw2').write_bytes(b'raw');(src/'RAW'/'a.xmp').write_text('xmp')
    lib=Library(tmp_path/'library')
    yield src,lib
    lib.close()

def test_split_group_jpeg_then_raw_supplements_same_photo(fixture):
    src,lib=fixture;groups=scan_source(src)
    lib.import_groups(groups,'event','jpeg');p=lib.catalog.photos()[0]
    person=lib.catalog.add_person(p['activity_id'],'model');lib.set_person([p['id']],person['id'])
    result=lib.import_groups(groups,'event','raw')
    assert result['updated']==[p['id']] and not result['imported']
    assert len(lib.catalog.photos())==1
    p=lib.catalog.photo(p['id']);assert p['person_id']==person['id'] and p['manual_person']
    assert {a['kind'] for a in p['assets']}=={'jpeg','raw','xmp'}

def test_trash_restores_every_file_and_preserves_sources(fixture):
    src,lib=fixture;before={str(p):p.read_bytes() for p in src.rglob('*') if p.is_file()}
    lib.import_groups(scan_source(src),'event');p=lib.catalog.photos()[0]
    lib.set_finished([p['id']],True);lib.set_finished([p['id']],False);lib.set_finished([p['id']],True)
    original=lib.catalog.photo(p['id']);payload={a['id']:Path(a['path']).read_bytes() for a in original['assets']}
    detached=lib.catalog.rows('SELECT * FROM detached_exports')[0];old_detached=detached['path']
    r=lib.trash_photos([p['id']]);assert not r['errors'] and not lib.catalog.photos()
    assert len(lib.catalog.photos(trashed=True))==1 and not Path(old_detached).exists()
    assert all('回收站' in a['path'] and Path(a['path']).is_file() for a in lib.catalog.photos(trashed=True)[0]['assets'])
    assert lib.set_edited([p['id']],False)['errors']
    assert lib.import_groups(scan_source(src),'event')['errors'],'reimport must ask to restore, not silently skip trash'
    assert not lib.restore_photos([p['id']])['errors']
    restored=lib.catalog.photo(p['id']);assert restored['primary_export_id']==original['primary_export_id'] and restored['edited']
    assert {a['id']:Path(a['path']).read_bytes() for a in restored['assets']}==payload
    assert Path(old_detached).exists() and not lib.catalog.photos(trashed=True)
    assert before=={str(p):p.read_bytes() for p in src.rglob('*') if p.is_file()}

def test_trash_failure_is_atomic(fixture,monkeypatch):
    from pianji import fileops
    src,lib=fixture;lib.import_groups(scan_source(src),'event');p=lib.catalog.photos()[0]
    original=fileops.transfer;calls=[]
    def fail_second(*args):
        calls.append(1)
        if len(calls)==2:raise PermissionError('file in use')
        return original(*args)
    monkeypatch.setattr(fileops,'transfer',fail_second)
    assert lib.trash_photos([p['id']])['errors']
    assert len(lib.catalog.photos())==1 and not lib.catalog.photos(trashed=True)
    assert all(Path(a['path']).exists() for a in p['assets'])

def test_restore_collision_and_missing_files(fixture):
    src,lib=fixture;lib.import_groups(scan_source(src),'event');p=lib.catalog.photos()[0]
    missing=next(a for a in p['assets'] if a['kind']=='raw');Path(missing['path']).unlink()
    jpeg=next(a for a in p['assets'] if a['kind']=='jpeg');assert not lib.trash_photos([p['id']])['errors']
    Path(jpeg['path']).write_bytes(b'foreign')
    assert not lib.restore_photos([p['id']])['errors']
    restored=lib.catalog.photo(p['id']);assert Path(jpeg['path']).read_bytes()==b'foreign'
    assert next(a for a in restored['assets'] if a['kind']=='jpeg')['path']!=jpeg['path']
    assert not Path(next(a for a in restored['assets'] if a['kind']=='raw')['path']).exists()

def test_new_library_recents_and_grants(tmp_path):
    parent=tmp_path/'parent';parent.mkdir();bridge=Bridge(tmp_path/'config',dialog=lambda kind:str(parent))
    try:
        assert not bridge.create_library('arbitrary','a')['ok']
        grant=bridge.choose_library_parent()['data'];assert grant['path']==str(parent)
        result=bridge.create_library(grant['token'],'我的照片库');assert result['ok']
        root=parent/'我的照片库';assert (root/'.片集'/'catalog.sqlite3').exists()
        assert bridge.list_libraries()['data'][0]['current']
        assert not bridge.create_library(grant['token'],'我的照片库')['ok']
        assert not bridge.create_library(grant['token'],'../bad')['ok']
        assert bridge.create_library(grant['token'],'第二个')['ok']
        assert bridge.open_library(str(root))['ok']
        assert not bridge.open_library(str(tmp_path/'unknown'))['ok']
        assert bridge.remove_recent_library(str(parent/'第二个'))['ok']
        assert (parent/'第二个'/'.片集'/'catalog.sqlite3').is_file()
    finally:bridge._close()
    again=Bridge(tmp_path/'config')
    assert again.get_settings()['data']['library_available'] and len(again.list_libraries()['data'])==1
    again._close()

def test_new_library_rejects_source_overlap_and_cancel(tmp_path):
    source=tmp_path/'source';source.mkdir();bridge=Bridge(tmp_path/'config',dialog=lambda kind:str(source))
    try:
        bridge.choose_source();grant=bridge.choose_library_parent()['data']
        assert not bridge.create_library(grant['token'],'inside-source')['ok']
        assert not (source/'inside-source').exists()
        bridge._dialog=lambda kind:None
        assert bridge.choose_library_parent()['data'] is None
    finally:bridge._close()

def test_selected_jpeg_import_ignores_unreadable_unselected_raw(fixture,monkeypatch):
    from pianji import library
    src,lib=fixture;groups=scan_source(src);original=library.digest
    def denied(path):
        if Path(path).suffix.lower()=='.rw2':raise PermissionError('raw card unavailable')
        return original(path)
    monkeypatch.setattr(library,'digest',denied)
    result=lib.import_groups(groups,'event','jpeg')
    assert not result['errors'] and len(result['imported'])==1

def test_restore_after_person_rename_and_merge(fixture):
    src,lib=fixture;lib.import_groups(scan_source(src),'event');p=lib.catalog.photos()[0]
    first=lib.catalog.add_person(p['activity_id'],'first');second=lib.catalog.add_person(p['activity_id'],'second')
    lib.set_person([p['id']],first['id']);lib.trash_photos([p['id']]);lib.rename_person(first['id'],'renamed')
    lib.merge_people(first['id'],second['id']);assert not lib.restore_photos([p['id']])['errors']
    p=lib.catalog.photo(p['id']);assert p['person_id']==second['id'] and all('second' in a['path'] for a in p['assets'])

def test_new_library_cannot_nest_inside_current(tmp_path):
    bridge=Bridge(tmp_path/'config',dialog=lambda kind:str(tmp_path/'lib'))
    try:
        bridge.choose_library();grant=bridge.choose_library_parent()['data']
        assert not bridge.create_library(grant['token'],'nested')['ok']
        assert not (tmp_path/'lib'/'nested').exists()
    finally:bridge._close()

def test_missing_detached_version_restores_original_location_record(fixture):
    src,lib=fixture;lib.import_groups(scan_source(src),'event');p=lib.catalog.photos()[0]
    lib.set_finished([p['id']],True);lib.set_finished([p['id']],False)
    original=lib.catalog.rows('SELECT * FROM detached_exports')[0]
    lib.trash_photos([p['id']]);trashed=lib.catalog.rows('SELECT * FROM detached_exports')[0];Path(trashed['path']).unlink()
    assert not lib.restore_photos([p['id']])['errors']
    after=lib.catalog.rows('SELECT * FROM detached_exports')[0]
    assert after['path']==original['path'] and not Path(after['path']).exists()

def test_remove_unavailable_startup_library_record(tmp_path):
    import json
    config=tmp_path/'config';config.mkdir();missing=str(tmp_path/'missing')
    (config/'settings.json').write_text(json.dumps({'library':missing,'recent_libraries':[missing]}))
    bridge=Bridge(config)
    try:
        assert len(bridge.list_libraries()['data'])==1 and not bridge.get_settings()['data']['library_available']
        assert bridge.remove_recent_library(missing)['ok']
        assert bridge.list_libraries()['data']==[]
    finally:bridge._close()
