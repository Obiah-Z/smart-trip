from __future__ import annotations

from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "smart_trip.sqlite3"
MEMORY_PATH = DATA_DIR / "memory_store.json"
SESSION_RUNS_PATH = DATA_DIR / "session_runs_store.json"

try:
    import sqlite3  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    sqlite3 = None


def sqlite_available() -> bool:
    return sqlite3 is not None


def get_connection():
    if sqlite3 is None:
        raise RuntimeError("sqlite3 is unavailable in current Python environment")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_json_store() -> None:
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
    if sqlite_available():
        with get_connection() as connection:
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
            connection.commit()
        return
    ensure_json_store()
