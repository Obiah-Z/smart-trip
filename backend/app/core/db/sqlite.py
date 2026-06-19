from __future__ import annotations

from pathlib import Path
import json
import uuid
from typing import Any

from app.core.paths import backend_root

BASE_DIR = backend_root()
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "smart_trip.sqlite3"
MEMORY_PATH = DATA_DIR / "memory_store.json"
SESSION_RUNS_PATH = DATA_DIR / "session_runs_store.json"

try:
    import sqlite3  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    try:
        import pysqlite3 as sqlite3  # type: ignore
    except ModuleNotFoundError:
        sqlite3 = None


def sqlite_available() -> bool:
    """当前 Python 环境是否能使用 sqlite 驱动。"""
    return sqlite3 is not None


def get_connection():
    """创建 SQLite 连接，并使用 Row 方便按字段名读取结果。"""
    if sqlite3 is None:
        raise RuntimeError("sqlite3 is unavailable in current Python environment")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_json_store() -> None:
    """确保 JSON 快照/fallback 文件存在。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not MEMORY_PATH.exists():
        MEMORY_PATH.write_text("[]", encoding="utf-8")
    if not SESSION_RUNS_PATH.exists():
        SESSION_RUNS_PATH.write_text("[]", encoding="utf-8")


def load_json_records(path: Path) -> list[dict]:
    ensure_json_store()
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_records(path: Path, records: list[dict]) -> None:
    ensure_json_store()
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def init_db() -> None:
    """初始化持久化层。

    SQLite 可用时是主存储：创建核心表、从旧 JSON 快照迁移初始数据，并同步一份 JSON
    快照方便本地查看。SQLite 不可用时退回纯 JSON 存储。
    """
    if sqlite_available():
        with get_connection() as connection:
            _ensure_core_schema(connection)
            _migrate_json_snapshots_to_sqlite(connection)
            connection.commit()
            sync_sqlite_snapshots(connection=connection)
        return
    ensure_json_store()


def _ensure_core_schema(connection) -> None:
    """创建核心表和索引，并处理早期 session_runs 无 run_id 的结构迁移。"""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_memory (
            user_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            scope TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS session_runs (
            run_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            request_text TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(session_runs)").fetchall()
    }
    if "run_id" not in columns:
        connection.execute("DROP TABLE session_runs")
        connection.execute(
            """
            CREATE TABLE session_runs (
                run_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                request_text TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_session_runs_session_created ON session_runs(session_id, created_at DESC)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_session_runs_user_created ON session_runs(user_id, created_at DESC)"
    )


def _migrate_json_snapshots_to_sqlite(connection) -> None:
    """仅在 SQLite 表为空时从 JSON 快照导入历史数据。"""
    if _table_count(connection, "user_memory") == 0:
        _migrate_memory_snapshot(connection, records=_load_snapshot_records(MEMORY_PATH))
    if _table_count(connection, "session_runs") == 0:
        _migrate_session_run_snapshot(connection, records=_load_snapshot_records(SESSION_RUNS_PATH))


def _load_snapshot_records(path: Path) -> list[dict[str, Any]]:
    """安全读取 JSON 快照；文件损坏时返回空列表。"""
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _migrate_memory_snapshot(connection, *, records: list[dict[str, Any]]) -> None:
    """把旧 memory_store.json 记录迁移到 user_memory 表。"""
    for record in records:
        user_id = str(record.get("user_id") or "").strip()
        key = str(record.get("key") or "").strip()
        value = str(record.get("value") or "").strip()
        scope = str(record.get("scope") or "travel_preference").strip()
        updated_at = str(record.get("updated_at") or "").strip()
        if not user_id or not key:
            continue
        connection.execute(
            """
            INSERT INTO user_memory (user_id, key, value, scope, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET
                value = excluded.value,
                scope = excluded.scope,
                updated_at = excluded.updated_at
            """,
            (user_id, key, value, scope or "travel_preference", updated_at or "1970-01-01T00:00:00+00:00"),
        )


