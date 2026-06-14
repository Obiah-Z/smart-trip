from __future__ import annotations

import json
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_ROOT / "data"
KNOWLEDGE_PATH = DATA_DIR / "knowledge" / "cities.json"
TRAVEL_DATA_PATH = DATA_DIR / "mock" / "travel_data.json"
RAW_MARKDOWN_DIR = DATA_DIR / "rag" / "raw_markdown"
FIXED_GENERATED_AT = "2026-01-01T00:00:00+00:00"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def slugify_city(city: str) -> str:
    mapping = {
        "北京": "beijing",
        "杭州": "hangzhou",
        "成都": "chengdu",
        "上海": "shanghai",
        "西安": "xian",
        "重庆": "chongqing",
        "苏州": "suzhou",
        "广州": "guangzhou",
        "厦门": "xiamen",
        "南京": "nanjing",
        "深圳": "shenzhen",
        "青岛": "qingdao",
        "长沙": "changsha",
        "武汉": "wuhan",
        "昆明": "kunming",
        "三亚": "sanya",
        "哈尔滨": "harbin",
        "桂林": "guilin",
        "天津": "tianjin",
        "洛阳": "luoyang",
    }
    return mapping.get(city, city)


def render_city_markdown(*, city_doc: dict, travel_data: dict) -> str:
    city = city_doc["city"]
    city_slug = slugify_city(city)
    tags = city_doc.get("tags", [])
    documents = city_doc.get("documents", [])
    attractions = travel_data.get("attractions", {}).get(city, [])
    hotels = travel_data.get("hotels", {}).get(city, [])
    weather = travel_data.get("weather", {}).get(city, {})

    route_docs = [item for item in documents if item.get("topic") == "trip_route"]
    food_docs = [item for item in documents if item.get("topic") == "food"]
    hotel_docs = [item for item in documents if item.get("topic") == "hotel_area"]
    other_docs = [item for item in documents if item.get("topic") not in {"trip_route", "food", "hotel_area"}]
    generated_at = FIXED_GENERATED_AT
    section_counts = {
        "route_docs": len(route_docs),
        "food_docs": len(food_docs),
        "hotel_docs": len(hotel_docs),
        "other_docs": len(other_docs),
        "attractions": len(attractions),
        "hotels": len(hotels),
        "has_weather": 1 if weather else 0,
    }

    lines = _build_frontmatter(
        city=city,
        city_slug=city_slug,
        tags=tags,
        generated_at=generated_at,
        section_counts=section_counts,
    )

    lines.extend(
        [
        f"# {city}旅行知识库",
        "",
        "## 城市概览",
        "",
        f"- 城市：{city}",
        f"- 主题标签：{', '.join(tags) if tags else '暂无'}",
        f"- 景点条目数：{len(attractions)}",
        f"- 酒店条目数：{len(hotels)}",
        "",
        ]
    )

    if weather:
        lines.extend(
            [
                "## 天气与出行提醒",
                "",
                f"- 天气概况：{weather.get('summary', '暂无')}",
                f"- 出行建议：{weather.get('advice', '暂无')}",
                "",
            ]
        )

    if route_docs:
        lines.extend(["## 路线与行程建议", ""])
        for item in route_docs:
            lines.extend(
                [
                    f"### {item['title']}",
                    "",
                    item["content"],
                    "",
                    f"- 关键词：{', '.join(item.get('keywords', []))}",
                    "",
                ]
            )

    if attractions:
        lines.extend(["## 景点与玩法清单", ""])
        for item in attractions:
            lines.extend(
                [
                    f"### {item['name']}",
                    "",
                    f"- 类型：{item.get('type', 'unknown')}",
                    f"- 区域：{item.get('area', '未知')}",
                    f"- 参考时长：{item.get('durationHours', '未知')} 小时",
                    f"- 门票：{item.get('cost', 0)} 元",
                    f"- 适配节奏：{item.get('pace', 'balanced')}",
                    f"- 标签：{', '.join(item.get('tags', [])) or '暂无'}",
                    "",
                ]
            )

    if food_docs:
        lines.extend(["## 餐饮与本地特色", ""])
        for item in food_docs:
            lines.extend(
                [
                    f"### {item['title']}",
                    "",
                    item["content"],
                    "",
                    f"- 关键词：{', '.join(item.get('keywords', []))}",
                    "",
                ]
            )

    if hotels:
        lines.extend(["## 住宿建议", ""])
        for item in hotels:
            hotel_environment = "安静" if item.get("quiet") else "热闹"
            lines.extend(
                [
                    f"### {item['name']}",
                    "",
                    f"- 区域：{item.get('area', '未知')}",
                    f"- 每晚价格：{item.get('pricePerNight', 0)} 元",
                    f"- 环境倾向：{hotel_environment}",
                    f"- 评分：{item.get('rating', '未知')}",
                    f"- 舒适度：{item.get('comfortScore', '未知')}",
                    f"- 标签：{', '.join(item.get('tags', [])) or '暂无'}",
                    "",
                ]
            )

    if hotel_docs:
        lines.extend(["## 住宿区域知识", ""])
        for item in hotel_docs:
            lines.extend(
                [
                    f"### {item['title']}",
                    "",
                    item["content"],
                    "",
                    f"- 关键词：{', '.join(item.get('keywords', []))}",
                    "",
                ]
            )

    if other_docs:
        lines.extend(["## 主题玩法补充", ""])
        for item in other_docs:
            lines.extend(
                [
                    f"### {item['title']}",
                    "",
                    f"- 主题：{item.get('topic', 'unknown')}",
                    item["content"],
                    "",
                    f"- 关键词：{', '.join(item.get('keywords', []))}",
                    "",
                ]
            )

    return "\n".join(lines).strip() + "\n"


