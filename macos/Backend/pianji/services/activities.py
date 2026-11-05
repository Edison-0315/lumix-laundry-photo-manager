"""Activities operations on the existing Library context; no owned resources."""

from ..paths import safe_name, inside


def create_activity(library, name):
    with library.lock:
        library._ready()
        safe_name(name)
        if any(
            a["name"].casefold() == name.casefold()
            for a in library.catalog.activities()
        ):
            raise ValueError("同名活动已存在，请选择已有活动")
        deleted = library.catalog.rows(
            "SELECT a.* FROM activities a JOIN deleted_activities d ON d.activity_id=a.id WHERE lower(a.name)=lower(?)",
            (name,),
        )
        if deleted:
            if library.catalog.rows(
                "SELECT id FROM photos WHERE activity_id=?", (deleted[0]["id"],)
            ):
                raise ValueError("此活动仍有照片在回收站，请先恢复照片或使用其他名称")
            library.journal.execute(
                "recreate_activity",
                [],
                [
                    (
                        "DELETE FROM deleted_activities WHERE activity_id=?",
                        (deleted[0]["id"],),
                    )
                ],
            )
            return deleted[0]
        folder = inside(library.root, library.root / name)
        import os
        if os.path.lexists(folder): raise FileExistsError('同名文件夹已存在，请使用其他活动名称')
        # Allocate physical directories lazily in the journal's first file transaction.
        return library.catalog.activity(name)


def delete_activity(
    library, activity_id, cancel=lambda: False, progress=lambda n, t, m: None
):
    with library.lock:
        library._ready()
        if not any(a["id"] == activity_id for a in library.catalog.activities()):
            raise ValueError("活动不存在或已删除")
        ids = [p["id"] for p in library.catalog.photos(activity_id)]
        result = library.trash_photos(ids, cancel, progress)
        result["deleted_activity"] = None
        if cancel():
            result["cancelled"] = True
        if not result["errors"] and not result["cancelled"]:
            library.journal.execute(
                "delete_activity",
                [],
                [
                    (
                        "INSERT INTO deleted_activities(activity_id) VALUES(?)",
                        (activity_id,),
                    )
                ],
            )
            result["deleted_activity"] = activity_id
            from ..cleanup import cleanup_library

            folder = library.catalog.rows(
                "SELECT folder FROM activities WHERE id=?", (activity_id,)
            )[0]["folder"]
            cleanup = cleanup_library(library, library.root / folder)
            result["errors"].extend({"id": activity_id, "message": "活动已移入回收站；空目录清理需检查：" + issue["path"] + "；" + issue["message"]}
                                    for issue in cleanup["errors"])
        return result
