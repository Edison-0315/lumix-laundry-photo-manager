"""Exports operations on the existing Library context; no owned resources."""

from pathlib import Path
import hashlib
import os
from ..domain import uid
from ..paths import inside
from ..fileops import digest
from ..safeos import absolute, open_regular


def link_export(library, photo_id, file):
    with library.lock:
        library._ready()
        p = library.catalog.photo(photo_id)
        source = absolute(file)
        if source.suffix.lower() not in (
            ".jpg",
            ".jpeg",
            ".png",
            ".tif",
            ".tiff",
            ".webp",
        ):
            raise ValueError("请选择导出的图片文件")
        from PIL import Image

        # Validate and hash one no-follow descriptor; the journal verifies it
        # again while copying, so a changed export cannot be silently adopted.
        with os.fdopen(open_regular(source), 'rb') as stream:
            before = os.fstat(stream.fileno())
            with Image.open(stream) as im: im.verify()
            stream.seek(0); checksum = hashlib.sha256()
            while True:
                block = stream.read(1024 * 1024)
                if not block: break
                checksum.update(block)
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('成片在读取期间发生变化')
        ident = uid()
        sha = checksum.hexdigest()
        asset = {
            "id": ident,
            "photo_id": photo_id,
            "kind": "export",
            "path": str(source),
            "sha256": sha,
        }
        dst = library._destinations(
            [asset], p["activity_id"], p["person_id"], True, p["stem"]
        )[0]
        originals = library._fresh_assets(p)
        destinations = library._destinations(
            originals, p["activity_id"], p["person_id"], True, p["stem"]
        )
        changes = []
        sql = []
        for a, d in zip(originals, destinations):
            if str(Path(a["path"]).resolve()) != d:
                changes.append(
                    {"src": a["path"], "dst": d, "sha256": a["sha256"], "move": True}
                )
            sql.append(library._asset_sql(a, d))
        # A directly marked JPEG may be one of the originals being moved.
        # Copy it before relocating the originals, in the same journal.
        changes.insert(
            0, {"src": str(source), "dst": dst, "sha256": sha, "move": False}
        )
        sql += [
            (
                "INSERT INTO assets VALUES(?,?,?,?,?)",
                (ident, photo_id, "export", dst, sha),
            ),
            (
                "UPDATE photos SET edited=1,primary_export_id=? WHERE id=?",
                (ident, photo_id),
            ),
        ]
        return library.journal.execute(
            "export", changes, sql, {"photo_id": photo_id, "export_id": ident}
        )


def set_finished(
    library, ids, value, cancel=lambda: False, progress=lambda n, t, m: None
):
    def apply(photo):
        if value:
            if photo["primary_export_id"]:
                return None
            jpeg = next((a for a in photo["assets"] if a["kind"] == "jpeg"), None)
            if not jpeg:
                raise ValueError("RAW不能直接作为成片，请先导出JPEG后关联")
            return library.link_export(photo["id"], jpeg["path"])
        return library.unlink_export(photo["id"])

    return library._batch(ids, apply, cancel, progress)


def unlink_export(library, photo_id, asset_id=None):
    with library.lock:
        library._ready()
        photo = library.catalog.photo(photo_id)
        removed = [
            a
            for a in photo["assets"]
            if a["kind"] == "export" and (asset_id is None or a["id"] == asset_id)
        ]
        if not removed:
            if asset_id:
                raise ValueError("成片关联已不存在，请刷新后重试")
            return None
        changes = []
        sql = []
        for a in removed:
            source = inside(library.root, a["path"])
            if source.exists():
                sha = digest(source)
                destination = inside(
                    library.root,
                    library.catalog.meta
                    / "取消关联保留"
                    / photo_id
                    / a["id"]
                    / source.name,
                )
                changes.append(
                    {
                        "src": str(source),
                        "dst": str(destination),
                        "sha256": sha,
                        "move": True,
                    }
                )
            else:
                sha = a["sha256"]
                destination = source
            sql += [
                (
                    "INSERT INTO detached_exports VALUES(?,?,?,?)",
                    (a["id"], photo_id, str(destination), sha),
                ),
                ("DELETE FROM assets WHERE id=?", (a["id"],)),
            ]
        remaining = [
            a for a in photo["assets"] if a["kind"] == "export" and a not in removed
        ]
        primary = (
            photo["primary_export_id"]
            if any(a["id"] == photo["primary_export_id"] for a in remaining)
            else (remaining[-1]["id"] if remaining else None)
        )
        sql.append(
            ("UPDATE photos SET primary_export_id=? WHERE id=?", (primary, photo_id))
        )
        return library.journal.execute(
            "unlink_export",
            changes,
            sql,
            {"photo_id": photo_id, "detached": [a["id"] for a in removed]},
        )

def set_export_cover(library, photo_id, asset_id):
    with library.lock:
        library._ready()
        photo = library.catalog.photo(photo_id)
        if not any(a['id'] == asset_id and a['kind'] == 'export' for a in photo['assets']):
            raise ValueError('成片不存在或不属于此照片')
        return library.journal.execute('export_cover', [], [
            ('UPDATE photos SET primary_export_id=? WHERE id=?', (asset_id, photo_id))])
