"""Read-only source scanning; publish a new scan only after completion."""

from pathlib import Path
from dataclasses import asdict
from ..domain import uid
from ..discovery import scan_source


def scan_photos(
    root, scans, cancel=lambda: False, progress=lambda n, t, m: None, formats="both"
):
    errors = []
    groups = scan_source(root, cancel, progress, errors=errors, formats=formats)
    if cancel():
        return {"cancelled": True}
    if not groups and errors:
        return {"photos": [], "errors": errors, "cancelled": False}
    scan_id = uid()
    scans[scan_id] = {g.id: g for g in groups}

    def relative(path):
        p = Path(path).relative_to(root)
        return "" if p == Path(".") else p.as_posix()

    return {
        "scan_id": scan_id,
        "photos": [
            {
                **asdict(g),
                "relative_dir": relative(g.source_dir),
                "relative_dirs": sorted(
                    {relative(Path(a.path).parent) for a in g.files}
                ),
            }
            for g in groups
        ],
        "errors": errors,
        "cancelled": False,
    }
