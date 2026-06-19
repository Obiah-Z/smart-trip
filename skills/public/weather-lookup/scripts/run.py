"""Weather Lookup Skill 沙箱执行脚本。

该脚本由 SkillSandboxRunner 在独立子进程中运行：
- 输入：--payload-json，其中至少包含 destination。
- 输出：stdout 打印天气查询 JSON，供轻咨询和完整规划链路复用。
- 失败：异常、非法 JSON 输出或非 0 退出码会被 ToolService 收敛为工具失败。
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from app.capabilities.mock.travel_engine import load_travel_data, weather_lookup


def build_weather_response(*, data: dict[str, Any], destination: str) -> dict[str, Any]:
    """查询目的地天气并生成旅行适宜性标签。

    当前数据来自本地旅行数据集，输出字段保持工具化结构，供轻咨询回答和完整规划链路共同使用。
    """
    normalized_destination = destination.strip()
    if not normalized_destination:
        return {
            "destination": "",
            "matched": False,
            "summary": "缺少目的地，暂时无法查询天气",
            "advice": "请先确认城市或目的地，再继续判断天气和出行适宜性。",
            "travel_suitability": "unknown",
            "risk_flags": ["missing_destination"],
            "data_source": "local_mock_travel_data",
        }

    weather_data = data.get("weather", {})
    matched = normalized_destination in weather_data
    result = weather_lookup(data=data, destination=normalized_destination)
    summary = str(result.get("summary", "暂无天气数据"))
    advice = str(result.get("advice", "建议灵活安排行程"))
    return {
        "destination": normalized_destination,
        "matched": matched,
        **result,
        "travel_suitability": _infer_travel_suitability(summary=summary, advice=advice, matched=matched),
        "risk_flags": _infer_risk_flags(summary=summary, advice=advice, matched=matched),
        "data_source": "local_mock_travel_data",
    }


def _infer_travel_suitability(*, summary: str, advice: str, matched: bool) -> str:
    """根据天气摘要和建议推断旅行适宜性。"""
    if not matched:
        return "unknown"
    text = f"{summary} {advice}"
    if any(token in text for token in ("暴雨", "高温", "寒潮", "不适合", "减少户外")):
        return "limited"
    if any(token in text for token in ("雨", "阵雨", "闷热", "降温", "雾")):
        return "moderate"
    return "good"


def _infer_risk_flags(*, summary: str, advice: str, matched: bool) -> list[str]:
    """抽取 rain/heat/cold 等风险标签，供前端或 Agent 做提示。"""
    if not matched:
        return ["unknown_weather"]
    text = f"{summary} {advice}"
    flags = []
    if any(token in text for token in ("雨", "阵雨", "暴雨")):
        flags.append("rain")
    if any(token in text for token in ("热", "高温", "补水")):
        flags.append("heat")
    if any(token in text for token in ("冷", "降温", "外套")):
        flags.append("cold")
    if any(token in text for token in ("防晒", "日晒", "紫外线")):
        flags.append("sun_exposure")
    if any(token in text for token in ("雾", "能见度")):
        flags.append("visibility")
    return flags


def main() -> None:
    """Skill 子进程入口：从 --payload-json 读取 destination 并输出天气 JSON。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    destination = str(payload.get("destination", ""))

    data = load_travel_data()
    result = build_weather_response(data=data, destination=destination)
    # 沙箱执行器会把 stdout 解析为 Skill output，不能在这里打印调试文本。
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
