import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Backend'))
from managed import ManagedLibrary
from pianji.domain import PhotoGroup, FileAsset

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.base=Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-export-')))
        self.addCleanup(shutil.rmtree,self.base)
        self.lib=ManagedLibrary.create(self.base/'照片库');self.addCleanup(self.lib.close)
        self.source=self.base/'来源';self.source.mkdir()
        # Real synthetic JPEG fixture, never a user photograph.
        fixture=Path(__file__).resolve().parents[2]/'build/fixtures/UITestSource/JPEG/A.JPG'
        self.jpeg=self.source/'A.JPG';shutil.copyfile(fixture,self.jpeg)
        raw=self.source/'R.RW2';raw.write_bytes(b'synthetic RAW')
        report=self.lib.import_groups([
            PhotoGroup('a','','A',None,[FileAsset('a','a','jpeg',str(self.jpeg))]),
            PhotoGroup('r','','R',None,[FileAsset('r','r','raw',str(raw))])],'活动')
        self.photo,self.raw=report['imported'];self.original=self.jpeg.read_bytes()
    def test_versions_cover_unlink_keep_bytes_and_raw_mark_refusal(self):
        self.lib.link_export(self.photo,self.jpeg)
        p=self.lib.catalog.photo(self.photo);first=p['primary_export_id']
        self.lib.link_export(self.photo,self.jpeg)
        p=self.lib.catalog.photo(self.photo);second=p['primary_export_id']
        self.assertNotEqual(first,second);self.assertTrue(p['edited'])
        self.lib.set_export_cover(self.photo,first)
        self.assertEqual(self.lib.catalog.photo(self.photo)['primary_export_id'],first)
        with self.assertRaises(ValueError):self.lib.set_export_cover(self.raw,first)
        self.lib.unlink_export(self.photo,first)
        self.assertEqual(self.lib.catalog.photo(self.photo)['primary_export_id'],second)
        self.assertEqual(Path(self.lib.catalog.rows('SELECT path FROM detached_exports')[0]['path']).read_bytes(),self.original)
        refused=self.lib.set_finished([self.raw],True)
        self.assertEqual(len(refused['errors']),1)
        self.assertEqual(self.jpeg.read_bytes(),self.original)
    def test_invalid_or_symlinked_export_never_changes_catalog(self):
        bad=self.source/'bad.JPG';bad.write_bytes(b'not an image')
        for file in (bad,self.source/'linked.JPG'):
            if file.name=='linked.JPG':file.symlink_to(self.jpeg)
            with self.assertRaises((ValueError,OSError)):self.lib.link_export(self.photo,file)
        self.assertIsNone(self.lib.catalog.photo(self.photo)['primary_export_id'])
        self.assertEqual(self.jpeg.read_bytes(),self.original)
    def test_undo_rejects_a_later_state(self):
        first=self.lib.set_edited([self.photo],True)['operations'][0]
        self.lib.undo_operation(first)
        self.assertFalse(self.lib.catalog.photo(self.photo)['edited'])
        with self.assertRaises(ValueError):self.lib.undo_operation(first)

    def test_undo_does_not_accept_foreign_history(self):
        import json
        p=self.lib.catalog.photo(self.photo)
        state={key:p[key] for key in ('person_id','edited','manual_person')}
        payload={'photo_id':self.photo,'before':state,'after':state,'format':'foreign'}
        with self.lib.catalog.connect() as db:
            db.execute('INSERT INTO operations VALUES(?,?,?,?,NULL)',('foreign','move','committed',json.dumps(payload)))
        with self.assertRaises(ValueError):self.lib.undo_operation('foreign')

    def test_relink_copies_matching_bytes_without_adopting_external_path(self):
        photo=self.lib.catalog.photo(self.photo);missing=Path(photo['assets'][0]['path']);missing.unlink()
        candidates=self.base/'找回';candidates.mkdir()
        candidate=candidates/'OtherName.JPG';candidate.write_bytes(self.original)
        (candidates/'Linked.JPG').symlink_to(self.jpeg)
        before=(candidate.read_bytes(),candidate.stat().st_mtime_ns)
        report=self.lib.relink_missing(self.photo,candidates)
        self.assertEqual(report['errors'],[]);self.assertEqual(len(report['relinked']),1)
        self.assertEqual(missing.read_bytes(),self.original)
        self.assertEqual((candidate.read_bytes(),candidate.stat().st_mtime_ns),before)
        self.assertEqual(self.lib.catalog.photo(self.photo)['assets'][0]['path'],str(missing))

    def test_editor_open_records_time_without_marking_edited(self):
        self.lib.record_opened(self.photo)
        photo=self.lib.catalog.photo(self.photo)
        self.assertIsNotNone(photo['opened_at'])
        self.assertFalse(photo['edited'])
        self.assertEqual(Path(photo['assets'][0]['path']).read_bytes(),self.original)
