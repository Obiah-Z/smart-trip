from pathlib import Path
import runpy


def test_seed_mock_data_script_rebuilds_snapshots() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "seed_mock_data.py"

    runpy.run_path(str(script_path), run_name="__main__")

    memory_path = Path(__file__).resolve().parents[2] / "data" / "memory_store.json"
    session_path = Path(__file__).resolve().parents[2] / "data" / "session_runs_store.json"

    memory_text = memory_path.read_text(encoding="utf-8")
    session_text = session_path.read_text(encoding="utf-8")

    assert "demo-user" in memory_text
    assert "manual-family-user" in memory_text
    assert "preference_family" in memory_text
    assert "厦门" in session_text
    assert "南京" in session_text
    assert "三亚" in session_text
    assert "下雨天适合带娃去哪玩" in session_text
