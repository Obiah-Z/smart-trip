from app.db.repositories import MemoryRepository
from app.db.sqlite import init_db
from app.memory.memory_service import MemoryService


def test_memory_round_trip() -> None:
    init_db()
    service = MemoryService(MemoryRepository())
    service.upsert_memory(user_id="test-user", key="hotel_style", value="quiet", scope="travel_preference")

    memories = service.list_memories(user_id="test-user")

    assert any(item["key"] == "hotel_style" and item["value"] == "quiet" for item in memories)


def test_persist_preferences_overrides_conflicting_preferences() -> None:
    init_db()
    service = MemoryService(MemoryRepository())
    service.persist_preferences(
        user_id="test-user-preference-override",
        preferences=["lively_hotel", "avoid_local_food"],
        pace="intensive",
    )

    memories = {item["key"]: item["value"] for item in service.list_memories(user_id="test-user-preference-override")}

    assert memories["hotel_style"] == "prefer_lively_location"
    assert memories["preference_quiet_hotel"] == "avoid_quiet_hotel"
    assert memories["preference_local_food"] == "avoid_local_food"
    assert memories["travel_pace"] == "intensive"


def test_persist_preferences_keeps_family_preference() -> None:
    init_db()
    service = MemoryService(MemoryRepository())
    service.persist_preferences(
        user_id="test-user-family-preference",
        preferences=["family", "quiet_hotel", "local_food"],
        pace="relaxed",
    )

    memories = {item["key"]: item["value"] for item in service.list_memories(user_id="test-user-family-preference")}

    assert memories["preference_family"] == "family"
    assert memories["hotel_style"] == "prefer_quiet_location"
    assert memories["preference_local_food"] == "local_food"
    assert memories["travel_pace"] == "relaxed"
