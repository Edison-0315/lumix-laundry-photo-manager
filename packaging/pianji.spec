from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_data_files

project = Path(SPECPATH).parent
datas=[(str(project/'pianji'/'ui'),'pianji/ui'),(str(project/'models'),'models'),(str(project/'licenses'),'licenses'),(str(project/'THIRD-PARTY-NOTICES.md'),'.')]
datas += collect_data_files('webview')
a=Analysis([str(project/'run.py')],pathex=[str(project)],binaries=[],datas=datas,hiddenimports=['webview.platforms.edgechromium','pianji.selftest'],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['tkinter','pytest','PyInstaller'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='洗衣机管理器',icon=str(project/'pianji/ui/lumix.ico'),debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,disable_windowed_traceback=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name=os.environ.get('PIANJI_BUNDLE_NAME','洗衣机管理器-Windows-0.7'))
