from app.workflow.reviewer import PlanReviewer


def test_workflow_review_repairs_excluded_attraction_from_final_plan() -> None:
    reviewer = PlanReviewer()
    constraints = {
        "destination": "杭州",
        "days": 3,
        "budget": 3000,
        "pace": "relaxed",
        "preferences": ["quiet_hotel"],
        "excluded_attractions": ["西湖"],
        "expanded_excluded_attractions": ["西湖", "断桥"],
    }
    final_plan = {
        "summary": {"destinationCity": "杭州", "days": 3, "totalBudget": 2500},
        "budget": {"transport": 500, "accommodation": 1200, "food": 500, "tickets": 300},
        "days": [
            {"day": 1, "activities": ["西湖", "河坊街"]},
            {"day": 2, "activities": ["西溪湿地"]},
            {"day": 3, "activities": ["断桥", "良渚博物院"]},
        ],
        "dailyGuide": [{"day": 1, "activities": ["西湖", "河坊街"]}],
        "attractionRecommendations": [{"name": "西湖"}, {"name": "西溪湿地"}],
        "hotelOptions": [{"name": "武林静居酒店", "quiet": True}],
        "planHighlights": ["西湖经典慢游", "西溪湿地轻松路线"],
        "tripTips": ["避开晚高峰"],
    }

    review = reviewer.build_review(
        final_plan=final_plan,
        structured_constraints=constraints,
    )
    repaired = reviewer.apply_repairs(
        final_plan=final_plan,
        structured_constraints=constraints,
        review=review,
    )
    repaired_review = reviewer.build_review(
        final_plan=repaired,
        structured_constraints=constraints,
    )

    assert review["needs_repair"] is True
    assert "excluded_attractions_present" in [item["name"] for item in review["issues"]]
    assert repaired_review["needs_repair"] is False
    all_activities = [activity for day in repaired["days"] for activity in day["activities"]]
    assert "西湖" not in all_activities
    assert "断桥" not in all_activities
    assert repaired["itineraryAudit"]["workflow_exclusion_repair"]["removed_terms"] == ["西湖", "断桥"]


def test_workflow_review_repairs_missing_hotel_for_multi_day_plan() -> None:
    reviewer = PlanReviewer()
    constraints = {
        "destination": "成都",
        "days": 3,
        "budget": 3000,
        "pace": "balanced",
        "preferences": ["quiet_hotel"],
        "excluded_attractions": [],
        "expanded_excluded_attractions": [],
    }
    final_plan = {
        "summary": {"destinationCity": "成都", "days": 3, "totalBudget": 2200},
        "budget": {"transport": 600, "accommodation": 0, "food": 800, "tickets": 800},
        "days": [
            {"day": 1, "activities": ["宽窄巷子"]},
            {"day": 2, "activities": ["杜甫草堂"]},
            {"day": 3, "activities": ["东郊记忆"]},
        ],
        "hotelOptions": [],
        "hotelRecommendation": [],
    }

    review = reviewer.build_review(
        final_plan=final_plan,
        structured_constraints=constraints,
    )
    repaired = reviewer.apply_repairs(
        final_plan=final_plan,
        structured_constraints=constraints,
        review=review,
    )
    repaired_review = reviewer.build_review(
        final_plan=repaired,
        structured_constraints=constraints,
    )

    assert "hotel_missing" in [item["name"] for item in review["issues"]]
    assert repaired["hotelRecommendation"]
    assert repaired["hotelRecommendation"][0]["name"] == "成都舒适住宿待确认"
    assert repaired_review["needs_repair"] is False


def test_workflow_review_repairs_budget_over_limit() -> None:
    reviewer = PlanReviewer()
    constraints = {
        "destination": "北京",
        "days": 3,
        "budget": 3000,
        "pace": "balanced",
        "preferences": [],
        "excluded_attractions": [],
        "expanded_excluded_attractions": [],
    }
    final_plan = {
        "summary": {"destinationCity": "北京", "days": 3, "totalBudget": 5200},
        "budget": {"transport": 1200, "accommodation": 2500, "food": 900, "tickets": 600},
        "days": [
            {"day": 1, "activities": ["天坛"]},
            {"day": 2, "activities": ["颐和园"]},
            {"day": 3, "activities": ["前门"]},
        ],
        "hotelOptions": [{"name": "北京中轴舒适酒店"}],
    }

    review = reviewer.build_review(
        final_plan=final_plan,
        structured_constraints=constraints,
    )
    repaired = reviewer.apply_repairs(
        final_plan=final_plan,
        structured_constraints=constraints,
        review=review,
    )
    repaired_review = reviewer.build_review(
        final_plan=repaired,
        structured_constraints=constraints,
    )

    assert "budget_over_limit" in [item["name"] for item in review["issues"]]
    assert repaired["summary"]["totalBudget"] <= 3000
    assert repaired_review["needs_repair"] is False
