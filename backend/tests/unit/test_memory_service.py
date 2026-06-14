import json

import pytest

from app.db import repositories as repository_module
from app.db import sqlite as sqlite_store
from app.db.repositories import MemoryRepository
from app.db.sqlite import init_db
from app.memory.memory_service import MemoryService


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "smart_trip.sqlite3"
    memory_path = tmp_path / "memory_store.json"
    session_runs_path = tmp_path / "session_runs_store.json"

    monkeypatch.setattr(sqlite_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(sqlite_store, "DB_PATH", db_path)
    monkeypatch.setattr(sqlite_store, "MEMORY_PATH", memory_path)
    monkeypatch.setattr(sqlite_store, "SESSION_RUNS_PATH", session_runs_path)
    monkeypatch.setattr(repository_module, "MEMORY_PATH", memory_path)
    monkeypatch.setattr(repository_module, "SESSION_RUNS_PATH", session_runs_path)


def test_memory_round_trip() -> None:
    init_db()
    service = MemoryService(MemoryRepository())
    service.upsert_memory(user_id="test-user", key="hotel_style", value="quiet", scope="travel_preference")

    memories = service.list_memories(user_id="test-user")

    assert any(item["key"] == "hotel_style" and item["value"] == "quiet" for item in memories)


def test_persist_preferences_overrides_conflicting_preferences() -> None:
    init_db()
    service = MemoryService(MemoryRepository())
    service.persist_preferences(
        user_id="test-user-preference-override",
        preferences=["lively_hotel", "avoid_local_food"],
        pace="intensive",
    )

    memories = {item["key"]: item["value"] for item in service.list_memories(user_id="test-user-preference-override")}

    profile = json.loads(memories["profile:accommodation"])
    assert profile["dimension"] == "accommodation"
    assert profile["active_values"] == ["lively_hotel"]
    assert memories["hotel_style"] == "prefer_lively_location"
    assert memories["preference_quiet_hotel"] == "avoid_quiet_hotel"
    assert memories["preference_local_food"] == "avoid_local_food"
    assert memories["travel_pace"] == "intensive"


def test_persist_preferences_keeps_family_preference() -> None:
    init_db()
    service = MemoryService(MemoryRepository())
    service.persist_preferences(
        user_id="test-user-family-preference",
        preferences=["family", "quiet_hotel", "local_food"],
        pace="relaxed",
    )

    memories = {item["key"]: item["value"] for item in service.list_memories(user_id="test-user-family-preference")}

    assert memories["preference_family"] == "family"
    assert memories["hotel_style"] == "prefer_quiet_location"
    assert memories["preference_local_food"] == "local_food"
    assert memories["travel_pace"] == "relaxed"


def test_persist_preferences_does_not_write_default_balanced_pace() -> None:
    init_db()
    service = MemoryService(MemoryRepository())
    updates = service.persist_preferences(
        user_id="test-user-default-pace",
        preferences=[],
        pace="balanced",
        pace_explicit=False,
    )

    memories = {item["key"]: item["value"] for item in service.list_memories(user_id="test-user-default-pace")}

    assert updates == []
    assert "travel_pace" not in memories
    assert "profile:pace" not in memories


def test_persist_preferences_merges_profile_dimension_without_new_top_level_key() -> None:
    init_db()
    service = MemoryService(MemoryRepository())
    service.persist_preferences(
        user_id="test-user-profile-merge",
        preferences=["quiet_hotel"],
        pace="balanced",
        pace_explicit=False,
        source_text="酒店尽量安静",
        session_id="session-1",
    )
    service.persist_preferences(
        user_id="test-user-profile-merge",
        preferences=["comfortable_hotel"],
        pace="balanced",
        pace_explicit=False,
        source_text="住宿舒适度高一些",
        session_id="session-1",
    )

    memories = {item["key"]: item["value"] for item in service.list_memories(user_id="test-user-profile-merge")}
    profile = json.loads(memories["profile:accommodation"])

    assert set(profile["active_values"]) == {"quiet_hotel", "comfortable_hotel"}
    assert "profile:accommodation" in memories


def test_memory_audit_groups_profiles_and_shadowed_records() -> None:
    init_db()
    service = MemoryService(MemoryRepository())
    service.persist_preferences(
        user_id="test-user-audit",
        preferences=["quiet_hotel", "avoid_local_food", "family"],
        pace="relaxed",
        source_text="酒店尽量安静，不吃本地特色，适合亲子",
        session_id="session-audit",
    )
    service.upsert_memory(user_id="test-user-audit", key="hotel_style", value="prefer_quiet_location", scope="travel_preference")
    service.upsert_memory(user_id="test-user-audit", key="custom_note", value="manual-note", scope="user_preference")

    audit = service.audit(user_id="test-user-audit")

    assert audit["user_id"] == "test-user-audit"
    assert audit["profile_count"] >= 1
    assert "accommodation" in audit["profiles"]
    assert audit["shadowed_legacy_records"]
    assert any(item["key"] == "hotel_style" for item in audit["shadowed_legacy_records"])
    assert any("profile" in item and "legacy" in item for item in audit["recommendations"])
    assert any(item["key"] == "custom_note" for item in audit["unknown_records"])
