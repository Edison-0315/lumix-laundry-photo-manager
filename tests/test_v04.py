from pathlib import Path
import pytest
from PIL import Image
from pianji.discovery import scan_source
from pianji.library import Library
from pianji.bridge import Bridge
from test_jobs import wait

def image(p):
    p.parent.mkdir(parents=True,exist_ok=True);Image.new('RGB',(30,30),'red').save(p)

def corrupt(path):
    e=OSError(1392,'文件或目录损坏且无法读取',str(path));e.winerror=1392;return e

def test_one_corrupt_file_does_not_abort_good_jpeg_or_raw(tmp_path,monkeypatch):
    image(tmp_path/'JPEG'/'good.jpg');image(tmp_path/'JPEG'/'bad.jpg');(tmp_path/'RAW').mkdir();(tmp_path/'RAW'/'good.rw2').write_bytes(b'raw')
    original=Path.is_symlink
    def check(p):
        if p.name=='bad.jpg':raise corrupt(p)
        return original(p)
    monkeypatch.setattr(Path,'is_symlink',check);errors=[]
    groups=scan_source(tmp_path,errors=errors)
    assert len(groups)==1 and {f.kind for f in groups[0].files}=={'jpeg','raw'}
    assert errors[0]['winerror']==1392 and errors[0]['path'].endswith('bad.jpg')

def test_corrupt_directory_and_unselected_format_are_isolated(tmp_path,monkeypatch):
    image(tmp_path/'JPEG'/'good.jpg');(tmp_path/'RAW').mkdir();(tmp_path/'RAW'/'bad.rw2').write_bytes(b'raw')
    original=Path.is_junction;seen=[]
    def junction(p):
        if p.name=='RAW':raise corrupt(p)
        return original(p)
    monkeypatch.setattr(Path,'is_junction',junction);errors=[]
    assert len(scan_source(tmp_path,errors=errors,formats='jpeg'))==1 and errors[0]['path'].endswith('RAW')
    monkeypatch.setattr(Path,'is_junction',original);symlink=Path.is_symlink
    def filecheck(p):
        if p.name=='bad.rw2':seen.append(p);raise corrupt(p)
        return symlink(p)
    monkeypatch.setattr(Path,'is_symlink',filecheck)
    assert len(scan_source(tmp_path,formats='jpeg'))==1 and not seen

def test_unreadable_directory_enumeration_reported(tmp_path,monkeypatch):
    from pianji import discovery
    image(tmp_path/'good.jpg');original=discovery.os.walk
    def walk(root,**kwargs):
        kwargs['onerror'](corrupt(tmp_path/'broken'));yield from original(root,**kwargs)
    monkeypatch.setattr(discovery.os,'walk',walk);errors=[]
    assert len(scan_source(tmp_path,errors=errors))==1 and errors[0]['operation']=='枚举文件夹'

def test_bridge_partial_scan_publishes_good_results_but_all_failed_does_not(tmp_path,monkeypatch):
    from pianji import discovery
    image(tmp_path/'source'/'good.jpg');image(tmp_path/'source'/'bad.jpg');bridge=Bridge(tmp_path/'config',dialog=lambda kind:str(tmp_path/'source'))
    try:
        token=bridge.choose_source()['data']['token'];original=Path.is_symlink
        def bad(p):
            if p.suffix=='.jpg' and (p.name=='bad.jpg' or all_bad[0]):raise corrupt(p)
            return original(p)
        all_bad=[False];monkeypatch.setattr(Path,'is_symlink',bad)
        result=wait(bridge._jobs,bridge.scan(token,'jpeg')['data']['task_id']);assert result['status']=='partial'
        assert len(result['result']['photos'])==1 and result['result']['scan_id'] in bridge._scans
        old=set(bridge._scans);all_bad[0]=True
        result=wait(bridge._jobs,bridge.scan(token,'jpeg')['data']['task_id'])
        assert result['status']=='partial' and not result['result'].get('scan_id') and set(bridge._scans)==old
    finally:bridge._close()

def test_create_activity_explicit_and_duplicate_protection(tmp_path):
    bridge=Bridge(tmp_path/'config',dialog=lambda kind:str(tmp_path/'library'));bridge.choose_library()
    try:
        result=bridge.create_activity('新 活动');assert result['ok'];activity=result['data']
        assert (tmp_path/'library'/'新 活动').is_dir()
        assert {p['role'] for p in bridge.list_people(activity['id'])['data']}=={'group','unclassified'}
        assert not bridge.create_activity('新 活动')['ok'] and not bridge.create_activity('../bad')['ok']
        assert len(bridge.list_activities()['data'])==1
    finally:bridge._close()

def test_delete_people_keeps_photos_and_trash_and_protects_fixed_roles(tmp_path):
    image(tmp_path/'source'/'a.jpg');lib=Library(tmp_path/'library');lib.import_groups(scan_source(tmp_path/'source'),'event')
    try:
        p=lib.catalog.photos()[0];person=lib.catalog.add_person(p['activity_id'],'model');lib.set_person([p['id']],person['id'])
        lib.trash_photos([p['id']]);result=lib.delete_people([person['id']]);assert not result['errors']
        assert not any(row['id']==person['id'] for row in lib.catalog.people(p['activity_id']))
        assert not lib.restore_photos([p['id']])['errors']
        p=lib.catalog.photo(p['id']);assert lib.catalog.person(p['person_id'])['role']=='unclassified'
        assert all(Path(a['path']).is_file() for a in p['assets'])
        assert lib.delete_people([p['person_id']])['errors']
    finally:lib.close()

def test_delete_person_move_failure_keeps_classification(tmp_path,monkeypatch):
    from pianji import fileops
    image(tmp_path/'source'/'a.jpg');lib=Library(tmp_path/'library');lib.import_groups(scan_source(tmp_path/'source'),'event')
    try:
        p=lib.catalog.photos()[0];person=lib.catalog.add_person(p['activity_id'],'model');lib.set_person([p['id']],person['id'])
        def locked(*args):raise PermissionError('locked')
        monkeypatch.setattr(fileops,'transfer',locked)
        assert lib.delete_people([person['id']])['errors']
        assert lib.catalog.person(person['id']) and lib.catalog.photo(p['id'])['person_id']==person['id']
        assert lib.delete_people([person['id']],cancel=lambda:True)['cancelled']
    finally:lib.close()
