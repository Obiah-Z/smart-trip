from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.paths import data_dir

MOCK_TRAVEL_DATA_PATH = data_dir() / "mock" / "travel_data.json"
CITY_KNOWLEDGE_PATH = data_dir() / "knowledge" / "cities.json"

CITY_HERO_TIMES = {
    "北京": "清晨金色光线",
    "杭州": "清晨薄雾",
    "成都": "午后柔光",
    "上海": "傍晚蓝调时刻",
    "西安": "落日前暖光",
    "重庆": "夜幕初上",
    "苏州": "清晨柔光",
    "广州": "傍晚热带暖光",
    "厦门": "海边日落前",
    "南京": "傍晚秦淮河灯光时段",
    "深圳": "海风傍晚",
    "青岛": "海边晴朗午后",
    "长沙": "夜色初上",
    "武汉": "傍晚江景时段",
    "昆明": "晴朗午后",
    "三亚": "海边黄金时刻",
    "哈尔滨": "晴冷清晨",
    "桂林": "山水晨雾",
    "天津": "傍晚街区灯光时段",
    "洛阳": "古城傍晚暖光",
}

ATTRACTION_TIME_BY_TYPE = {
    "nature": "清晨柔光",
    "culture": "上午柔光",
    "museum": "白天通透光线",
    "citywalk": "傍晚步行时段",
    "food": "傍晚烟火时刻",
    "relaxed": "午后松弛时段",
}

HOTEL_TIME_BY_TAG = {
    "quiet_hotel": "下午安静柔光",
    "lively_hotel": "夜晚城市灯光",
    "comfortable_hotel": "午后暖光",
    "design_hotel": "傍晚室内氛围灯光",
}


