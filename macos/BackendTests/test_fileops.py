import errno
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Backend'))
from managed import ManagedLibrary
from pianji.fileops import FORMAT
from pianji.safeos import identity

class FileOperationTests(unittest.TestCase):
    def setUp(self):
        self.base=Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-fileops-')))
        self.addCleanup(shutil.rmtree,self.base)
        self.library=ManagedLibrary.create(self.base/'库');self.addCleanup(self.library.close)
        self.source=self.base/'source.JPG';self.source.write_bytes(b'original')
        self.target=self.library.root/'活动/A.JPG'
    def change(self):
        return {'src':str(self.source),'dst':str(self.target),'sha256':hashlib.sha256(self.source.read_bytes()).hexdigest(),'move':False}
    def test_exclusive_rename_preserves_both_existing_files(self):
        source=self.library.root/'source.JPG';source.write_bytes(b'ours')
        self.target.parent.mkdir();self.target.write_bytes(b'foreign')
        with self.assertRaises(FileExistsError):self.library.journal.root.rename(source,self.target,identity(source))
        self.assertEqual(source.read_bytes(),b'ours');self.assertEqual(self.target.read_bytes(),b'foreign')
    def test_symbolic_destination_directory_never_writes_outside_library(self):
        outside=self.base/'outside';outside.mkdir()
        (self.library.root/'活动').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):self.library.journal.execute('import',[self.change()],[])
        self.assertEqual(list(outside.iterdir()),[]);self.assertEqual(self.source.read_bytes(),b'original')
    def test_foreign_same_bytes_copy_destination_is_preserved_without_blocking_future_work(self):
        self.target.parent.mkdir();self.target.write_bytes(b'original')
        owned=identity(self.target)
        old=self.target.with_name('old-owned.JPG');self.target.rename(old)
        self.target.write_bytes(b'original')
        change={**self.change(),'identity':owned,'temp':str(self.target)+'.test.partial'}
        result=self.library.journal.rollback({'format':FORMAT,'library_id':self.library.marker['library_id'],'changes':[change]})
        self.assertEqual(result,[])
        self.assertEqual(self.target.read_bytes(),b'original');self.assertEqual(old.read_bytes(),b'original')
    def test_unknown_partial_is_kept_and_requires_attention(self):
        self.target.parent.mkdir();temporary=Path(str(self.target)+'.test.partial');temporary.write_bytes(b'unknown')
        data={'format':FORMAT,'library_id':self.library.marker['library_id'],'changes':[{**self.change(),'identity':None,'temp':str(temporary)}]}
        import json
        with self.library.catalog.connect() as db:db.execute('INSERT INTO operations VALUES(?,?,?,?,NULL)',('pending','import','planned',json.dumps(data)))
        report=self.library.recover_pending()
        self.assertTrue(report['errors']);self.assertEqual(temporary.read_bytes(),b'unknown')
        self.assertEqual(self.library.catalog.rows("SELECT phase FROM operations")[0]['phase'],'needs_attention')
    def test_disk_full_cleans_owned_stage_and_preserves_source(self):
        with patch('pianji.safeos.os.write',side_effect=OSError(errno.ENOSPC,'simulated disk full')):
            with self.assertRaises(OSError):self.library.journal.execute('import',[self.change()],[])
        self.assertFalse(self.target.exists());self.assertEqual(self.source.read_bytes(),b'original')
        self.assertEqual(list(self.library.root.rglob('*.partial')),[])
        self.assertEqual(self.library.catalog.rows('SELECT phase FROM operations')[0]['phase'],'committed')
    def test_source_changed_while_copying_is_not_published_or_rolled_back(self):
        self.source.write_bytes(b'A'*(2*1024*1024));change=self.change()
        write=os.write;changed=[False]
        def write_and_edit(fd,data):
            result=write(fd,data)
            if not changed[0]:changed[0]=True;self.source.write_bytes(b'B'*(2*1024*1024))
            return result
        with patch('pianji.safeos.os.write',side_effect=write_and_edit):
            with self.assertRaises(ValueError):self.library.journal.execute('import',[change],[])
        self.assertFalse(self.target.exists());self.assertEqual(self.source.read_bytes(),b'B'*(2*1024*1024))
        self.assertEqual(list(self.library.root.rglob('*.partial')),[])

if __name__=='__main__':unittest.main()
