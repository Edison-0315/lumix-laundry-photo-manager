import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Backend'))
from managed import ManagedLibrary
from pianji.domain import FileAsset, PhotoGroup

class TrashTests(unittest.TestCase):
    def setUp(self):
        self.base=Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-trash-')));self.addCleanup(shutil.rmtree,self.base)
        self.lib=ManagedLibrary.create(self.base/'照片库');self.addCleanup(self.lib.close)
        self.source=self.base/'SD';self.source.mkdir()
        groups=[]
        for n in ['A','B']:
            file=self.source/(n+'.JPG');file.write_bytes(n.encode()*32)
            groups.append(PhotoGroup(n,'',n,None,[FileAsset(n,n,'jpeg',str(file))]))
        report=self.lib.import_groups(groups,'活动');self.ids=report['imported'];self.activity=report['activity_id']
    def test_trash_restore_keeps_ids_and_sources_and_avoids_original_name_conflict(self):
        ident=self.ids[0];before=self.lib.catalog.photo(ident);old=Path(before['assets'][0]['path'])
        result=self.lib.trash_photos([ident]);self.assertEqual(result['errors'],[])
        self.assertFalse(old.exists());old.write_bytes(b'foreign')
        self.assertEqual(self.lib.restore_photos([ident])['errors'],[])
        restored=self.lib.catalog.photo(ident)
        self.assertEqual(restored['id'],ident);self.assertEqual(old.read_bytes(),b'foreign')
        self.assertEqual(Path(restored['assets'][0]['path']).read_bytes(),b'A'*32)
        self.assertEqual((self.source/'A.JPG').read_bytes(),b'A'*32)
    def test_activity_partial_failure_stays_visible_and_restore_reveals_activity(self):
        file=Path(self.lib.catalog.photo(self.ids[1])['assets'][0]['path'])
        saved=file.with_name('original.JPG');file.rename(saved);file.symlink_to(saved)
        report=self.lib.delete_activity(self.activity)
        self.assertTrue(report['errors']);self.assertEqual(len(self.lib.catalog.activities()),1)
        file.unlink();saved.rename(file)
        self.assertEqual(self.lib.delete_activity(self.activity)['errors'],[])
        self.assertEqual(self.lib.catalog.activities(),[])
        self.assertEqual(self.lib.restore_photos([self.ids[0]])['errors'],[])
        self.assertEqual(len(self.lib.catalog.activities()),1)
    def test_delete_person_moves_active_and_trash_relations_to_unclassified(self):
        person=self.lib.catalog.add_person(self.activity,'人物')
        self.lib.set_person(self.ids,person['id']);self.lib.trash_photos([self.ids[0]])
        report=self.lib.delete_people([person['id']]);self.assertEqual(report['errors'],[])
        fixed=next(p for p in self.lib.catalog.people(self.activity) if p['role']=='unclassified')
        for ident in self.ids:self.assertEqual(self.lib.catalog.photo(ident,include_trashed=True)['person_id'],fixed['id'])
        self.assertTrue(self.lib.delete_people([fixed['id']])['errors'])
    def test_purge_deletes_only_receipted_files_and_keeps_source(self):
        self.lib.trash_photos([self.ids[0]])
        file=Path(self.lib.catalog.photo(self.ids[0],include_trashed=True)['assets'][0]['path'])
        report=self.lib.purge_trash([self.ids[0]])
        self.assertEqual(report['deleted'],[self.ids[0]]);self.assertEqual(report['errors'],[])
        self.assertFalse(file.exists());self.assertEqual((self.source/'A.JPG').read_bytes(),b'A'*32)
        self.assertTrue(self.lib.purge_trash([self.ids[1]])['errors'])
    def test_purge_refuses_same_bytes_replacement(self):
        self.lib.trash_photos([self.ids[0]])
        file=Path(self.lib.catalog.photo(self.ids[0],include_trashed=True)['assets'][0]['path'])
        file.rename(file.with_name('owned.JPG'));file.write_bytes(b'A'*32)
        self.assertTrue(self.lib.purge_trash([self.ids[0]])['errors'])
        self.assertEqual(file.read_bytes(),b'A'*32)
        self.assertEqual(file.with_name('owned.JPG').read_bytes(),b'A'*32)
    def test_purge_resumes_after_quarantine_and_blocks_restore(self):
        self.lib.trash_photos([self.ids[0]])
        with patch.object(self.lib.journal.root,'unlink_verified',side_effect=OSError('simulated locked file')):
            report=self.lib.purge_trash([self.ids[0]])
        self.assertTrue(report['errors']);self.assertTrue(self.lib.catalog.rows('SELECT * FROM purges'))
        with self.assertRaises(ValueError):self.lib.restore_photos([self.ids[0]])
        self.assertEqual(self.lib.purge_trash([self.ids[0]])['errors'],[])
        self.assertEqual(self.lib.catalog.rows('SELECT * FROM purges'),[])
    def test_missing_normal_file_that_reappears_is_never_purged(self):
        ident=self.ids[0];file=Path(self.lib.catalog.photo(ident)['assets'][0]['path']);file.unlink()
        self.lib.trash_photos([ident]);file.write_bytes(b'new unrelated file')
        self.assertEqual(self.lib.purge_trash([ident])['errors'],[])
        self.assertEqual(file.read_bytes(),b'new unrelated file')

    def test_crashed_purge_reopens_blocked_then_resumes_through_protocol(self):
        ident=self.ids[0];self.lib.trash_photos([ident]);root=self.lib.root;self.lib.close()
        backend=Path(__file__).resolve().parents[1]/'Backend'
        code="""
import sys,os
sys.path.insert(0,sys.argv[1])
from managed import ManagedLibrary
library=ManagedLibrary.open(sys.argv[2])
library.journal.root.unlink_verified=lambda *args:os._exit(77)
library.purge_trash([sys.argv[3]])
"""
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(backend),str(root),ident],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,77)
        child=subprocess.Popen([sys.executable,'-I','-B',str(backend/'main.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(json.loads(child.stdout.readline())['protocol'],1)
            def request(method,params=None):
                child.stdin.write(json.dumps({'id':method,'method':method,'params':params or {}})+'\n');child.stdin.flush()
                while True:
                    packet=json.loads(child.stdout.readline())
                    if packet['type']=='result':return packet
            self.assertFalse(request('open',{'root':str(root)})['value']['writable'])
            self.assertFalse(request('restore_photos',{'ids':[ident]})['ok'])
            resumed=request('purge_trash',{'ids':[ident]})
            self.assertTrue(resumed['ok'],resumed)
            self.assertEqual(resumed['value']['deleted'],[ident])
            self.assertTrue(request('state')['value']['writable'])
            self.assertEqual((self.source/'A.JPG').read_bytes(),b'A'*32)
        finally:
            child.stdin.close()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            child.stdout.close();child.stderr.close()

    def test_partial_purge_resumes_without_deleting_foreign_trash_files(self):
        ident=self.ids[0];raw=self.source/'A.RW2';raw.write_bytes(b'raw')
        self.lib.import_groups([PhotoGroup('a','','A',None,[FileAsset('j','a','jpeg',str(self.source/'A.JPG')),FileAsset('r','a','raw',str(raw))])],'活动')
        self.lib.trash_photos([ident])
        folder=self.lib.catalog.meta/'回收站'/ident;foreign=folder/'foreign.txt';foreign.write_bytes(b'keep')
        unlink=self.lib.journal.root.unlink_verified;calls=[]
        def partial(*args):
            calls.append(args)
            if len(calls)==2:raise OSError('simulated failure after first deletion')
            return unlink(*args)
        with patch.object(self.lib.journal.root,'unlink_verified',side_effect=partial):
            self.assertTrue(self.lib.purge_trash([ident])['errors'])
        self.assertEqual(self.lib.purge_trash([ident])['errors'],[])
        self.assertEqual(foreign.read_bytes(),b'keep');self.assertEqual(raw.read_bytes(),b'raw')

    def test_replaced_quarantine_is_preserved_and_purge_stays_pending(self):
        ident=self.ids[0];self.lib.trash_photos([ident])
        with patch.object(self.lib.journal.root,'unlink_verified',side_effect=OSError('locked')):
            self.lib.purge_trash([ident])
        plan=json.loads(self.lib.catalog.rows('SELECT payload FROM purges')[0]['payload'])
        quarantine=Path(plan['files'][0]['quarantine']);owned=quarantine.with_name('original-owned')
        quarantine.rename(owned);quarantine.write_bytes(b'A'*32)
        self.assertTrue(self.lib.purge_trash([ident])['errors'])
        self.assertEqual(quarantine.read_bytes(),b'A'*32);self.assertEqual(owned.read_bytes(),b'A'*32)
        self.assertTrue(self.lib.catalog.rows('SELECT * FROM purges'))

    def test_cancel_purge_between_photos_keeps_completed_deletions(self):
        self.lib.trash_photos(self.ids);cancelled=[False]
        report=self.lib.purge_trash(self.ids,cancel=lambda:cancelled[0],progress=lambda *args:cancelled.__setitem__(0,True))
        self.assertTrue(report['cancelled']);self.assertEqual(report['deleted'],[self.ids[0]])
        self.assertTrue(self.lib.catalog.photo(self.ids[1],include_trashed=True))

    def test_restore_keeps_raw_xmp_exports_detached_versions_and_person(self):
        from PIL import Image
        jpeg=self.source/'C.JPG';Image.new('RGB',(2,2),'blue').save(jpeg)
        raw=self.source/'C.RW2';raw.write_bytes(b'raw');xmp=self.source/'C.xmp';xmp.write_bytes(b'<xmp/>')
        group=PhotoGroup('c','','C',None,[FileAsset(k,'c',k,str(p)) for k,p in [('jpeg',jpeg),('raw',raw),('xmp',xmp)]])
        ident=self.lib.import_groups([group],'活动')['imported'][0]
        self.lib.link_export(ident,jpeg);first=self.lib.catalog.photo(ident)['primary_export_id']
        self.lib.link_export(ident,jpeg);cover=self.lib.catalog.photo(ident)['primary_export_id']
        self.lib.unlink_export(ident,first)
        detached=Path(self.lib.catalog.rows('SELECT path FROM detached_exports WHERE photo_id=?',(ident,))[0]['path'])
        original=jpeg.read_bytes();person=self.lib.catalog.add_person(self.activity,'保留人物')
        self.lib.set_person([ident],person['id'])
        self.assertEqual(self.lib.trash_photos([ident])['errors'],[])
        self.assertEqual(self.lib.restore_photos([ident])['errors'],[])
        restored=self.lib.catalog.photo(ident)
        self.assertEqual(restored['person_id'],person['id']);self.assertTrue(restored['edited'])
        self.assertEqual(restored['primary_export_id'],cover)
        self.assertEqual(sorted(a['kind'] for a in restored['assets']),['export','jpeg','raw','xmp'])
        self.assertEqual(detached.read_bytes(),original);self.assertEqual(jpeg.read_bytes(),original)