class TripVisualTaskBuilder:
    def __init__(
        self,
        *,
        travel_data_path: Path = MOCK_TRAVEL_DATA_PATH,
        city_knowledge_path: Path = CITY_KNOWLEDGE_PATH,
    ) -> None:
        self._travel_data = json.loads(travel_data_path.read_text(encoding="utf-8"))
        self._city_knowledge = json.loads(city_knowledge_path.read_text(encoding="utf-8")).get("cities", [])
        self._knowledge_by_city = {
            str(item.get("city")): item
            for item in self._city_knowledge
            if item.get("city")
        }

    def build_tasks(self, *, asset_groups: set[str] | None = None) -> list[dict[str, Any]]:
        requested_groups = asset_groups or {"hero", "attractions", "hotels", "foods"}
        tasks: list[dict[str, Any]] = []
        city_names = list(self._travel_data.get("attractions", {}).keys())

        for city in city_names:
            if "hero" in requested_groups:
                tasks.append(self._build_hero_task(city))

            if "attractions" in requested_groups:
                for attraction in self._travel_data.get("attractions", {}).get(city, []):
                    tasks.append(self._build_attraction_task(city, attraction))

            if "hotels" in requested_groups:
                for hotel in self._travel_data.get("hotels", {}).get(city, []):
                    tasks.append(self._build_hotel_task(city, hotel))

            if "foods" in requested_groups:
                for spot in self._food_candidates(city):
                    tasks.append(self._build_food_task(city, spot))

        return tasks

    def build_summary(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        by_group: dict[str, int] = {}
        by_city: dict[str, dict[str, int]] = {}
        for item in tasks:
            group = str(item.get("asset_group"))
            city = str(item.get("destination"))
            by_group[group] = by_group.get(group, 0) + 1
            city_bucket = by_city.setdefault(city, {})
            city_bucket[group] = city_bucket.get(group, 0) + 1

        return {
            "total_tasks": len(tasks),
            "asset_groups": by_group,
            "cities": len(by_city),
            "city_breakdown": by_city,
        }

    def _build_hero_task(self, city: str) -> dict[str, Any]:
        city_knowledge = self._knowledge_by_city.get(city, {})
        doc_titles = [doc.get("title") for doc in city_knowledge.get("documents", [])[:3] if doc.get("title")]
        content_hint = "、".join(doc_titles) if doc_titles else f"突出 {city} 的目的地气质与代表性旅行场景"
        return {
            "asset_group": "hero",
            "destination": city,
            "subject_name": city,
            "subject_type": "destination",
            "area": self._hero_area(city),
            "style": "travel_editorial",
            # Current Kolors relay only works reliably with square generation.
            # The frontend hero still crops well via object-fit cover.
            "aspect": "square",
            "time_of_day": CITY_HERO_TIMES.get(city, "清晨或傍晚柔和光线"),
            "weather_hint": self._weather_hint(city),
            "tags": city_knowledge.get("tags", []),
            "content_hint": content_hint,
            "size": "1024x1024",
            "output_format": "jpeg",
        }

    def _build_attraction_task(self, city: str, attraction: dict[str, Any]) -> dict[str, Any]:
        attraction_type = str(attraction.get("type") or "citywalk")
        tags = list(attraction.get("tags", []))
        return {
            "asset_group": "attractions",
            "destination": city,
            "subject_name": attraction.get("name"),
            "subject_type": attraction_type,
            "area": attraction.get("area"),
            "style": "travel_editorial",
            "aspect": "square",
            "time_of_day": ATTRACTION_TIME_BY_TYPE.get(attraction_type, "白天通透光线"),
            "weather_hint": self._weather_hint(city),
            "tags": tags,
            "content_hint": self._attraction_hint(city, attraction),
            "size": "1024x1024",
            "output_format": "jpeg",
        }

    def _build_hotel_task(self, city: str, hotel: dict[str, Any]) -> dict[str, Any]:
        hotel_tags = list(hotel.get("tags", []))
        return {
            "asset_group": "hotels",
            "destination": city,
            "subject_name": hotel.get("name"),
            "subject_type": "hotel",
            "area": hotel.get("area"),
            "style": "hotel_editorial",
            "aspect": "square",
            "time_of_day": self._hotel_time(hotel_tags),
            "weather_hint": self._weather_hint(city),
            "tags": hotel_tags,
            "content_hint": self._hotel_hint(hotel),
            "size": "1024x1024",
            "output_format": "jpeg",
        }

    def _build_food_task(self, city: str, spot: dict[str, Any]) -> dict[str, Any]:
        tags = list(spot.get("tags", []))
        return {
            "asset_group": "foods",
            "destination": city,
            "subject_name": spot.get("name"),
            "subject_type": "food",
            "area": spot.get("area"),
            "style": "food_editorial",
            "aspect": "square",
            "time_of_day": "傍晚烟火时刻",
            "weather_hint": self._weather_hint(city),
            "tags": tags,
            "content_hint": self._food_hint(city, spot),
            "size": "1024x1024",
            "output_format": "jpeg",
        }

    def _hero_area(self, city: str) -> str:
        attractions = self._travel_data.get("attractions", {}).get(city, [])
        if not attractions:
            return city
        first_item = attractions[0]
        return str(first_item.get("area") or city)

    def _weather_hint(self, city: str) -> str:
        summary = str(self._travel_data.get("weather", {}).get(city, {}).get("summary") or "").strip()
        if not summary:
            return "适合旅行的清爽天气"
        return summary.split("，")[0].split(",")[0]

    def _attraction_hint(self, city: str, attraction: dict[str, Any]) -> str:
        attraction_type = str(attraction.get("type") or "")
        if attraction_type == "museum":
            return "突出馆舍空间、观展氛围和城市文化体验感"
        if attraction_type == "food":
            return f"在 {city} 的旅行语境下体现街区烟火感和顺路觅食氛围"
        return f"突出 {attraction.get('name')} 作为 {city} 旅行代表性场景的到达感"

    def _hotel_time(self, hotel_tags: list[str]) -> str:
        for item in hotel_tags:
            if item in HOTEL_TIME_BY_TAG:
                return HOTEL_TIME_BY_TAG[item]
        return "午后暖光"

    def _hotel_hint(self, hotel: dict[str, Any]) -> str:
        quiet_text = "安静住宿" if hotel.get("quiet") else "热闹商圈氛围"
        comfort = hotel.get("comfortScore")
        rating = hotel.get("rating")
        return f"突出 {quiet_text}、空间舒适度与真实入住体验，参考评分 {rating} / 舒适度 {comfort}"

    def _food_hint(self, city: str, spot: dict[str, Any]) -> str:
        food_doc = self._city_food_doc(city)
        if food_doc:
            return f"结合 {spot.get('name')} 所在街区氛围，适度体现 {food_doc}"
        return f"突出 {city} 本地旅行中的顺路用餐与街区烟火感"

    def _city_food_doc(self, city: str) -> str:
        city_knowledge = self._knowledge_by_city.get(city, {})
        for doc in city_knowledge.get("documents", []):
            if doc.get("topic") == "food":
                return str(doc.get("content") or "")
        return ""

    def _food_candidates(self, city: str) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in self._travel_data.get("attractions", {}).get(city, []):
            name = str(item.get("name") or "").strip()
            if not name or name in seen:
                continue
            tags = set(map(str, item.get("tags", [])))
            attraction_type = str(item.get("type") or "")
            if attraction_type in {"food", "night_market", "snack"} or tags.intersection({"food", "local_food", "snack", "night_market"}):
                candidates.append(item)
                seen.add(name)
        return candidates
