from __future__ import annotations

import json
import re
from pathlib import Path

from app.rag.indexer import RAGIndexBuilder
from app.rag.tokenizer import tokenize


FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
H2_PATTERN = re.compile(r"^##\s+(.+?)\n", re.MULTILINE)
H3_SPLIT_PATTERN = re.compile(r"(?=^###\s+)", re.MULTILINE)

SECTION_TOPIC_MAP = {
    "天气与出行提醒": "weather",
    "路线与行程建议": "trip_route",
    "景点与玩法清单": "attraction_catalog",
    "餐饮与本地特色": "food",
    "住宿建议": "hotel",
    "住宿区域知识": "hotel_area",
    "主题玩法补充": "theme_extension",
    "城市概览": "city_overview",
}
SUBSECTION_TOPIC_HINTS = {
    "亲子": "family",
    "雨天": "rainy_day",
    "citywalk": "citywalk",
    "博物馆": "museum",
    "文化": "culture",
    "海边": "nature",
    "自然": "nature",
    "住宿": "hotel_area",
    "天气": "weather",
    "美食": "food",
}


def build_manifest(*, markdown_dir: Path) -> dict[str, object]:
    chunks: list[dict[str, object]] = []
    for file_path in sorted(markdown_dir.glob("*.md")):
        if file_path.name == "README.md":
            continue
        content = file_path.read_text(encoding="utf-8")
        metadata, body = parse_markdown_document(content)
        chunks.extend(build_chunks_from_markdown(file_path=file_path, metadata=metadata, body=body))
    return {"version": 2, "source": "raw_markdown", "chunks": chunks}


def write_corpus_and_index(
    *,
    manifest: dict[str, object],
    corpus_dir: Path,
    index_dir: Path,
) -> dict[str, object]:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = corpus_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    builder = RAGIndexBuilder(corpus_dir=corpus_dir, index_dir=index_dir)
    result = builder.build()
    return {"manifest_path": str(manifest_path), **result}


def parse_markdown_document(content: str) -> tuple[dict[str, object], str]:
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return {}, content
    raw_frontmatter = match.group(1)
    body = content[match.end():]
    metadata = parse_frontmatter(raw_frontmatter)
    return metadata, body


def parse_frontmatter(raw_frontmatter: str) -> dict[str, object]:
    metadata: dict[str, object] = {}
    current_key: str | None = None
    current_nested_key: str | None = None
    for raw_line in raw_frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        if line.startswith("  - ") and current_key:
            metadata.setdefault(current_key, [])
            metadata[current_key].append(_strip_quotes(line[4:].strip()))
            continue

        if line.startswith("  ") and ":" in line and current_key and isinstance(metadata.get(current_key), dict):
            nested_key, nested_value = line.strip().split(":", 1)
            metadata[current_key][nested_key.strip()] = _coerce_value(nested_value.strip())
            current_nested_key = nested_key.strip()
            continue

        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        current_nested_key = None
        if not value:
            if key == "section_counts":
                metadata[key] = {}
            else:
                metadata[key] = []
            continue
        metadata[key] = _coerce_value(value)
    return metadata


def build_chunks_from_markdown(
    *,
    file_path: Path,
    metadata: dict[str, object],
    body: str,
) -> list[dict[str, object]]:
    city = str(metadata.get("city") or file_path.stem)
    city_slug = str(metadata.get("city_slug") or file_path.stem)
    tags = [str(item) for item in metadata.get("tags", [])] if isinstance(metadata.get("tags"), list) else []
    generated_at = str(metadata.get("generated_at", ""))
    source_files = [str(item) for item in metadata.get("source_files", [])] if isinstance(metadata.get("source_files"), list) else []
    section_counts = dict(metadata.get("section_counts", {})) if isinstance(metadata.get("section_counts"), dict) else {}

    h2_matches = list(H2_PATTERN.finditer(body))
    chunks: list[dict[str, object]] = []
    for section_index, match in enumerate(h2_matches):
        section_title = match.group(1).strip()
        start = match.end()
        end = h2_matches[section_index + 1].start() if section_index + 1 < len(h2_matches) else len(body)
        section_body = body[start:end].strip()
        if not section_body:
            continue
        chunks.extend(
            _split_section_into_chunks(
                city=city,
                city_slug=city_slug,
                tags=tags,
                generated_at=generated_at,
                source_files=source_files,
                section_counts=section_counts,
                section_title=section_title,
                section_body=section_body,
                file_path=file_path,
            )
        )
    return chunks


