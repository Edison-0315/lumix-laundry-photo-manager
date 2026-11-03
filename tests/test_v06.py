from pathlib import Path
from PIL.TiffImagePlugin import IFDRational as Fraction
import pytest
from PIL import Image
from pianji.library import Library
from pianji.discovery import scan_source
from pianji.bridge import Bridge
from test_jobs import wait


@pytest.fixture
def fixture(tmp_path):
    source=tmp_path/'SD';source.mkdir()
    exif=Image.Exif();exif[271]='Panasonic';exif[272]='DC-S5M2'
    exif[34665]={36867:'2026:10:28 12:34:56',33434:Fraction(1,250),33437:Fraction(28,10),34855:640,37386:Fraction(85),42036:'LUMIX S 85/F1.8'}
    Image.new('RGB',(40,40),'red').save(source/'a.jpg',exif=exif)
    (source/'a.rw2').write_bytes(b'owned fake raw');(source/'a.xmp').write_text('owned xmp')
    Image.new('RGB',(40,40),'blue').save(source/'b.jpg')
    lib=Library(tmp_path/'library');lib.import_groups(scan_source(source),'event')
    yield source,lib
    lib.close()


def test_delete_activity_moves_all_versions_to_trash_and_restore_revives(fixture):
    source,lib=fixture;before={p.name:p.read_bytes() for p in source.iterdir()};act=lib.catalog.activities()[0]
    photo=next(p for p in lib.catalog.photos() if p['stem']=='a')
    lib.set_finished([photo['id']],True);lib.set_finished([photo['id']],False)
    unknown=lib.root/'event'/'do-not-delete.txt';unknown.write_text('foreign')
    result=lib.delete_activity(act['id'])
    assert not result['errors'] and result['deleted_activity']==act['id']
    assert not lib.catalog.activities() and not lib.catalog.photos()
    assert len(lib.catalog.photos(trashed=True))==2 and unknown.read_text()=='foreign'
    assert not lib.restore_photos([photo['id']])['errors']
    assert lib.catalog.activities()[0]['id']==act['id'] and len(lib.catalog.photos())==1
    assert before=={p.name:p.read_bytes() for p in source.iterdir()}


def test_delete_activity_cancellation_or_file_failure_keeps_it_visible(fixture,monkeypatch):
    _,lib=fixture;act=lib.catalog.activities()[0]
    assert lib.delete_activity(act['id'],cancel=lambda:True)['cancelled']
    assert lib.catalog.activities() and len(lib.catalog.photos())==2
    real=lib.journal.execute
    def fail(kind,*args,**kwargs):
        if kind=='trash':raise PermissionError('locked')
        return real(kind,*args,**kwargs)
    monkeypatch.setattr(lib.journal,'execute',fail)
    assert lib.delete_activity(act['id'])['errors']
    assert lib.catalog.activities() and len(lib.catalog.photos())==2


def test_deleted_activity_missing_assets_existing_trash_and_reimport_guard(fixture):
    source,lib=fixture;act=lib.catalog.activities()[0];photos=lib.catalog.photos()
    lib.trash_photos([photos[0]['id']]);Path(photos[1]['assets'][0]['path']).unlink()
    assert not lib.delete_activity(act['id'])['errors']
    with pytest.raises(ValueError,match='回收站'):
        lib.import_groups(scan_source(source),'event')
    assert not lib.restore_photos([photos[1]['id']])['errors']
    assert lib.catalog.activities() and len(lib.catalog.photos())==1


def test_recreate_empty_deleted_activity(fixture):
    _,lib=fixture;act=lib.create_activity('empty')
    assert not lib.delete_activity(act['id'])['errors']
    assert lib.create_activity('empty')['id']==act['id']


def test_details_real_exif_sizes_source_and_library_and_missing_fallback(fixture,tmp_path):
    source,lib=fixture
    bridge=Bridge(tmp_path/'config',dialog=lambda kind:str(source));bridge._lib=lib
    try:
        scan=wait(bridge._jobs,bridge.scan(bridge.choose_source()['data']['token'])['data']['task_id'])['result']
        group=next(p for p in scan['photos'] if p['stem']=='a')
        details=bridge.get_photo_details(group['id'],scan['scan_id'])['data']
        assert details['camera']=='Panasonic DC-S5M2' and details['focal_length']=='85 mm'
        assert details['captured_at']=='2026-10-28 12:34:56' and details['lens']=='LUMIX S 85/F1.8'
        assert details['aperture']=='f/2.8' and details['shutter']=='1/250 s' and details['iso']=='640'
        assert details['total_bytes']==sum(p.stat().st_size for p in source.glob('a.*'))
        photo=next(p for p in lib.catalog.photos() if p['stem']=='a')
        assert bridge.get_photo_details(photo['id'])['data']['camera']==details['camera']
        for a in photo['assets']:Path(a['path']).unlink()
        missing=bridge.get_photo_details(photo['id'])['data']
        assert missing['total_bytes'] is None and missing['errors']
        assert not bridge.get_photo_details('invalid','invalid')['ok']
    finally:bridge._jobs.close();bridge._previews.shutdown(wait=True)


