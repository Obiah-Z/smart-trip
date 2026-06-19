from pathlib import Path

from app.capabilities.image_generation.audit import (
    audit_trip_visual_assets,
    move_relative_files,
    prune_unexpected_manifest_records,
)
from app.capabilities.image_generation.asset_utils import normalize_manifest_record


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-jpeg-bytes")


def test_normalize_manifest_record_fills_legacy_fields(tmp_path: Path) -> None:
    asset_root = tmp_path / "images"
    relative_path = "杭州/attractions/西湖-nature-travel-editorial-square-清晨薄雾-多云.jpg"
    _write_image(asset_root / relative_path)

    normalized = normalize_manifest_record(
        {
            "asset_group": "attractions",
            "destination": "杭州",
            "attraction_name": "西湖",
            "relative_path": relative_path,
        },
        asset_root=asset_root,
    )

    assert normalized["subject_name"] == "西湖"
    assert normalized["attraction_name"] == "西湖"
    assert normalized["file_name"] == "西湖-nature-travel-editorial-square-清晨薄雾-多云.jpg"
    assert normalized["asset_key"] == "杭州/attractions/西湖-nature-travel-editorial-square-清晨薄雾-多云"
    assert normalized["image_url"] == f"/media/generated/{relative_path}"
    assert normalized["local_path"].endswith(relative_path)
    assert normalized["destination_folder"] == "杭州"


def test_normalize_manifest_record_attaches_existing_thumbnails(tmp_path: Path) -> None:
    asset_root = tmp_path / "images"
    relative_path = "杭州/attractions/西湖-nature-travel-editorial-square-清晨薄雾-多云.jpg"
    thumb_320 = "__thumbs__/320/杭州/attractions/西湖-nature-travel-editorial-square-清晨薄雾-多云.jpg"
    thumb_640 = "__thumbs__/640/杭州/attractions/西湖-nature-travel-editorial-square-清晨薄雾-多云.jpg"
    _write_image(asset_root / relative_path)
    _write_image(asset_root / thumb_320)
    _write_image(asset_root / thumb_640)

    normalized = normalize_manifest_record(
        {
            "asset_group": "attractions",
            "destination": "杭州",
            "attraction_name": "西湖",
            "relative_path": relative_path,
        },
        asset_root=asset_root,
    )

    assert normalized["thumbnail_url"] == f"/media/generated/{thumb_640}"
    assert normalized["thumbnail_urls"] == {
        "320": f"/media/generated/{thumb_320}",
        "640": f"/media/generated/{thumb_640}",
    }
    assert normalized["thumbnail_paths"] == {"320": thumb_320, "640": thumb_640}


def test_audit_trip_visual_assets_detects_unexpected_and_stale_files(tmp_path: Path) -> None:
    asset_root = tmp_path / "images"
    expected_relative_path = "杭州/attractions/西湖-nature-travel-editorial-square-清晨柔光-多云.jpg"
    unexpected_relative_path = "杭州/attractions/西湖-nature-travel-editorial-square-清晨薄雾-多云.jpg"
    stale_relative_path = "2026/06/10/imgtask_4173f9a0eef9.jpg"

    _write_image(asset_root / expected_relative_path)
    _write_image(asset_root / unexpected_relative_path)
    _write_image(asset_root / stale_relative_path)

    tasks = [
        {
            "asset_group": "attractions",
            "destination": "杭州",
            "subject_name": "西湖",
            "subject_type": "nature",
            "style": "travel_editorial",
            "aspect": "square",
            "time_of_day": "清晨柔光",
            "weather_hint": "多云",
            "output_format": "jpeg",
        }
    ]
    manifest_records = [
        {
            "asset_group": "attractions",
            "destination": "杭州",
            "subject_name": "西湖",
            "subject_type": "nature",
            "style": "travel_editorial",
            "aspect": "square",
            "relative_path": expected_relative_path,
        },
        {
            "asset_group": "attractions",
            "destination": "杭州",
            "attraction_name": "西湖",
            "subject_type": "nature",
            "style": "travel_editorial",
            "aspect": "square",
            "relative_path": unexpected_relative_path,
        },
    ]

    report = audit_trip_visual_assets(
        tasks=tasks,
        manifest_records=manifest_records,
        asset_root=asset_root,
    )

    assert report["summary"]["expected_assets"] == 1
    assert report["summary"]["manifest_records"] == 2
    assert report["summary"]["unexpected_manifest_entries"] == 1
    assert report["summary"]["stale_files"] == 1
    assert report["summary"]["missing_manifest_entries"] == 0
    assert report["summary"]["expected_file_gaps"] == 0
    assert report["unexpected_manifest_entries"][0]["relative_path"] == unexpected_relative_path
    assert report["stale_files"][0]["relative_path"] == stale_relative_path

    pruned_manifest = prune_unexpected_manifest_records(
        report["normalized_manifest"],
        report["unexpected_manifest_entries"],
    )
    assert len(pruned_manifest) == 1
    assert pruned_manifest[0]["relative_path"] == expected_relative_path


def test_move_relative_files_moves_into_quarantine(tmp_path: Path) -> None:
    asset_root = tmp_path / "images"
    quarantine_dir = tmp_path / "quarantine"
    relative_path = "2026/06/10/imgtask_aca78f0a2bdf.jpg"
    source = asset_root / relative_path
    _write_image(source)

    moved = move_relative_files(
        asset_root=asset_root,
        relative_paths=[relative_path],
        quarantine_dir=quarantine_dir,
    )

    assert len(moved) == 1
    assert not source.exists()
    assert (quarantine_dir / relative_path).exists()
