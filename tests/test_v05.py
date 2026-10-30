from pathlib import Path
import pytest
from PIL import Image
from pianji.library import Library
from pianji.discovery import scan_source

@pytest.fixture
def fixture(tmp_path):
    src=tmp_path/'SD';src.mkdir()
    Image.new('RGB',(30,30),'red').save(src/'a.jpg');(src/'a.rw2').write_bytes(b'raw');(src/'a.xmp').write_text('xmp')
    Image.new('RGB',(30,30),'blue').save(src/'b.jpg')
    lib=Library(tmp_path/'library');lib.import_groups(scan_source(src),'event')
    yield src,lib
    lib.close()

def test_permanent_selected_removes_group_versions_not_sources_or_live_photos(fixture):
    src,lib=fixture;before={p.name:p.read_bytes() for p in src.iterdir()};p=next(p for p in lib.catalog.photos() if p['stem']=='a')
    lib.set_finished([p['id']],True);lib.set_finished([p['id']],False);lib.set_finished([p['id']],True);lib.trash_photos([p['id']])
    files=lib.catalog.photo(p['id'],include_trashed=True)['assets']+lib.catalog.rows('SELECT * FROM detached_exports WHERE photo_id=?',(p['id'],))
    result=lib.purge_trash([p['id']]);assert not result['errors'] and result['deleted']==[p['id']]
    assert all(not Path(a['path']).exists() for a in files)
    assert not lib.catalog.photos(trashed=True) and len(lib.catalog.photos())==1
    assert not lib.catalog.rows('SELECT * FROM photos WHERE id=?',(p['id'],)) and not lib.catalog.rows('SELECT * FROM import_members WHERE photo_id=?',(p['id'],))
    assert before=={p.name:p.read_bytes() for p in src.iterdir()}
    assert lib.import_groups(scan_source(src),'event')['imported'],'permanent delete allows explicit reimport'

def test_purge_rejects_live_photo_and_retains_unknown_trash_file(fixture):
    src,lib=fixture;p=lib.catalog.photos()[0];assert lib.purge_trash([p['id']])['errors']
    lib.trash_photos([p['id']]);photo=lib.catalog.photo(p['id'],include_trashed=True)
    unknown=Path(photo['assets'][0]['path']).parent/'unknown.jpg';unknown.write_bytes(b'foreign')
    assert not lib.purge_trash([p['id']])['errors'] and unknown.read_bytes()==b'foreign'

def test_purge_partial_failure_blocks_restore_and_retries_after_reopen(fixture,monkeypatch):
    src,lib=fixture;p=next(p for p in lib.catalog.photos() if p['stem']=='a');lib.trash_photos([p['id']])
    real=Path.unlink;calls=[]
    def locked(path,*args,**kwargs):
        if '回收站' in path.parts:
            calls.append(path)
            if len(calls)==2:raise PermissionError('file in use')
        return real(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',locked);result=lib.purge_trash([p['id']]);assert result['errors'] and not result['deleted']
    assert lib.restore_photos([p['id']])['errors'];root=lib.root;lib.close();monkeypatch.setattr(Path,'unlink',real)
    reopened=Library(root)
    try:
        assert reopened.restore_photos([p['id']])['errors']
        assert not reopened.purge_trash([p['id']])['errors'] and not reopened.catalog.photos(trashed=True)
    finally:reopened.close()

def test_failed_purge_does_not_delete_replacement_file(fixture,monkeypatch):
    src,lib=fixture;p=lib.catalog.photos()[0];lib.trash_photos([p['id']]);asset=lib.catalog.photo(p['id'],include_trashed=True)['assets'][0];path=Path(asset['path'])
    real=Path.unlink
    def locked(p,*args,**kwargs):
        if str(p)==str(path):raise PermissionError('locked')
        return real(p,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',locked);assert lib.purge_trash([p['id']])['errors'];monkeypatch.setattr(Path,'unlink',real)
    path.unlink();path.write_bytes(b'foreign replacement')
    assert lib.purge_trash([p['id']])['errors'] and path.read_bytes()==b'foreign replacement'

def test_first_purge_rejects_file_replaced_before_deletion_plan(fixture):
    src,lib=fixture;p=lib.catalog.photos()[0];lib.trash_photos([p['id']]);path=Path(lib.catalog.photo(p['id'],include_trashed=True)['assets'][0]['path'])
    path.unlink();path.write_bytes(b'foreign before first purge')
    assert lib.purge_trash([p['id']])['errors'] and path.read_bytes()==b'foreign before first purge'

def test_first_purge_rejects_identical_content_replacement_inode(fixture):
    src,lib=fixture;p=lib.catalog.photos()[0];lib.trash_photos([p['id']]);path=Path(lib.catalog.photo(p['id'],include_trashed=True)['assets'][0]['path'])
    owned=path.with_name('owned-original-preserved');path.rename(owned);path.write_bytes(owned.read_bytes())
    assert lib.purge_trash([p['id']])['errors'] and path.exists() and owned.exists()

def test_purge_missing_original_path_does_not_delete_later_foreign_file(fixture):
    src,lib=fixture;p=lib.catalog.photos()[0];asset=p['assets'][0];path=Path(asset['path']);path.unlink();lib.trash_photos([p['id']]);path.write_bytes(b'foreign at old position')
    assert not lib.purge_trash([p['id']])['errors'] and path.read_bytes()==b'foreign at old position'

def test_delete_person_with_missing_asset_preserves_missing_link(fixture):
    src,lib=fixture;p=next(p for p in lib.catalog.photos() if p['stem']=='a');person=lib.catalog.add_person(p['activity_id'],'model');lib.set_person([p['id']],person['id'])
    photo=lib.catalog.photo(p['id']);missing=next(a for a in photo['assets'] if a['kind']=='raw');Path(missing['path']).unlink()
    result=lib.delete_people([person['id']]);assert not result['errors'] and result['deleted_people']==[person['id']]
    after=lib.catalog.photo(p['id']);assert lib.catalog.person(after['person_id'])['role']=='unclassified'
    assert {a['id'] for a in after['assets']}=={a['id'] for a in photo['assets']}
    assert not Path(next(a['path'] for a in after['assets'] if a['id']==missing['id'])).exists()
    assert all('待分类' in a['path'] for a in after['assets'])
