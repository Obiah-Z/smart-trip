from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from app.integrations.amap_geo_service import AmapGeoService


DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "presentation"
CITY_GEO_PATH = DATA_ROOT / "city_geo.json"
POI_GEO_PATH = DATA_ROOT / "poi_geo.json"
AMAP_CACHE_PATH = DATA_ROOT / "poi_geo_amap_cache.json"
ROUTE_CACHE_PATH = DATA_ROOT / "route_geo_amap_cache.json"


class GeoPresentationService:
    ROUTE_COLORS = ("#3bb58f", "#f59e0b", "#4f86f7", "#ef6f6c", "#8b5cf6")
    TYPE_LABELS = {
        "city_center": "城市中心",
        "hotel": "住宿",
        "attraction": "景点",
        "food": "餐饮",
    }

    def __init__(
        self,
        *,
        city_geo_path: Path = CITY_GEO_PATH,
        poi_geo_path: Path = POI_GEO_PATH,
        amap_cache_path: Path = AMAP_CACHE_PATH,
        route_cache_path: Path = ROUTE_CACHE_PATH,
        amap_geo_service: AmapGeoService | None = None,
    ) -> None:
        self._city_geo = self._load_json(city_geo_path)
        self._poi_geo = self._load_json(poi_geo_path)
        self._amap_cache_path = amap_cache_path
        self._amap_cache = self._load_json(amap_cache_path)
        self._route_cache_path = route_cache_path
        self._route_cache = self._load_json(route_cache_path)
        self._amap_geo_service = amap_geo_service

    def enrich_final_plan(
        self,
        *,
        final_plan: dict[str, Any],
        structured_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        visual = self.build_visual(final_plan=final_plan, structured_constraints=structured_constraints)
        return {
            **final_plan,
            "visual": visual,
        }

    def build_visual(
        self,
        *,
        final_plan: dict[str, Any],
        structured_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        summary = final_plan.get("summary") or {}
        destination = summary.get("destinationCity") or structured_constraints.get("destination")
        if not destination:
            return {}

        center = self._resolve_city_center(destination=destination)
        activity_day_map = self._build_activity_day_map(final_plan=final_plan)
        hotel_options = list(final_plan.get("hotelOptions") or final_plan.get("hotelRecommendation") or [])
        attraction_items = list(final_plan.get("attractionRecommendations") or [])
        food_items = list(final_plan.get("foodRecommendations") or [])

        markers: list[dict[str, Any]] = []
        markers.extend(
            self._build_markers(
                destination=destination,
                items=hotel_options[:2],
                marker_type="hotel",
                activity_day_map=activity_day_map,
            )
        )
        markers.extend(
            self._build_markers(
                destination=destination,
                items=attraction_items[:6],
                marker_type="attraction",
                activity_day_map=activity_day_map,
            )
        )
        markers.extend(
            self._build_markers(
                destination=destination,
                items=food_items[:3],
                marker_type="food",
                activity_day_map=activity_day_map,
            )
        )

        markers = self._dedupe_markers(markers=markers)
        if not markers:
            markers = [
                {
                    "id": f"city-{destination}",
                    "name": destination,
                    "type": "city_center",
                    "typeLabel": self.TYPE_LABELS["city_center"],
                    "area": "城市中心",
                    "day": None,
                    "lng": center["lng"],
                    "lat": center["lat"],
                    "source": "city_center",
                }
            ]

        routes = self._build_routes(destination=destination, final_plan=final_plan, markers=markers)
        diagnostics = self._build_diagnostics(markers=markers, routes=routes)
        return {
            "map": {
                "provider": "amap_ready" if self._amap_geo_service is not None and self._amap_geo_service.enabled() else "local_preview",
                "mode": "hybrid_preview",
                "destination": destination,
                "title": f"{destination} 行程位置预览",
                "subtitle": "点位会优先命中本地注册表与高德坐标，路线可按配置升级为真实步行路径。",
                "center": center,
                "zoom": center.get("zoom", 11),
                "bounds": self._build_bounds(markers=markers, center=center),
                "markers": markers,
                "routes": routes,
                "diagnostics": diagnostics,
            }
        }

    def _build_markers(
        self,
        *,
        destination: str,
        items: list[dict[str, Any]],
        marker_type: str,
        activity_day_map: dict[str, int],
    ) -> list[dict[str, Any]]:
        markers: list[dict[str, Any]] = []
        for item in items:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            point = self._resolve_point(destination=destination, name=name, marker_type=marker_type)
            marker_day = activity_day_map.get(name)
            markers.append(
                {
                    "id": f"{marker_type}-{self._slugify(name)}",
                    "name": name,
                    "type": marker_type,
                    "typeLabel": self.TYPE_LABELS.get(marker_type, marker_type),
                    "area": item.get("area") or point.get("area") or "核心城区",
                    "day": marker_day,
                    "lng": point["lng"],
                    "lat": point["lat"],
                    "source": point.get("source", "fallback"),
                    "pricePerNight": item.get("pricePerNight"),
                    "cost": item.get("cost"),
                    "durationHours": item.get("durationHours"),
                    "reason": item.get("reason"),
                }
            )
        return markers

    def _build_activity_day_map(self, *, final_plan: dict[str, Any]) -> dict[str, int]:
        mapping: dict[str, int] = {}
        day_groups = final_plan.get("dailyGuide") or final_plan.get("days") or []
        for day in day_groups:
            day_number = day.get("day")
            if not isinstance(day_number, int):
                continue
            for name in day.get("activities", []) or []:
                if isinstance(name, str) and name not in mapping:
                    mapping[name] = day_number
        return mapping

    def _build_routes(
        self,
        *,
        destination: str,
        final_plan: dict[str, Any],
        markers: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        marker_lookup = {item["name"]: item for item in markers}
        hotel_marker = next((item for item in markers if item.get("type") == "hotel"), None)
        route_days = final_plan.get("dailyGuide") or final_plan.get("days") or []
        routes: list[dict[str, Any]] = []
        for index, day in enumerate(route_days):
            activities = [item for item in day.get("activities", []) or [] if item in marker_lookup]
            points = [marker_lookup[name] for name in activities]
            if len(points) == 1 and hotel_marker is not None:
                points = [hotel_marker, points[0]]
            if len(points) < 2:
                continue
            route_geometry = self._resolve_route_geometry(destination=destination, points=points)
            routes.append(
                {
                    "day": day.get("day"),
                    "label": f"Day {day.get('day')}",
                    "color": self.ROUTE_COLORS[index % len(self.ROUTE_COLORS)],
                    "points": route_geometry["points"],
                    "source": route_geometry["source"],
                    "distanceMeters": route_geometry.get("distanceMeters", 0),
                    "durationSeconds": route_geometry.get("durationSeconds", 0),
                }
            )
        return routes

    def _build_bounds(self, *, markers: list[dict[str, Any]], center: dict[str, Any]) -> dict[str, float]:
        if not markers:
            return {
                "min_lng": center["lng"] - 0.05,
                "max_lng": center["lng"] + 0.05,
                "min_lat": center["lat"] - 0.04,
                "max_lat": center["lat"] + 0.04,
            }

        lng_values = [float(item["lng"]) for item in markers]
        lat_values = [float(item["lat"]) for item in markers]
        min_lng = min(lng_values)
        max_lng = max(lng_values)
        min_lat = min(lat_values)
        max_lat = max(lat_values)
        lng_padding = max(0.02, (max_lng - min_lng) * 0.18)
        lat_padding = max(0.015, (max_lat - min_lat) * 0.22)
        return {
            "min_lng": min_lng - lng_padding,
            "max_lng": max_lng + lng_padding,
            "min_lat": min_lat - lat_padding,
            "max_lat": max_lat + lat_padding,
        }

    def _dedupe_markers(self, *, markers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in markers:
            key = (item.get("name", ""), item.get("type", ""))
            if key in seen:
                continue
            deduped.append(item)
            seen.add(key)
        return deduped

    def _build_diagnostics(self, *, markers: list[dict[str, Any]], routes: list[dict[str, Any]]) -> dict[str, Any]:
        source_counts: dict[str, int] = {}
        for item in markers:
            source = str(item.get("source") or "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1

        route_source_counts: dict[str, int] = {}
        for item in routes:
            source = str(item.get("source") or "unknown")
            route_source_counts[source] = route_source_counts.get(source, 0) + 1

        registry_count = source_counts.get("registry", 0)
        amap_cache_count = source_counts.get("amap_cache", 0)
        amap_poi_count = source_counts.get("amap_poi", 0)
        amap_tip_count = source_counts.get("amap_tip", 0)
        amap_geocode_count = source_counts.get("amap_geocode", 0)
        generated_count = source_counts.get("generated_fallback", 0)
        city_center_count = source_counts.get("city_center", 0)
        total = len(markers)
        registry_ratio = round(registry_count / total, 3) if total else 0.0
        return {
            "total_markers": total,
            "registry_count": registry_count,
            "amap_cache_count": amap_cache_count,
            "amap_poi_count": amap_poi_count,
            "amap_tip_count": amap_tip_count,
            "amap_geocode_count": amap_geocode_count,
            "generated_count": generated_count,
            "city_center_count": city_center_count,
            "registry_ratio": registry_ratio,
            "source_counts": source_counts,
            "total_routes": len(routes),
            "route_source_counts": route_source_counts,
            "walking_route_count": route_source_counts.get("amap_walking", 0),
            "route_cache_count": route_source_counts.get("amap_walking_cache", 0),
            "fallback_route_count": route_source_counts.get("straight_line", 0),
        }

    def _resolve_city_center(self, *, destination: str) -> dict[str, float | int]:
        item = self._city_geo.get(destination) or {}
        if item:
            return {
                "lng": float(item.get("lng", 116.3974)),
                "lat": float(item.get("lat", 39.9093)),
                "zoom": int(item.get("zoom", 11)),
            }
        return {"lng": 116.3974, "lat": 39.9093, "zoom": 11}

    def _resolve_point(self, *, destination: str, name: str, marker_type: str) -> dict[str, Any]:
        city_points = self._poi_geo.get(destination) or {}
        stored = city_points.get(name)
        if stored:
            return {
                "lng": float(stored["lng"]),
                "lat": float(stored["lat"]),
                "area": stored.get("area"),
                "source": "registry",
            }

        cached = self._resolve_cached_point(destination=destination, name=name)
        if cached is not None:
            return cached

        amap_point = self._resolve_amap_point(destination=destination, name=name)
        if amap_point is not None:
            return amap_point

        center = self._resolve_city_center(destination=destination)
        digest = hashlib.md5(f"{destination}:{marker_type}:{name}".encode("utf-8")).hexdigest()
        seed = int(digest[:8], 16)
        angle = math.radians(seed % 360)
        radius = 0.018 + ((seed >> 4) % 7) * 0.004
        lng_scale = 1.15 if marker_type == "hotel" else 1.0
        lat_scale = 0.72 if marker_type == "food" else 0.82
        return {
            "lng": round(float(center["lng"]) + math.cos(angle) * radius * lng_scale, 6),
            "lat": round(float(center["lat"]) + math.sin(angle) * radius * lat_scale, 6),
            "area": "城市核心区",
            "source": "generated_fallback",
        }

    def _resolve_cached_point(self, *, destination: str, name: str) -> dict[str, Any] | None:
        city_points = self._amap_cache.get(destination) or {}
        stored = city_points.get(name)
        if not stored:
            return None
        return {
            "lng": float(stored["lng"]),
            "lat": float(stored["lat"]),
            "area": stored.get("area") or "城市核心区",
            "source": stored.get("source") or "amap_cache",
        }

    def _resolve_amap_point(self, *, destination: str, name: str) -> dict[str, Any] | None:
        if self._amap_geo_service is None or not self._amap_geo_service.enabled():
            return None

        poi_point = self._resolve_amap_poi(destination=destination, name=name)
        if poi_point is not None:
            return poi_point

        tip_point = self._resolve_amap_tip(destination=destination, name=name)
        if tip_point is not None:
            return tip_point

        try:
            point = self._amap_geo_service.geocode(address=name, city=destination)
        except Exception:
            return None
        if point is None:
            return None

        result = {
            "lng": float(point.lng),
            "lat": float(point.lat),
            "area": destination,
            "source": point.source,
        }
        self._store_amap_cache(destination=destination, name=name, point=result)
        return result

    def _resolve_amap_poi(self, *, destination: str, name: str) -> dict[str, Any] | None:
        try:
            pois = self._amap_geo_service.poi_search(keywords=name, city=destination)
        except Exception:
            return None
        if not pois:
            return None
        item = pois[0]
        location = str(item.get("location") or "")
        if "," not in location:
            return None
        lng_text, lat_text = location.split(",", 1)
        result = {
            "lng": float(lng_text),
            "lat": float(lat_text),
            "area": item.get("address") or item.get("pname") or destination,
            "source": "amap_poi",
        }
        self._store_amap_cache(destination=destination, name=name, point=result)
        return result

    def _resolve_amap_tip(self, *, destination: str, name: str) -> dict[str, Any] | None:
        try:
            tips = self._amap_geo_service.input_tips(keywords=name, city=destination)
        except Exception:
            return None
        if not tips:
            return None
        item = tips[0]
        location = str(item.get("location") or "")
        if "," not in location:
            return None
        lng_text, lat_text = location.split(",", 1)
        result = {
            "lng": float(lng_text),
            "lat": float(lat_text),
            "area": item.get("district") or destination,
            "source": "amap_tip",
        }
        self._store_amap_cache(destination=destination, name=name, point=result)
        return result

    def _store_amap_cache(self, *, destination: str, name: str, point: dict[str, Any]) -> None:
        if destination not in self._amap_cache:
            self._amap_cache[destination] = {}
        self._amap_cache[destination][name] = {
            "lng": point["lng"],
            "lat": point["lat"],
            "area": point.get("area"),
            "source": point.get("source") or "amap_cache",
        }
        self._amap_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._amap_cache_path.write_text(
            json.dumps(self._amap_cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _resolve_route_geometry(self, *, destination: str, points: list[dict[str, Any]]) -> dict[str, Any]:
        direct_points = [{"lng": item["lng"], "lat": item["lat"]} for item in points]
        cached = self._resolve_cached_route(destination=destination, points=points)
        if cached is not None:
            return cached

        if self._amap_geo_service is None or not self._amap_geo_service.enabled():
            return {"points": direct_points, "source": "straight_line", "distanceMeters": 0, "durationSeconds": 0}

        full_path: list[dict[str, float]] = []
        total_distance = 0
        total_duration = 0
        all_segments_from_amap = True
        for index in range(len(points) - 1):
            origin = points[index]
            destination_point = points[index + 1]
            try:
                route = self._amap_geo_service.walking_route(
                    origin_lng=float(origin["lng"]),
                    origin_lat=float(origin["lat"]),
                    destination_lng=float(destination_point["lng"]),
                    destination_lat=float(destination_point["lat"]),
                )
            except Exception:
                route = None

            if route is None:
                all_segments_from_amap = False
                break

            segment_points = [{"lng": lng, "lat": lat} for lng, lat in route.points]
            if full_path and segment_points and full_path[-1] == segment_points[0]:
                segment_points = segment_points[1:]
            full_path.extend(segment_points)
            total_distance += route.distance_meters
            total_duration += route.duration_seconds

        if all_segments_from_amap and full_path:
            result = {
                "points": full_path,
                "source": "amap_walking",
                "distanceMeters": total_distance,
                "durationSeconds": total_duration,
            }
            self._store_route_cache(destination=destination, points=points, route=result)
            return result

        return {"points": direct_points, "source": "straight_line", "distanceMeters": 0, "durationSeconds": 0}

    def _resolve_cached_route(self, *, destination: str, points: list[dict[str, Any]]) -> dict[str, Any] | None:
        cache_key = self._route_cache_key(points=points)
        city_routes = self._route_cache.get(destination) or {}
        route = city_routes.get(cache_key)
        if not route:
            return None
        return {
            "points": list(route.get("points") or []),
            "source": route.get("source") or "amap_walking_cache",
            "distanceMeters": int(route.get("distanceMeters") or 0),
            "durationSeconds": int(route.get("durationSeconds") or 0),
        }

    def _store_route_cache(self, *, destination: str, points: list[dict[str, Any]], route: dict[str, Any]) -> None:
        if destination not in self._route_cache:
            self._route_cache[destination] = {}
        cache_key = self._route_cache_key(points=points)
        self._route_cache[destination][cache_key] = {
            "points": route["points"],
            "source": "amap_walking_cache",
            "distanceMeters": route.get("distanceMeters") or 0,
            "durationSeconds": route.get("durationSeconds") or 0,
        }
        self._route_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._route_cache_path.write_text(
            json.dumps(self._route_cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _route_cache_key(self, *, points: list[dict[str, Any]]) -> str:
        normalized = [
            {
                "name": str(item.get("name") or ""),
                "lng": round(float(item["lng"]), 6),
                "lat": round(float(item["lat"]), 6),
            }
            for item in points
        ]
        return hashlib.md5(json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def _slugify(self, value: str) -> str:
        digest = hashlib.md5(value.encode("utf-8")).hexdigest()[:10]
        return digest

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
