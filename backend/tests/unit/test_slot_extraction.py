from app.planning.slot_extractor import SlotExtractor


def test_extracts_trip_constraints() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("帮我规划杭州3天旅行，预算3000，节奏轻松一点，想吃本地特色")

    assert result.destination == "杭州"
    assert result.destination_explicit is True
    assert result.days == 3
    assert result.budget == 3000
    assert result.pace == "relaxed"
    assert result.pace_explicit is True
    assert "local_food" in result.preferences


def test_extracts_beijing_destination() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("帮我规划北京三日游，预算4000，节奏轻松，想吃美食")

    assert result.destination == "北京"
    assert result.destination_explicit is True
    assert result.days == 3
    assert result.budget == 4000
    assert result.pace == "relaxed"
    assert result.pace_explicit is True
    assert "food" in result.preferences


def test_extracts_negative_preferences_and_intensive_pace() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("帮我规划一个杭州三日游，预算3000，节奏紧张一点，酒店尽量嘈杂，不想吃本地特色")

    assert result.destination == "杭州"
    assert result.destination_explicit is True
    assert result.days == 3
    assert result.budget == 3000
    assert result.pace == "intensive"
    assert result.pace_explicit is True
    assert "lively_hotel" in result.preferences
    assert "avoid_local_food" in result.preferences
    assert "local_food" not in result.preferences
    assert "quiet_hotel" not in result.preferences


def test_extracts_simple_consulting_query_without_trip_defaults() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("杭州有哪些推荐的景点")

    assert result.destination == "杭州"
    assert result.destination_explicit is True
    assert result.days is None
    assert result.budget is None
    assert result.preferences == []
    assert result.pace == "balanced"
    assert result.pace_explicit is False


def test_extracts_followup_budget_and_comfort_update_without_destination() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("帮我把预算提升到10000，主要是提升住宿舒适度")

    assert result.destination is None
    assert result.destination_explicit is False
    assert result.budget == 10000
    assert "comfortable_hotel" in result.preferences
    assert result.pace == "balanced"
    assert result.pace_explicit is False


def test_extracts_budget_target_near_policy_from_followup_expression() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("将总体预算尽可能贴近3000")

    assert result.destination is None
    assert result.days is None
    assert result.budget == 3000
    assert result.target_budget == 3000
    assert result.budget_policy == "target_near"


def test_extracts_budget_cap_policy_from_followup_expression() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("把总花费控制在3000以内")

    assert result.budget == 3000
    assert result.target_budget == 3000
    assert result.budget_policy == "cap"


def test_extracts_followup_comfort_phrase_variants() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("酒店住得更舒适一点，最好继续安静一些")

    assert result.destination is None
    assert result.days is None
    assert "comfortable_hotel" in result.preferences
    assert "quiet_hotel" in result.preferences


def test_extracts_followup_excluded_attraction_without_reasking_destination_or_days() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("不想要去逛故宫")

    assert result.destination is None
    assert result.days is None
    assert result.excluded_attractions == ["故宫"]


def test_extracts_excluded_attraction_from_negative_phrase_without_action_verb() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("不想武侯祠，请重新规划一下")

    assert result.destination is None
    assert result.days is None
    assert result.excluded_attractions == ["武侯祠"]


def test_extracts_city_prefixed_excluded_attraction_without_action_verb() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("不想成都大熊猫繁育研究基地")

    assert result.destination == "成都"
    assert result.days is None
    assert result.excluded_attractions == ["成都大熊猫繁育研究基地"]


def test_does_not_treat_attraction_after_separate_negative_clause_as_excluded() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("不想吃本地特色，西湖可以正常安排")

    assert result.excluded_attractions == []
    assert "avoid_local_food" in result.preferences


def test_extracts_new_city_from_dynamic_knowledge_catalog() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("帮我规划西安三日游，预算3500，想看博物馆和文化景点")

    assert result.destination == "西安"
    assert result.destination_explicit is True
    assert result.days == 3
    assert result.budget == 3500
    assert "culture" in result.preferences


def test_extracts_two_day_trip_and_citywalk_preferences() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("帮我规划一个南京两日游，预算3500，想看博物馆和文化景点，也想 citywalk")

    assert result.destination == "南京"
    assert result.days == 2
    assert result.budget == 3500
    assert "museum" in result.preferences
    assert "culture" in result.preferences
    assert "citywalk" in result.preferences


def test_extracts_shenzhen_from_expanded_dynamic_knowledge_catalog() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("帮我规划一个深圳四日游，预算6000，想看海边和 citywalk，酒店尽量安静一点")

    assert result.destination == "深圳"
    assert result.destination_explicit is True
    assert result.days == 4
    assert result.budget == 6000
    assert "nature" in result.preferences
    assert "citywalk" in result.preferences
    assert "quiet_hotel" in result.preferences


def test_extracts_arabic_digit_day_trip_with_ri_you_format() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("帮我规划一个杭州5日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色")

    assert result.destination == "杭州"
    assert result.days == 5
    assert result.budget == 3000
    assert result.pace == "relaxed"
    assert "local_food" in result.preferences
    assert "quiet_hotel" in result.preferences


def test_extracts_family_preferences() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("帮我规划一个三亚四日游，预算9000，节奏轻松一点，酒店尽量安静，适合亲子")

    assert result.destination == "三亚"
    assert result.destination_explicit is True
    assert result.days == 4
    assert result.budget == 9000
    assert result.pace == "relaxed"
    assert "family" in result.preferences
    assert "quiet_hotel" in result.preferences


def test_extracts_rainy_day_consulting_preferences() -> None:
    extractor = SlotExtractor()

    result = extractor.extract("上海下雨天适合带娃去哪玩")

    assert result.destination == "上海"
    assert result.destination_explicit is True
    assert result.days is None
    assert result.budget is None
    assert "rainy_day" in result.preferences
    assert "family" in result.preferences