def _split_section_into_chunks(
    *,
    city: str,
    city_slug: str,
    tags: list[str],
    generated_at: str,
    source_files: list[str],
    section_counts: dict[str, object],
    section_title: str,
    section_body: str,
    file_path: Path,
) -> list[dict[str, object]]:
    topic = SECTION_TOPIC_MAP.get(section_title, "generic")
    chunk_parts = [part.strip() for part in H3_SPLIT_PATTERN.split(section_body) if part.strip()]

    chunks: list[dict[str, object]] = []
    for chunk_index, part in enumerate(chunk_parts):
        subsection_title, subsection_content = _extract_subsection(part)
        resolved_topic = _resolve_topic(base_topic=topic, subsection_title=subsection_title)
        keywords = _collect_keywords(
            city=city,
            tags=tags,
            section_title=section_title,
            subsection_title=subsection_title,
            content=subsection_content,
        )
        content = subsection_content.strip()
        title = subsection_title or section_title
        chunk_id = f"{city_slug}-{resolved_topic}-{chunk_index:03d}-{_slugify_fragment(title)}"
        chunks.append(
            {
                "id": chunk_id,
                "city": city,
                "topic": resolved_topic,
                "title": title,
                "content": content,
                "keywords": keywords,
                "source": str(file_path.relative_to(file_path.parents[2])),
                "chunk_index": chunk_index,
                "token_count": len(tokenize(content)),
                "metadata": {
                    "kind": "markdown_section",
                    "doc_type": metadata_value("travel_city_knowledge"),
                    "city_slug": city_slug,
                    "section_title": section_title,
                    "subsection_title": subsection_title,
                    "generated_at": generated_at,
                    "source_files": source_files,
                    "section_counts": section_counts,
                    "tags": tags,
                },
            }
        )
    return chunks


def _extract_subsection(part: str) -> tuple[str, str]:
    if part.startswith("### "):
        lines = part.splitlines()
        title = lines[0][4:].strip()
        body = "\n".join(lines[1:]).strip()
        return title, body
    return "", part


def _resolve_topic(*, base_topic: str, subsection_title: str) -> str:
    if base_topic == "trip_route":
        return "trip_route"
    for keyword, topic in SUBSECTION_TOPIC_HINTS.items():
        if keyword.lower() in subsection_title.lower():
            return topic
    return base_topic


def _collect_keywords(
    *,
    city: str,
    tags: list[str],
    section_title: str,
    subsection_title: str,
    content: str,
) -> list[str]:
    keywords = [city, section_title]
    if subsection_title:
        keywords.append(subsection_title)
    keywords.extend(tags)
    keywords.extend(_section_keywords(section_title))
    token_terms = tokenize(f"{subsection_title} {content}")[:24]
    keywords.extend(token_terms)
    return list(dict.fromkeys([item for item in keywords if item]))


def _section_keywords(section_title: str) -> list[str]:
    mapping = {
        "路线与行程建议": ["路线", "行程", "攻略", "推荐", "几日游"],
        "景点与玩法清单": ["景点", "玩法", "推荐"],
        "餐饮与本地特色": ["美食", "本地特色", "餐饮"],
        "住宿建议": ["酒店", "住宿", "住哪里"],
        "住宿区域知识": ["酒店", "区域", "住宿"],
        "天气与出行提醒": ["天气", "出行建议"],
        "主题玩法补充": ["主题玩法", "路线"],
    }
    return mapping.get(section_title, [])


def _coerce_value(value: str) -> object:
    stripped = _strip_quotes(value)
    if stripped.isdigit():
        return int(stripped)
    return stripped


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _slugify_fragment(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", value.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized[:40] or "section"


def metadata_value(value: str) -> str:
    return value
