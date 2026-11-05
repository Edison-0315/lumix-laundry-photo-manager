"""Imports operations on the existing Library context; no owned resources."""

from pathlib import Path
import hashlib
from ..domain import uid
from ..paths import safe_name
from ..fileops import digest
from ..safeos import absolute


def import_groups(
    library,
    groups,
    activity,
    formats="both",
    cancel=lambda: False,
    progress=lambda n, t, m: None,
):
    with library.lock:
        library._ready()
        if formats not in ("both", "jpeg", "raw"):
            raise ValueError("未知照片格式")
        act = library.catalog.activity(activity)
        unclassified = next(
            p for p in library.catalog.people(act["id"]) if p["role"] == "unclassified"
        )
        report = {
            "imported": [],
            "updated": [],
            "skipped": 0,
            "errors": [],
            "cancelled": False,
            "activity_id": act["id"],
        }
        for n, g in enumerate(groups):
            if cancel():
                report["cancelled"] = True
                break
            try:
                safe_name(g.stem)
                files = [
                    a
                    for a in g.files
                    if a.kind
                    in (
                        ("jpeg", "raw", "xmp")
                        if formats == "both"
                        else ("raw", "xmp") if formats == "raw" else ("jpeg",)
                    )
                ]
                if not any(a.kind in ("jpeg", "raw") for a in files):
                    report["skipped"] += 1
                    continue
                ident = uid()
                assets = []
                # Hash companions too, so separately importing JPEG then RAW
                # from the same scan retains the established group identity.
                companions = []
                for a in g.files:
                    source = absolute(a.path)
                    if source.is_relative_to(library.root):
                        raise ValueError("来源位于照片库内，请选择SD卡或库外文件夹")
                    try:
                        sha = digest(source)
                    except OSError:
                        if a not in files:
                            continue
                        raise
                    item = {
                        "id": uid(),
                        "photo_id": ident,
                        "kind": a.kind,
                        "path": str(source),
                        "sha256": sha,
                    }
                    companions.append(item)
                    if a in files:
                        assets.append(item)
                sig = hashlib.sha256(
                    repr(sorted((a["kind"], a["sha256"]) for a in assets)).encode()
                ).hexdigest()
                existing = library._matching_photo(act["id"], companions)
                if existing:
                    if library._supplement(existing, assets):
                        report["updated"].append(existing["id"])
                    else:
                        report["skipped"] += 1
                    continue
                if library.catalog.rows(
                    "SELECT id FROM photos WHERE activity_id=? AND signature=?",
                    (act["id"], sig),
                ):
                    report["skipped"] += 1
                    continue
                destinations = library._destinations(
                    assets, act["id"], unclassified["id"], False, g.stem
                )
                changes = [
                    {"src": a["path"], "dst": d, "sha256": a["sha256"], "move": False}
                    for a, d in zip(assets, destinations)
                ]
                sql = [
                    (
                        "INSERT INTO photos(id,activity_id,person_id,stem,captured_at,signature) VALUES(?,?,?,?,?,?)",
                        (
                            ident,
                            act["id"],
                            unclassified["id"],
                            g.stem,
                            g.captured_at,
                            sig,
                        ),
                    )
                ]
                sql += [
                    (
                        "INSERT INTO assets VALUES(?,?,?,?,?)",
                        (a["id"], ident, a["kind"], d, a["sha256"]),
                    )
                    for a, d in zip(assets, destinations)
                ]
                sql += library._import_member_sql(act["id"], ident, assets)
                library.journal.execute("import", changes, sql, {"photo_id": ident})
                report["imported"].append(ident)
            except Exception as e:
                report["errors"].append({"name": g.stem, "message": str(e)})
            finally:
                progress(n + 1, len(groups), "复制并校验照片")
        return report


def _import_member_sql(activity_id, photo_id, assets):
    return [
        (
            "INSERT OR IGNORE INTO import_members VALUES(?,?,?,?)",
            (activity_id, a["kind"], a["sha256"], photo_id),
        )
        for a in assets
        if a["kind"] in ("jpeg", "raw")
    ]


def _matching_photo(library, activity_id, assets):
    candidates = set()
    for a in assets:
        if a["kind"] in ("jpeg", "raw"):
            candidates.update(
                r["photo_id"]
                for r in library.catalog.rows(
                    "SELECT photo_id FROM import_members WHERE activity_id=? AND kind=? AND sha256=?",
                    (activity_id, a["kind"], a["sha256"]),
                )
            )
    if len(candidates) > 1:
        raise ValueError("相同内容对应多个已有照片，请先核对照片库，未自动合并")
    if not candidates:
        return None
    ident = next(iter(candidates))
    for a in assets:
        if a["kind"] not in ("jpeg", "raw"):
            continue
        prior = library.catalog.rows(
            "SELECT sha256 FROM import_members WHERE photo_id=? AND kind=?",
            (ident, a["kind"]),
        )
        if prior and a["sha256"] not in {r["sha256"] for r in prior}:
            return None
    return library.catalog.photo(ident)


def _supplement(library, photo, incoming):
    originals = library._fresh_assets(photo)
    kinds = {a["kind"] for a in originals}
    extra = [
        {**a, "id": uid(), "photo_id": photo["id"], "_new": True, "_copy": True}
        for a in incoming
        if a["kind"] not in kinds
    ]
    if not extra:
        return False
    all_assets = originals + extra
    # Existing group metadata and even locally edited JPEG bytes survive.
    destinations = library._destinations(
        all_assets,
        photo["activity_id"],
        photo["person_id"],
        photo["edited"],
        photo["stem"],
    )
    changes = []
    sql = []
    for a, d in zip(all_assets, destinations):
        if str(Path(a["path"]).resolve()) != d:
            changes.append(
                {
                    "src": a["path"],
                    "dst": d,
                    "sha256": a["sha256"],
                    "move": not bool(a.get("_copy")),
                }
            )
        sql.append(library._asset_sql(a, d))
    sql += library._import_member_sql(photo["activity_id"], photo["id"], incoming)
    library.journal.execute("supplement", changes, sql, {"photo_id": photo["id"]})
    return True