def _migrate_session_run_snapshot(connection, *, records: list[dict[str, Any]]) -> None:
    """把旧 session_runs_store.json 记录迁移到 session_runs 表。"""
    for index, record in enumerate(records):
        session_id = str(record.get("session_id") or "").strip()
        user_id = str(record.get("user_id") or "").strip()
        request_text = str(record.get("request_text") or "").strip()
        created_at = str(record.get("created_at") or "").strip()
        response_json = _normalize_response_json(record)
        if not session_id or not user_id or not response_json:
            continue
        run_id = str(record.get("run_id") or "").strip()
        if not run_id:
            run_id = _generate_legacy_run_id(index=index, record=record)
        connection.execute(
            """
            INSERT OR IGNORE INTO session_runs (run_id, session_id, user_id, request_text, response_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, session_id, user_id, request_text, response_json, created_at or "1970-01-01T00:00:00+00:00"),
        )


def _normalize_response_json(record: dict[str, Any]) -> str:
    """兼容 response_json 字符串和早期 response 对象两种快照格式。"""
    response_json = record.get("response_json")
    if isinstance(response_json, str) and response_json.strip():
        return response_json
    if response_json is not None:
        return json.dumps(response_json, ensure_ascii=False)
    response = record.get("response")
    if response is not None:
        return json.dumps(response, ensure_ascii=False)
    return ""


def _generate_legacy_run_id(*, index: int, record: dict[str, Any]) -> str:
    """为旧快照生成稳定 run_id，避免重复迁移时产生不同主键。"""
    stable_key = "|".join(
        [
            str(index),
            str(record.get("session_id") or ""),
            str(record.get("user_id") or ""),
            str(record.get("request_text") or ""),
            str(record.get("created_at") or ""),
        ]
    )
    return f"run-{uuid.uuid5(uuid.NAMESPACE_URL, stable_key).hex[:12]}"


def _table_count(connection, table_name: str) -> int:
    """返回白名单表的记录数。"""
    if table_name not in {"user_memory", "session_runs", "graph_nodes", "graph_edges"}:
        raise ValueError(f"unsupported table: {table_name}")
    exists = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if not exists:
        return 0
    return int(connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()["count"])


def sync_sqlite_snapshots(*, connection=None) -> None:
    """把 SQLite 运行表镜像到 JSON 快照，供本地查看和备份。"""
    if not sqlite_available():
        ensure_json_store()
        return

    if connection is not None:
        _write_core_table_snapshots(connection)
        return

    with get_connection() as active_connection:
        _ensure_core_schema(active_connection)
        _write_core_table_snapshots(active_connection)


def _write_core_table_snapshots(connection) -> None:
    """写出 user_memory 和 session_runs 两个核心表的 JSON 快照。"""
    memory_rows = connection.execute(
        """
        SELECT user_id, key, value, scope, updated_at
        FROM user_memory
        ORDER BY user_id ASC, key ASC
        """
    ).fetchall()
    session_rows = connection.execute(
        """
        SELECT run_id, session_id, user_id, request_text, response_json, created_at
        FROM session_runs
        ORDER BY created_at ASC, run_id ASC
        """
    ).fetchall()

    save_json_records(MEMORY_PATH, [dict(row) for row in memory_rows])
    save_json_records(SESSION_RUNS_PATH, [dict(row) for row in session_rows])


def _json_snapshot_counts() -> dict[str, int]:
    return {
        "memory": len(_load_snapshot_records(MEMORY_PATH)),
        "session_runs": len(_load_snapshot_records(SESSION_RUNS_PATH)),
    }


def get_storage_status() -> dict[str, Any]:
    """返回存储状态，供 /api/debug/storage 和前端调试视图使用。"""
    if not sqlite_available():
        ensure_json_store()
        return {
            "backend": "json",
            "sqlite_available": False,
            "db_path": str(DB_PATH),
            "json_snapshot_counts": _json_snapshot_counts(),
            "json_paths": {
                "memory": str(MEMORY_PATH),
                "session_runs": str(SESSION_RUNS_PATH),
            },
        }

    init_db()
    with get_connection() as connection:
        table_counts = {
            table_name: _table_count(connection, table_name)
            for table_name in ("user_memory", "session_runs", "graph_nodes", "graph_edges")
        }
    return {
        "backend": "sqlite",
        "sqlite_available": True,
        "db_path": str(DB_PATH),
        "db_exists": DB_PATH.exists(),
        "table_counts": table_counts,
        "json_snapshot_counts": _json_snapshot_counts(),
        "json_snapshot_paths": {
            "memory": str(MEMORY_PATH),
            "session_runs": str(SESSION_RUNS_PATH),
        },
    }
