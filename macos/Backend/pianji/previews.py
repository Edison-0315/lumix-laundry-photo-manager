"""Original classification RGB preprocessing, with no-follow descriptor reads."""
from io import BytesIO
import os
from PIL import Image,ImageOps
from .safeos import open_regular


def _image_preview(image,size=None):
    if size:
        image.draft('RGB',(size,size))
        image.thumbnail((size,size),Image.Resampling.LANCZOS,reducing_gap=3.0)
    return ImageOps.exif_transpose(image).convert('RGB')


def decode(group,size=None):
    for asset in sorted(group.files,key=lambda asset:asset.kind!='jpeg'):
        try:
            if asset.kind in ('jpeg','export'):
                with os.fdopen(open_regular(asset.path),'rb') as stream,Image.open(stream) as image:
                    return _image_preview(image,size)
            if asset.kind=='raw':
                import rawpy
                with os.fdopen(open_regular(asset.path),'rb') as stream,rawpy.imread(stream) as raw:
                    try:
                        thumbnail=raw.extract_thumb()
                        if thumbnail.format==rawpy.ThumbFormat.JPEG:
                            with Image.open(BytesIO(thumbnail.data)) as image:return _image_preview(image,size)
                        return _image_preview(Image.fromarray(thumbnail.data),size)
                    except (rawpy.LibRawNoThumbnailError,rawpy.LibRawUnsupportedThumbnailError):
                        return _image_preview(Image.fromarray(raw.postprocess(use_camera_wb=True,half_size=True,output_bps=8)),size)
        except Exception:continue
    raise ValueError('无法读取照片图像；原文件保留，请检查格式或使用外部编辑器。')
