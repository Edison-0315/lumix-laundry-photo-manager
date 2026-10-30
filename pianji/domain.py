from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import uuid

def uid(): return uuid.uuid4().hex

@dataclass
class FileAsset:
    id: str
    photo_id: str
    kind: str
    path: str
    sha256: Optional[str] = None

@dataclass
class PhotoGroup:
    id: str
    source_dir: str
    stem: str
    captured_at: Optional[str]
    files: list[FileAsset]
    error: Optional[str] = None

@dataclass
class PreviewResult:
    path: Optional[str] = None
    error: Optional[str] = None

@dataclass
class Operation:
    id: str
    kind: str
    phase: str
    payload: dict
    error: Optional[str] = None

@dataclass
class TaskSnapshot:
    id: str
    status: str = 'queued'
    done: int = 0
    total: int = 0
    message: str = ''
    errors: list = field(default_factory=list)
    result: object = None

def jsonable(value):
    if hasattr(value,'__dataclass_fields__'): return asdict(value)
    if isinstance(value,Path): return str(value)
    raise TypeError(type(value).__name__)
