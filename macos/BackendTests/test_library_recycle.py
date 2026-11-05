import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Backend'))
from managed import ManagedLibrary

class LibraryRecycleTests(unittest.TestCase):
    def setUp(self):
        self.base=Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-recycle-')));self.addCleanup(shutil.rmtree,self.base)
        self.lib=ManagedLibrary.create(self.base/'本机库');self.addCleanup(self.lib.close)
        (self.lib.root/'photo.JPG').write_bytes(b'original')
    def inspector(self):
        from pianji.library_recycle import LibraryRecycleInspector
        return LibraryRecycleInspector(self.lib)
    def test_preview_and_name_confirmation_do_not_modify_files(self):
        inspector=self.inspector();before=(self.lib.root/'photo.JPG').stat()
        plan=inspector.inspect([],[])
        self.assertEqual(plan['name'],'本机库');self.assertGreater(plan['bytes'],0);self.assertGreater(plan['file_count'],1)
        with self.assertRaises(ValueError):inspector.validate(plan['token'],'wrong',[],[])
        self.assertEqual(inspector.validate(plan['token'],plan['name'],[],[])['root'],str(self.lib.root))
        self.assertEqual((self.lib.root/'photo.JPG').stat().st_mtime_ns,before.st_mtime_ns)
    def test_changed_tree_and_replaced_file_invalidate_preview(self):
        inspector=self.inspector();plan=inspector.inspect([],[])
        file=self.lib.root/'photo.JPG';file.rename(file.with_name('original.JPG'));file.write_bytes(b'original')
        with self.assertRaises(ValueError):inspector.validate(plan['token'],plan['name'],[],[])
    def test_source_overlap_and_application_paths_are_blocked(self):
        inspector=self.inspector()
        for protected in [self.lib.root,self.lib.root/'SD',self.lib.root.parent]:
            with self.assertRaises(ValueError):inspector.inspect([str(protected)],[])
        with self.assertRaises(ValueError):inspector.inspect([],[str(self.lib.root/'App.app')])
    def test_nested_library_and_symlink_are_not_recycled(self):
        inspector=self.inspector()
        link=self.lib.root/'linked';link.symlink_to(self.base)
        with self.assertRaises(ValueError):inspector.inspect([],[])
        link.unlink();nested=self.lib.root/'nested/.片集';nested.mkdir(parents=True);(nested/'catalog.sqlite3').write_bytes(b'other library')
        with self.assertRaises(ValueError):inspector.inspect([],[])
    def test_newly_selected_source_is_checked_again_on_confirmation(self):
        inspector=self.inspector();plan=inspector.inspect([],[])
        with self.assertRaises(ValueError):inspector.validate(plan['token'],plan['name'],[str(self.lib.root)],[])
    def test_source_alias_with_different_case_still_blocks_ancestor_overlap(self):
        source=self.lib.root/'Camera';source.mkdir()
        alias=Path(str(source).replace(self.base.name,self.base.name.upper()))
        if not alias.exists():self.skipTest('Case-sensitive test volume has no case alias')
        with self.assertRaises(ValueError):self.inspector().inspect([str(alias)],[])
    def test_database_changes_still_invalidate_preview(self):
        activity=self.lib.create_activity('活动');inspector=self.inspector();plan=inspector.inspect([],[])
        self.lib.catalog.add_person(activity['id'],'新增人物')
        with self.assertRaises(ValueError):inspector.validate(plan['token'],plan['name'],[],[])
    def test_cancel_statistics_keeps_the_library(self):
        calls=[0]
        def cancelled():calls[0]+=1;return calls[0]>2
        with self.assertRaisesRegex(ValueError,'取消'):self.inspector().inspect([],[],cancelled)
        self.assertEqual((self.lib.root/'photo.JPG').read_bytes(),b'original')
