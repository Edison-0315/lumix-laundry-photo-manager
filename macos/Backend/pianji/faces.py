from dataclasses import dataclass,field
from pathlib import Path
import json
import hashlib
import numpy as np
from .previews import decode

@dataclass
class Face:
    box: list
    confidence: float
    embedding: object

@dataclass
class FaceResult:
    faces: list[Face]=field(default_factory=list)

def normalized(vector):
    v=np.asarray(vector,dtype=np.float32).flatten()
    norm=float(np.linalg.norm(v))
    if norm<=0 or not np.isfinite(norm): raise ValueError('无效人脸特征')
    return v/norm

def subjects(result):
    faces=[f for f in result.faces if f.confidence>=.9 and min(f.box[2:])>=48]
    if not faces: return []
    largest=max(f.box[2]*f.box[3] for f in faces)
    return [f for f in faces if f.box[2]*f.box[3]>=largest*.08]

def choose_person(result,people):
    faces=subjects(result)
    if len(faces)>1: return 'group',None
    if len(faces)!=1: return 'unclassified',None
    v=normalized(faces[0].embedding)
    scores=sorted([(float(v@normalized(embedding)),ident) for ident,embedding in people],reverse=True)
    if scores and scores[0][0]>=.55:
        if len(scores)>1 and scores[0][0]-scores[1][0]<.05: return 'unclassified',None
        return 'match',scores[0][1]
    if scores and scores[0][0]>=.40: return 'unclassified',None
    return 'new',None

class FaceEngine:
    def __init__(self,model_root):
        import cv2
        cv2.setNumThreads(2)
        root=Path(model_root)
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        for entry in manifest['models']:
            path=root/entry['filename']
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
                raise ValueError('人脸模型缺失或校验失败，请重新解压完整程序')
        # OpenCV's Windows filename loader is not Unicode-safe. Python reads
        # the verified files; OpenCV consumes buffers without a path conversion.
        empty=np.empty(0,dtype=np.uint8)
        detector=np.frombuffer((root/'face_detection_yunet_2023mar.onnx').read_bytes(),dtype=np.uint8)
        recognizer=np.frombuffer((root/'face_recognition_sface_2021dec.onnx').read_bytes(),dtype=np.uint8)
        self.detector=cv2.FaceDetectorYN.create('onnx',detector,empty,(320,320),.9,.3,5000)
        self.recognizer=cv2.FaceRecognizerSF.create('onnx',recognizer,empty)

    def detect_and_embed(self,group):
        import cv2
        im=decode(group); im.thumbnail((1600,1600))
        bgr=cv2.cvtColor(np.asarray(im),cv2.COLOR_RGB2BGR)
        self.detector.setInputSize((bgr.shape[1],bgr.shape[0]))
        _,rows=self.detector.detect(bgr)
        result=FaceResult()
        if rows is not None:
            for row in rows:
                crop=self.recognizer.alignCrop(bgr,row)
                vec=self.recognizer.feature(crop).flatten()
                result.faces.append(Face(row[:4].tolist(),float(row[-1]),normalized(vec)))
        return result

def classify_activity(lib,activity_id,engine,cancel=lambda:False,progress=lambda n,t,m:None):
    report={'classified':0,'skipped':0,'errors':[],'cancelled':False}
    with lib.lock:
        lib._ready()
        photos=lib.catalog.photos(activity_id)
        for n,p in enumerate(photos):
            if cancel(): report['cancelled']=True; break
            try:
                if p['manual_person']: report['skipped']+=1; continue
                people=lib.catalog.people(activity_id)
                known=[(person['id'],json.loads(person['embedding'])) for person in people if person['embedding']]
                result=engine.detect_and_embed(lib.group(p['id']))
                decision,ident=choose_person(result,known)
                if decision in ('group','unclassified'): ident=next(person['id'] for person in people if person['role']==decision)
                if decision=='new':
                    names={person['name'] for person in people}; index=1
                    while f'人物{index:02d}' in names: index+=1
                    person=lib.catalog.add_person(activity_id,f'人物{index:02d}',embedding=normalized(subjects(result)[0].embedding).tolist())
                    ident=person['id']
                moved=lib.set_person([p['id']],ident,manual=False)
                if moved['errors']: report['errors']+=moved['errors']
                else: report['classified']+=1
            except Exception as e: report['errors'].append({'id':p['id'],'message':str(e)})
            finally: progress(n+1,len(photos),'在本机识别人脸')
    return report
