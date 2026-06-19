from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from app.core.paths import backend_root


def _backend_root() -> Path:
    """返回 backend 目录根路径。"""
    return backend_root()


def default_rag_index_path() -> str:
    return str(_backend_root() / "data" / "rag" / "index" / "rag_index.json")


def default_embedding_index_path() -> str:
    return str(_backend_root() / "data" / "rag" / "index" / "embedding_index.json")


def default_image_output_dir() -> str:
    return str(_backend_root() / "data" / "generated_images")


def default_knowledge_graph_vault_dir() -> str:
    return str(_backend_root() / "data" / "knowledge_graph" / "obsidian_vault")


def _read_int_env(name: str, default: int) -> int:
    """读取整数环境变量，非法值回退默认值。"""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value.strip())
    except ValueError:
        return default


def _read_csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """读取逗号分隔环境变量。"""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    values = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    return values or default


@dataclass(frozen=True)
class Settings:
    """应用运行配置。

    配置按能力分组：主 LLM、图片生成、高德地图、RAG/Embedding、知识图谱和 CORS。
    使用 frozen dataclass 可以避免运行中被意外修改。
    """

    openai_mode: str = "mock"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    image_mode: str = "disabled"
    image_base_url: str = "https://api.openai.com/v1"
    image_api_key: str = ""
    image_model: str = "gpt-image-2"
    image_output_dir: str = ""
    image_default_size: str = "1536x1024"
    image_default_quality: str = "medium"
    image_default_format: str = "jpeg"
    image_default_compression: int = 85
    image_moderation: str = "auto"
    image_timeout_seconds: int = 120
    image_enable_cache: bool = True
    amap_web_service_key: str = ""
    amap_base_url: str = "https://restapi.amap.com"
    amap_timeout_seconds: int = 20
    map_provider: str = "local_preview"
    rag_mode: str = "local"
    rag_index_path: str = ""
    embedding_mode: str = "disabled"
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 0
    embedding_index_path: str = ""
    embedding_timeout_seconds: int = 60
    embedding_max_retries: int = 2
    embedding_batch_size: int = 8
    embedding_trust_env: bool = True
    knowledge_graph_enabled: bool = True
    knowledge_graph_vault_dir: str = ""
    cors_allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    )


def load_env_file() -> None:
    """加载 backend/.env 风格配置。

    使用 setdefault 是为了让 shell 中显式传入的环境变量优先级更高，便于部署和测试覆盖。
    """
    env_path = backend_root() / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_settings() -> Settings:
    """从环境变量构造 Settings。"""
    load_env_file()
    return Settings(
        openai_mode=os.getenv("OPENAI_MODE", "mock").strip().lower(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        image_mode=os.getenv("IMAGE_MODE", "disabled").strip().lower(),
        image_base_url=os.getenv("IMAGE_BASE_URL", "https://api.openai.com/v1").strip(),
        image_api_key=os.getenv("IMAGE_API_KEY", "").strip(),
        image_model=os.getenv("IMAGE_MODEL", "gpt-image-2").strip(),
        image_output_dir=os.getenv("IMAGE_OUTPUT_DIR", default_image_output_dir()).strip(),
        image_default_size=os.getenv("IMAGE_DEFAULT_SIZE", "1536x1024").strip(),
        image_default_quality=os.getenv("IMAGE_DEFAULT_QUALITY", "medium").strip().lower(),
        image_default_format=os.getenv("IMAGE_DEFAULT_FORMAT", "jpeg").strip().lower(),
        image_default_compression=_read_int_env("IMAGE_DEFAULT_COMPRESSION", 85),
        image_moderation=os.getenv("IMAGE_MODERATION", "auto").strip().lower(),
        image_timeout_seconds=_read_int_env("IMAGE_TIMEOUT_SECONDS", 120),
        image_enable_cache=os.getenv("IMAGE_ENABLE_CACHE", "true").strip().lower() in {"1", "true", "yes", "on"},
        amap_web_service_key=os.getenv("AMAP_WEB_SERVICE_KEY", "").strip(),
        amap_base_url=os.getenv("AMAP_BASE_URL", "https://restapi.amap.com").strip(),
        amap_timeout_seconds=_read_int_env("AMAP_TIMEOUT_SECONDS", 20),
        map_provider=os.getenv("MAP_PROVIDER", "local_preview").strip().lower(),
        rag_mode=os.getenv("RAG_MODE", "local").strip().lower(),
        rag_index_path=os.getenv("RAG_INDEX_PATH", default_rag_index_path()).strip(),
        embedding_mode=os.getenv("EMBEDDING_MODE", "disabled").strip().lower(),
        embedding_base_url=os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1").strip(),
        embedding_api_key=os.getenv("EMBEDDING_API_KEY", "").strip(),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip(),
        embedding_dimensions=_read_int_env("EMBEDDING_DIMENSIONS", 0),
        embedding_index_path=os.getenv("EMBEDDING_INDEX_PATH", default_embedding_index_path()).strip(),
        embedding_timeout_seconds=_read_int_env("EMBEDDING_TIMEOUT_SECONDS", 60),
        embedding_max_retries=_read_int_env("EMBEDDING_MAX_RETRIES", 2),
        embedding_batch_size=_read_int_env("EMBEDDING_BATCH_SIZE", 8),
        embedding_trust_env=os.getenv("EMBEDDING_TRUST_ENV", "true").strip().lower() in {"1", "true", "yes", "on"},
        knowledge_graph_enabled=os.getenv("KNOWLEDGE_GRAPH_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"},
        knowledge_graph_vault_dir=os.getenv("KNOWLEDGE_GRAPH_VAULT_DIR", default_knowledge_graph_vault_dir()).strip(),
        cors_allowed_origins=_read_csv_env(
            "CORS_ALLOWED_ORIGINS",
            (
                "http://127.0.0.1:5174",
                "http://localhost:5174",
            ),
        ),
    )
