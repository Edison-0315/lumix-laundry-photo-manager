"""Download the original pinned models, verifying bytes and SHA-256."""
import hashlib
import json
from pathlib import Path
import urllib.request
root=Path(__file__).resolve().parent
for entry in json.loads((root/'manifest.json').read_text())['models']:
    path=root/entry['filename']
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']:continue
    temporary=path.with_suffix('.download')
    with urllib.request.urlopen(entry['source'],timeout=60) as response,temporary.open('wb') as stream:
        while True:
            block=response.read(1024*1024)
            if not block:break
            stream.write(block)
    if temporary.stat().st_size!=entry['bytes'] or hashlib.sha256(temporary.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Model checksum mismatch: '+entry['filename'])
    temporary.replace(path)
    print('Prepared '+entry['filename'])
