from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config.settings import Settings


@dataclass(frozen=True)
class AmapGeoPoint:
    name: str
    lng: float
    lat: float
    source: str
    formatted_address: str | None = None


@dataclass(frozen=True)
class AmapWalkingRoute:
    points: list[tuple[float, float]]
    distance_meters: int
    duration_seconds: int
    source: str = "amap_walking"


class AmapGeoService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def enabled(self) -> bool:
        return bool(self._settings.amap_web_service_key)

    def geocode(self, *, address: str, city: str | None = None) -> AmapGeoPoint | None:
        if not self.enabled() or not address.strip():
            return None

        payload = {
            "key": self._settings.amap_web_service_key,
            "address": address,
        }
        if city:
            payload["city"] = city

        data = self._get("/v3/geocode/geo", params=payload)
        geocodes = data.get("geocodes") or []
        if not geocodes:
            return None

        item = geocodes[0]
        location = str(item.get("location") or "")
        if "," not in location:
            return None
        lng_text, lat_text = location.split(",", 1)
        return AmapGeoPoint(
            name=address,
            lng=float(lng_text),
            lat=float(lat_text),
            source="amap_geocode",
            formatted_address=item.get("formatted_address"),
        )

    def input_tips(self, *, keywords: str, city: str | None = None) -> list[dict[str, Any]]:
        if not self.enabled() or not keywords.strip():
            return []
        payload = {
            "key": self._settings.amap_web_service_key,
            "keywords": keywords,
        }
        if city:
            payload["city"] = city
        data = self._get("/v3/assistant/inputtips", params=payload)
        return list(data.get("tips") or [])

    def poi_search(self, *, keywords: str, city: str | None = None) -> list[dict[str, Any]]:
        if not self.enabled() or not keywords.strip():
            return []
        payload = {
            "key": self._settings.amap_web_service_key,
            "keywords": keywords,
            "extensions": "base",
            "citylimit": "true" if city else "false",
        }
        if city:
            payload["city"] = city
        data = self._get("/v3/place/text", params=payload)
        return list(data.get("pois") or [])

    def walking_route(
        self,
        *,
        origin_lng: float,
        origin_lat: float,
        destination_lng: float,
        destination_lat: float,
    ) -> AmapWalkingRoute | None:
        if not self.enabled():
            return None

        payload = {
            "key": self._settings.amap_web_service_key,
            "origin": f"{origin_lng:.6f},{origin_lat:.6f}",
            "destination": f"{destination_lng:.6f},{destination_lat:.6f}",
        }
        data = self._get("/v3/direction/walking", params=payload)
        route = data.get("route") or {}
        paths = route.get("paths") or []
        if not paths:
            return None

        path = paths[0]
        step_points: list[tuple[float, float]] = []
        for step in path.get("steps") or []:
            step_points.extend(self._parse_polyline(str(step.get("polyline") or "")))

        if not step_points:
            step_points = [
                (round(origin_lng, 6), round(origin_lat, 6)),
                (round(destination_lng, 6), round(destination_lat, 6)),
            ]

        return AmapWalkingRoute(
            points=self._dedupe_points(step_points),
            distance_meters=int(float(path.get("distance") or 0)),
            duration_seconds=int(float(path.get("duration") or 0)),
        )

    def _get(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._settings.amap_base_url.rstrip('/')}{path}"
        with httpx.Client(timeout=float(self._settings.amap_timeout_seconds), trust_env=False) as client:
            response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("status")) != "1":
            info = payload.get("info") or "AMap request failed"
            raise RuntimeError(str(info))
        return payload

    def _parse_polyline(self, polyline: str) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        for raw_pair in polyline.split(";"):
            item = raw_pair.strip()
            if "," not in item:
                continue
            lng_text, lat_text = item.split(",", 1)
            try:
                points.append((round(float(lng_text), 6), round(float(lat_text), 6)))
            except ValueError:
                continue
        return points

    def _dedupe_points(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        deduped: list[tuple[float, float]] = []
        for point in points:
            if deduped and deduped[-1] == point:
                continue
            deduped.append(point)
        return deduped
