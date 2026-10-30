from pathlib import Path
import pytest
from pianji.library import Library
from pianji.discovery import scan_source
from PIL import Image

def fixture(tmp_path):
    src=tmp_path/'sd'; src.mkdir()
    Image.new('RGB',(10,10)).save(src/'A.jpg'); (src/'A.rw2').write_bytes(b'raw')
    lib=Library(tmp_path/'lib'); lib.import_groups(scan_source(src),'活动','both')
    return lib,lib.catalog.photos()[0]

def test_locked_member_rolls_back_or_stays_pending(tmp_path,monkeypatch):
    lib,p=fixture(tmp_path)
    from pianji import fileops
    original=fileops.transfer
    count=[0]
    def fail(src,dst,move):
        count[0]+=1
        if count[0]==2: raise PermissionError('locked')
        return original(src,dst,move)
    monkeypatch.setattr(fileops,'transfer',fail)
    result=lib.set_edited([p['id']],True)
    assert result['errors'] and not lib.catalog.photo(p['id'])['edited']
    monkeypatch.setattr(fileops,'transfer',original)
    lib.recover_pending()
    after=lib.catalog.photo(p['id'])
    assert all(Path(a['path']).is_file() for a in after['assets'])

def test_cancel_preserves_completed(tmp_path):
    src=tmp_path/'sd'; src.mkdir()
    for n in range(3): Image.new('RGB',(10,10),(n*50,0,0)).save(src/f'{n}.jpg')
    lib=Library(tmp_path/'lib'); done=[0]
    result=lib.import_groups(scan_source(src),'活动','both',lambda:done[0]>=1,lambda n,t,m:done.__setitem__(0,n))
    assert len(result['imported'])==1 and result['cancelled']
    assert len(lib.catalog.photos())==1 and len(list(src.glob('*.jpg')))==3

def test_disk_full_never_publishes_incomplete_group(tmp_path,monkeypatch):
    from pianji import fileops
    src=tmp_path/'sd'; src.mkdir()
    Image.new('RGB',(10,10)).save(src/'a.jpg'); (src/'a.rw2').write_bytes(b'raw')
    lib=Library(tmp_path/'lib')
    original=fileops.transfer; calls=[0]
    def full(s,d,m):
        calls[0]+=1
        if calls[0]==2: raise OSError('disk full')
        return original(s,d,m)
    monkeypatch.setattr(fileops,'transfer',full)
    result=lib.import_groups(scan_source(src),'event','both')
    assert result['errors'] and lib.catalog.photos()==[]
    assert len(list(src.iterdir()))==2

def test_recover_after_partial_group_move(tmp_path):
    import json,os
    from pianji.fileops import digest
    lib,p=fixture(tmp_path)
    changes=[]
    for a in p['assets']:
        dst=str(Path(a['path']).parent.parent.parent/'已修原片'/Path(a['path']).parent.name/Path(a['path']).name)
        changes.append({'src':a['path'],'dst':dst,'temp':dst+'.op.partial','sha256':digest(a['path']),'move':True,'identity':list((Path(a['path']).stat().st_dev,Path(a['path']).stat().st_ino))})
    with lib.catalog.connect() as db:db.execute('INSERT INTO operations VALUES(?,?,?,?,NULL)',('crash','move','running',json.dumps({'changes':changes,'sql':[]})))
    Path(changes[0]['dst']).parent.mkdir(parents=True,exist_ok=True);os.rename(changes[0]['src'],changes[0]['dst'])
    # Simulate process termination releasing the library lock.
    lib.close()
    reopened=Library(lib.root)
    assert not reopened.recovery['errors']
    assert all(Path(a['path']).is_file() for a in reopened.catalog.photo(p['id'])['assets'])
    assert not reopened.catalog.photo(p['id'])['edited']

def test_rollback_does_not_remove_unowned_destination(tmp_path,monkeypatch):
    from pianji import fileops
    lib,p=fixture(tmp_path)
    original=fileops.transfer
    def competing(src,dst,move):
        dst=Path(dst);dst.parent.mkdir(parents=True,exist_ok=True)
        if move:
            dst.write_bytes(Path(src).read_bytes())
            raise FileExistsError('external file created after planning')
        return original(src,dst,move)
    monkeypatch.setattr(fileops,'transfer',competing)
    result=lib.set_edited([p['id']],True)
    assert result['errors']
    external=list(lib.root.glob('*/待分类/已修原片/JPEG/*.jpg'))
    assert len(external)==1 and external[0].is_file()

def test_changed_xmp_can_be_archived_without_losing_new_edits(tmp_path):
    lib,p=fixture(tmp_path)
    raw=next(a for a in p['assets'] if a['kind']=='raw')
    Path(raw['path']).write_bytes(b'edited original content')
    result=lib.set_edited([p['id']],True)
    assert not result['errors']
    after=lib.catalog.photo(p['id'])
    assert after['edited']
    assert Path(next(a['path'] for a in after['assets'] if a['kind']=='raw')).read_bytes()==b'edited original content'

def test_copy_rollback_keeps_foreign_file_created_after_plan(tmp_path,monkeypatch):
    from pianji import fileops
    src=tmp_path/'sd';src.mkdir();Image.new('RGB',(10,10)).save(src/'a.jpg')
    lib=Library(tmp_path/'lib');foreign=[]
    def competing(s,d,m):
        dst=Path(d);dst.parent.mkdir(parents=True,exist_ok=True)
        final=dst.with_name(dst.name.rsplit('.',2)[0]);final.write_bytes(Path(s).read_bytes());foreign.append(final)
        raise OSError('failed before our file was created')
    monkeypatch.setattr(fileops,'transfer',competing)
    lib.import_groups(scan_source(src),'event','both')
    assert foreign[0].is_file()

def test_second_instance_cannot_recover_active_library(tmp_path):
    import subprocess,sys
    lib,p=fixture(tmp_path)
    with pytest.raises(ValueError,match='已.*打开'): Library(lib.root)
    code="from pianji.library import Library; import sys;\ntry: Library(sys.argv[1])\nexcept ValueError: sys.exit(0)\nelse: sys.exit(2)"
    process=subprocess.run([sys.executable,'-c',code,str(lib.root)],capture_output=True)
    assert process.returncode==0,process.stderr.decode(errors='replace')
    lib.close()
    reopened=Library(lib.root)
    assert all(Path(a['path']).is_file() for a in reopened.catalog.photo(p['id'])['assets'])
