from __future__ import annotations

from pathlib import Path


def app_root() -> Path:
    """Return the backend/app package directory."""
    return Path(__file__).resolve().parents[1]


def backend_root() -> Path:
    """Return the backend service root directory."""
    return app_root().parent


def project_root() -> Path:
    """Return the repository root directory."""
    return backend_root().parent


def data_dir() -> Path:
    """Return the backend runtime data directory."""
    return backend_root() / "data"
