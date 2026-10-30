from PIL import Image
from pianji.discovery import scan_source
from pianji.previews import PreviewCache

def test_oriented_preview_and_failure(tmp_path):
    source=tmp_path/'source'; source.mkdir()
    im=Image.new('RGB',(100,50),'red'); exif=im.getexif(); exif[274]=6
    im.save(source/'rotated.jpg',exif=exif)
    group=scan_source(source)[0]
    cache=PreviewCache(tmp_path/'cache')
    result=cache.get(group,640)
    assert result.error is None
    with Image.open(result.path) as out: assert out.size==(50,100)
    (source/'rotated.jpg').write_bytes(b'bad')
    assert cache.get(group,640).error
