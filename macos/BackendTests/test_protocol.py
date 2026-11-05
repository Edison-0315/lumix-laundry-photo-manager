import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import unittest

BACKEND=Path(__file__).resolve().parents[1]/'Backend'
class ProtocolTests(unittest.TestCase):
    def test_client_disconnect_after_first_progress_keeps_committed_groups_and_releases_lock(self):
        sys.path.insert(0,str(BACKEND))
        from managed import ManagedLibrary
        root=self.base/'Disconnect Library';self.request('create',{'root':str(root)})
        source=self.base/'SD';source.mkdir();groups=[]
        for index in range(3):
            path=source/(str(index)+'.JPG');path.write_bytes(bytes([index])*262144)
            groups.append({'id':str(index),'stem':str(index),'files':[{'kind':'jpeg','path':str(path)}]})
        before={p.name:p.read_bytes() for p in source.iterdir()}
        self.serial+=1
        self.child.stdin.write(json.dumps({'id':self.serial,'method':'import','params':{'source_root':str(source),'activity':'Disconnect','groups':groups}})+'\n');self.child.stdin.flush()
        first=json.loads(self.child.stdout.readline())
        self.assertEqual(first['type'],'progress');self.assertEqual(first['done'],1)
        self.child.stdin.close();self.child.stdout.close()
        # CPython may use 120 when its final stdout flush also sees the closed pipe.
        self.assertIn(self.child.wait(timeout=10),(0,120))
        with_library=ManagedLibrary.open(root)
        try:
            with_library._ready()
            photos=with_library.catalog.photos()
            self.assertGreaterEqual(len(photos),1);self.assertLessEqual(len(photos),3)
            for photo in photos:
                for asset in photo['assets']:
                    self.assertEqual(Path(asset['path']).read_bytes(),before[photo['stem']+'.JPG'])
            self.assertFalse(with_library.catalog.rows("SELECT id FROM operations WHERE phase!='committed'"))
        finally:with_library.close()
        self.assertEqual({p.name:p.read_bytes() for p in source.iterdir()},before)
    def setUp(self):
        self.base=Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-protocol-')));self.addCleanup(shutil.rmtree,self.base)
        self.child=subprocess.Popen([sys.executable,'-I','-B',str(BACKEND/'main.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.close_child)
        self.assertEqual(json.loads(self.child.stdout.readline())['protocol'],1)
        self.serial=0
    def close_child(self):
        if self.child.poll() is None:
            self.child.stdin.close()
            try:self.child.wait(timeout=10)
            except subprocess.TimeoutExpired:self.child.kill();self.child.wait()
        self.child.stdout.close();self.child.stderr.close()
    def request(self,method,params=None,on_progress=None):
        self.serial+=1
        self.child.stdin.write(json.dumps({'id':self.serial,'method':method,'params':params or {}})+'\n');self.child.stdin.flush()
        while True:
            packet=json.loads(self.child.stdout.readline())
            self.assertEqual(packet['id'],self.serial)
            if packet['type']=='result':return packet
            if on_progress:on_progress(packet)
    def test_new_session_and_rejected_old_library_preserve_current_session(self):
        root=self.base/'本机库'
        result=self.request('create',{'root':str(root)})
        self.assertTrue(result['ok']);self.assertTrue(result['value']['writable'])
        self.assertTrue(self.request('create_activity',{'name':'活动'})['ok'])
        old=self.base/'旧库';old.mkdir()
        self.assertFalse(self.request('open',{'root':str(old)})['ok'])
        self.assertEqual(self.request('state')['value']['root'],str(root))
        self.assertEqual(list(old.iterdir()),[])
        self.assertFalse(self.request('execute_sql',{'sql':'DELETE FROM photos'})['ok'])
    def test_sigint_cancels_between_groups_without_undoing_completed_copies(self):
        root=self.base/'本机库';self.request('create',{'root':str(root)})
        source=self.base/'SD';source.mkdir();groups=[]
        for n in range(30):
            file=source/(str(n)+'.JPG');file.write_bytes(bytes([n])*1024*1024)
            groups.append({'id':str(n),'stem':str(n),'files':[{'id':str(n),'kind':'jpeg','path':str(file)}]})
        sent=[False]
        def cancel(_):
            if not sent[0]:sent[0]=True;self.child.send_signal(signal.SIGINT)
        response=self.request('import',{'source_root':str(source),'groups':groups,'activity':'活动'},cancel)
        self.assertTrue(response['ok']);report=response['value']
        self.assertTrue(report['cancelled']);self.assertGreaterEqual(len(report['imported']),1);self.assertLess(len(report['imported']),30)
        self.assertEqual(self.request('state')['value']['photo_count'],len(report['imported']))
        self.assertEqual(len(list(source.iterdir())),30)
    def test_import_reuses_activity_case_and_does_not_mix_with_foreign_folder(self):
        root=self.base/'本机库';self.request('create',{'root':str(root)})
        source=self.base/'SD';source.mkdir();file=source/'A.JPG';file.write_bytes(b'original')
        params={'source_root':str(source),'groups':[{'id':'a','stem':'A','files':[{'kind':'jpeg','path':str(file)}]}],'activity':'Activity'}
        self.assertTrue(self.request('import',params)['ok'])
        params['activity']='ACTIVITY'
        again=self.request('import',params)
        self.assertTrue(again['ok']);self.assertEqual(again['value']['skipped'],1)
        self.assertEqual(len(self.request('state')['value']['activities']),1)
        (root/'Foreign').mkdir();(root/'Foreign/keep.txt').write_bytes(b'foreign')
        params['activity']='Foreign'
        self.assertFalse(self.request('import',params)['ok'])
        self.assertEqual((root/'Foreign/keep.txt').read_bytes(),b'foreign')
    def test_crash_after_stage_ownership_is_explicitly_recoverable(self):
        root=self.base/'本机库';self.request('create',{'root':str(root)});self.request('close')
        source=self.base/'source.JPG';source.write_bytes(b'original')
        code='''
import os,sys
from managed import ManagedLibrary
from pianji.domain import PhotoGroup,FileAsset
lib=ManagedLibrary.open(sys.argv[1]);save=lib.journal._save
def crash(ident,data):
    save(ident,data);os._exit(77)
lib.journal._save=crash
lib.import_groups([PhotoGroup('g','','A',None,[FileAsset('a','g','jpeg',sys.argv[2])])],'活动')
'''
        crashed=subprocess.run([sys.executable,'-B','-c',code,str(root),str(source)],env={**os.environ,'PYTHONPATH':str(BACKEND)},capture_output=True,timeout=10)
        self.assertEqual(crashed.returncode,77)
        opened=self.request('open',{'root':str(root)})
        self.assertTrue(opened['ok']);self.assertFalse(opened['value']['writable'])
        self.assertTrue(list(root.rglob('*.partial')))
        recovered=self.request('recover')
        self.assertTrue(recovered['ok']);self.assertFalse(recovered['value']['errors'])
        self.assertEqual(list(root.rglob('*.partial')),[]);self.assertEqual(source.read_bytes(),b'original')
        self.assertTrue(self.request('state')['value']['writable'])

    def test_people_rename_merge_preserve_files_and_fixed_roles(self):
        root=self.base/'本机库';self.request('create',{'root':str(root)})
        source=self.base/'SD';source.mkdir();file=source/'A.JPG';file.write_bytes(b'original')
        imported=self.request('import',{'source_root':str(source),'groups':[{'id':'a','stem':'A','files':[{'kind':'jpeg','path':str(file)}]}],'activity':'活动'})['value']
        activity=imported['activity_id'];ident=imported['imported'][0]
        alice=self.request('create_person',{'activity_id':activity,'name':'Alice'})['value']['id']
        bob=self.request('create_person',{'activity_id':activity,'name':'Bob'})['value']['id']
        self.assertTrue(self.request('set_person',{'ids':[ident],'person_id':alice})['ok'])
        renamed=self.request('rename_person',{'person_id':alice,'name':'Alice New'})
        self.assertTrue(renamed['ok'],renamed)
        self.assertEqual(len(list((root/'活动/Alice New').rglob('*.JPG'))),1)
        self.assertTrue(self.request('merge_people',{'source_id':alice,'target_id':bob})['ok'])
        self.assertEqual(len(list((root/'活动/Bob').rglob('*.JPG'))),1)
        self.assertFalse(self.request('rename_person',{'person_id':alice,'name':'Gone'})['ok'])
        other=self.request('create_activity',{'name':'另一活动'})['value']['id']
        foreign=self.request('create_person',{'activity_id':other,'name':'Foreign'})['value']['id']
        self.assertFalse(self.request('merge_people',{'source_id':bob,'target_id':foreign})['ok'])
        with sqlite3.connect(root/'.片集/catalog.sqlite3') as db:
            fixed=db.execute("SELECT id FROM people WHERE activity_id=? AND role='group'",(activity,)).fetchone()[0]
        self.assertFalse(self.request('rename_person',{'person_id':fixed,'name':'Changed'})['ok'])
        self.assertFalse(self.request('merge_people',{'source_id':fixed,'target_id':bob})['ok'])
        self.assertEqual(file.read_bytes(),b'original')

if __name__=='__main__':unittest.main()
