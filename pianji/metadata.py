"""Read actual file sizes and EXIF on demand, without decoding RAW pixels."""
from pathlib import Path
from datetime import datetime
from fractions import Fraction
import math
import exifread


def _number(tag):
    if tag is None:return None
    try:
        values=tag.values
        if isinstance(values,(list,tuple)) and not values:return None
        value=values[0] if isinstance(values,(list,tuple)) else values
        result=float(value)
        return result if math.isfinite(result) else None
    except (AttributeError,TypeError,ValueError,ZeroDivisionError,OverflowError):return None


def _read(path):
    with path.open('rb') as stream:
        tags=exifread.process_file(stream,details=False,strict=False)
    text=lambda key:str(tags.get(key,'')).strip().strip('\x00') or None
    make,model=text('Image Make'),text('Image Model')
    camera=model
    if make and model and not model.casefold().startswith(make.casefold()):camera=make+' '+model
    elif make and not model:camera=make
    date=None
    value=text('EXIF DateTimeOriginal') or text('EXIF DateTimeDigitized') or text('Image DateTime')
    if value:
        try:date=datetime.strptime(value[:19],'%Y:%m:%d %H:%M:%S').isoformat(' ')
        except ValueError:pass
    focal=_number(tags.get('EXIF FocalLength'));aperture=_number(tags.get('EXIF FNumber'))
    exposure=_number(tags.get('EXIF ExposureTime'));iso=_number(tags.get('EXIF ISOSpeedRatings') or tags.get('EXIF PhotographicSensitivity'))
    bias=_number(tags.get('EXIF ExposureBiasValue'))
    shutter=None
    if exposure and exposure>0:
        shutter=(str(Fraction(exposure).limit_denominator(100000)) if exposure<1 else f'{exposure:g}')+' s'
    return {'camera':camera,'lens':text('EXIF LensModel'),'captured_at':date,
        'focal_length':f'{focal:g} mm' if focal and focal>0 else None,
        'aperture':f'f/{aperture:g}' if aperture and aperture>0 else None,
        'shutter':shutter,'iso':f'{iso:g}' if iso and iso>0 else None,
        'exposure_bias':f'{bias:+g} EV' if bias is not None else None}


def photo_details(assets,captured_at=None):
    keys=('camera','lens','captured_at','focal_length','aperture','shutter','iso','exposure_bias')
    result={k:None for k in keys};result.update(files=[],total_bytes=None,errors=[])
    available=[]
    for a in assets:
        path=Path(a['path']);size=None
        try:
            size=path.stat().st_size
            if not path.is_file():raise OSError('文件不可用')
            available.append((a,path))
        except OSError as e:result['errors'].append({'path':str(path),'message':str(e)})
        result['files'].append({'kind':a['kind'],'name':path.name,'bytes':size})
    # Original camera EXIF takes precedence over exported editor metadata.
    for a,path in sorted(available,key=lambda pair: {'jpeg':0,'raw':1,'export':2}.get(pair[0]['kind'],3)):
        if a['kind'] not in ('jpeg','raw','export'):continue
        if all(result[k] is not None for k in keys):break
        try:
            for k,value in _read(path).items():
                if result[k] is None and value is not None:result[k]=value
        except Exception as e:result['errors'].append({'path':str(path),'message':str(e)})
    if not result['captured_at'] and captured_at:result['captured_at']=captured_at.replace('T',' ')
    if result['files'] and all(f['bytes'] is not None for f in result['files']):
        result['total_bytes']=sum(f['bytes'] for f in result['files'])
    return result