def test_raw_metadata_fallback_does_not_require_renderable_raw(fixture,monkeypatch,tmp_path):
    from pianji import metadata
    from exifread.core.ifd_tag import IfdTag
    from exifread.utils import Ratio
    _,lib=fixture;photo=next(p for p in lib.catalog.photos() if p['stem']=='a')
    for a in photo['assets']:
        if a['kind']=='jpeg':Path(a['path']).unlink()
    # Raw parser values, including rational tags, must be handled without raw decoding.
    monkeypatch.setattr(metadata.exifread,'process_file',lambda *a,**k:{
        'Image Model':IfdTag('DC-S5M2',272,2,[],0,0),
        'EXIF FocalLength':IfdTag('85',37386,5,[Ratio(85,1)],0,0),
        'EXIF ExposureTime':IfdTag('1/125',33434,5,[Ratio(1,125)],0,0)})
    details=metadata.photo_details(photo['assets'],photo['captured_at'])
    assert details['camera']=='DC-S5M2' and details['focal_length']=='85 mm' and details['shutter']=='1/125 s'


def test_bridge_delete_activity_retains_name_for_trash_listing(fixture,tmp_path):
    _,lib=fixture;bridge=Bridge(tmp_path/'config');bridge._lib=lib;act=lib.catalog.activities()[0]
    try:
        task=bridge.delete_activity(act['id'])['data']['task_id']
        assert wait(bridge._jobs,task)['status']=='succeeded'
        assert not bridge.list_activities()['data']
        assert {p['activity_name'] for p in bridge.list_photos({'trashed':True})['data']}=={'event'}
    finally:bridge._jobs.close();bridge._previews.shutdown(wait=True)


def test_partial_activity_delete_keeps_remaining_photos_and_activity(fixture,monkeypatch):
    _,lib=fixture;act=lib.catalog.activities()[0];photos=lib.catalog.photos();real=lib.journal.execute;calls=[]
    def one_locked(kind,*args,**kwargs):
        if kind=='trash':
            calls.append(kind)
            if len(calls)==2:raise PermissionError('second group locked')
        return real(kind,*args,**kwargs)
    monkeypatch.setattr(lib.journal,'execute',one_locked)
    result=lib.delete_activity(act['id'])
    assert result['errors'] and not result['deleted_activity']
    assert len(lib.catalog.photos())==1 and len(lib.catalog.photos(trashed=True))==1 and lib.catalog.activities()
    monkeypatch.setattr(lib.journal,'execute',real)
    assert not lib.delete_activity(act['id'])['errors'] and not lib.catalog.activities()
    assert not lib.restore_photos([p['id'] for p in photos])['errors'] and len(lib.catalog.photos())==2


def test_metadata_file_read_lease_delays_move(fixture,monkeypatch,tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from pianji import metadata
    _,lib=fixture;photo=lib.catalog.photos()[0];bridge=Bridge(tmp_path/'config');bridge._lib=lib
    opened=threading.Event();release=threading.Event();moved=threading.Event();original=metadata._read
    def hold(path):
        opened.set();assert release.wait(5);return original(path)
    monkeypatch.setattr(metadata,'_read',hold)
    def move():
        try:return lib.set_edited([photo['id']],True)
        finally:moved.set()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reading=pool.submit(bridge.get_photo_details,photo['id']);assert opened.wait(5)
            moving=pool.submit(move)
            try:assert not moved.wait(.2)
            finally:release.set()
            assert reading.result()['ok'] and not moving.result()['errors']
    finally:bridge._jobs.close();bridge._previews.shutdown(wait=True)


def test_empty_numeric_exif_tag_keeps_other_valid_fields(tmp_path):
    from pianji.metadata import photo_details
    exif=Image.Exif();exif[271]='Panasonic';exif[272]='DC-S5M2'
    exif[34665]={36867:'2026:10:28 12:34:56',34855:640,37386:()}
    photo=tmp_path/'empty-focal.jpg';Image.new('RGB',(20,20)).save(photo,exif=exif)
    details=photo_details([{'kind':'jpeg','path':str(photo)}])
    assert details['camera']=='Panasonic DC-S5M2' and details['iso']=='640'
    assert details['captured_at']=='2026-10-28 12:34:56' and details['focal_length'] is None
    assert not details['errors']

