import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Backend'))
from main import Session
from managed import ManagedLibrary

class SourceProtectionTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-source-guard-')))
        self.addCleanup(shutil.rmtree, self.base)
        self.root = self.base / 'Library'
        library = ManagedLibrary.create(self.root); library.close()
        (self.root/'Photos').mkdir()
        self.session = Session(); self.addCleanup(self.session.close)
    def request(self, method, **params):
        return self.session.dispatch(method, params, lambda *args: None)
    def test_open_refuses_source_root_ancestor_descendant_and_volume_alias_before_writes(self):
        aliases = [self.root, self.base, self.root/'Photos']
        upper = self.base/'LIBRARY'
        if upper.exists() and os.path.samefile(upper, self.root): aliases.append(upper)
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for source in aliases:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, '只读来源'):
                    self.request('open', root=str(self.root), protected_roots=[str(source)])
        self.assertIsNone(self.session.library)
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_writes_recovery_and_purge_refuse_new_overlap_and_keep_source_protection(self):
        self.request('open', root=str(self.root))
        for method, params in [('create_activity', {'name':'No write'}), ('recover', {}), ('purge_trash', {'ids':[]})]:
            with self.subTest(method=method):
                with self.assertRaisesRegex(ValueError, '只读来源'):
                    self.request(method, protected_roots=[str(self.root/'Photos')], **params)
        # A subsequent request cannot silently drop already registered source roots.
        with self.assertRaisesRegex(ValueError, '只读来源'): self.request('create_activity', name='Still blocked')
        self.assertEqual(self.session.library.catalog.activities(), [])
    def test_sibling_with_same_prefix_is_allowed_but_import_inside_library_is_refused(self):
        source = self.base/'Library-Source';source.mkdir()
        self.request('open', root=str(self.root), protected_roots=[str(source)])
        result = self.request('create_activity', name='Allowed')
        self.assertEqual(result['name'], 'Allowed')
        with self.assertRaisesRegex(ValueError, '只读来源'):
            self.request('import', source_root=str(self.root/'Photos'), activity='No import', groups=[])
