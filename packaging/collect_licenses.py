from importlib.metadata import distributions
from pathlib import Path
import json
import shutil
import sys

def collect(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);manifest=[]
    for dist in distributions():
        name=dist.metadata['Name'];target=root/name;files=[]
        for entry in dist.files or []:
            parts=str(entry).replace('\\','/').split('/')
            if any('license' in p.lower() or 'copying' in p.lower() or p.upper()=='NOTICE' for p in parts):
                source=Path(dist.locate_file(entry))
                if source.is_file():
                    target.mkdir(exist_ok=True);out=target/('_'.join(parts[-3:]));shutil.copyfile(source,out);files.append(str(out.relative_to(root)))
        manifest.append({'name':name,'version':dist.version,'license':dist.metadata.get('License-Expression') or dist.metadata.get('License'),'files':files})
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.exists():shutil.copyfile(python_license,root/'Python-LICENSE.txt')
    (root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':collect(sys.argv[1])
