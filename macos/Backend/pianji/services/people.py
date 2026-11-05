"""People operations on the existing Library context; no owned resources."""

from pathlib import Path
from ..paths import safe_name


def set_person(
    library,
    ids,
    person_id,
    manual=True,
    cancel=lambda: False,
    progress=lambda n, t, m: None,
):
    library.catalog.person(person_id)
    return library._batch(
        ids,
        lambda p: library._move(p, person_id=person_id, manual=manual),
        cancel,
        progress,
    )


def rename_person(library, person_id, name):
    with library.lock:
        library._ready()
        safe_name(name)
        person = library.catalog.person(person_id)
        if person["role"]:
            raise ValueError("合照和待分类名称固定")
        if any(
            p["name"].casefold() == name.casefold() and p["id"] != person_id
            for p in library.catalog.people(person["activity_id"])
        ):
            raise ValueError("同名人物已存在，请使用合并")
        # One journal for the entire rename, so no mixed-name partial result.
        changes = []
        sql = []
        reserved = set()
        for p in library.catalog.photos(person["activity_id"]):
            if p["person_id"] != person_id:
                continue
            originals = library._fresh_assets(p)
            destinations = library._destinations(
                originals,
                p["activity_id"],
                person_id,
                p["edited"],
                p["stem"],
                name,
                reserved,
            )
            reserved.update(d.casefold() for d in destinations)
            for a, d in zip(originals, destinations):
                if str(Path(a["path"]).resolve()) != d:
                    changes.append(
                        {
                            "src": a["path"],
                            "dst": d,
                            "sha256": a["sha256"],
                            "move": True,
                        }
                    )
                sql.append(library._asset_sql(a, d))
        sql.append(
            ("UPDATE people SET name=?,folder=? WHERE id=?", (name, name, person_id))
        )
        return library.journal.execute("rename", changes, sql)


def merge_people(
    library, source_id, target_id, cancel=lambda: False, progress=lambda n, t, m: None
):
    with library.lock:
        library._ready()
        src = library.catalog.person(source_id)
        target = library.catalog.person(target_id)
        if (
            source_id == target_id
            or src["activity_id"] != target["activity_id"]
            or src["role"]
        ):
            raise ValueError("请选择同活动内不同的普通人物")
        ids = [
            p["id"]
            for p in library.catalog.photos(src["activity_id"])
            if p["person_id"] == source_id
        ]
        result = library.set_person(ids, target_id, cancel=cancel, progress=progress)
        if not result["errors"] and not result["cancelled"]:
            with library.catalog.connect() as db:
                # Trashed photos retain their files but follow a merged person
                # when restored; never leave a dangling person reference.
                db.execute(
                    "UPDATE photos SET person_id=? WHERE person_id=?",
                    (target_id, source_id),
                )
                db.execute("DELETE FROM people WHERE id=?", (source_id,))
        return result


def delete_people(
    library, person_ids, cancel=lambda: False, progress=lambda n, t, m: None
):
    with library.lock:
        library._ready()
        result = {
            "deleted_people": [],
            "operations": [],
            "photo_ids": [],
            "errors": [],
            "cancelled": False,
        }
        for ident in dict.fromkeys(person_ids):
            if cancel():
                result["cancelled"] = True
                break
            try:
                person = library.catalog.person(ident)
                if person["role"]:
                    raise ValueError("合照和待分类是固定分类，不能删除")
                target = next(
                    p
                    for p in library.catalog.people(person["activity_id"])
                    if p["role"] == "unclassified"
                )
                ids = [
                    p["id"]
                    for p in library.catalog.photos(person["activity_id"])
                    if p["person_id"] == ident
                ]
                batch = library._batch(
                    ids,
                    lambda photo: library._move(
                        photo, person_id=target["id"], manual=True, allow_missing=True
                    ),
                    cancel,
                    progress,
                )
                for key in ("operations", "photo_ids", "errors"):
                    result[key].extend(batch[key])
                if batch["cancelled"] or cancel():
                    result["cancelled"] = True
                    break
                if batch["errors"]:
                    continue
                library.journal.execute(
                    "delete_person",
                    [],
                    [
                        (
                            "UPDATE photos SET person_id=? WHERE person_id=?",
                            (target["id"], ident),
                        ),
                        ("DELETE FROM people WHERE id=?", (ident,)),
                    ],
                )
                result["deleted_people"].append(ident)
                from ..cleanup import cleanup_library

                activity = library.catalog.rows(
                    "SELECT folder FROM activities WHERE id=?", (person["activity_id"],)
                )[0]
                cleanup = cleanup_library(
                    library, library.root / activity["folder"] / person["folder"]
                )
                result["errors"].extend({"id": ident, "message": "人物整理已完成；空目录清理需检查：" + issue["path"] + "；" + issue["message"]}
                                        for issue in cleanup["errors"])
            except Exception as e:
                result["errors"].append({"id": ident, "message": str(e)})
        return result
