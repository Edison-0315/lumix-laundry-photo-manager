"""Build and package an Apple Silicon local preview. Does not publish or notarize."""
import argparse
import hashlib
import json
import plistlib
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime

repository = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--skip-build', action='store_true', help='Package the existing ReleaseValidation build')
args = parser.parse_args()

def run(*command):
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

if not args.skip_build:
    subprocess.run(['/usr/bin/python3', '-I', '-B', str(repository/'macos/Runtime/prepare_runtime.py')], check=True)
    subprocess.run(['/usr/bin/python3', '-I', '-B', str(repository/'macos/Models/prepare_models.py')], check=True)
    subprocess.run(['xcodebuild', '-quiet', '-project', str(repository/'macos/LaundryPhotoManager.xcodeproj'),
                    '-scheme', 'LaundryPhotoManager', '-configuration', 'Release', '-destination', 'platform=macOS,arch=arm64',
                    '-derivedDataPath', str(repository/'build/ReleaseValidation'), 'build', 'CODE_SIGN_IDENTITY=-', 'CODE_SIGNING_ALLOWED=YES'], check=True)
app = repository/'build/ReleaseValidation/Build/Products/Release/LaundryPhotoManager.app'
resources = app/'Contents/Resources'
info = plistlib.loads((app/'Contents/Info.plist').read_bytes())
run('/usr/bin/codesign', '--verify', '--deep', '--strict', str(app))
for folder in ('Backend', 'Models', 'ThirdPartyNotices'):
    for source in (repository/'macos'/folder).rglob('*'):
        if source.is_file() and '__pycache__' not in source.parts and source.suffix not in ('.pyc', '.download'):
            relative = source.relative_to(repository/'macos')
            if digest(source) != digest(resources/relative):
                raise ValueError('Bundled resource is stale: '+str(relative))
notices = json.loads((resources/'ThirdPartyNotices/manifest.json').read_text())
if notices['runtime_lock_sha256'] != digest(repository/'macos/Runtime/runtime-lock.json') or notices['models_manifest_sha256'] != digest(repository/'macos/Models/manifest.json'):
    raise ValueError('Dependency versions changed: refresh third-party notices first')
for item in notices['files']:
    if digest(resources/'ThirdPartyNotices'/item['path']) != item['sha256']:
        raise ValueError('License digest mismatch: '+item['path'])

# Inspect every actual executable/library, including extensionless runtime tools.
native = []
for path in (app/'Contents').rglob('*'):
    if not path.is_file() or path.is_symlink():
        continue
    with path.open('rb') as stream:
        magic = stream.read(4)
    if magic not in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'):
        continue
    if run('/usr/bin/lipo', '-archs', str(path)).strip() != 'arm64':
        raise ValueError('Only arm64 is supported: '+str(path))
    install_names = {line.strip() for line in run('/usr/bin/otool', '-D', str(path)).splitlines()[1:]}
    for line in run('/usr/bin/otool', '-L', str(path)).splitlines()[1:]:
        dependency = line.strip().split(' (', 1)[0]
        if dependency in install_names:  # LC_ID_DYLIB identifies this file; it is not a load dependency.
            continue
        if dependency.startswith('/') and not dependency.startswith(('/usr/lib/', '/System/Library/')):
            raise ValueError('External runtime dependency: '+dependency)
    native.append(str(path.relative_to(app)))
if not native:
    raise ValueError('No application binary found')

output = repository/'build/LocalPackages'/datetime.now().strftime('%Y%m%d-%H%M%S')
output.mkdir(parents=True, exist_ok=False)
copy = output/'LUMIX 洗衣机管理器.app'
subprocess.run(['/usr/bin/ditto', str(app), str(copy)], check=True)
run('/usr/bin/codesign', '--verify', '--deep', '--strict', str(copy))
archive = output/'LUMIX-macOS-arm64-local.zip'
subprocess.run(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(copy), str(archive)], check=True)
with tempfile.TemporaryDirectory(prefix='Lumix-package-check-') as temporary:
    subprocess.run(['/usr/bin/ditto', '-x', '-k', str(archive), temporary], check=True)
    run('/usr/bin/codesign', '--verify', '--deep', '--strict', str(Path(temporary)/copy.name))
report = {'application': str(copy), 'zip': str(archive), 'zip_sha256': digest(archive),
          'architecture': 'arm64', 'native_files': len(native), 'signing': 'ad hoc; not notarized',
          'version': info.get('CFBundleShortVersionString'), 'build': info.get('CFBundleVersion'),
          'license_files': len(notices['files']), 'source_commit': run('git', '-C', str(repository), 'rev-parse', 'HEAD').strip(),
          'source_dirty': bool(run('git', '-C', str(repository), 'status', '--porcelain').strip())}
(output/'package.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
shutil.copyfile(repository/'docs/LOCAL_PREVIEW.md', output/'使用说明.md')
print(json.dumps(report, ensure_ascii=False, indent=2))
