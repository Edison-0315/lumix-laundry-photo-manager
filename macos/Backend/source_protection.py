"""Reject library writes overlapping any read-only source in this session."""
import fcntl
import os
from pathlib import Path
from pianji.safeos import absolute, RootAccess

def _physical(access):
    return Path(os.fsdecode(fcntl.fcntl(access.fd, 50, b'\0'*1024).split(b'\0', 1)[0]))

def reject_source_overlap(root, sources):
    if not sources: return
    root = absolute(root)
    access = RootAccess(root)
    try:
        actual = _physical(access)
        for value in sources:
            source = absolute(value)
            if root.is_relative_to(source) or source.is_relative_to(root):
                raise ValueError('照片库与只读来源重叠，请选择独立目录')
            try: protected = RootAccess(source)
            except FileNotFoundError: continue
            try:
                physical = _physical(protected)
                if actual.is_relative_to(physical) or physical.is_relative_to(actual):
                    raise ValueError('照片库与只读来源重叠，请选择独立目录')
            finally: protected.close()
    finally: access.close()
