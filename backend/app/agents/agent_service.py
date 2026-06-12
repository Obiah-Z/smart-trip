from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentExecutionResult:
    name: str
    summary: str
    payload: dict[str, Any]


class AgentService:
    TOOL_NAME_MAP = {
        "route": "route.plan",
        "hotel": "hotel.search",
        "weather": "weather.lookup",
        "attraction": "attraction.search",
        "budget": "budget.optimize",
        "audit": "itinerary.audit",
    }
    ATTRACTION_TYPE_LABELS = {
        "nature": "自然风景",
        "culture": "人文体验",
        "museum": "博物馆",
        "citywalk": "城市漫步",
        "food": "餐饮小吃",
        "relaxed": "轻松休闲",
    }
    PACE_LABELS = {
        "relaxed": "轻松",
        "balanced": "均衡",
        "intensive": "紧凑",
    }

    def run(
        self,
        *,
        constraints: dict[str, Any],
        retrieval_context: dict[str, Any],
        tool_results: list[dict[str, Any]],
        memory_context: dict[str, Any],
        task_profile: dict[str, Any],
    ) -> list[AgentExecutionResult]:
        planner_result = self._planner_agent(
            constraints=constraints,
            memory_context=memory_context,
            task_profile=task_profile,
        )
        retriever_result = self._retriever_agent(retrieval_context=retrieval_context, tool_results=tool_results)
        executor_result = self._executor_agent(
            constraints=constraints,
            tool_results=tool_results,
            planner_payload=planner_result.payload,
            retrieval_context=retrieval_context,
        )
        reviewer_result = self._reviewer_agent(
            constraints=constraints,
            executor_payload=executor_result.payload,
            tool_results=tool_results,
        )
        return [planner_result, retriever_result, executor_result, reviewer_result]

    def _planner_agent(
        self,
        *,
        constraints: dict[str, Any],
        memory_context: dict[str, Any],
        task_profile: dict[str, Any],
    ) -> AgentExecutionResult:
        budget_label = f"{constraints['budget']} 元" if (constraints.get("budget") or 0) > 0 else "未指定"
        summary = f"已识别 {constraints['destination']} {constraints['days']} 天行程，预算 {budget_label}。"
        payload = {
            "task_breakdown": ["读取记忆", "检索知识", "调用工具", "生成行程", "做一致性检查"],
            "constraints": constraints,
            "memory_highlights": memory_context.get("relevant_long_term_memory", []),
            "task_profile": task_profile,
            "shared_state_projection": ["structured_constraints", "relevant_long_term_memory", "session_context"],
        }
        return AgentExecutionResult(name="planner_agent", summary=summary, payload=payload)

    def _retriever_agent(self, *, retrieval_context: dict[str, Any], tool_results: list[dict[str, Any]]) -> AgentExecutionResult:
        summary = f"召回 {len(retrieval_context['retrieved_documents'])} 条知识，并完成 {len(tool_results)} 个工具调用。"
        payload = {
            "knowledge": retrieval_context["injected_knowledge"],
            "tools": [item["tool_name"] for item in tool_results],
            "rerank_trace": [
                {
                    "id": item.get("id"),
                    "topic": item.get("topic"),
                    "score": item.get("score"),
                    "lexical_overlap": item.get("lexical_overlap"),
                    "preference_bonus": item.get("preference_bonus"),
                }
                for item in retrieval_context["retrieved_documents"]
            ],
        }
        return AgentExecutionResult(name="retriever_agent", summary=summary, payload=payload)

    def _executor_agent(
        self,
        *,
        constraints: dict[str, Any],
        tool_results: list[dict[str, Any]],
        planner_payload: dict[str, Any],
        retrieval_context: dict[str, Any],
    ) -> AgentExecutionResult:
        route_result = self._tool_result(tool_results, self.TOOL_NAME_MAP["route"])
        hotel_result = self._tool_result(tool_results, self.TOOL_NAME_MAP["hotel"])
        weather_result = self._tool_result(tool_results, self.TOOL_NAME_MAP["weather"])
        attraction_result = self._tool_result(tool_results, self.TOOL_NAME_MAP["attraction"])
        budget_result = self._tool_result(tool_results, self.TOOL_NAME_MAP["budget"])
        audit_result = self._tool_result(tool_results, self.TOOL_NAME_MAP["audit"])
        route_days = route_result["output"]["days"] if route_result is not None else []
        hotel_candidates = hotel_result["output"].get("hotels", []) if hotel_result is not None else []
        nightly_budget = hotel_result["output"].get("nightly_budget", 0) if hotel_result is not None else 0
        attractions = attraction_result["output"].get("attractions", []) if attraction_result is not None else []
        weather_payload = weather_result["output"] if weather_result is not None else None
        budget_optimization = budget_result["output"] if budget_result is not None else {}
        itinerary_audit = audit_result["output"] if audit_result is not None else {}

        hotel_options = hotel_candidates[:2]
        estimated_hotel_cost = 0
        if hotel_result is not None:
            stay_nights = max(1, constraints["days"] - 1)
            estimated_hotel_cost = (
                sum(hotel["pricePerNight"] for hotel in hotel_options[:1]) * stay_nights
            )

        estimated_ticket_cost = 0
        if attraction_result is not None:
            estimated_ticket_cost = sum(item.get("cost", 0) for item in attraction_result["output"].get("attractions", []))

        transport_cost = max(300, constraints["budget"] // 6) if tool_results else 0
        food_cost = max(200, constraints["days"] * 120) if tool_results else 0
        total_budget = transport_cost + food_cost + estimated_hotel_cost + estimated_ticket_cost
        budget_breakdown = {
            "transport": transport_cost,
            "accommodation": estimated_hotel_cost,
            "food": food_cost,
            "tickets": estimated_ticket_cost,
        }
        budget_plan = self._apply_budget_policy(
            constraints=constraints,
            hotel_candidates=hotel_candidates,
            hotel_options=hotel_options,
            budget_breakdown=budget_breakdown,
            total_budget=total_budget,
        )
        hotel_options = budget_plan["hotel_options"]
        budget_breakdown = budget_plan["budget_breakdown"]
        total_budget = budget_plan["total_budget"]
        estimated_hotel_cost = budget_breakdown["accommodation"]
        food_cost = budget_breakdown["food"]
        estimated_ticket_cost = budget_breakdown["tickets"]
        transport_cost = budget_breakdown["transport"]
        if budget_optimization:
            optimized_breakdown = budget_optimization.get("budget_breakdown")
            if isinstance(optimized_breakdown, dict) and optimized_breakdown:
                budget_breakdown = {
                    "transport": int(optimized_breakdown.get("transport", transport_cost) or 0),
                    "accommodation": int(optimized_breakdown.get("accommodation", estimated_hotel_cost) or 0),
                    "food": int(optimized_breakdown.get("food", food_cost) or 0),
                    "tickets": int(optimized_breakdown.get("tickets", estimated_ticket_cost) or 0),
                    **({"experience": int(optimized_breakdown.get("experience", 0) or 0)} if optimized_breakdown.get("experience") else {}),
                    **({"buffer": int(optimized_breakdown.get("buffer", 0) or 0)} if optimized_breakdown.get("buffer") else {}),
                }
                total_budget = int(budget_optimization.get("total_estimated") or sum(budget_breakdown.values()))
                estimated_hotel_cost = budget_breakdown["accommodation"]
                food_cost = budget_breakdown["food"]
                estimated_ticket_cost = budget_breakdown["tickets"]
                transport_cost = budget_breakdown["transport"]
            selected_hotel = budget_optimization.get("selected_hotel")
            if isinstance(selected_hotel, dict) and selected_hotel.get("name"):
                hotel_options = self._prioritize_selected_hotel(hotel_options=hotel_options, selected_hotel=selected_hotel)
        food_recommendations = self._build_food_recommendations(
            attractions=attractions,
            preferences=constraints["preferences"],
            retrieval_context=retrieval_context,
        )
        attraction_recommendations = self._build_attraction_recommendations(
            attractions=attractions,
            preferences=constraints["preferences"],
            pace=constraints["pace"],
        )
        daily_guide = self._build_daily_guide(
            route_days=route_days,
            attractions=attractions,
            food_recommendations=food_recommendations,
            pace=constraints["pace"],
        )
        stay_advice = self._build_stay_advice(
            hotel_options=hotel_options,
            nightly_budget=nightly_budget,
            preferences=constraints["preferences"],
            days=constraints["days"],
        )
        budget_insights = self._build_budget_insights(
            budget_limit=constraints.get("budget") or 0,
            total_budget=total_budget,
            budget_breakdown=budget_breakdown,
            primary_hotel=hotel_options[0] if hotel_options else None,
            days=constraints["days"],
            budget_policy=constraints.get("budget_policy"),
            target_budget=constraints.get("target_budget"),
        )
        budget_insights = [
            *self._build_budget_optimizer_insights(budget_optimization=budget_optimization),
            *budget_insights,
        ]
        trip_tips = self._build_trip_tips(
            constraints=constraints,
            weather=weather_payload,
            hotel_options=hotel_options,
            retrieval_context=retrieval_context,
            route_days=route_days,
            food_recommendations=food_recommendations,
        )
        plan_highlights = self._build_plan_highlights(
            destination=constraints["destination"],
            days=constraints["days"],
            route_days=route_days,
            hotel_options=hotel_options,
            weather=weather_payload,
            food_recommendations=food_recommendations,
        )
        planning_narrative = self._build_planning_narrative(
            destination=constraints["destination"],
            route_days=route_days,
            hotel_options=hotel_options,
            food_recommendations=food_recommendations,
            pace=constraints["pace"],
        )

        payload = {
            "summary": {
                "destinationCity": constraints["destination"],
                "days": constraints["days"],
                "totalBudget": total_budget,
                "currency": "CNY",
                "tags": constraints["preferences"],
            },
            "budget": {
                "transport": transport_cost,
                "accommodation": estimated_hotel_cost,
                "food": food_cost,
                "tickets": estimated_ticket_cost,
                **({"experience": budget_breakdown["experience"]} if budget_breakdown.get("experience") else {}),
                **({"buffer": budget_breakdown["buffer"]} if budget_breakdown.get("buffer") else {}),
            },
            "days": route_days,
            "weather": [weather_payload] if weather_payload is not None else [],
            "hotelRecommendation": hotel_options[:1],
            "hotelOptions": hotel_options,
            "attractionRecommendations": attraction_recommendations,
            "foodRecommendations": food_recommendations,
            "dailyGuide": daily_guide,
            "stayAdvice": stay_advice,
            "budgetInsights": budget_insights,
            "budgetOptimization": budget_optimization,
            "itineraryAudit": itinerary_audit,
            "tripTips": trip_tips,
            "planHighlights": plan_highlights,
            "planningNarrative": planning_narrative,
            "evidence_trace": [
                {"source": item["tool_name"], "provider": item.get("provider"), "sandbox_mode": item.get("sandbox", {}).get("mode")}
                for item in tool_results
            ],
        }
        summary = "已根据工具结果生成按天行程草案和预算拆分。"
        return AgentExecutionResult(name="executor_agent", summary=summary, payload=payload)

    def _reviewer_agent(
        self,
        *,
        constraints: dict[str, Any],
        executor_payload: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> AgentExecutionResult:
        budget_limit = constraints.get("budget") or 0
        within_budget = True if budget_limit <= 0 else executor_payload["summary"]["totalBudget"] <= budget_limit + 600
        pace_aligned = constraints["pace"] != "intensive" or constraints["days"] >= 2
        weather_result = self._tool_result(tool_results, self.TOOL_NAME_MAP["weather"])
        weather_summary = weather_result["output"]["summary"] if weather_result is not None else "未查询天气"
        audit_result = self._tool_result(tool_results, self.TOOL_NAME_MAP["audit"])
        if audit_result is not None:
            audit_payload = audit_result["output"]
            final_status = "approved" if audit_payload.get("safe_to_present") else "needs_review"
            return AgentExecutionResult(
                name="reviewer_agent",
                summary=str(audit_payload.get("summary") or "已完成行程一致性审计。"),
                payload={
                    "within_budget": not any(
                        item.get("name") == "budget_within_limit"
                        for item in audit_payload.get("issues", [])
                    ),
                    "pace_aligned": not any(
                        item.get("name") == "pace_density_aligned"
                        for item in [*audit_payload.get("issues", []), *audit_payload.get("warnings", [])]
                    ),
                    "weather_summary": weather_summary,
                    "final_status": final_status,
                    "audit_status": audit_payload.get("audit_status"),
                    "validation_checks": audit_payload.get("passed_checks", []),
                    "issues": audit_payload.get("issues", []),
                    "warnings": audit_payload.get("warnings", []),
                    "recommendations": audit_payload.get("recommendations", []),
                },
            )
        summary = "方案已通过预算与节奏校验。" if within_budget and pace_aligned else "方案需要进一步人工调整。"
        payload = {
            "within_budget": within_budget,
            "pace_aligned": pace_aligned,
            "weather_summary": weather_summary,
            "final_status": "approved" if within_budget and pace_aligned else "needs_review",
            "validation_checks": [
                {"name": "budget_guardrail", "passed": within_budget},
                {"name": "pace_alignment", "passed": pace_aligned},
                {"name": "weather_context_available", "passed": weather_result is not None},
            ],
        }
        return AgentExecutionResult(name="reviewer_agent", summary=summary, payload=payload)

    def _tool_result(self, tool_results: list[dict[str, Any]], tool_name: str) -> dict[str, Any] | None:
        return next((item for item in tool_results if item["tool_name"] == tool_name), None)

    def _prioritize_selected_hotel(
        self,
        *,
        hotel_options: list[dict[str, Any]],
        selected_hotel: dict[str, Any],
    ) -> list[dict[str, Any]]:
        selected_name = selected_hotel.get("name")
        if not selected_name:
            return hotel_options
        merged_selected = dict(selected_hotel)
        rest = [item for item in hotel_options if item.get("name") != selected_name]
        existing = next((item for item in hotel_options if item.get("name") == selected_name), None)
        if existing is not None:
            merged_selected = {**existing, **selected_hotel}
        return [merged_selected, *rest][:2]

    def _build_budget_optimizer_insights(self, *, budget_optimization: dict[str, Any]) -> list[dict[str, Any]]:
        if not budget_optimization:
            return []
        insights: list[dict[str, Any]] = []
        status = budget_optimization.get("budget_status")
        if status:
            insights.append(
                {
                    "label": "预算优化",
                    "value": str(status),
                    "detail": "已通过预算优化 Skill 对交通、住宿、餐饮、门票和体验预算做了拆分。",
                }
            )
        for recommendation in budget_optimization.get("recommendations", [])[:2]:
            insights.append(
                {
                    "label": "优化建议",
                    "value": "建议",
                    "detail": str(recommendation),
                }
            )
        return insights

    def _apply_budget_policy(
        self,
        *,
        constraints: dict[str, Any],
        hotel_candidates: list[dict[str, Any]],
        hotel_options: list[dict[str, Any]],
        budget_breakdown: dict[str, int],
        total_budget: int,
    ) -> dict[str, Any]:
        target_budget = constraints.get("target_budget") or constraints.get("budget") or 0
        budget_policy = constraints.get("budget_policy")
        if budget_policy != "target_near" or target_budget <= 0 or total_budget >= target_budget:
            return {
                "hotel_options": hotel_options,
                "budget_breakdown": {**budget_breakdown, "experience": 0},
                "total_budget": total_budget,
            }

        stay_nights = max(1, constraints["days"] - 1)
        selected_hotels = hotel_options
        upgraded_hotel_cost = budget_breakdown["accommodation"]
        fixed_without_hotel = total_budget - budget_breakdown["accommodation"]
        hotel_budget_cap = max(0, target_budget - fixed_without_hotel)

        affordable_hotels = [
            item
            for item in hotel_candidates
            if int(item.get("pricePerNight", 0) or 0) * stay_nights <= hotel_budget_cap
        ]
        if affordable_hotels:
            preferred_hotel = max(
                affordable_hotels,
                key=lambda item: (
                    int(item.get("pricePerNight", 0) or 0),
                    float(item.get("comfortScore", 0) or 0),
                    float(item.get("rating", 0) or 0),
                ),
            )
            backups = [item for item in hotel_candidates if item.get("name") != preferred_hotel.get("name")]
            selected_hotels = [preferred_hotel, *backups][:2]
            upgraded_hotel_cost = int(preferred_hotel.get("pricePerNight", 0) or 0) * stay_nights

        adjusted_breakdown = {
            **budget_breakdown,
            "accommodation": upgraded_hotel_cost,
            "experience": 0,
        }
        adjusted_total = (
            adjusted_breakdown["transport"]
            + adjusted_breakdown["accommodation"]
            + adjusted_breakdown["food"]
            + adjusted_breakdown["tickets"]
        )
        remaining = max(0, target_budget - adjusted_total)
        if remaining > 0:
            food_boost = min(remaining, max(120, constraints["days"] * 80))
            adjusted_breakdown["food"] += food_boost
            remaining -= food_boost
        if remaining > 0:
            adjusted_breakdown["experience"] = remaining

        adjusted_total = sum(adjusted_breakdown.values())
        return {
            "hotel_options": selected_hotels,
            "budget_breakdown": adjusted_breakdown,
            "total_budget": adjusted_total,
        }

    def _build_food_recommendations(
        self,
        *,
        attractions: list[dict[str, Any]],
        preferences: list[str],
        retrieval_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if "avoid_local_food" in preferences or "avoid_food" in preferences:
            return []

        seen: set[str] = set()
        items: list[dict[str, Any]] = []
        for attraction in attractions:
            name = attraction.get("name")
            tags = set(attraction.get("tags", []))
            if not name or name in seen:
                continue
            if attraction.get("type") != "food" and not tags.intersection({"food", "local_food", "snack", "night_market"}):
                continue

            style_parts: list[str] = []
            if "local_food" in tags:
                style_parts.append("本地风味")
            if "night_market" in tags or "night_walk" in tags:
                style_parts.append("适合晚餐或夜逛")
            if "snack" in tags:
                style_parts.append("小吃补给")

            items.append(
                {
                    "name": name,
                    "area": attraction.get("area", "核心城区"),
                    "style": " / ".join(style_parts) or "顺路用餐点",
                    "estimatedCost": attraction.get("cost", 0),
                    "reason": f"更适合安排在 {attraction.get('area', '当天路线附近')} 这一段，方便边走边吃。",
                }
            )
            seen.add(name)

        knowledge_tip = self._topic_hint(retrieval_context=retrieval_context, topic="food")
        if items and knowledge_tip:
            items[0]["knowledgeTip"] = knowledge_tip
        return items[:3]

    def _build_attraction_recommendations(
        self,
        *,
        attractions: list[dict[str, Any]],
        preferences: list[str],
        pace: str,
    ) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        for attraction in attractions[:6]:
            tags = set(attraction.get("tags", []))
            attraction_type = str(attraction.get("type", "citywalk"))
            reasons: list[str] = []
            if attraction_type in preferences:
                reasons.append(f"契合你想看的{self.ATTRACTION_TYPE_LABELS.get(attraction_type, attraction_type)}")
            if attraction_type == "food" and "local_food" in preferences:
                reasons.append("能补上本地特色这一条需求")
            if "classic" in tags:
                reasons.append("属于这座城市的经典点位")
            if pace == "relaxed" and float(attraction.get("durationHours", 0) or 0) <= 2.5:
                reasons.append("停留时间比较好控制")
            if pace == "intensive" and float(attraction.get("durationHours", 0) or 0) >= 2:
                reasons.append("适合放进更紧凑的行程里")
            if "family" in tags:
                reasons.append("亲子接受度较高")

            recommendations.append(
                {
                    "name": attraction.get("name"),
                    "area": attraction.get("area", "核心城区"),
                    "type": attraction_type,
                    "typeLabel": self.ATTRACTION_TYPE_LABELS.get(attraction_type, attraction_type),
                    "cost": attraction.get("cost", 0),
                    "durationHours": attraction.get("durationHours", 0),
                    "tags": attraction.get("tags", []),
                    "reason": "，".join(reasons) or "适合作为这次行程的代表性点位。",
                }
            )
        return recommendations

    def _build_daily_guide(
        self,
        *,
        route_days: list[dict[str, Any]],
        attractions: list[dict[str, Any]],
        food_recommendations: list[dict[str, Any]],
        pace: str,
    ) -> list[dict[str, Any]]:
        attraction_lookup = {
            str(item.get("name")): item
            for item in attractions
            if item.get("name")
        }
        guides: list[dict[str, Any]] = []
        total_days = len(route_days)

        for day in route_days:
            matched_items = [attraction_lookup.get(name, {"name": name}) for name in day.get("activities", [])]
            highlights = [item.get("name") for item in matched_items if item.get("type") != "food"][:3]
            if not highlights:
                highlights = [item.get("name") for item in matched_items if item.get("name")][:3]
            estimated_duration = round(
                sum(float(item.get("durationHours", 0) or 0) for item in matched_items),
                1,
            )
            estimated_tickets = sum(int(item.get("cost", 0) or 0) for item in matched_items)
            meal_stop = next((item for item in matched_items if self._is_food_item(item)), None)
            if meal_stop is None:
                meal_stop = next(
                    (item for item in food_recommendations if item.get("area") == day.get("area")),
                    None,
                )

            guides.append(
                {
                    "day": day.get("day"),
                    "theme": day.get("theme"),
                    "area": day.get("area"),
                    "activities": day.get("activities", []),
                    "highlights": [item for item in highlights if item],
                    "estimatedDurationHours": estimated_duration,
                    "estimatedTickets": estimated_tickets,
                    "paceLabel": self.PACE_LABELS.get(pace, pace),
                    "mealHint": self._build_meal_hint(meal_stop=meal_stop, area=day.get("area")),
                    "note": self._build_day_note(
                        day_number=int(day.get("day", 1) or 1),
                        total_days=total_days,
                        pace=pace,
                        activity_count=len(day.get("activities", [])),
                    ),
                }
            )
        return guides

    def _build_stay_advice(
        self,
        *,
        hotel_options: list[dict[str, Any]],
        nightly_budget: int,
        preferences: list[str],
        days: int,
    ) -> dict[str, Any]:
        if not hotel_options:
            return {}

        primary = hotel_options[0]
        backup = hotel_options[1] if len(hotel_options) > 1 else None
        reasons: list[str] = []
        if "quiet_hotel" in preferences and primary.get("quiet"):
            reasons.append("优先照顾了你想住得更安静的要求")
        if "lively_hotel" in preferences and not primary.get("quiet"):
            reasons.append("会更贴近热闹商圈和夜间活动")
        if "comfortable_hotel" in preferences and "comfortable_hotel" in primary.get("tags", []):
            reasons.append("住宿舒适度和房间品质会更高")
        reasons.append(f"落脚在 {primary.get('area', '核心区')}，更方便接当天主要路线")

        return {
            "recommendedArea": primary.get("area"),
            "nightlyBudget": nightly_budget,
            "stayNights": max(1, days - 1),
            "recommendedHotel": primary.get("name"),
            "backupHotel": backup.get("name") if backup else None,
            "reason": "，".join(reasons) + "。",
        }

    def _build_budget_insights(
        self,
        *,
        budget_limit: int,
        total_budget: int,
        budget_breakdown: dict[str, int],
        primary_hotel: dict[str, Any] | None,
        days: int,
        budget_policy: str | None = None,
        target_budget: int | None = None,
    ) -> list[dict[str, Any]]:
        insights: list[dict[str, Any]] = []
        if budget_policy == "target_near" and (target_budget or budget_limit) > 0:
            target = target_budget or budget_limit
            delta = abs(target - total_budget)
            insights.append(
                {
                    "label": "贴近预算",
                    "value": f"目标 ¥{target}",
                    "detail": (
                        f"已按“尽可能贴近预算”重新分配，当前估算约 ¥{total_budget}，"
                        f"与目标相差约 ¥{delta}；优先把余量用于住宿、餐饮和体验升级。"
                    ),
                }
            )

        if budget_limit > 0:
            delta = budget_limit - total_budget
            if delta >= 0:
                detail = f"当前估算约 ¥{total_budget}，距离你的预算上限还剩 ¥{delta} 的机动空间。"
            else:
                detail = f"当前估算约 ¥{total_budget}，比预算上限高出 ¥{abs(delta)}，后续可继续压缩住宿或门票安排。"
            insights.append(
                {
                    "label": "预算状态",
                    "value": f"约 ¥{total_budget}",
                    "detail": detail,
                }
            )
        else:
            insights.append(
                {
                    "label": "预算状态",
                    "value": f"约 ¥{total_budget}",
                    "detail": "你这轮没有给出总预算，所以系统按较常规的交通、住宿和餐饮水平做了估算。",
                }
            )

        if primary_hotel is not None:
            insights.append(
                {
                    "label": "住宿占比",
                    "value": f"约 ¥{budget_breakdown.get('accommodation', 0)}",
                    "detail": (
                        f"按 {max(1, days - 1)} 晚计算，当前首选酒店约 ¥{primary_hotel.get('pricePerNight', 0)}/晚，"
                        f"住宿会是这次预算里的最大块。"
                    ),
                }
            )

        insights.append(
            {
                "label": "餐饮与门票",
                "value": f"¥{budget_breakdown.get('food', 0)} + ¥{budget_breakdown.get('tickets', 0)}",
                "detail": "餐饮和门票是最容易继续加减的部分；如果你想升级体验，通常先从这两块微调更自然。",
            }
        )
        if budget_breakdown.get("experience", 0) > 0:
            insights.append(
                {
                    "label": "体验预留",
                    "value": f"约 ¥{budget_breakdown.get('experience', 0)}",
                    "detail": "这部分用于更好的座位、茶馆/夜游/讲解等弹性体验，不强行塞进门票或酒店价格里。",
                }
            )
        return insights

    def _build_trip_tips(
        self,
        *,
        constraints: dict[str, Any],
        weather: dict[str, Any] | None,
        hotel_options: list[dict[str, Any]],
        retrieval_context: dict[str, Any],
        route_days: list[dict[str, Any]],
        food_recommendations: list[dict[str, Any]],
    ) -> list[str]:
        tips: list[str] = []
        if weather and weather.get("advice"):
            tips.append(str(weather["advice"]))

        if hotel_options:
            primary = hotel_options[0]
            tips.append(
                f"住宿建议优先锁定在 {primary.get('area', '核心区')} 一带，首选 {primary.get('name', '当前推荐酒店')}，"
                f"这样更容易兼顾舒适度和每天的往返效率。"
            )

        if constraints.get("pace") == "relaxed":
            tips.append("这次节奏偏轻松，更适合每天只抓 1 到 2 个核心点，中间预留喝咖啡或回酒店休息的时间。")
        elif constraints.get("pace") == "intensive":
            tips.append("这次节奏会更紧凑，尽量早点出门，把同一区域的点位放在同一天，减少跨区折返。")
        else:
            tips.append("这次节奏偏均衡，上午和下午各安排一个主点位，整体更容易兼顾体验和体力。")

        route_hint = self._topic_hint(retrieval_context=retrieval_context, topic="trip_route")
        if route_hint:
            tips.append(f"路线参考：{route_hint}")

        if food_recommendations:
            tips.append(f"如果想把吃这件事安排得更顺一点，可以重点围绕 {food_recommendations[0].get('name')} 这一站展开。")

        deduped: list[str] = []
        seen: set[str] = set()
        for tip in tips:
            normalized = tip.strip()
            if not normalized or normalized in seen:
                continue
            deduped.append(normalized)
            seen.add(normalized)
        return deduped[:5]

    def _build_plan_highlights(
        self,
        *,
        destination: str,
        days: int,
        route_days: list[dict[str, Any]],
        hotel_options: list[dict[str, Any]],
        weather: dict[str, Any] | None,
        food_recommendations: list[dict[str, Any]],
    ) -> list[str]:
        highlights: list[str] = [
            f"{destination} 这次按 {days} 天拆开安排，不会把主要内容全塞到同一天。",
        ]
        if route_days:
            areas = [day.get("area") for day in route_days if day.get("area")]
            unique_areas = []
            for area in areas:
                if area not in unique_areas:
                    unique_areas.append(area)
            if unique_areas:
                highlights.append(f"路线会优先围绕 {' / '.join(unique_areas[:3])} 这些区域展开。")
        if hotel_options:
            highlights.append(f"住宿首选 {hotel_options[0].get('name')}，落脚在 {hotel_options[0].get('area', '核心区')}。")
        if food_recommendations:
            highlights.append(f"餐饮可以重点放在 {food_recommendations[0].get('name')} 这一站附近。")
        if weather and weather.get("summary"):
            highlights.append(f"当前天气参考为 {weather['summary']}。")
        return highlights[:4]

    def _build_planning_narrative(
        self,
        *,
        destination: str,
        route_days: list[dict[str, Any]],
        hotel_options: list[dict[str, Any]],
        food_recommendations: list[dict[str, Any]],
        pace: str,
    ) -> str:
        area_names: list[str] = []
        for day in route_days:
            area = day.get("area")
            if area and area not in area_names:
                area_names.append(area)

        parts = [f"{destination} 这次会按{self.PACE_LABELS.get(pace, pace)}节奏来走"]
        if area_names:
            parts.append(f"主要围绕 {' / '.join(area_names[:3])} 这些区域展开")
        if hotel_options:
            parts.append(f"住宿优先放在 {hotel_options[0].get('area', '核心区')} 的 {hotel_options[0].get('name')}")
        if food_recommendations:
            parts.append(f"餐饮可以顺路安排到 {food_recommendations[0].get('name')}")
        return "，".join(parts) + "。"

    def _build_meal_hint(self, *, meal_stop: dict[str, Any] | None, area: str | None) -> str:
        if meal_stop is None:
            return f"当天更适合在 {area or '主要活动区'} 附近就近吃饭，避免为了用餐单独折返。"
        return f"用餐可放在 {meal_stop.get('name')}，和 {meal_stop.get('area', area or '当天路线')} 这一段顺路。"

    def _build_day_note(self, *, day_number: int, total_days: int, pace: str, activity_count: int) -> str:
        if day_number == 1:
            return "第一天更适合先入住、熟悉周边，再从附近开始，不用把强度拉太满。"
        if day_number == total_days:
            return "最后一天建议预留一点机动时间，方便返程前补漏或临时调整。"
        if pace == "relaxed":
            return f"这一天建议控制在 {activity_count} 个左右的小段安排，中间保留休息和随走随停的空间。"
        if pace == "intensive":
            return "这一天点位会更密一些，尽量早点出发，把同一区域内容连着走完。"
        return "这一天适合上午一个主点、下午一个主点，整体不会太赶，也不至于太散。"

    def _topic_hint(self, *, retrieval_context: dict[str, Any], topic: str) -> str | None:
        documents = retrieval_context.get("retrieved_documents", [])
        match = next((item for item in documents if item.get("topic") == topic and item.get("content")), None)
        if match is None:
            return None
        return self._clean_hint_text(str(match.get("content", "")))

    def _clean_hint_text(self, text: str) -> str:
        snippet = text.replace("\n", " ").replace("- ", "").strip()
        if "。" in snippet:
            snippet = snippet.split("。", 1)[0]
        if len(snippet) > 70:
            snippet = snippet[:70].rstrip() + "..."
        return snippet

    def _is_food_item(self, item: dict[str, Any]) -> bool:
        tags = set(item.get("tags", []))
        return item.get("type") == "food" or bool(tags.intersection({"food", "local_food", "snack", "night_market"}))
