"""Reproducible, SHA-verified developer download; never run at normal startup."""
import urllib.request
import hashlib
import re
import json
import subprocess
import urllib.error
from pathlib import Path

COMMIT='48b10fa505aeb51fbd127fc60a5c660040e823b7'
ROOT=Path(__file__).resolve().parents[1]/'models'
def fetch(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Pianji-build'}),timeout=180).read()
    except urllib.error.URLError:
        # Windows curl uses the OS trust/network stack; retain TLS verification.
        return subprocess.check_output(['curl.exe','--fail','--location','--silent','--show-error','--retry','2','--max-time','180',url])

def main():
    ROOT.mkdir(exist_ok=True)
    entries=[]
    for folder,filename in [('face_detection_yunet','face_detection_yunet_2023mar.onnx'),('face_recognition_sface','face_recognition_sface_2021dec.onnx')]:
        relative=f'models/{folder}/{filename}'
        base=f'https://raw.githubusercontent.com/opencv/opencv_zoo/{COMMIT}/'
        pointer=fetch(base+relative).decode()
        sha=re.search(r'oid sha256:([a-f0-9]{64})',pointer).group(1)
        url=f'https://media.githubusercontent.com/media/opencv/opencv_zoo/{COMMIT}/{relative}'
        data=fetch(url)
        if hashlib.sha256(data).hexdigest()!=sha: raise ValueError('Model SHA mismatch')
        (ROOT/filename).write_bytes(data)
        license_name=folder+'-LICENSE.txt'
        (ROOT/license_name).write_bytes(fetch(base+f'models/{folder}/LICENSE'))
        entries.append({'filename':filename,'sha256':sha,'bytes':len(data),'source':url,'license':license_name})
        print(filename,len(data),sha,flush=True)
    (ROOT/'manifest.json').write_text(json.dumps({'repository':'opencv/opencv_zoo','commit':COMMIT,'models':entries},indent=2),encoding='utf-8')

if __name__=='__main__': main()
