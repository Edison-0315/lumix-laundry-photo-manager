import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Backend'))
from managed import ManagedLibrary
from pianji.domain import FileAsset, PhotoGroup

class ManagedLibraryTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-mac-backend-')))
        self.addCleanup(shutil.rmtree, self.base)
        self.root = self.base / '照片库'
        self.source = self.base / 'SD'
        self.source.mkdir()
        for name, content in [('A.JPG', b'original jpeg'), ('A.RW2', b'original raw'), ('A.xmp', b'<xmp/>')]:
            (self.source/name).write_bytes(content)
    def group(self):
        return PhotoGroup('scan-a', str(self.source), 'A', '2026-11-04T00:15:00', [
            FileAsset(name, 'scan-a', kind, str(self.source/name))
            for name, kind in [('A.JPG','jpeg'),('A.RW2','raw'),('A.xmp','xmp')]])
    def fingerprint(self, root):
        return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    def create(self):
        library = ManagedLibrary.create(self.root)
        self.addCleanup(library.close)
        return library
    def test_old_library_is_refused_without_creating_lock_or_changing_files(self):
        self.root.mkdir(); (self.root/'.片集').mkdir()
        (self.root/'.片集/catalog.sqlite3').write_bytes(b'old library placeholder')
        before = self.fingerprint(self.root)
        with self.assertRaises(ValueError): ManagedLibrary.open(self.root)
        self.assertEqual(self.fingerprint(self.root), before)
    def test_new_library_cannot_be_nested_in_old_library_or_readonly_source(self):
        old=self.base/'旧库';(old/'.片集').mkdir(parents=True)
        (old/'.片集/catalog.sqlite3').write_bytes(b'old placeholder')
        before=self.fingerprint(old)
        with self.assertRaises(ValueError):ManagedLibrary.create(old/'新库')
        self.assertEqual(self.fingerprint(old),before)
        before_source=self.fingerprint(self.source)
        with self.assertRaises(ValueError):ManagedLibrary.create(self.source/'新库',protected_roots=[self.source])
        self.assertEqual(self.fingerprint(self.source),before_source)
    def test_new_library_has_ten_tables_and_a_lifetime_cross_process_lock(self):
        library = self.create()
        tables = library.catalog.rows("SELECT name FROM sqlite_master WHERE type='table'")
        self.assertEqual(len(tables), 10)
        marker = json.loads((self.root/'.片集/macos-library.json').read_text())
        self.assertEqual(marker['format'], 'lumix-macos-1')
        child = subprocess.run([sys.executable, '-B', '-c',
            'from managed import ManagedLibrary; ManagedLibrary.open(__import__("sys").argv[1])', str(self.root)],
            env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]/'Backend')}, capture_output=True, timeout=10)
        self.assertNotEqual(child.returncode, 0)
        library.close()
        reopened = ManagedLibrary.open(self.root); reopened.close()
    def test_database_replaced_between_open_preflight_and_initialization_is_refused(self):
        library = self.create(); library.close()
        initialize = ManagedLibrary._initialize
        path = self.root/'.片集/catalog.sqlite3'
        def replace_before_initialize(instance, root, create, marker=None):
            path.rename(path.with_name('original.sqlite3'))
            shutil.copyfile(path.with_name('original.sqlite3'), path)
            return initialize(instance, root, create, marker)
        with patch.object(ManagedLibrary, '_initialize', replace_before_initialize):
            with self.assertRaises(ValueError): ManagedLibrary.open(self.root)
        self.assertEqual(path.read_bytes(), path.with_name('original.sqlite3').read_bytes())
    def test_import_is_copy_only_idempotent_and_raw_supplement_keeps_edited_jpeg(self):
        library = self.create(); before = self.fingerprint(self.source)
        first = library.import_groups([self.group()], '测试活动', 'jpeg')
        self.assertEqual(len(first['imported']), 1); self.assertFalse(first['errors'])
        ident = first['imported'][0]; photo = library.catalog.photo(ident)
        person = library.catalog.add_person(photo['activity_id'], '人物')
        self.assertFalse(library.set_person([ident], person['id'])['errors'])
        self.assertFalse(library.set_edited([ident], True)['errors'])
        photo = library.catalog.photo(ident); jpeg = Path(next(a['path'] for a in photo['assets'] if a['kind']=='jpeg'))
        jpeg.write_bytes(b'locally edited jpeg')
        result = library.import_groups([self.group()], '测试活动', 'raw')
        self.assertEqual(result['updated'], [ident]); self.assertFalse(result['errors'])
        final = library.catalog.photo(ident)
        self.assertEqual(final['person_id'], person['id']); self.assertEqual(final['edited'], 1); self.assertEqual(final['manual_person'], 1)
        self.assertEqual({a['kind'] for a in final['assets']}, {'jpeg','raw','xmp'})
        self.assertEqual(jpeg.read_bytes(), b'locally edited jpeg')
        again = library.import_groups([self.group()], '测试活动')
        self.assertEqual(again['skipped'], 1); self.assertFalse(again['errors'])
        self.assertEqual(len(library.catalog.photos()), 1)
        self.assertEqual(self.fingerprint(self.source), before)
    def test_source_symlinks_are_not_followed(self):
        library = self.create()
        (self.source/'A.JPG').unlink(); (self.source/'A.JPG').symlink_to(self.source/'A.RW2')
        result = library.import_groups([self.group()], '测试活动', 'jpeg')
        self.assertTrue(result['errors']); self.assertEqual(library.catalog.photos(), [])
    def test_unselected_unreadable_raw_does_not_block_jpeg_import(self):
        library = self.create()
        (self.source/'A.RW2').unlink(); (self.source/'A.RW2').symlink_to(self.source/'A.JPG')
        result = library.import_groups([self.group()], '测试活动', 'jpeg')
        self.assertFalse(result['errors']); self.assertEqual(len(result['imported']), 1)
    def test_activity_and_fixed_people_are_one_database_transaction(self):
        library = self.create()
        with library.catalog.connect() as db:
            db.execute("CREATE TRIGGER fail_role BEFORE INSERT ON people WHEN NEW.role='unclassified' BEGIN SELECT RAISE(ABORT,'simulated failure'); END")
        with self.assertRaises(Exception): library.create_activity('活动')
        self.assertEqual(library.catalog.activities(), [])
        self.assertEqual(library.catalog.rows('SELECT * FROM people'), [])
        self.assertFalse((self.root/'活动').exists())
    def test_pending_purge_blocks_ordinary_library_writes(self):
        library = self.create()
        with library.catalog.connect() as db: db.execute("INSERT INTO purges VALUES('interrupted','{}','incomplete')")
        with self.assertRaises(ValueError): library.create_activity('活动')
        self.assertEqual(library.catalog.activities(), [])
    def test_sql_failure_rolls_back_owned_files_only(self):
        library = self.create(); source = self.source/'A.JPG'; dst = self.root/'activity/target.JPG'
        before = self.fingerprint(self.source)
        with self.assertRaises(Exception):
            library.journal.execute('test', [{'src':str(source),'dst':str(dst),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'move':False}],
                [('INSERT INTO missing_table VALUES(1)', ())])
        self.assertFalse(dst.exists()); self.assertEqual(self.fingerprint(self.source), before)
        self.assertEqual(library.catalog.rows("SELECT phase FROM operations")[0]['phase'], 'committed')
    def test_open_does_not_automatically_recover_foreign_logs(self):
        library = self.create()
        with library.catalog.connect() as db:
            db.execute("INSERT INTO operations VALUES('old','import','planned',?,NULL)", (json.dumps({'changes':[], 'sql':[]}),))
        library.close(); before = self.fingerprint(self.root)
        opened = ManagedLibrary.open(self.root); self.addCleanup(opened.close)
        self.assertEqual(opened.catalog.rows('SELECT phase FROM operations')[0]['phase'], 'planned')
        self.assertEqual((self.root/'.片集/catalog.sqlite3').read_bytes(), before['.片集/catalog.sqlite3'][0])
        with self.assertRaises(ValueError): opened.create_activity('禁止写入')
        recovery = opened.recover_pending()
        self.assertTrue(recovery['errors'])
        self.assertEqual(opened.catalog.rows('SELECT phase FROM operations')[0]['phase'], 'needs_attention')

if __name__ == '__main__': unittest.main()
