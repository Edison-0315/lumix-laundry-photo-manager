import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Backend'))
from managed import ManagedLibrary
from pianji import safeos

class ReplacementBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-boundaries-')))
        self.addCleanup(shutil.rmtree, self.base)
        self.library = ManagedLibrary.create(self.base/'Library'); self.addCleanup(self.library.close)
        self.database = self.library.root/'.片集/catalog.sqlite3'
        other = ManagedLibrary.create(self.base/'Other'); other.create_activity('Foreign'); other.close()
        self.foreign = (self.base/'Other/.片集/catalog.sqlite3').read_bytes()
    def replace_database(self):
        saved = self.database.with_name('original.sqlite3')
        self.database.rename(saved); self.database.write_bytes(self.foreign)
        return saved
    def test_database_replacement_after_guard_before_sqlite_open_is_refused(self):
        connect = sqlite3.connect; changed = [False]
        def replacing(*args, **kwargs):
            if not changed[0]: changed[0] = True; self.replace_database()
            return connect(*args, **kwargs)
        with patch('pianji.catalog.sqlite3.connect', side_effect=replacing):
            with self.assertRaisesRegex(ValueError, '替换|变化'):
                with self.library.catalog.connect() as db:
                    db.execute("INSERT INTO activities VALUES('foreign-write','Must not write','Must not write')")
        self.assertEqual(self.database.read_bytes(), self.foreign)
    def test_replacement_before_commit_rolls_back_and_leaves_foreign_database(self):
        saved = None
        try:
            with self.assertRaisesRegex(ValueError, '替换|变化'):
                with self.library.catalog.connect() as db:
                    db.execute("INSERT INTO activities VALUES('not-committed','Pending','Pending')")
                    saved = self.replace_database()
            self.assertEqual(self.database.read_bytes(), self.foreign)
        finally:
            if saved is not None:
                self.database.unlink(); saved.rename(self.database)
        self.assertEqual(self.library.catalog.activities(), [])
    def test_destination_parent_replaced_during_rename_restores_owned_source(self):
        source = self.library.root/'source'; source.write_bytes(b'owned')
        target = self.library.root/'Target'; target.mkdir(); displaced = self.library.root/'Displaced'
        destination = target/'photo'; rename = safeos._rename; changed = [False]
        def replacing(*args):
            if not changed[0]:
                changed[0] = True; target.rename(displaced); target.mkdir(); destination.write_bytes(b'foreign')
            return rename(*args)
        with patch('pianji.safeos._rename', side_effect=replacing):
            with self.assertRaises(safeos.OwnershipError): self.library.journal.root.rename(source, destination, safeos.identity(source))
        self.assertEqual(source.read_bytes(), b'owned')
        self.assertEqual(destination.read_bytes(), b'foreign')
        self.assertEqual(list(displaced.iterdir()), [])
    def test_copy_parent_replacement_keeps_foreign_files_and_marks_attention(self):
        source = self.base/'Source.JPG'; source.write_bytes(b'original source')
        target = self.library.root/'Target'; target.mkdir(); displaced = self.library.root/'Displaced'
        destination = target/'Photo.JPG'; write = os.write; changed = [False]
        def replacing(*args):
            if not changed[0]:
                changed[0] = True; target.rename(displaced); target.mkdir(); destination.write_bytes(b'foreign')
            return write(*args)
        with patch('pianji.safeos.os.write', side_effect=replacing):
            with self.assertRaises(Exception):
                self.library.journal.execute('copy', [{'src':str(source),'dst':str(destination),'move':False,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}], [])
        self.assertEqual(source.read_bytes(), b'original source')
        self.assertEqual(destination.read_bytes(), b'foreign')
        self.assertEqual(self.library.catalog.rows('SELECT phase FROM operations')[0]['phase'], 'needs_attention')
        with self.assertRaises(ValueError): self.library._ready()
        # Explicit recovery must not report success while the old directory is displaced.
        blocked=self.library.recover_pending()
        self.assertTrue(blocked['errors'])
        self.assertEqual(self.library.catalog.rows('SELECT phase FROM operations')[0]['phase'], 'needs_attention')
        foreign_hold=self.library.root/'Foreign Preserved'; target.rename(foreign_hold); displaced.rename(target)
        recovered=self.library.recover_pending()
        self.assertEqual(recovered['errors'],[])
        self.assertEqual((foreign_hold/'Photo.JPG').read_bytes(),b'foreign')
        self.assertEqual(list(target.iterdir()),[])
        self.library._ready()
