import os
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Backend'))
from managed import ManagedLibrary,validate_marker
from pianji import safeos

class VolumeIdentityTests(unittest.TestCase):
    def setUp(self):
        self.base=Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-volume-id-')))
        self.addCleanup(shutil.rmtree,self.base)
        self.library=ManagedLibrary.create(self.base/'Library');self.addCleanup(self.library.close)
    def test_marker_accepts_changed_device_only_with_matching_volume_and_inodes(self):
        lib=self.library;marker=dict(lib.marker)
        volume=safeos.volume_uuid_fd(lib._access.fd)
        self.assertEqual(marker['volume_uuid'],volume)
        marker['root_identity']=[987654321,lib._access.identity[1]]
        marker['catalog_identity']=[987654321,lib._catalog_identity[1]]
        validate_marker(marker,lib.root,lib._access.identity,lib._catalog_identity,volume)
        for bad in [dict(marker,volume_uuid='0'*32),dict(marker,root_identity=[987654321,0]),dict(marker,catalog_identity=[987654321,0])]:
            with self.assertRaises(ValueError):validate_marker(bad,lib.root,lib._access.identity,lib._catalog_identity,volume)
        legacy=dict(marker);legacy.pop('volume_uuid')
        with self.assertRaises(ValueError):validate_marker(legacy,lib.root,lib._access.identity,lib._catalog_identity,volume)
    def test_file_receipt_uses_volume_uuid_and_supports_strict_same_device_legacy_receipts(self):
        file=self.library.root/'Photo';file.write_bytes(b'owned')
        stable=safeos.identity(file);legacy=safeos.identity(file,legacy=True)
        self.assertIsInstance(stable[0],str);self.assertEqual(len(stable[0]),32)
        self.assertEqual(stable[1],legacy[1]);self.assertTrue(safeos.matches_identity(file,stable));self.assertTrue(safeos.matches_identity(file,legacy))
        self.assertFalse(safeos.matches_identity(file,[legacy[0]+100,legacy[1]]))
        file.rename(file.with_name('Saved'));file.write_bytes(b'owned')
        self.assertFalse(safeos.matches_identity(file,stable));self.assertFalse(safeos.matches_identity(file,legacy))
    def test_persistent_receipts_and_recycle_plan_keep_their_separate_identity_contracts(self):
        lib=self.library;file=self.base/'Source';file.write_bytes(b'original')
        from pianji.safeos import digest
        lib.journal.execute('copy',[{'src':str(file),'dst':str(lib.root/'Target'),'move':False,'sha256':digest(file)}],[])
        receipt=lib.catalog.operation(lib.catalog.rows('SELECT id FROM operations')[0]['id'])['payload']['changes'][0]['identity']
        self.assertIsInstance(receipt[0],str)
        from pianji.library_recycle import LibraryRecycleInspector
        plan=LibraryRecycleInspector(lib).inspect([],[])
        self.assertTrue(all(isinstance(n,int) for n in plan['root_identity']+plan['catalog_identity']))
    def test_legacy_native_marker_opens_on_same_device_without_automatic_rewrite(self):
        lib=self.library;root=lib.root;lib.close()
        path=root/'.片集/macos-library.json';marker=json.loads(path.read_text());marker.pop('volume_uuid')
        path.write_text(json.dumps(marker));before=path.read_bytes()
        opened=ManagedLibrary.open(root)
        try:opened._ready()
        finally:opened.close()
        self.assertEqual(path.read_bytes(),before)
    def test_live_library_refuses_different_volume_even_if_numeric_device_id_is_reused(self):
        with patch('pianji.safeos.volume_uuid_fd',return_value='0'*32):
            with self.assertRaises(safeos.OwnershipError):self.library._guard()
