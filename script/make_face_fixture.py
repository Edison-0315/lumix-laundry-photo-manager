"""Prepare a pinned public test portrait and a disposable classification library."""
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
import uuid
root=Path(__file__).resolve().parents[1]
lock=json.loads((root/'macos/BackendTests/face-sample.json').read_text())
samples=root/'build/fixtures/FaceSamples';samples.mkdir(parents=True,exist_ok=True)
portrait=samples/'portrait.jpg'
if not portrait.is_file() or hashlib.sha256(portrait.read_bytes()).hexdigest()!=lock['sha256']:
    data=urllib.request.urlopen(lock['source'],timeout=30).read()
    if hashlib.sha256(data).hexdigest()!=lock['sha256']:raise ValueError('Test portrait checksum mismatch')
    portrait.write_bytes(data)
if '--sample-only' in sys.argv:raise SystemExit(0)
sys.path.insert(0,str(root/'macos/Backend'))
from managed import ManagedLibrary
from pianji.domain import PhotoGroup,FileAsset
from PIL import Image
source=samples/'source';source.mkdir(exist_ok=True);original=portrait.read_bytes()
for name,comment in [('A',b''),('B',b'variant B'),('Manual',b'variant manual')]:
    data=original if not comment else original[:2]+b'\xff\xfe'+(len(comment)+2).to_bytes(2,'big')+comment+original[2:]
    (source/(name+'.JPG')).write_bytes(data)
with Image.open(portrait) as image:
    pair=Image.new('RGB',(image.width*2,image.height));pair.paste(image,(0,0));pair.paste(image,(image.width,0));pair.save(source/'Group.JPG',quality=98)
Image.new('RGB',(512,512),'white').save(source/'Blank.JPG')
folder=root/'build/fixtures/NativeFaces'
library=ManagedLibrary.open(folder) if folder.exists() else ManagedLibrary.create(folder)
try:
    name='Faces-'+uuid.uuid4().hex[:8]
    groups=[PhotoGroup(n,'',n,None,[FileAsset(n,n,'jpeg',str(source/(n+'.JPG')))]) for n in ['A','B','Group','Blank','Manual']]
    imported=library.import_groups(groups,name)
    person=library.catalog.add_person(imported['activity_id'],'手动人物')
    library.set_person([imported['imported'][-1]],person['id'])
    (root/'build/fixtures/faces-ui.json').write_text(json.dumps({'root':str(folder),'activity_name':name,'activity_id':imported['activity_id'],'photos':imported['imported'],'manual_person':person['id']},ensure_ascii=False))
finally:library.close()
(folder/'Fixture Ready').mkdir(exist_ok=True)
print(name)
