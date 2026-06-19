import json

import pytest

from app.core.db import sqlite as sqlite_store
from app.core.db.repositories import MemoryRepository, SessionRunRepository


def test_init_db_migrates_existing_json_snapshots_to_sqlite(tmp_path, monkeypatch) -> None:
    if not sqlite_store.sqlite_available():
        pytest.skip("sqlite3 is unavailable")

    db_path = tmp_path / "smart_trip.sqlite3"
    memory_path = tmp_path / "memory_store.json"
    session_runs_path = tmp_path / "session_runs_store.json"
    memory_path.write_text(
        json.dumps(
            [
                {
                    "user_id": "sqlite-user",
                    "key": "hotel_style",
                    "value": "prefer_quiet_location",
                    "scope": "travel_preference",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    session_runs_path.write_text(
        json.dumps(
            [
                {
                    "session_id": "session-sqlite",
                    "user_id": "sqlite-user",
                    "request_text": "帮我规划一个杭州三日游",
                    "response_json": json.dumps(
                        {
                            "session_id": "session-sqlite",
                            "task_profile": {"task_type": "travel_planning"},
                            "final_plan": {"summary": {"destinationCity": "杭州", "days": 3}},
                        },
                        ensure_ascii=False,
                    ),
                    "created_at": "2026-01-01T00:01:00+00:00",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(sqlite_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(sqlite_store, "DB_PATH", db_path)
    monkeypatch.setattr(sqlite_store, "MEMORY_PATH", memory_path)
    monkeypatch.setattr(sqlite_store, "SESSION_RUNS_PATH", session_runs_path)

    sqlite_store.init_db()

    assert db_path.exists()
    with sqlite_store.get_connection() as connection:
        memory_row = connection.execute(
            "SELECT user_id, key, value FROM user_memory WHERE user_id = ?",
            ("sqlite-user",),
        ).fetchone()
        session_row = connection.execute(
            "SELECT run_id, session_id, request_text FROM session_runs WHERE session_id = ?",
            ("session-sqlite",),
        ).fetchone()

    assert dict(memory_row) == {
        "user_id": "sqlite-user",
        "key": "hotel_style",
        "value": "prefer_quiet_location",
    }
    assert session_row["run_id"].startswith("run-")
    assert session_row["request_text"] == "帮我规划一个杭州三日游"


def test_sqlite_writes_are_mirrored_to_json_snapshots(tmp_path, monkeypatch) -> None:
    if not sqlite_store.sqlite_available():
        pytest.skip("sqlite3 is unavailable")

    db_path = tmp_path / "smart_trip.sqlite3"
    memory_path = tmp_path / "memory_store.json"
    session_runs_path = tmp_path / "session_runs_store.json"

    monkeypatch.setattr(sqlite_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(sqlite_store, "DB_PATH", db_path)
    monkeypatch.setattr(sqlite_store, "MEMORY_PATH", memory_path)
    monkeypatch.setattr(sqlite_store, "SESSION_RUNS_PATH", session_runs_path)

    sqlite_store.init_db()
    MemoryRepository().upsert_memory(
        user_id="mirror-user",
        key="travel_pace",
        value="relaxed",
        scope="travel_preference",
    )
    SessionRunRepository().save_run(
        session_id="session-mirror",
        user_id="mirror-user",
        request_text="帮我规划一个成都三日游",
        response={
            "session_id": "session-mirror",
            "task_profile": {"task_type": "travel_planning"},
            "final_plan": {"summary": {"destinationCity": "成都", "days": 3}},
        },
    )

    memory_records = json.loads(memory_path.read_text(encoding="utf-8"))
    session_records = json.loads(session_runs_path.read_text(encoding="utf-8"))

    assert memory_records == [
        {
            "user_id": "mirror-user",
            "key": "travel_pace",
            "value": "relaxed",
            "scope": "travel_preference",
            "updated_at": memory_records[0]["updated_at"],
        }
    ]
    assert len(session_records) == 1
    assert session_records[0]["session_id"] == "session-mirror"
    assert session_records[0]["request_text"] == "帮我规划一个成都三日游"

    assert SessionRunRepository().delete_run(session_id="session-mirror") is True

    assert json.loads(session_runs_path.read_text(encoding="utf-8")) == []
