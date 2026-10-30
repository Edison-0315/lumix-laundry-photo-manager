from pathlib import Path
import pytest
from PIL import Image
from pianji.library import Library
from pianji.discovery import scan_source
from pianji.photoshop import open_in_photoshop

def test_spaces_and_chinese_are_single_argument_and_open_does_not_mark_edited(tmp_path):
    src=tmp_path/'SD'; src.mkdir(); Image.new('RGB',(20,20)).save(src/'模特 一.jpg')
    lib=Library(tmp_path/'库'); lib.import_groups(scan_source(src),'活动')
    exe=tmp_path/'Adobe Photoshop'/'Photoshop.exe'; exe.parent.mkdir(); exe.write_bytes(b'fake launcher')
    calls=[]
    p=lib.catalog.photos()[0]
    open_in_photoshop(lib,p['id'],'jpeg',str(exe),launcher=lambda args,**kwargs:calls.append((args,kwargs)))
    assert calls==[([str(exe),p['assets'][0]['path']],{'shell':False})]
    assert not lib.catalog.photo(p['id'])['edited']
    with pytest.raises(ValueError,match='RAW'): open_in_photoshop(lib,p['id'],'raw',str(exe),launcher=lambda *a,**kw:None)
