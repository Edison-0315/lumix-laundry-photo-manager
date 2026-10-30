import numpy as np
from pianji.faces import choose_person,FaceResult,Face

def face(vector=(1.,0.,0.),confidence=.99,size=100):
    return Face([0,0,size,size],confidence,np.array(vector,dtype=float))

def test_two_subjects_go_to_group():
    assert choose_person(FaceResult([face(),face()]),[])==('group',None)

def test_no_or_low_quality_face_is_unclassified():
    assert choose_person(FaceResult([]),[])==('unclassified',None)
    assert choose_person(FaceResult([face(confidence=.6)]),[])==('unclassified',None)
    assert choose_person(FaceResult([face(size=15)]),[])==('unclassified',None)

def test_same_embedding_groups_same_person():
    assert choose_person(FaceResult([face()]),[('a',[1,0,0])])==('match','a')

def test_distant_faces_create_distinct_people():
    assert choose_person(FaceResult([face((0,1,0))]),[('a',[1,0,0])])==('new',None)
    assert choose_person(FaceResult([face((.46,.8879,0))]),[('a',[1,0,0])])==('unclassified',None)

def test_manual_person_survives_rerun(tmp_path):
    from PIL import Image
    from pianji.library import Library
    from pianji.discovery import scan_source
    from pianji.faces import classify_activity
    src=tmp_path/'sd'; src.mkdir(); Image.new('RGB',(100,100)).save(src/'a.jpg')
    lib=Library(tmp_path/'lib'); result=lib.import_groups(scan_source(src),'活动')
    p=lib.catalog.photos()[0]; person=lib.catalog.add_person(p['activity_id'],'我确认的人')
    lib.set_person([p['id']],person['id']); lib.set_edited([p['id']],True)
    class Engine:
        def detect_and_embed(self,g): raise AssertionError('manual photo must not be processed')
    classify_activity(lib,p['activity_id'],Engine())
    after=lib.catalog.photo(p['id'])
    assert after['person_id']==person['id'] and after['edited']

def test_real_models_load_from_chinese_path(tmp_path):
    from pathlib import Path
    import shutil
    from pianji.faces import FaceEngine
    models=Path(__file__).resolve().parents[1]/'models'
    target=tmp_path/'模型 中文 路径';shutil.copytree(models,target)
    engine=FaceEngine(target)
    assert engine.detector is not None and engine.recognizer is not None
