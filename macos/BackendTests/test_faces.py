import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Backend'))

class FaceTests(unittest.TestCase):
    def test_face_rules_keep_group_background_and_ambiguity_thresholds(self):
        from pianji.faces import Face, FaceResult, choose_person, normalized
        import numpy as np
        def face(vector,size=100):return Face([0,0,size,size],.99,np.asarray(vector,dtype=np.float32))
        one=FaceResult([face([1,0])])
        self.assertEqual(choose_person(FaceResult(),[]),('unclassified',None))
        self.assertEqual(choose_person(FaceResult([face([1,0],200),face([1,0],48)]),[]),('new',None))
        self.assertEqual(choose_person(FaceResult([face([1,0]),face([1,0])]),[]),('group',None))
        self.assertEqual(choose_person(one,[('a',[1,0])]),('match','a'))
        self.assertEqual(choose_person(one,[('a',[.6,.8]),('b',[.59,(1-.59**2)**.5])]),('unclassified',None))
        self.assertEqual(choose_person(one,[('a',[.5,(1-.5**2)**.5])]),('unclassified',None))
        self.assertEqual(choose_person(one,[('a',[.39,(1-.39**2)**.5])]),('new',None))
        self.assertEqual(choose_person(one,[('a',[.4,(1-.4**2)**.5])]),('unclassified',None))
        self.assertEqual(choose_person(one,[('a',[.55,(1-.55**2)**.5])]),('match','a'))
        self.assertEqual(choose_person(one,[('a',[.75,(1-.75**2)**.5]),('b',[.7,(1-.7**2)**.5])]),('match','a'))
        with self.assertRaises(ValueError):normalized([0,0])
        with self.assertRaises(ValueError):normalized([float('nan'),1])
    def test_activity_classification_preserves_manual_edits_and_cancelled_groups(self):
        from pianji.faces import Face, FaceResult, classify_activity
        from managed import ManagedLibrary
        from pianji.domain import PhotoGroup,FileAsset
        import numpy as np
        base=Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-faces-')));self.addCleanup(shutil.rmtree,base)
        library=ManagedLibrary.create(base/'库');self.addCleanup(library.close)
        sources=base/'SD';sources.mkdir();groups=[]
        for n in range(4):
            file=sources/(str(n)+'.JPG');file.write_bytes(bytes([n])*64)
            groups.append(PhotoGroup(str(n),'',str(n),None,[FileAsset(str(n),str(n),'jpeg',str(file))]))
        report=library.import_groups(groups,'活动');ids=report['imported']
        manual=library.catalog.add_person(report['activity_id'],'手动人物')
        library.set_person([ids[0]],manual['id']);library.set_edited([ids[1]],True)
        class Engine:
            def detect_and_embed(self,group):return FaceResult([Face([0,0,100,100],.99,np.array([1,0],dtype=np.float32))])
        result=classify_activity(library,report['activity_id'],Engine())
        self.assertEqual(result['classified'],3);self.assertEqual(result['skipped'],1);self.assertEqual(result['errors'],[])
        self.assertEqual(library.catalog.photo(ids[0])['person_id'],manual['id'])
        self.assertTrue(library.catalog.photo(ids[1])['edited'])
        self.assertEqual(len({library.catalog.photo(i)['person_id'] for i in ids[1:]}),1)
        cancelled=[False]
        class OtherEngine:
            def detect_and_embed(self,group):return FaceResult([Face([0,0,100,100],.99,np.array([0,1],dtype=np.float32))])
        result=classify_activity(library,report['activity_id'],OtherEngine(),cancel=lambda:cancelled[0],progress=lambda n,*a:cancelled.__setitem__(0,n>=2))
        self.assertTrue(result['cancelled'])
        self.assertEqual(result['classified'],1)
        self.assertNotEqual(library.catalog.photo(ids[1])['person_id'],library.catalog.photo(ids[2])['person_id'])
        self.assertEqual((sources/'0.JPG').read_bytes(),bytes([0])*64)
    def test_decode_rejects_symlink_sources(self):
        from pianji.previews import decode
        from pianji.domain import PhotoGroup,FileAsset
        base=Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-face-decode-')));self.addCleanup(shutil.rmtree,base)
        file=base/'original.JPG';file.write_bytes(b'data');link=base/'link.JPG';link.symlink_to(file)
        with self.assertRaises(ValueError):decode(PhotoGroup('x','','x',None,[FileAsset('f','x','jpeg',str(link))]))

    def test_real_model_features_and_corrupt_model_refusal(self):
        from pianji.faces import FaceEngine,subjects
        from pianji.domain import PhotoGroup,FileAsset
        import numpy as np
        root=Path(__file__).resolve().parents[2]
        portrait=root/'build/fixtures/FaceSamples/portrait.jpg'
        engine=FaceEngine(root/'macos/Models')
        result=engine.detect_and_embed(PhotoGroup('p','','p',None,[FileAsset('p','p','jpeg',str(portrait))]))
        self.assertEqual(len(subjects(result)),1)
        face=result.faces[0];self.assertEqual(face.embedding.shape,(128,));self.assertEqual(face.embedding.dtype,np.float32)
        self.assertAlmostEqual(float(np.linalg.norm(face.embedding)),1,places=5)
        np.testing.assert_allclose(face.box,[207.7856,182.5317,145.9389,206.92],atol=1)
        broken=Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-model-')));self.addCleanup(shutil.rmtree,broken)
        (broken/'manifest.json').write_bytes((root/'macos/Models/manifest.json').read_bytes())
        (broken/'face_detection_yunet_2023mar.onnx').write_bytes(b'invalid model')
        with self.assertRaises(ValueError):FaceEngine(broken)

    def test_real_inference_groups_duplicates_and_multi_face_photos(self):
        from pianji.faces import FaceEngine,classify_activity
        from pianji.domain import PhotoGroup,FileAsset
        from managed import ManagedLibrary
        from PIL import Image
        base=Path(os.path.realpath(tempfile.mkdtemp(prefix='Lumix-real-face-')));self.addCleanup(shutil.rmtree,base)
        library=ManagedLibrary.create(base/'库');self.addCleanup(library.close)
        source=base/'照片';source.mkdir()
        root=Path(__file__).resolve().parents[2];original=(root/'build/fixtures/FaceSamples/portrait.jpg').read_bytes()
        (source/'A.JPG').write_bytes(original)
        comment=b'fixture variant';(source/'B.JPG').write_bytes(original[:2]+b'\xff\xfe'+(len(comment)+2).to_bytes(2,'big')+comment+original[2:])
        with Image.open(source/'A.JPG') as image:
            pair=Image.new('RGB',(image.width*2,image.height));pair.paste(image,(0,0));pair.paste(image,(image.width,0));pair.save(source/'Group.JPG',quality=98)
        Image.new('RGB',(512,512),'white').save(source/'Blank.JPG')
        groups=[PhotoGroup(n,'',n,None,[FileAsset(n,n,'jpeg',str(source/(n+'.JPG')))]) for n in ['A','B','Group','Blank']]
        imported=library.import_groups(groups,'活动');engine=FaceEngine(root/'macos/Models')
        report=classify_activity(library,imported['activity_id'],engine)
        self.assertEqual(report['errors'],[]);self.assertEqual(report['classified'],4)
        photos=[library.catalog.photo(i) for i in imported['imported']]
        self.assertEqual(photos[0]['person_id'],photos[1]['person_id'])
        self.assertIsNone(library.catalog.person(photos[0]['person_id'])['role'])
        self.assertEqual(library.catalog.person(photos[2]['person_id'])['role'],'group')
        self.assertEqual(library.catalog.person(photos[3]['person_id'])['role'],'unclassified')
        self.assertEqual((source/'A.JPG').read_bytes(),original)
