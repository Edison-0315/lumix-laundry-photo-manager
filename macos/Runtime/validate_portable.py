"""One-off validation of a newly embedded runtime, using disposable app/data copies."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

app=Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='Lumix-portable-') as temporary:
    base=Path(os.path.realpath(temporary))
    moved=base/'搬移 App'/'LUMIX Test.app';moved.parent.mkdir()
    shutil.copytree(app,moved,symlinks=True)
    subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(moved)],check=True)
    runtime=moved/'Contents/Resources/Python'
    native=[runtime/'bin/python3.12']+[p for p in runtime.rglob('*') if p.is_file() and p.suffix in ('.so','.dylib')]
    for file in native:
        arch=subprocess.check_output(['/usr/bin/lipo','-archs',str(file)],text=True).strip()
        if arch!='arm64':raise ValueError('Unsupported architecture: '+str(file)+' '+arch)
    env={'PATH':'/nonexistent','PYTHONHOME':'/nonexistent','PYTHONPATH':'/nonexistent','TMPDIR':str(base)}
    if '--faces-only' in sys.argv[2:]:
        resources=moved/'Contents/Resources'
        fixture=Path(__file__).resolve().parents[2]/'build/fixtures/FaceSamples/portrait.jpg'
        probe="import sys;from pathlib import Path;root=Path(sys.argv[1]);sys.path.insert(0,str(root/'Backend'));import numpy,cv2,rawpy;from pianji.faces import FaceEngine,subjects;from pianji.domain import PhotoGroup,FileAsset;result=FaceEngine(root/'Models').detect_and_embed(PhotoGroup('p','','p',None,[FileAsset('f','p','jpeg',sys.argv[2])]));assert len(subjects(result))==1;print('Relocated model inference: 1 face; NumPy '+numpy.__version__+', OpenCV '+cv2.__version__+', rawpy '+rawpy.__version__)"
        subprocess.run([str(runtime/'bin/python3'),'-I','-B','-c',probe,str(resources),str(fixture)],env=env,cwd=base,check=True,timeout=40)
        print('Relocated app: deep strict signature and '+str(len(native))+' arm64 binaries verified, no host Python/PATH dependency')
        raise SystemExit(0)
    child=subprocess.Popen([str(runtime/'bin/python3'),'-I','-B',str(moved/'Contents/Resources/Backend/main.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,cwd=base)
    try:
        greeting=json.loads(child.stdout.readline());assert greeting['architecture']=='arm64' and greeting['python'].startswith('3.12.')
        def request(method,params=None):
            child.stdin.write(json.dumps({'id':method,'method':method,'params':params or {}})+'\n');child.stdin.flush()
            while True:
                result=json.loads(child.stdout.readline())
                if result['type']=='result':
                    if not result['ok']:raise ValueError(result['error'])
                    return result['value']
        request('create',{'root':str(base/'本机 库')})
        source=base/'测试 来源';source.mkdir();file=source/'A.JPG'
        fixture=Path(__file__).resolve().parents[2]/'build/fixtures/UITestSource/JPEG/A.JPG'
        shutil.copyfile(fixture,file)
        report=request('import',{'source_root':str(source),'activity':'活动','groups':[{'id':'a','stem':'A','files':[{'kind':'jpeg','path':str(file)}]}]})
        request('link_export',{'photo_id':report['imported'][0],'path':str(file)})
        request('close')
        child.stdin.close();child.wait(timeout=10)
        assert child.returncode==0
        print('Relocated app runtime: signed, '+str(len(native))+' arm64 binaries, no host Python/PATH dependency; export completed')
    finally:
        if child.poll() is None:child.kill();child.wait()
