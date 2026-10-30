"""Explicit opt-in packaged/native diagnostic using only a marked temp fixture."""
from pathlib import Path
import json
import time
import hashlib
import traceback
from .bridge import Bridge
from .app import resource_root

def run(root):
    root=root.resolve()
    if not (root/'_pianji_test_fixture').is_file(): raise ValueError('Self-test requires a marked development fixture')
    import webview
    result={'ok':False,'checks':[]}
    source=root/'SD'; library=root/'照片库'; config=root/'config'
    before={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
    choices=iter([str(source),str(library),str(root/'成片.jpg')])
    bridge=Bridge(config,dialog=lambda kind:next(choices),model_root=resource_root()/'models')
    window=webview.create_window('片集 · 临时目录验证',str(resource_root()/'pianji'/'ui'/'index.html'),js_api=bridge,width=1440,height=960,background_color='#151619')
    bridge._window=window
    def check(response):
        if not response['ok']: raise AssertionError(response)
        return response['data']
    def wait(ident):
        for _ in range(2400):
            snap=check(bridge.get_task(ident))
            if snap['status'] in ('failed','partial','cancelled'): raise AssertionError(snap)
            if snap['status']=='succeeded': return snap['result']
            time.sleep(.05)
        raise TimeoutError('Desktop test timed out')
    def diagnostic():
        try:
            window.events.loaded.wait(30)
            for _ in range(100):
                if window.evaluate_js("Boolean(window.pywebview?.api&&document.querySelector('#gallery'))"): break
                time.sleep(.1)
            else: raise AssertionError('WebView bridge not ready')
            result['checks'].append('native WebView2 renders real UI and bridge')
            token=check(bridge.choose_source())['token'];check(bridge.choose_library())
            scan=wait(check(bridge.scan(token))['task_id'])
            imported=wait(check(bridge.import_selected(scan['scan_id'],[p['id'] for p in scan['photos']],'桌面 验证','both'))['task_id'])
            photos=check(bridge.list_photos({}));p=photos[0]
            assert check(bridge.get_preview(p['id'],'preview'))['url']
            person=next((person for person in check(bridge.list_people(p['activity_id'])) if person['name']=='模特 测试'),None)
            if not person: person=check(bridge.create_person(p['activity_id'],'模特 测试'))
            wait(check(bridge.set_person([p['id']],person['id']))['task_id'])
            wait(check(bridge.set_edited([p['id']],True))['task_id'])
            wait(check(bridge.choose_and_link_export(p['id']))['task_id'])
            p=bridge._lib.catalog.photo(p['id']);assert p['edited'] and p['manual_person'] and p['primary_export_id']
            assert all(Path(a['path']).is_file() for a in p['assets'])
            result['checks'].append('real scan/import/manual person/stage/export/preview')
            from .faces import FaceEngine
            engine=FaceEngine(resource_root()/'models');faces=engine.detect_and_embed(bridge._lib.group(p['id']))
            result['face_count']=len(faces.faces);result['checks'].append('bundled YuNet/SFace execute')
            # Ask the real JS entrypoint to render the resulting library.
            window.evaluate_js("document.querySelector('[data-view=library]').click()")
            window.evaluate_js("location.reload()")
            time.sleep(2)
            window.evaluate_js("document.querySelector('[data-view=library]').click()")
            time.sleep(1)
            assert window.evaluate_js("document.querySelectorAll('.photo').length")>=1
            result['checks'].append('real JavaScript lists persisted library')
            from .library import Library
            bridge._close()
            reopened_library=Library(library)
            reopened=reopened_library.catalog.photo(p['id']);assert reopened['primary_export_id']==p['primary_export_id']
            reopened_library.close()
            after={str(f.relative_to(source)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source.rglob('*') if f.is_file()}
            assert before==after;result['checks'].append('reopen persistence; SD hashes unchanged')
            result['ok']=True;result['photos']=len(photos)
        except Exception: result['error']=traceback.format_exc()
        finally:
            (root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            bridge._close();window.destroy()
    webview.start(diagnostic,gui='edgechromium',storage_path=str(config/'webview'),private_mode=True,debug=False)
    return 0 if result['ok'] else 1