def _build_frontmatter(
    *,
    city: str,
    city_slug: str,
    tags: list[str],
    generated_at: str,
    section_counts: dict[str, int],
) -> list[str]:
    lines = [
        "---",
        'doc_type: "travel_city_knowledge"',
        f'city: "{city}"',
        f'city_slug: "{city_slug}"',
        'language: "zh-CN"',
        'source_files:',
        '  - "backend/data/knowledge/cities.json"',
        '  - "backend/data/mock/travel_data.json"',
        "tags:",
    ]
    if tags:
        for tag in tags:
            lines.append(f'  - "{tag}"')
    else:
        lines.append('  - "generic"')
    lines.extend(
        [
            "section_counts:",
            f"  route_docs: {section_counts['route_docs']}",
            f"  food_docs: {section_counts['food_docs']}",
            f"  hotel_docs: {section_counts['hotel_docs']}",
            f"  other_docs: {section_counts['other_docs']}",
            f"  attractions: {section_counts['attractions']}",
            f"  hotels: {section_counts['hotels']}",
            f"  has_weather: {section_counts['has_weather']}",
            f'generated_at: "{generated_at}"',
            "---",
            "",
        ]
    )
    return lines


def build_markdown_corpus() -> list[Path]:
    knowledge = load_json(KNOWLEDGE_PATH)
    travel_data = load_json(TRAVEL_DATA_PATH)
    RAW_MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)

    written_files: list[Path] = []
    for city_doc in knowledge["cities"]:
        city = city_doc["city"]
        content = render_city_markdown(city_doc=city_doc, travel_data=travel_data)
        file_path = RAW_MARKDOWN_DIR / f"{slugify_city(city)}.md"
        _write_text_if_changed(file_path, content)
        written_files.append(file_path)

    readme_path = RAW_MARKDOWN_DIR / "README.md"
    _write_text_if_changed(
        readme_path,
        "\n".join(
            [
                "# Raw Markdown Corpus",
                "",
                "这里存放旅行系统后续用于 RAG 处理的原始 Markdown 语料。",
                "",
                "## 结构",
                "",
                "- 每个城市一份 Markdown 文档",
                "- 每份文档带有 YAML frontmatter",
                "- 文档包含：城市概览、路线建议、景点清单、餐饮、住宿、主题玩法",
                "",
                "## Frontmatter 字段",
                "",
                "- `doc_type`：文档类型",
                "- `city` / `city_slug`：城市标识",
                "- `language`：语料语言",
                "- `source_files`：原始来源文件",
                "- `tags`：城市主题标签",
                "- `section_counts`：各类章节条目数",
                "- `generated_at`：生成时间",
                "",
                "## 生成方式",
                "",
                "```bash",
                "cd backend",
                "python scripts/build_rag_markdown_corpus.py",
                "```",
                "",
                "## 后续建议",
                "",
                "后续可以直接基于这些 Markdown：",
                "",
                "1. 切 chunk",
                "2. 提取 metadata",
                "3. 生成向量索引或 BM25 索引",
                "4. 增加来源时间和可信度标记",
                "",
            ]
        )
        + "\n",
    )
    written_files.append(readme_path)
    return written_files


def _write_text_if_changed(path: Path, content: str) -> None:
    if path.exists():
        try:
            current = path.read_text(encoding="utf-8")
        except OSError:
            current = None
        if current == content:
            return
    path.write_text(content, encoding="utf-8")


def main() -> None:
    written_files = build_markdown_corpus()
    print("raw markdown corpus built")
    print(f"- files: {len(written_files)}")
    print(f"- directory: {RAW_MARKDOWN_DIR}")
    for path in written_files[:5]:
        print(f"  - {path.name}")


if __name__ == "__main__":
    main()
