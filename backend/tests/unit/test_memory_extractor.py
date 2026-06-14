from app.memory.memory_extractor import MemoryExtractor
from app.planning.slot_extractor import SlotExtractor


def test_memory_extractor_extracts_long_term_preferences_and_pace() -> None:
    extractor = MemoryExtractor(SlotExtractor())

    result = extractor.extract(message="帮我规划一个杭州三日游，酒店尽量安静，不想吃本地特色，节奏紧张")

    signal_names = {signal.name for signal in result.signals}

    assert signal_names == {"quiet_hotel", "avoid_local_food", "intensive"}
    assert result.pace == "intensive"
    assert result.pace_explicit is True
    assert result.source_text == "帮我规划一个杭州三日游，酒店尽量安静，不想吃本地特色，节奏紧张"
    assert "识别到显式行程节奏" in " ".join(result.extraction_steps)


def test_memory_extractor_recovers_preferences_from_initial_request() -> None:
    extractor = MemoryExtractor(SlotExtractor())

    result = extractor.extract(
        message="3天",
        session_context={
            "session_found": True,
            "latest_final_plan": {"missingFields": ["days"]},
            "initial_request_text": "帮我规划一个杭州三日游，酒店尽量安静，节奏紧张，不想吃本地特色",
        },
    )

    signal_names = {signal.name for signal in result.signals}

    assert signal_names == {"quiet_hotel", "avoid_local_food", "intensive"}
    assert result.pace == "intensive"
    assert result.pace_explicit is True
    assert result.source_text == "帮我规划一个杭州三日游，酒店尽量安静，节奏紧张，不想吃本地特色 / 3天"
    assert "澄清恢复" in " ".join(result.extraction_steps)
