from app.capabilities.presentation.geo_service import GeoPresentationService


class _FakeRoute:
    def __init__(self, points, distance_meters=1200, duration_seconds=900, source="amap_walking"):
        self.points = points
        self.distance_meters = distance_meters
        self.duration_seconds = duration_seconds
        self.source = source


class _FakeAmapGeoService:
    def __init__(self, enabled=True):
        self._enabled = enabled
        self.walking_calls = 0

    def enabled(self):
        return self._enabled

    def poi_search(self, *, keywords, city=None):
        return []

    def input_tips(self, *, keywords, city=None):
        return []

    def geocode(self, *, address, city=None):
        return None

    def walking_route(self, *, origin_lng, origin_lat, destination_lng, destination_lat):
        self.walking_calls += 1
        return _FakeRoute(
            points=[
                (round(origin_lng, 6), round(origin_lat, 6)),
                (round((origin_lng + destination_lng) / 2, 6), round((origin_lat + destination_lat) / 2, 6)),
                (round(destination_lng, 6), round(destination_lat, 6)),
            ]
        )


def test_geo_presentation_builds_detailed_diagnostics(tmp_path) -> None:
    service = GeoPresentationService(
        amap_cache_path=tmp_path / "poi_cache.json",
        route_cache_path=tmp_path / "route_cache.json",
        amap_geo_service=_FakeAmapGeoService(enabled=False),
    )

    diagnostics = service._build_diagnostics(
        markers=[
            {"source": "registry"},
            {"source": "amap_cache"},
            {"source": "amap_poi"},
            {"source": "amap_tip"},
            {"source": "amap_geocode"},
            {"source": "generated_fallback"},
        ],
        routes=[
            {"source": "amap_walking"},
            {"source": "amap_walking_cache"},
            {"source": "straight_line"},
        ],
    )

    assert diagnostics["registry_count"] == 1
    assert diagnostics["amap_cache_count"] == 1
    assert diagnostics["amap_poi_count"] == 1
    assert diagnostics["amap_tip_count"] == 1
    assert diagnostics["amap_geocode_count"] == 1
    assert diagnostics["generated_count"] == 1
    assert diagnostics["walking_route_count"] == 1
    assert diagnostics["route_cache_count"] == 1
    assert diagnostics["fallback_route_count"] == 1


def test_geo_presentation_prefers_amap_walking_route_and_caches_it(tmp_path) -> None:
    fake_amap = _FakeAmapGeoService(enabled=True)
    service = GeoPresentationService(
        amap_cache_path=tmp_path / "poi_cache.json",
        route_cache_path=tmp_path / "route_cache.json",
        amap_geo_service=fake_amap,
    )

    points = [
        {"name": "酒店A", "lng": 120.100001, "lat": 30.200001},
        {"name": "景点B", "lng": 120.120001, "lat": 30.220001},
    ]

    first_route = service._resolve_route_geometry(destination="杭州", points=points)
    second_route = service._resolve_route_geometry(destination="杭州", points=points)

    assert first_route["source"] == "amap_walking"
    assert first_route["distanceMeters"] == 1200
    assert first_route["durationSeconds"] == 900
    assert len(first_route["points"]) >= 3
    assert second_route["source"] == "amap_walking_cache"
    assert fake_amap.walking_calls == 1
