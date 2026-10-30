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

def test_thumbnail_decode_is_reduced_before_full_rgb_conversion(tmp_path):
    from pianji.previews import decode
    source=tmp_path/'source';source.mkdir()
    im=Image.new('RGB',(6000,4000),'red');exif=im.getexif();exif[274]=6;im.save(source/'big.jpg',exif=exif)
    image=decode(scan_source(source)[0],size=640)
    assert max(image.size)<=640 and image.height>image.width

def test_different_thumbnails_decode_concurrently(tmp_path,monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from pianji import previews
    source=tmp_path/'source';source.mkdir()
    Image.new('RGB',(1200,800),'red').save(source/'a.jpg');Image.new('RGB',(1200,800),'blue').save(source/'b.jpg')
    groups=scan_source(source);cache=PreviewCache(tmp_path/'cache');barrier=threading.Barrier(2)
    original=previews.decode
    def decode(*args,**kwargs):
        barrier.wait(timeout=2)
        return original(*args,**kwargs)
    monkeypatch.setattr(previews,'decode',decode)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(cache.get,groups))
    assert all(r.path and not r.error for r in results)

def test_prune_cannot_delete_cache_entry_being_read(tmp_path,monkeypatch):
    import threading
    from pathlib import Path
    from concurrent.futures import ThreadPoolExecutor
    source=tmp_path/'source';source.mkdir()
    Image.new('RGB',(400,400),'red').save(source/'a.jpg');Image.new('RGB',(400,400),'blue').save(source/'b.jpg')
    a,b=scan_source(source);cache=PreviewCache(tmp_path/'cache');first=cache.get(a);path=Path(first.path);cache.limit=path.stat().st_size+100
    entered=threading.Event();release=threading.Event();exists=Path.exists
    def pause_hit(p):
        result=exists(p)
        if p==path and threading.current_thread().name.startswith('cache-reader'):
            entered.set();assert release.wait(5)
        return result
    monkeypatch.setattr(Path,'exists',pause_hit)
    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='cache-reader') as executor:
        reading=executor.submit(cache.get,a)
        try:
            assert entered.wait(5);other=cache.get(b);assert not other.error
        finally:release.set()
        result=reading.result()
    assert not result.error
    with Image.open(result.path) as image:assert image.size==(400,400)
