from pathlib import Path
from datetime import datetime
import subprocess

def validate_executable(path):
    exe=Path(path).expanduser()
    if not exe.is_absolute() or not exe.is_file() or exe.suffix.lower()!='.exe': raise ValueError('请选择有效的Photoshop.exe程序路径')
    return exe.resolve()

def open_in_photoshop(lib,photo_id,format,executable,launcher=subprocess.Popen):
    exe=validate_executable(executable)
    if format not in ('jpeg','raw'): raise ValueError('请选择JPEG或RAW')
    with lib.lock:
        p=lib.catalog.photo(photo_id)
        asset=next((a for a in p['assets'] if a['kind']==format),None)
        if not asset: raise ValueError('此照片未导入'+('RAW' if format=='raw' else 'JPEG'))
        file=Path(asset['path'])
        if not file.is_file(): raise ValueError('照片文件缺失，请重新定位文件')
        launcher([str(exe),str(file)],shell=False)
        with lib.catalog.connect() as db: db.execute('UPDATE photos SET opened_at=? WHERE id=?',(datetime.now().isoformat(),photo_id))
    return {'requested':True,'format':format}
