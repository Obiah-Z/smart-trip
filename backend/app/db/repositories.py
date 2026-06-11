from __future__ import annotations

import json
from datetime import datetime, timezone
import uuid
from typing import Any

from app.db.sqlite import (
    MEMORY_PATH,
    SESSION_RUNS_PATH,
    get_connection,
    load_json_records,
    save_json_records,
    sqlite_available,
)


class MemoryRepository:
    def list_memories(self, *, user_id: str) -> list[dict[str, str]]:
        if sqlite_available():
            with get_connection() as connection:
                rows = connection.execute(
                    "SELECT user_id, key, value, scope, updated_at FROM user_memory WHERE user_id = ? ORDER BY key ASC",
                    (user_id,),
                ).fetchall()
            return [dict(row) for row in rows]

        records = load_json_records(MEMORY_PATH)
        filtered = [record for record in records if record["user_id"] == user_id]
        return sorted(filtered, key=lambda item: item["key"])

    def upsert_memory(self, *, user_id: str, key: str, value: str, scope: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if sqlite_available():
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO user_memory (user_id, key, value, scope, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, key) DO UPDATE SET
                        value = excluded.value,
                        scope = excluded.scope,
                        updated_at = excluded.updated_at
                    """,
                    (user_id, key, value, scope, now),
                )
                connection.commit()
            return

        records = load_json_records(MEMORY_PATH)
        next_records = [record for record in records if not (record["user_id"] == user_id and record["key"] == key)]
        next_records.append(
            {
                "user_id": user_id,
                "key": key,
                "value": value,
                "scope": scope,
                "updated_at": now,
            }
        )
        save_json_records(MEMORY_PATH, next_records)


class SessionRunRepository:
    def save_run(self, *, session_id: str, user_id: str, request_text: str, response: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        payload = json.dumps(response, ensure_ascii=False)
        if sqlite_available():
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO session_runs (run_id, session_id, user_id, request_text, response_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, session_id, user_id, request_text, payload, now),
                )
                connection.commit()
            return

        records = load_json_records(SESSION_RUNS_PATH)
        records.append(
            {
                "run_id": run_id,
                "session_id": session_id,
                "user_id": user_id,
                "request_text": request_text,
                "response_json": payload,
                "created_at": now,
            }
        )
        save_json_records(SESSION_RUNS_PATH, records)

    def get_run(self, *, session_id: str) -> dict[str, Any] | None:
        records = self.list_session_runs(session_id=session_id)
        if not records:
            return None
        return self._select_session_display_run(records)

    def list_session_runs(self, *, session_id: str) -> list[dict[str, Any]]:
        if sqlite_available():
            with get_connection() as connection:
                rows = connection.execute(
                    """
                    SELECT run_id, session_id, user_id, request_text, response_json, created_at
                    FROM session_runs
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                    """,
                    (session_id,),
                ).fetchall()
            return [self._deserialize_row(dict(row)) for row in rows]

        records = load_json_records(SESSION_RUNS_PATH)
        normalized = [self._deserialize_row(record) for record in records if record["session_id"] == session_id]
        normalized.sort(key=lambda item: item["created_at"], reverse=True)
        return normalized

    def list_runs(self, *, user_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        resolved_limit = max(1, min(limit, 100))
        session_runs = self._list_all_runs(user_id=user_id)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for run in session_runs:
            grouped.setdefault(run["session_id"], []).append(run)

        normalized = [self._select_session_display_run(records) for records in grouped.values() if records]
        normalized.sort(key=lambda item: item["created_at"], reverse=True)
        return normalized[:resolved_limit]

    def find_latest_planning_session_id(self, *, user_id: str) -> str | None:
        for run in self.list_runs(user_id=user_id, limit=100):
            response = run.get("response") or {}
            task_profile = response.get("task_profile") or {}
            summary = (response.get("final_plan") or {}).get("summary") or {}
            if task_profile.get("task_type") != "travel_planning":
                continue
            if not summary.get("destinationCity") or not summary.get("days"):
                continue
            return run["session_id"]
        return None

    def _list_all_runs(self, *, user_id: str | None = None) -> list[dict[str, Any]]:
        if sqlite_available():
            with get_connection() as connection:
                if user_id:
                    rows = connection.execute(
                        """
                        SELECT run_id, session_id, user_id, request_text, response_json, created_at
                        FROM session_runs
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        """,
                        (user_id,),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """
                        SELECT run_id, session_id, user_id, request_text, response_json, created_at
                        FROM session_runs
                        ORDER BY created_at DESC
                        """,
                    ).fetchall()
            return [self._deserialize_row(dict(row)) for row in rows]

        records = load_json_records(SESSION_RUNS_PATH)
        normalized = [self._deserialize_row(record) for record in records if not user_id or record["user_id"] == user_id]
        normalized.sort(key=lambda item: item["created_at"], reverse=True)
        return normalized

    def delete_run(self, *, session_id: str) -> bool:
        if sqlite_available():
            with get_connection() as connection:
                cursor = connection.execute(
                    "DELETE FROM session_runs WHERE session_id = ?",
                    (session_id,),
                )
                connection.commit()
            return cursor.rowcount > 0

        records = load_json_records(SESSION_RUNS_PATH)
        next_records = [record for record in records if record["session_id"] != session_id]
        deleted = len(next_records) != len(records)
        if deleted:
            save_json_records(SESSION_RUNS_PATH, next_records)
        return deleted

    def _deserialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": row.get("run_id"),
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "request_text": row["request_text"],
            "response": json.loads(row["response_json"]),
            "created_at": row["created_at"],
        }

    def _select_session_display_run(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        ranked = sorted(records, key=lambda item: item["created_at"], reverse=True)
        planning_candidates = [
            item
            for item in ranked
            if ((item.get("response") or {}).get("task_profile") or {}).get("task_type") == "travel_planning"
        ]
        latest_run = ranked[0]
        if planning_candidates:
            display = dict(planning_candidates[0])
            display["latest_run"] = latest_run
            display["created_at"] = latest_run["created_at"]
            display["display_reason"] = "latest_planning"
            return display

        display = dict(ranked[0])
        display["latest_run"] = ranked[0]
        display["display_reason"] = "latest_run"
        return display
