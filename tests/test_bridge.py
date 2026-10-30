from pathlib import Path
from PIL import Image
from pianji.bridge import Bridge
from test_jobs import wait

def test_path_grants_and_dialog_cancel(tmp_path):
    bridge=Bridge(tmp_path/'settings',dialog=lambda *args:None)
    assert not bridge.scan(str(tmp_path))['ok']
    assert bridge.scan(str(tmp_path))['error']['code']=='PATH_NOT_GRANTED'
    assert bridge.choose_source()=={'ok':True,'data':None}
    assert bridge.get_settings()['data'].get('source') is None
    assert not bridge.save_settings({'library':str(tmp_path/'arbitrary')})['ok']
    bridge._jobs.close()

def test_partial_relink_reports_remaining_files(tmp_path):
    import shutil
    src=tmp_path/'source';src.mkdir();Image.new('RGB',(20,20)).save(src/'a.jpg');(src/'a.rw2').write_bytes(b'raw');(src/'a.xmp').write_text('xmp')
    choices=iter([str(tmp_path/'library'),str(tmp_path/'found')])
    bridge=Bridge(tmp_path/'config',dialog=lambda kind:next(choices))
    bridge.choose_library();bridge._lib.import_groups(__import__('pianji.discovery',fromlist=['scan_source']).scan_source(src),'event')
    photo=bridge._lib.catalog.photos()[0];found=tmp_path/'found';found.mkdir()
    for a in photo['assets']:
        path=Path(a['path'])
        if a['kind']!='xmp':shutil.copyfile(path,found/path.name)
        path.unlink()
    result=bridge.relink_missing(photo['id'])
    snapshot=wait(bridge._jobs,result['data']['task_id'])
    assert snapshot['status']=='partial' and len(snapshot['result']['recovered'])==2
    assert len(snapshot['errors'])==1 and '.xmp' in snapshot['errors'][0]['message']
    bridge._close()

def test_real_bridge_import_failure_and_listing(tmp_path):
    src=tmp_path/'source'; src.mkdir(); Image.new('RGB',(20,20)).save(src/'a.jpg')
    choices=iter([str(src),str(tmp_path/'library')])
    bridge=Bridge(tmp_path/'config',dialog=lambda *args:next(choices))
    token=bridge.choose_source()['data']['token']
    assert bridge.choose_library()['ok']
    job=bridge.scan(token)['data']['task_id']; scan=wait(bridge._jobs,job)['result']
    group=scan['photos'][0]
    task=bridge.import_selected(scan['scan_id'],[group['id']],'event','jpeg')['data']['task_id']
    assert wait(bridge._jobs,task)['status']=='succeeded'
    photos=bridge.list_photos({})['data']
    assert len(photos)==1 and photos[0]['stem']=='a'
    assert not bridge.open_photoshop(photos[0]['id'],'raw')['ok']
    assert bridge.get_preview(photos[0]['id'],'thumb')['ok']
    bridge._jobs.close()

def test_bridge_cancellation_reaches_batch_boundary(tmp_path,monkeypatch):
    import threading
    from pianji.discovery import scan_source
    src=tmp_path/'source';src.mkdir()
    for i in range(3):Image.new('RGB',(20,20),(i*50,0,0)).save(src/f'{i}.jpg')
    bridge=Bridge(tmp_path/'config',dialog=lambda kind:str(tmp_path/'library'))
    bridge.choose_library();lib=bridge._lib;lib.import_groups(scan_source(src),'event')
    first=threading.Event();release=threading.Event();original=lib._move;count=[0]
    def move(*args,**kwargs):
        result=original(*args,**kwargs);count[0]+=1
        if count[0]==1:first.set();assert release.wait(5)
        return result
    monkeypatch.setattr(lib,'_move',move)
    ident=bridge.set_edited([p['id'] for p in lib.catalog.photos()],True)['data']['task_id']
    assert first.wait(5);bridge.cancel_task(ident);release.set()
    snapshot=wait(bridge._jobs,ident)
    assert snapshot['status']=='cancelled' and len(snapshot['result']['operations'])==1
    assert sum(p['edited'] for p in lib.catalog.photos())==1
    bridge._close()
