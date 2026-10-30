from pathlib import Path
import re

def safe_name(value):
    if not isinstance(value,str) or not value or value!=value.strip() or len(value)>90:
        raise ValueError('名称须为1–90个字符，首尾不能有空格')
    if value.endswith('.') or re.search(r'[<>:"/\\|?*\x00-\x1f]',value) or value in ('.','..'):
        raise ValueError('名称不能包含路径符号、控制字符或末尾句点')
    if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',value,re.I):
        raise ValueError('此名称是Windows保留名称')
    return value

def inside(root,path):
    root=Path(root).resolve(); path=Path(path).resolve()
    if not path.is_relative_to(root): raise ValueError('路径超出了照片库范围')
    return path
