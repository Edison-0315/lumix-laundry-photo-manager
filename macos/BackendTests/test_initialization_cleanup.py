import errno
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'Backend'))
from managed import ManagedLibrary, OwnedCatalog
from pianji.cleanup import prune_empty
from pianji.locking import LibraryLock
from pianji import safeos


class InitializationTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-create-boundary-')))
        self.addCleanup(shutil.rmtree, self.base)
        self.root = self.base/'Library'

    def test_existing_target_is_unchanged_without_preparation_residue(self):
        self.root.mkdir(); file = self.root/'keep'; file.write_bytes(b'foreign original')
        before = (file.read_bytes(), file.stat().st_mtime_ns)
        with self.assertRaises(FileExistsError) as failure: ManagedLibrary.create(self.root)
        self.assertEqual(failure.exception.errno, errno.EEXIST)
        self.assertEqual((file.read_bytes(), file.stat().st_mtime_ns), before)
        self.assertEqual(list(self.base.iterdir()), [self.root])

    def test_final_name_is_not_visible_until_schema_is_ready(self):
        initialize = OwnedCatalog.__init__
        def inspect(catalog, root, create, guard):
            if create:
                self.assertFalse(self.root.exists(), 'An incomplete library must not use the final name')
            return initialize(catalog, root, create, guard)
        with patch.object(OwnedCatalog, '__init__', inspect):
            library = ManagedLibrary.create(self.root)
        try:
            self.assertEqual(library.root, self.root)
            self.assertEqual(library.marker['root'], str(self.root))
            self.assertEqual(len(library.catalog.rows("SELECT name FROM sqlite_master WHERE type='table'")), 10)
        finally:
            library.close()

    def test_schema_failure_retains_private_preparation_and_releases_lock(self):
        with patch('managed.OwnedCatalog', side_effect=OSError(errno.ENOSPC, 'fixture disk full')):
            with self.assertRaises(Exception):
                ManagedLibrary.create(self.root)
        self.assertFalse(self.root.exists())
        stages = [p for p in self.base.iterdir() if p.name.startswith('.lumix-create-')]
        self.assertEqual(len(stages), 1)
        self.assertTrue((stages[0]/'.片集/catalog.sqlite3').is_file())
        lock = LibraryLock(stages[0]); lock.close()

    def test_competing_final_directory_is_preserved_and_not_opened(self):
        initialize = ManagedLibrary._initialize
        def compete(instance, root, create, **kwargs):
            initialize(instance, root, create, **kwargs)
            if create:
                if self.root.exists():
                    self.root.rename(self.base/'Original')
                self.root.mkdir()
                (self.root/'keep').write_bytes(b'foreign directory')
        with patch.object(ManagedLibrary, '_initialize', compete):
            with self.assertRaises(Exception):
                library = ManagedLibrary.create(self.root)
                library.close()
        self.assertEqual(list(p.name for p in self.root.iterdir()), ['keep'])
        self.assertEqual((self.root/'keep').read_bytes(), b'foreign directory')

    def test_replaced_preparation_database_is_rejected_before_foreign_lock_write(self):
        initialize = ManagedLibrary._initialize; replaced = []
        def replace(instance, root, create, **kwargs):
            if create:
                meta = root/'.片集'; meta.rename(root/'Saved metadata'); meta.mkdir()
                (meta/'catalog.sqlite3').write_bytes(b'foreign database bytes')
                (meta/'keep').write_bytes(b'foreign file')
                replaced.append(meta)
            return initialize(instance, root, create, **kwargs)
        with patch.object(ManagedLibrary, '_initialize', replace):
            with self.assertRaises(ValueError): ManagedLibrary.create(self.root)
        self.assertEqual({p.name for p in replaced[0].iterdir()}, {'catalog.sqlite3', 'keep'})
        self.assertEqual((replaced[0]/'catalog.sqlite3').read_bytes(), b'foreign database bytes')
        self.assertFalse(self.root.exists())


class CleanupBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-cleanup-boundary-')))
        self.addCleanup(shutil.rmtree, self.base)
        self.library = ManagedLibrary.create(self.base/'Library')
        self.addCleanup(self.library.close)
        self.empty = self.library.root/'Empty'; self.empty.mkdir()

    def test_replacement_public_directory_survives_cleanup(self):
        original = self.empty.stat().st_ino
        real_stat = os.stat; fired = [False]; foreign = []
        def replace_after_stat(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            if not fired[0] and info.st_ino == original and kwargs.get('dir_fd') is not None:
                fired[0] = True
                if self.empty.exists():
                    self.empty.rename(self.library.root/'Saved original')
                self.empty.mkdir()
                foreign.append(real_stat(self.empty).st_ino)
            return info
        with patch('pianji.safeos.os.stat', replace_after_stat):
            prune_empty(self.library.root, [self.empty])
        self.assertTrue(fired[0], 'The replacement boundary must actually be exercised')
        self.assertTrue(self.empty.is_dir(), 'The unrelated replacement must survive')
        self.assertEqual(self.empty.stat().st_ino, foreign[0])

    def test_new_file_arriving_before_rmdir_is_restored_with_its_directory(self):
        original = self.empty.stat().st_ino
        real_rmdir = os.rmdir; fired = [False]
        def add_file(path, *args, **kwargs):
            parent = kwargs.get('dir_fd')
            if parent is not None and not fired[0] and os.stat(path, dir_fd=parent).st_ino == original:
                fired[0] = True
                directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                try:
                    file = os.open('incoming.JPG', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
                    try: os.write(file, b'arrived during cleanup')
                    finally: os.close(file)
                finally: os.close(directory)
            return real_rmdir(path, *args, **kwargs)
        with patch('pianji.safeos.os.rmdir', add_file):
            result = prune_empty(self.library.root, [self.empty])
        self.assertTrue(fired[0]); self.assertEqual(result, {'removed': [], 'errors': []})
        self.assertEqual((self.empty/'incoming.JPG').read_bytes(), b'arrived during cleanup')
        self.assertEqual(list((self.library.root/'.片集/staging').iterdir()), [])

    def test_blocked_restore_keeps_incoming_file_and_foreign_destination(self):
        original = self.empty.stat().st_ino; real_rmdir = os.rmdir; fired = [False]
        def block_restore(path, *args, **kwargs):
            parent = kwargs.get('dir_fd')
            if parent is not None and not fired[0] and os.stat(path, dir_fd=parent).st_ino == original:
                fired[0] = True
                directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                try:
                    file = os.open('incoming.JPG', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
                    try: os.write(file, b'keep incoming')
                    finally: os.close(file)
                finally: os.close(directory)
                self.empty.mkdir(); (self.empty/'foreign').write_bytes(b'keep destination')
            return real_rmdir(path, *args, **kwargs)
        with patch('pianji.safeos.os.rmdir', block_restore):
            result = prune_empty(self.library.root, [self.empty])
        self.assertTrue(fired[0]); self.assertEqual(len(result['errors']), 1)
        self.assertEqual((self.empty/'foreign').read_bytes(), b'keep destination')
        retained = list((self.library.root/'.片集/staging').iterdir())
        self.assertEqual(len(retained), 1)
        self.assertEqual((retained[0]/'incoming.JPG').read_bytes(), b'keep incoming')
        self.assertIn(str(retained[0]), result['errors'][0]['message'])

    def test_only_empty_managed_paths_are_pruned(self):
        leaf = self.empty/'Person/JPEG'; leaf.mkdir(parents=True)
        nonempty = self.library.root/'Nonempty'; nonempty.mkdir()
        keep = nonempty/'keep.JPG'; keep.write_bytes(b'keep managed contents'); modified = keep.stat().st_mtime_ns
        outside = self.base/'Outside'; outside.mkdir(); (outside/'keep').write_bytes(b'foreign')
        link = self.library.root/'Link'; link.symlink_to(outside, target_is_directory=True)
        result = prune_empty(self.library.root, [leaf, link, nonempty, self.library.root/'.片集/staging'])
        self.assertFalse(self.empty.exists()); self.assertTrue(link.is_symlink())
        self.assertEqual((outside/'keep').read_bytes(), b'foreign')
        self.assertTrue((self.library.root/'.片集/staging').is_dir())
        self.assertEqual(keep.read_bytes(), b'keep managed contents'); self.assertEqual(keep.stat().st_mtime_ns, modified)
        self.assertEqual(result['errors'], [])


class CleanupReportTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-cleanup-report-')))
        self.addCleanup(shutil.rmtree, self.base)
        self.library = ManagedLibrary.create(self.base/'Library'); self.addCleanup(self.library.close)
        self.activity = self.library.create_activity('Activity')['id']
        self.retained = self.library.root/'.片集/staging/empty-retained'; self.retained.mkdir()
        (self.retained/'incoming.JPG').write_bytes(b'retained incoming')
        self.problem = {'removed': [], 'errors': [{'path': str(self.retained), 'message': 'fixture needs inspection'}]}

    def assert_report(self, result):
        self.assertTrue(any(str(self.retained) in error['message'] for error in result['errors']))
        self.assertEqual((self.retained/'incoming.JPG').read_bytes(), b'retained incoming')

    def test_purge_completion_reports_retained_cleanup_path(self):
        from pianji.domain import FileAsset, PhotoGroup
        source = self.base/'Source.JPG'; source.write_bytes(b'original')
        group = PhotoGroup('a', '', 'A', None, [FileAsset('a', 'a', 'jpeg', str(source))])
        ids = self.library.import_groups([group], 'Activity')['imported']
        self.library.trash_photos(ids)
        with patch('pianji.cleanup.prune_empty', return_value=self.problem):
            result = self.library.purge_trash(ids)
        self.assertEqual(result['deleted'], ids)
        self.assertEqual(self.library.catalog.rows('SELECT id FROM photos'), [])
        self.assertEqual(source.read_bytes(), b'original')
        self.assert_report(result)

    def test_person_completion_reports_retained_cleanup_path(self):
        person = self.library.catalog.add_person(self.activity, 'Person')
        with patch('pianji.cleanup.cleanup_library', return_value=self.problem):
            result = self.library.delete_people([person['id']])
        self.assertEqual(result['deleted_people'], [person['id']])
        self.assertEqual(self.library.catalog.rows('SELECT id FROM people WHERE id=?', (person['id'],)), [])
        self.assert_report(result)

    def test_activity_completion_reports_retained_cleanup_path(self):
        with patch('pianji.cleanup.cleanup_library', return_value=self.problem):
            result = self.library.delete_activity(self.activity)
        self.assertEqual(result['deleted_activity'], self.activity)
        self.assertEqual(self.library.catalog.activities(), [])
        self.assert_report(result)
