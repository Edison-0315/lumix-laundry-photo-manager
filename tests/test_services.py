"""Real files and catalog checks across independently callable feature services."""

from pathlib import Path

from PIL import Image
from pianji.discovery import scan_source
from pianji.library import Library


def test_services_preserve_pair_stage_exports_and_restore_activity(tmp_path):
    # Detect a split transaction, new Library context, or lost association on supplementation.
    from pianji.services import imports, people, exports, trash, activities

    source = tmp_path / "SD"
    source.mkdir()
    Image.new("RGB", (50, 50), "red").save(source / "a.jpg")
    (source / "a.rw2").write_bytes(b"raw fixture, not decoded")
    groups = scan_source(source)
    with_library = Library(tmp_path / "中文照片库")
    try:
        result = imports.import_groups(with_library, groups, "活动", "jpeg")
        ident = result["imported"][0]
        photo = with_library.catalog.photo(ident)
        person = with_library.catalog.add_person(photo["activity_id"], "人物")
        assert not people.set_person(with_library, [ident], person["id"])["errors"]
        assert not exports.set_finished(with_library, [ident], True)["errors"]
        result = imports.import_groups(with_library, groups, "活动", "raw")
        assert result["updated"] == [ident] and result["imported"] == []
        photo = with_library.catalog.photo(ident)
        assert (
            photo["person_id"] == person["id"]
            and photo["edited"]
            and photo["primary_export_id"]
        )
        assert sorted(a["kind"] for a in photo["assets"]) == ["export", "jpeg", "raw"]
        assert (source / "a.jpg").is_file() and (source / "a.rw2").is_file()
        assert not people.delete_people(with_library, [person["id"]])["errors"]
        assert (
            with_library.catalog.person(with_library.catalog.photo(ident)["person_id"])[
                "role"
            ]
            == "unclassified"
        )
        removed = activities.delete_activity(with_library, photo["activity_id"])
        assert removed["deleted_activity"] == photo["activity_id"]
        assert with_library.catalog.activities() == []
        assert not trash.restore_photos(with_library, [ident])["errors"]
        restored = with_library.catalog.photo(ident)
        assert restored["primary_export_id"] == photo["primary_export_id"]
        assert len(with_library.catalog.activities()) == 1
        assert all(Path(a["path"]).is_file() for a in restored["assets"])
    finally:
        with_library.close()


def test_scan_and_preview_services_use_scan_identity_without_library(tmp_path):
    from pianji.services import source, photo_reads
    from pianji.previews import PreviewCache

    source_dir = tmp_path / "SD"
    source_dir.mkdir()
    Image.new("RGB", (60, 40), "blue").save(source_dir / "a.jpg")
    scans = {}
    scan = source.scan_photos(source_dir, scans)
    ident = scan["photos"][0]["id"]
    result = photo_reads.get_preview(
        None, PreviewCache(tmp_path / "cache"), scans, ident, "thumb", scan["scan_id"]
    )
    assert (
        result["url"].startswith("data:image/jpeg;base64,") and result["error"] is None
    )
    details = photo_reads.get_photo_details(None, scans, ident, scan["scan_id"])
    assert details["total_bytes"] > 0
    cancelled = source.scan_photos(source_dir, scans, cancel=lambda: True)
    assert cancelled == {"cancelled": True} and list(scans) == [scan["scan_id"]]
