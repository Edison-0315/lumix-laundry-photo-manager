"""Trash operations on the existing Library context; no owned resources."""

from pathlib import Path
import json
from ..paths import inside
from ..fileops import digest


def trash_photos(library, ids, cancel=lambda: False, progress=lambda n, t, m: None):
    def apply(photo):
        changes = []
        sql = []
        locations = []
        originals = library._fresh_assets(photo, allow_missing=True)
        detached = library.catalog.rows(
            "SELECT * FROM detached_exports WHERE photo_id=?", (photo["id"],)
        )
        for table, items in [("assets", originals), ("detached_exports", detached)]:
            for a in items:
                src = inside(library.root, a["path"])
                dst = src
                sha = a["sha256"]
                if src.is_file():
                    sha = digest(src)
                    dst = inside(
                        library.root,
                        library.catalog.meta
                        / "回收站"
                        / photo["id"]
                        / a["id"]
                        / src.name,
                    )
                    changes.append(
                        {"src": str(src), "dst": str(dst), "sha256": sha, "move": True}
                    )
                locations.append({"table": table, "id": a["id"], "original": str(src)})
                if table == "assets":
                    sql.append(library._asset_sql({**a, "sha256": sha}, str(dst)))
                else:
                    sql.append(
                        (
                            "UPDATE detached_exports SET path=?,sha256=? WHERE id=?",
                            (str(dst), sha, a["id"]),
                        )
                    )
        sql.append(
            (
                "INSERT INTO trashed_photos(photo_id,payload) VALUES(?,?)",
                (photo["id"], json.dumps(locations, ensure_ascii=False)),
            )
        )
        return library.journal.execute(
            "trash",
            changes,
            sql,
            {
                "photo_id": photo["id"],
                "cleanup_dirs": [
                    str(Path(a["path"]).parent) for a in originals + detached
                ],
            },
        )

    return library._batch(ids, apply, cancel, progress)


def restore_photos(library, ids, cancel=lambda: False, progress=lambda n, t, m: None):
    def apply(photo):
        from ..permanent import pending

        if pending(library.catalog, photo["id"]):
            raise ValueError(
                "此照片的永久删除尚未完成，不能恢复；请关闭占用程序后重试永久删除"
            )
        record = library.catalog.rows(
            "SELECT payload FROM trashed_photos WHERE photo_id=?", (photo["id"],)
        )
        if not record:
            return None
        changes = []
        sql = []
        originals = library._fresh_assets(photo, allow_missing=True)
        destinations = library._destinations(
            originals,
            photo["activity_id"],
            photo["person_id"],
            photo["edited"],
            photo["stem"],
        )
        for a, dst in zip(originals, destinations):
            if not a.get("_missing"):
                changes.append(
                    {"src": a["path"], "dst": dst, "sha256": a["sha256"], "move": True}
                )
            sql.append(library._asset_sql(a, dst))
        for entry in json.loads(record[0]["payload"]):
            if entry["table"] != "detached_exports":
                continue
            a = library.catalog.rows(
                "SELECT * FROM detached_exports WHERE id=?", (entry["id"],)
            )[0]
            src = inside(library.root, a["path"])
            dst = inside(library.root, entry["original"])
            if src == dst:
                continue
            if dst.exists():
                raise FileExistsError("保留版本原位置已有文件，请先移开同名文件后恢复")
            sha = a["sha256"]
            if src.is_file():
                sha = digest(src)
                changes.append(
                    {"src": str(src), "dst": str(dst), "sha256": sha, "move": True}
                )
            sql.append(
                (
                    "UPDATE detached_exports SET path=?,sha256=? WHERE id=?",
                    (str(dst), sha, a["id"]),
                )
            )
        sql.append(("DELETE FROM trashed_photos WHERE photo_id=?", (photo["id"],)))
        sql.append(
            (
                "DELETE FROM deleted_activities WHERE activity_id=?",
                (photo["activity_id"],),
            )
        )
        return library.journal.execute(
            "restore", changes, sql, {"photo_id": photo["id"]}
        )

    return library._batch(ids, apply, cancel, progress, include_trashed=True)


def purge_trash(library, ids, cancel=lambda: False, progress=lambda n, t, m: None):
    from ..permanent import purge

    return purge(library, ids, cancel, progress)
