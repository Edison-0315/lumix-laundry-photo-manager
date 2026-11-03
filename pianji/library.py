from pathlib import Path
import threading
from .catalog import Catalog
from .domain import uid, PhotoGroup, FileAsset
from .paths import safe_name, inside
from .fileops import FileJournal, digest
from .locking import LibraryLock

from .services import imports, people, exports, trash, activities


class Library:
    def __init__(self, root):
        self._root_lock = LibraryLock(Path(root).resolve())
        self._closed = False
        self.catalog = Catalog(root)
        self.root = self.catalog.root
        self.journal = FileJournal(self.catalog)
        self.lock = threading.RLock()
        self.recovery = self.recover_pending()

    def close(self):
        with self.lock, self.journal.access:
            if not self._closed:
                self._closed = True
                self._root_lock.close()

    def recover_pending(self):
        return self.journal.recover_pending()

    def create_activity(self, name):
        return activities.create_activity(self, name)

    def _ready(self):
        if self._closed:
            raise ValueError("照片库已关闭")
        if self.catalog.rows("SELECT id FROM operations WHERE phase!='committed'"):
            raise ValueError("有文件操作尚待恢复，请先关闭占用程序并重试恢复")

    def _folder(self, activity_id, person_id, edited, kind, person_folder=None):
        activity = self.catalog.rows(
            "SELECT * FROM activities WHERE id=?", (activity_id,)
        )[0]
        person = self.catalog.person(person_id)
        if person["activity_id"] != activity_id:
            raise ValueError("不能将照片放入其他活动的人物")
        base = self.root / activity["folder"] / (person_folder or person["folder"])
        return (
            base / "成片"
            if kind == "export"
            else base
            / ("已修原片" if edited else "选出原片")
            / ("JPEG" if kind == "jpeg" else "RAW")
        )

    def _destinations(
        self,
        assets,
        activity_id,
        person_id,
        edited,
        stem,
        person_folder=None,
        reserved=None,
    ):
        # Reserve one suffix for the entire group, across every format/version.
        safe_name(stem)
        old = {str(Path(a["path"]).resolve()) for a in assets}
        for n in range(10000):
            candidate = stem if n == 0 else f"{stem}_{n+1}"
            paths = []
            seen = set()
            for a in assets:
                suffix = Path(a["path"]).suffix
                filename = (
                    candidate
                    + ("_" + a["id"][:8] if a["kind"] == "export" else "")
                    + suffix
                )
                dst = inside(
                    self.root,
                    self._folder(
                        activity_id, person_id, edited, a["kind"], person_folder
                    )
                    / filename,
                )
                if str(dst) in seen:
                    filename = candidate + "_" + a["id"][:8] + suffix
                    dst = dst.with_name(filename)
                seen.add(str(dst))
                paths.append(str(dst))
            if all(
                (not Path(p).exists() or p in old)
                and p.casefold() not in (reserved or set())
                for p in paths
            ):
                return paths
        raise ValueError("同名照片过多，请更换名称")

    def import_groups(
        self,
        groups,
        activity,
        formats="both",
        cancel=lambda: False,
        progress=lambda n, t, m: None,
    ):
        return imports.import_groups(self, groups, activity, formats, cancel, progress)

    @staticmethod
    def _import_member_sql(activity_id, photo_id, assets):
        return imports._import_member_sql(activity_id, photo_id, assets)

    def _matching_photo(self, activity_id, assets):
        return imports._matching_photo(self, activity_id, assets)

    def _supplement(self, photo, incoming):
        return imports._supplement(self, photo, incoming)

    def _move(
        self,
        photo,
        person_id=None,
        edited=None,
        manual=None,
        person_folder=None,
        extra_sql=None,
        allow_missing=False,
    ):
        person_id = person_id or photo["person_id"]
        edited = bool(photo["edited"]) if edited is None else bool(edited)
        assets = self._fresh_assets(photo, allow_missing=allow_missing)
        destinations = self._destinations(
            assets,
            photo["activity_id"],
            person_id,
            edited,
            photo["stem"],
            person_folder,
        )
        changes = []
        sql = []
        for a, d in zip(assets, destinations):
            if str(Path(a["path"]).resolve()) != d and not a.get("_missing"):
                changes.append(
                    {"src": a["path"], "dst": d, "sha256": a["sha256"], "move": True}
                )
            sql.append(self._asset_sql(a, d))
        manual = photo["manual_person"] if manual is None else manual
        sql.append(
            (
                "UPDATE photos SET person_id=?,edited=?,manual_person=? WHERE id=?",
                (person_id, int(edited), int(manual), photo["id"]),
            )
        )
        sql += extra_sql or []
        return self.journal.execute(
            "move",
            changes,
            sql,
            {
                "photo_id": photo["id"],
                "before": {
                    k: photo[k] for k in ("person_id", "edited", "manual_person")
                },
                "after": {
                    "person_id": person_id,
                    "edited": int(edited),
                    "manual_person": int(manual),
                },
                "cleanup_dirs": [str(Path(a["path"]).parent) for a in assets],
            },
        )

    def _fresh_assets(self, photo, allow_missing=False):
        assets = [dict(a) for a in photo["assets"]]
        known = {str(Path(a["path"]).resolve()).casefold() for a in assets}
        for raw in [a for a in assets if a["kind"] == "raw"]:
            path = Path(raw["path"])
            for sidecar in (
                path.with_suffix(".xmp"),
                path.with_suffix(".XMP"),
                Path(str(path) + ".xmp"),
            ):
                resolved = str(sidecar.resolve())
                if sidecar.is_file() and resolved.casefold() not in known:
                    inside(self.root, sidecar)
                    if self.catalog.rows(
                        "SELECT id FROM assets WHERE path=?", (resolved,)
                    ):
                        continue
                    assets.append(
                        {
                            "id": uid(),
                            "photo_id": photo["id"],
                            "kind": "xmp",
                            "path": resolved,
                            "sha256": "",
                            "_new": True,
                        }
                    )
                    known.add(resolved.casefold())
        for a in assets:
            inside(self.root, a["path"])
            if allow_missing and not Path(a["path"]).is_file():
                a["_missing"] = True
            else:
                a["sha256"] = digest(a["path"])
        return assets

    @staticmethod
    def _asset_sql(asset, destination):
        if asset.get("_new"):
            return (
                "INSERT INTO assets VALUES(?,?,?,?,?)",
                (
                    asset["id"],
                    asset["photo_id"],
                    asset["kind"],
                    destination,
                    asset["sha256"],
                ),
            )
        return (
            "UPDATE assets SET path=?,sha256=? WHERE id=?",
            (destination, asset["sha256"], asset["id"]),
        )

    def _batch(
        self,
        ids,
        fn,
        cancel=lambda: False,
        progress=lambda n, t, m: None,
        include_trashed=False,
    ):
        with self.lock:
            self._ready()
            result = {
                "operations": [],
                "photo_ids": [],
                "skipped": 0,
                "errors": [],
                "cancelled": False,
            }
            unique = list(dict.fromkeys(ids))
            for n, ident in enumerate(unique):
                if cancel():
                    result["cancelled"] = True
                    break
                try:
                    operation = fn(
                        self.catalog.photo(ident, include_trashed=include_trashed)
                    )
                    if operation:
                        result["operations"].append(operation)
                        result["photo_ids"].append(ident)
                    else:
                        result["skipped"] += 1
                except Exception as e:
                    result["errors"].append({"id": ident, "message": str(e)})
                finally:
                    progress(n + 1, len(unique), "整理照片文件")
            return result

    def set_person(
        self,
        ids,
        person_id,
        manual=True,
        cancel=lambda: False,
        progress=lambda n, t, m: None,
    ):
        return people.set_person(self, ids, person_id, manual, cancel, progress)

    def set_edited(
        self, ids, value, cancel=lambda: False, progress=lambda n, t, m: None
    ):
        return self._batch(ids, lambda p: self._move(p, edited=value), cancel, progress)

    def trash_photos(self, ids, cancel=lambda: False, progress=lambda n, t, m: None):
        return trash.trash_photos(self, ids, cancel, progress)

    def restore_photos(self, ids, cancel=lambda: False, progress=lambda n, t, m: None):
        return trash.restore_photos(self, ids, cancel, progress)

    def purge_trash(self, ids, cancel=lambda: False, progress=lambda n, t, m: None):
        return trash.purge_trash(self, ids, cancel, progress)

    def delete_activity(
        self, activity_id, cancel=lambda: False, progress=lambda n, t, m: None
    ):
        return activities.delete_activity(self, activity_id, cancel, progress)

    def link_export(self, photo_id, file):
        return exports.link_export(self, photo_id, file)

    def set_finished(
        self, ids, value, cancel=lambda: False, progress=lambda n, t, m: None
    ):
        return exports.set_finished(self, ids, value, cancel, progress)

    def unlink_export(self, photo_id, asset_id=None):
        return exports.unlink_export(self, photo_id, asset_id)

    def undo_operation(self, opid):
        with self.lock:
            self._ready()
            op = self.catalog.operation(opid)
            if op["kind"] != "move" or op["phase"] != "committed" or op["error"]:
                raise ValueError("此操作不能撤销")
            data = op["payload"]
            p = self.catalog.photo(data["photo_id"])
            if any(p[k] != v for k, v in data["after"].items()):
                raise ValueError("照片后来已变更，请手动调整，避免覆盖新状态")
            return self._move(
                p,
                **{
                    "person_id": data["before"]["person_id"],
                    "edited": data["before"]["edited"],
                    "manual": data["before"]["manual_person"],
                },
            )

    def rename_person(self, person_id, name):
        return people.rename_person(self, person_id, name)

    def merge_people(
        self, source_id, target_id, cancel=lambda: False, progress=lambda n, t, m: None
    ):
        return people.merge_people(self, source_id, target_id, cancel, progress)

    def delete_people(
        self, person_ids, cancel=lambda: False, progress=lambda n, t, m: None
    ):
        return people.delete_people(self, person_ids, cancel, progress)

    def group(self, photo_id, prefer_export=False):
        p = self.catalog.photo(photo_id)
        assets = p["assets"]
        if prefer_export and p["primary_export_id"]:
            assets = [a for a in assets if a["id"] == p["primary_export_id"]]
        else:
            assets = [a for a in assets if a["kind"] != "export"]
        return PhotoGroup(
            p["id"], "", p["stem"], p["captured_at"], [FileAsset(**a) for a in assets]
        )
