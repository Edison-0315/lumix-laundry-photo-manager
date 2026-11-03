"""Preview and EXIF reads. Caller owns the executor, cache and scan registry."""

import base64
from dataclasses import asdict
from ..paths import inside


def get_preview(library, cache, scans, photo_id, kind="thumb", scan_id=None):
    if kind not in ("thumb", "preview", "export", "export-thumb"):
        raise ValueError("未知预览类型")
    if scan_id:
        group = scans.get(scan_id, {}).get(photo_id)
        if not group:
            raise ValueError("来源照片已失效，请重新扫描")
        result = cache.get(group, 640 if kind in ("thumb", "export-thumb") else 4096)
    else:
        with library.journal.access.read():
            library._ready()
            group = library.group(
                photo_id, prefer_export=kind in ("export", "export-thumb")
            )
            result = cache.get(
                group, 640 if kind in ("thumb", "export-thumb") else 4096
            )
    if result.error:
        return {"url": None, "error": result.error}
    return {
        "url": "data:image/jpeg;base64," + base64.b64encode(result.content).decode(),
        "error": None,
    }


def get_photo_details(library, scans, photo_id, scan_id=None):
    from ..metadata import photo_details

    if scan_id:
        group = scans.get(scan_id, {}).get(photo_id)
        if not group:
            raise ValueError("来源照片已失效，请重新扫描")
        return photo_details([asdict(a) for a in group.files], group.captured_at)
    with library.journal.access.read():
        library._ready()
        photo = library.catalog.photo(photo_id)
        for asset in photo["assets"]:
            inside(library.root, asset["path"])
        return photo_details(photo["assets"], photo["captured_at"])
