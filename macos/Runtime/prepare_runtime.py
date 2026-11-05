"""Prepare pinned Apple Silicon dependencies; Xcode copies this tree into the app."""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import tempfile
import uuid
import subprocess
import sys
import urllib.request

here=Path(__file__).resolve().parent
lock=json.loads((here/'runtime-lock.json').read_text())
cache=here.parents[1]/'build/runtime-downloads';cache.mkdir(parents=True,exist_ok=True)
runtime=here/'Python'
if sys.platform!='darwin' or platform.machine()!='arm64':raise SystemExit('Only Apple Silicon macOS is supported')

def download(entry):
    name=urllib.request.url2pathname(entry['url'].rsplit('/',1)[1])
    target=cache/name
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=entry['sha256']:
        temporary=target.with_name(target.name+'.download')
        with urllib.request.urlopen(entry['url'],timeout=60) as response,temporary.open('wb') as stream:
            while True:
                block=response.read(1024*1024)
                if not block:break
                stream.write(block)
        if hashlib.sha256(temporary.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Runtime download checksum mismatch')
        temporary.replace(target)
    return target

stamp=here/'Python/.lumix-runtime-lock.json'
if stamp.exists() and json.loads(stamp.read_text())==lock:
    print('Pinned arm64 runtime already prepared');raise SystemExit(0)
if runtime.is_symlink() or (runtime.exists() and not stamp.is_file()):raise SystemExit('Runtime is not an owned generated tree; inspect it before replacing')
archive=download(lock['python'])
wheels=[download(lock['pillow'])]+[download(entry) for entry in lock.get('packages',[])]
with tempfile.TemporaryDirectory(prefix='runtime-stage-',dir=cache) as staging:
    stage=Path(staging)
    subprocess.run(['/usr/bin/tar','-xzf',str(archive),'-C',str(stage)],check=True)
    prepared=stage/'python';python=prepared/'bin/python3'
    subprocess.run([str(python),'-I','-B','-m','pip','install','--no-deps','--no-index','--no-compile',*[str(w) for w in wheels]],check=True)
    subprocess.run([str(python),'-I','-B','-m','pip','check'],check=True)
    probe='import PIL,platform,sqlite3; assert platform.machine()=="arm64"; print(platform.python_version(),PIL.__version__)'
    if lock.get('packages'):probe+='; import numpy,cv2,rawpy; print(numpy.__version__,cv2.__version__,rawpy.__version__)'
    subprocess.run([str(python),'-I','-B','-c',probe],check=True)
    (prepared/'.lumix-runtime-lock.json').write_text(json.dumps(lock,indent=2)+'\n')
    previous=cache/('previous-runtime-'+uuid.uuid4().hex)
    if runtime.exists():runtime.rename(previous)
    try:prepared.rename(runtime)
    except BaseException:
        if previous.exists():previous.rename(runtime)
        raise
    if previous.exists():shutil.rmtree(previous)
print('Prepared pinned self-contained arm64 runtime')
