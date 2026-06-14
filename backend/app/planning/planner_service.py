from __future__ import annotations

import re
from typing import Any

from app.agents.agent_service import AgentService
from app.context.context_assembler import ContextAssembler
from app.context.session_context_service import SessionContextService
from app.db.repositories import SessionRunRepository
from app.llm.openai_client import OpenAIPlannerClient
from app.memory.memory_extractor import MemoryExtractor
from app.memory.memory_injection_service import MemoryInjectionService
from app.memory.memory_service import MemoryService
from app.planning.revision_intent import RevisionIntent, RevisionIntentResolver
from app.planning.slot_extractor import SlotExtractor
from app.planning.task_router import TaskRouter
from app.presentation.geo_service import GeoPresentationService
from app.retrieval.retrieval_service import RetrievalService
from app.skills.skill_selection_service import SkillSelectionService
from app.skills.tool_service import ToolService
from app.workflow.graph import TripPlanningWorkflow


class PlannerService:
    """旅行规划应用层门面。

    LangGraph 负责控制节点顺序，PlannerService 负责聚合各类业务依赖，并提供节点会调用的
    约束合并、会话恢复、澄清响应、轻咨询响应等方法。这样做可以让图拓扑保持清晰，同时
    避免每个 node 直接了解所有底层服务。
    """

    REPLAN_UPDATE_KEYWORDS = (
        "提升",
        "提高",
        "增加",
        "改成",
        "改为",
        "调整",
        "升级",
        "更舒服",
        "更舒适",
        "舒适度",
    )
    DESTINATION_UPDATE_KEYWORDS = ("目的地", "城市", "换到", "换成", "换为", "改到", "改成", "改为", "调整到", "调整成", "改去", "换去")
    EXCLUSION_UPDATE_KEYWORDS = ("不想去", "不要去", "不去", "别去", "避开", "去掉", "删掉", "移除")
    PREFERENCE_UPDATE_KEYWORDS = (
        "想吃",
        "想住",
        "想看",
        "想逛",
        "多看",
        "少看",
        "多安排",
        "少安排",
        "优先",
        "主要",
        "换成",
        "换个",
        "改住",
        "改吃",
        "改看",
        "想要",
        "尽量",
    )
    CLARIFICATION_SUGGESTIONS = {
        "destination": ["深圳", "北京", "上海", "成都"],
        "days": ["2天", "3天", "4天", "5天"],
    }

    def __init__(
        self,
        *,
        slot_extractor: SlotExtractor,
        memory_service: MemoryService,
        retrieval_service: RetrievalService,
        tool_service: ToolService,
        agent_service: AgentService,
        context_assembler: ContextAssembler,
        session_run_repository: SessionRunRepository,
        openai_client: OpenAIPlannerClient,
        skill_selection_service: SkillSelectionService,
        task_router: TaskRouter,
        session_context_service: SessionContextService,
        memory_injection_service: MemoryInjectionService,
        memory_extractor: MemoryExtractor,
        geo_presentation_service: GeoPresentationService,
        image_generation_service,
        graph_expansion_service=None,
    ) -> None:
        self._slot_extractor = slot_extractor
        self._memory_service = memory_service
        self._retrieval_service = retrieval_service
        self._tool_service = tool_service
        self._agent_service = agent_service
        self._context_assembler = context_assembler
        self._session_run_repository = session_run_repository
        self._openai_client = openai_client
        self._skill_selection_service = skill_selection_service
        self._task_router = task_router
        self._session_context_service = session_context_service
        self._memory_injection_service = memory_injection_service
        self._memory_extractor = memory_extractor
        self._geo_presentation_service = geo_presentation_service
        self._image_generation_service = image_generation_service
        self._graph_expansion_service = graph_expansion_service
        self._revision_intent_resolver = RevisionIntentResolver()
        self._workflow = TripPlanningWorkflow(self)

    def run(self, *, user_id: str, session_id: str | None, message: str) -> dict[str, Any]:
        """对外唯一执行入口；实际控制流交给 LangGraph workflow。"""
        return self._workflow.run(user_id=user_id, session_id=session_id, message=message)

    def _resolve_structured_constraints(
        self,
        *,
        slots,
        session_context: dict[str, Any],
        message: str,
        revision_intent: RevisionIntent,
    ) -> dict[str, Any]:
        """把本轮槽位、会话基线和追问修订合并成有效旅行约束。

        这里是多轮体验的核心：首次规划直接使用当前输入；澄清恢复会把用户补充的“3天”
        或“成都”接回原始请求；追问修改则继承上一轮目的地/天数并只覆盖预算、偏好、
        排除景点等被用户明确改变的字段。
        """
        latest_constraints = session_context.get("latest_structured_constraints") or {}
        baseline_constraints = self._resolve_session_baseline_constraints(session_context=session_context)
        is_followup_update = self._is_followup_update(
            message=message,
            slots=slots,
            session_context=session_context,
            revision_intent=revision_intent,
        )
        is_clarification_recovery = self._is_clarification_recovery(
            slots=slots,
            session_context=session_context,
        )
        resolved_destination = self._resolve_destination(
            slots=slots,
            latest_constraints=latest_constraints,
            baseline_constraints=baseline_constraints,
        )

        if is_clarification_recovery:
            base_preferences = list(latest_constraints.get("preferences") or baseline_constraints.get("preferences") or [])
            merged_preferences = self._merge_preferences(base_preferences=base_preferences, new_preferences=slots.preferences)
            resolved_budget = slots.budget if slots.budget is not None else latest_constraints.get("budget") or baseline_constraints.get("budget", 0)
            budget_policy = slots.budget_policy or latest_constraints.get("budget_policy")
            return {
                "destination": resolved_destination,
                "days": slots.days if slots.days is not None else latest_constraints.get("days") or baseline_constraints.get("days"),
                "budget": resolved_budget,
                "pace": slots.pace if slots.pace_explicit else latest_constraints.get("pace") or baseline_constraints.get("pace", "balanced"),
                "preferences": merged_preferences,
                "excluded_attractions": list(dict.fromkeys(slots.excluded_attractions)),
                "budget_policy": budget_policy,
                "target_budget": slots.target_budget if slots.target_budget is not None else latest_constraints.get("target_budget") or resolved_budget,
                "revision_intent": revision_intent.to_dict(),
                "_followup_replan": False,
            }

        if is_followup_update:
            base_preferences = list(latest_constraints.get("preferences") or baseline_constraints.get("preferences") or [])
            merged_preferences = self._merge_preferences(base_preferences=base_preferences, new_preferences=slots.preferences)
            is_destination_update = self._is_destination_update(slots=slots, latest_constraints=latest_constraints)
            base_excluded_attractions = [] if is_destination_update else (
                latest_constraints.get("excluded_attractions") or baseline_constraints.get("excluded_attractions") or []
            )
            merged_excluded_attractions = self._merge_excluded_attractions(
                base_attractions=base_excluded_attractions,
                new_attractions=slots.excluded_attractions,
            )
            resolved_budget = self._resolve_followup_budget(
                slots=slots,
                latest_constraints=latest_constraints,
                baseline_constraints=baseline_constraints,
                revision_intent=revision_intent,
            )
            budget_policy = revision_intent.budget_policy or slots.budget_policy or latest_constraints.get("budget_policy")
            target_budget = revision_intent.target_budget or slots.target_budget or latest_constraints.get("target_budget") or resolved_budget
            return {
                "destination": resolved_destination,
                "days": slots.days if slots.days is not None else self._resolve_followup_days(
                    latest_constraints=latest_constraints,
                    baseline_constraints=baseline_constraints,
                    message=message,
                ),
                "budget": resolved_budget,
                "pace": slots.pace if slots.pace_explicit else latest_constraints.get("pace") or baseline_constraints.get("pace", "balanced"),
                "preferences": merged_preferences,
                "excluded_attractions": merged_excluded_attractions,
                "budget_policy": budget_policy,
                "target_budget": target_budget,
                "revision_intent": revision_intent.to_dict(),
                "_followup_replan": True,
            }

        resolved_budget = slots.budget if slots.budget is not None else 0
        return {
            "destination": resolved_destination,
            "days": slots.days,
            "budget": resolved_budget,
            "pace": slots.pace,
            "preferences": slots.preferences,
            "excluded_attractions": list(dict.fromkeys(slots.excluded_attractions)),
            "budget_policy": slots.budget_policy,
            "target_budget": slots.target_budget,
            "revision_intent": revision_intent.to_dict(),
            "_followup_replan": False,
        }

    def _resolve_destination(
        self,
        *,
        slots,
        latest_constraints: dict[str, Any],
        baseline_constraints: dict[str, Any],
    ) -> str | None:
        """目的地优先使用当前明确表达，否则从最近规划或会话基线继承。"""
        if getattr(slots, "destination_explicit", False):
            return slots.destination

        inherited_destination = latest_constraints.get("destination") or baseline_constraints.get("destination")
        return inherited_destination or slots.destination

    def _expand_structured_constraints(self, *, structured_constraints: dict[str, Any]) -> dict[str, Any]:
        """用景点知识图谱扩展排除列表，例如把“故宫”扩展到相关别名/同组点位。"""
        raw_excluded = list(dict.fromkeys(structured_constraints.get("excluded_attractions") or []))
        if self._graph_expansion_service is None:
            return {
                **structured_constraints,
                "excluded_attractions": raw_excluded,
                "expanded_excluded_attractions": raw_excluded,
            }

        expanded = self._graph_expansion_service.expand_excluded_attractions(attractions=raw_excluded)
        return {
            **structured_constraints,
            "excluded_attractions": raw_excluded,
            "expanded_excluded_attractions": expanded,
        }

    def _is_clarification_recovery(
        self,
        *,
        slots,
        session_context: dict[str, Any],
    ) -> bool:
        """判断当前输入是否是在回答上一轮澄清问题。"""
        if not session_context.get("session_found"):
            return False
        missing_fields = self._latest_missing_fields(session_context=session_context)
        if not missing_fields:
            return False
        if "destination" in missing_fields and getattr(slots, "destination_explicit", False):
            return True
        if "days" in missing_fields and slots.days is not None:
            return True
        return False

    def _resolve_effective_message(
        self,
        *,
        message: str,
        slots,
        session_context: dict[str, Any],
    ) -> str:
        """为澄清恢复构造更完整的任务文本。

        用户只回复“3天”时，直接拿这句话做任务路由会丢掉原始目的地和规划意图。
        因此这里会把上一轮 initial_request_text 与新补充的目的地/天数组合成有效输入。
        """
        if not self._is_clarification_recovery(slots=slots, session_context=session_context):
            return message

        seed_message = session_context.get("initial_request_text") or message
        latest_constraints = session_context.get("latest_structured_constraints") or {}
        baseline_constraints = self._resolve_session_baseline_constraints(session_context=session_context)
        resolved_destination = slots.destination or latest_constraints.get("destination") or baseline_constraints.get("destination")
        resolved_days = slots.days if slots.days is not None else latest_constraints.get("days") or baseline_constraints.get("days")

        additions: list[str] = []
        if resolved_destination and resolved_destination not in seed_message:
            additions.append(f"目的地是{resolved_destination}")
        if resolved_days is not None and not self._contains_explicit_days(seed_message):
            additions.append(f"天数是{resolved_days}天")

        if not additions:
            return seed_message
        return f"{seed_message}，{'，'.join(additions)}"

    def _resolve_task_profile(
        self,
        *,
        message: str,
        slots,
        structured_constraints: dict[str, Any],
        session_context: dict[str, Any],
        revision_intent: RevisionIntent,
    ):
        """识别本轮任务类型，并强制把规划追问归回完整规划链路。"""
        profile = self._task_router.analyze(
            message,
            days=structured_constraints["days"],
            preferences=structured_constraints["preferences"],
        )
        if self._is_followup_update(
            message=message,
            slots=slots,
            session_context=session_context,
            revision_intent=revision_intent,
        ):
            return self._task_router.force_planning_profile(
                message=message,
                days=structured_constraints["days"],
                preferences=structured_constraints["preferences"],
            )
        return profile

    def _is_followup_update(
        self,
        *,
        message: str,
        slots,
        session_context: dict[str, Any],
        revision_intent: RevisionIntent | None = None,
    ) -> bool:
        """判断当前请求是否是对上一份旅行规划的修改。

        只有上一轮确实是 travel_planning 时才允许继承规划上下文；天气、门票等轻咨询追问
        不会被强行转成重新规划。
        """
        latest_constraints = session_context.get("latest_structured_constraints")
        latest_task_profile = session_context.get("latest_task_profile") or {}
        if not session_context.get("session_found") or not latest_constraints:
            return False
        if latest_task_profile.get("task_type") != "travel_planning":
            return False
        if revision_intent is not None and revision_intent.is_revision:
            return True
        normalized_message = self._normalize_followup_message(message)
        if self._looks_like_consulting_followup(message=normalized_message):
            return False
        has_update_signal = self._has_followup_update_signal(message=normalized_message, slots=slots)
        if has_update_signal:
            return True
        return False

    def _resolve_implicit_session_id(self, *, user_id: str, message: str, slots) -> str | None:
        """当前端未传 session_id 时，为明显的追问自动挂靠最近规划会话。

        这解决了用户在页面刷新或新输入入口继续说“不要西湖，重新规划”时，系统仍能找到
        上一次杭州三日游的上下文。
        """
        if not self._looks_like_followup_without_session(message=message, slots=slots):
            return None

        candidate_session_id = self._session_run_repository.find_latest_planning_session_id(user_id=user_id)
        if not candidate_session_id:
            return None

        candidate_context = self._session_context_service.load(session_id=candidate_session_id)
        if not candidate_context.get("session_found"):
            return None
        latest_constraints = candidate_context.get("latest_structured_constraints") or {}
        if not latest_constraints.get("destination"):
            return None
        if (
            getattr(slots, "destination_explicit", False)
            and slots.destination != latest_constraints.get("destination")
            and not self._revision_intent_resolver.has_destination_update_signal(message=message, slots=slots)
        ):
            return None
        revision_intent = self._revision_intent_resolver.analyze(
            message=message,
            slots=slots,
            session_context=candidate_context,
        )
        if not revision_intent.is_revision:
            return None
        return candidate_session_id

    def _looks_like_followup_without_session(self, *, message: str, slots) -> bool:
        return (
            self._revision_intent_resolver.has_revision_signal(message=message, slots=slots)
            or self._revision_intent_resolver.has_destination_update_signal(message=message, slots=slots)
        )

    def _has_followup_update_signal(self, *, message: str, slots) -> bool:
        """覆盖常见中文追问表达，降低“同义表达未命中导致走轻咨询”的概率。"""
        if self._revision_intent_resolver.has_revision_signal(message=message, slots=slots):
            return True
        if self._revision_intent_resolver.has_destination_update_signal(message=message, slots=slots):
            return True
        if any(keyword in message for keyword in self.EXCLUSION_UPDATE_KEYWORDS):
            return True
        if any(keyword in message for keyword in self.REPLAN_UPDATE_KEYWORDS):
            return True
        if re.search(r"(?:预算|总预算|总体预算|总花费|总费用|花费|费用).{0,12}?\d{3,6}|(\d{3,5})\s*元", message):
            return True
        if slots.days is not None or slots.budget is not None or getattr(slots, "pace_explicit", False):
            return True
        if getattr(slots, "excluded_attractions", []):
            return True
        if slots.preferences and any(token in message for token in self.PREFERENCE_UPDATE_KEYWORDS):
            return True
        return any(token in message for token in ("住宿", "酒店", "舒适", "舒服", "安静", "热闹"))

    def _is_destination_update(self, *, slots, latest_constraints: dict[str, Any]) -> bool:
        """判断本轮是否明确把既有规划切换到另一个目的地。"""
        return bool(
            getattr(slots, "destination_explicit", False)
            and slots.destination
            and latest_constraints.get("destination")
            and slots.destination != latest_constraints.get("destination")
        )

    def _normalize_followup_message(self, message: str) -> str:
        """把“不想逛/不要去逛”等表达归一成排除类信号。"""
        return (
            message.replace("不想要去逛", "不想去")
            .replace("不想再去", "不去")
            .replace("不要去逛", "不要去")
            .replace("不想逛", "不去")
            .replace("不去逛", "不去")
            .replace("别去逛", "别去")
        )

    def _looks_like_consulting_followup(self, *, message: str) -> bool:
        """识别天气、门票、开放时间等咨询问题，避免误触发重新规划。"""
        weather_hit = any(token in message for token in ("天气", "气温", "几度", "下雨", "穿什么", "适合旅游"))
        question_hit = bool(re.search(r"(有哪些|有什么|有啥|如何|怎么样|吗|几度|多少度|门票|开放时间)", message))
        return weather_hit or question_hit

    def _merge_preferences(self, *, base_preferences: list[str], new_preferences: list[str]) -> list[str]:
        """合并偏好，并允许酒店环境偏好被后续明确表达覆盖。

        quiet_hotel 与 lively_hotel 是互斥偏好；如果用户新一轮明确说“热闹/安静”，旧偏好
        需要被替换，不能同时保留造成规划冲突。
        """
        hotel_environment_preferences = {"quiet_hotel", "lively_hotel"}
        merged = [item for item in base_preferences if item not in hotel_environment_preferences]
        if not any(item in new_preferences for item in hotel_environment_preferences):
            merged.extend(item for item in base_preferences if item in hotel_environment_preferences)
        merged.extend(new_preferences)
        return list(dict.fromkeys(merged))

    def _resolve_session_baseline_constraints(self, *, session_context: dict[str, Any]) -> dict[str, Any]:
        """读取会话基线约束；缺失时从最初请求重新抽取。

        baseline 用于保护“最初确认过的目的地、天数、预算”等核心条件，避免后续轻咨询或
        局部追问把主方案状态覆盖掉。
        """
        baseline_constraints = session_context.get("session_baseline_constraints")
        if isinstance(baseline_constraints, dict) and baseline_constraints:
            return baseline_constraints

        initial_request_text = session_context.get("initial_request_text")
        if not isinstance(initial_request_text, str) or not initial_request_text.strip():
            return {}

        baseline_slots = self._slot_extractor.extract(initial_request_text)
        return {
            "destination": baseline_slots.destination,
            "days": baseline_slots.days,
            "budget": baseline_slots.budget if baseline_slots.budget is not None else 0,
            "pace": baseline_slots.pace,
            "preferences": baseline_slots.preferences,
            "excluded_attractions": baseline_slots.excluded_attractions,
        }

    def _merge_excluded_attractions(self, *, base_attractions: list[str], new_attractions: list[str]) -> list[str]:
        normalized = [str(item).strip() for item in [*base_attractions, *new_attractions] if str(item).strip()]
        return list(dict.fromkeys(normalized))

    def _resolve_followup_days(
        self,
        *,
        latest_constraints: dict[str, Any],
        baseline_constraints: dict[str, Any],
        message: str,
    ) -> int:
        """追问没有显式天数时优先继承上一轮规划天数，而不是重新询问用户。"""
        latest_days = latest_constraints.get("days")
        baseline_days = baseline_constraints.get("days")

        if isinstance(latest_days, int) and latest_days > 1:
            return latest_days
        if isinstance(baseline_days, int) and baseline_days > 1:
            return baseline_days
        if isinstance(latest_days, int) and latest_days > 0:
            return latest_days
        if isinstance(baseline_days, int) and baseline_days > 0:
            return baseline_days
        if self._contains_itinerary_keywords(message):
            return max(latest_days or 1, baseline_days or 1)
        return 1

    def _resolve_followup_budget(
        self,
        *,
        slots,
        latest_constraints: dict[str, Any],
        baseline_constraints: dict[str, Any],
        revision_intent: RevisionIntent,
    ) -> int:
        """追问预算解析优先级：当前输入 > 修订意图目标预算 > 最近规划 > 会话基线。"""
        if slots.budget is not None:
            return slots.budget
        if revision_intent.target_budget is not None:
            return revision_intent.target_budget
        latest_budget = latest_constraints.get("budget")
        baseline_budget = baseline_constraints.get("budget")
        if isinstance(latest_budget, int) and latest_budget > 0:
            return latest_budget
        if isinstance(baseline_budget, int) and baseline_budget > 0:
            return baseline_budget
        return 0

    def _finalize_session_context(
        self,
        *,
        session_context: dict[str, Any],
        structured_constraints: dict[str, Any],
        message: str,
    ) -> dict[str, Any]:
        """补齐历史消息和会话基线，供后续追问恢复使用。"""
        history_messages = [
            item for item in session_context.get("history_messages", [])
            if isinstance(item, str) and item.strip()
        ]
        if not history_messages:
            history_messages = [message]
        elif history_messages[-1] != message:
            history_messages = [*history_messages, message]

        baseline_constraints = self._resolve_session_baseline_constraints(session_context=session_context)
        if not baseline_constraints:
            baseline_constraints = {
                "destination": structured_constraints["destination"],
                "days": structured_constraints["days"],
                "budget": structured_constraints["budget"],
                "budget_policy": structured_constraints.get("budget_policy"),
                "target_budget": structured_constraints.get("target_budget"),
                "pace": structured_constraints["pace"],
                "preferences": structured_constraints["preferences"],
                "excluded_attractions": structured_constraints.get("excluded_attractions", []),
            }

        return {
            **session_context,
            "history_messages": history_messages,
            "initial_request_text": session_context.get("initial_request_text") or history_messages[0],
            "session_baseline_constraints": baseline_constraints,
        }

    def _contains_itinerary_keywords(self, message: str) -> bool:
        return any(token in message for token in ("规划", "行程", "路线", "安排", "几日游", "旅行方案", "旅游方案"))

    def _contains_explicit_days(self, message: str) -> bool:
        return bool(re.search(r"(\d+)\s*(?:天|日游)|([一二三四五六七两])\s*(?:天|日游)", message))

    def _resolve_memory_writeback_source(self, *, state: dict[str, Any]) -> dict[str, Any]:
        """决定哪些本轮信息允许写入长期 Memory。

        长期 Memory 只记录用户明确表达的可复用偏好。追问场景下，继承自上一轮的预算、
        节奏、住宿等约束不能被当作新偏好反复写入；澄清恢复则允许回看 initial_request_text，
        因为用户的明确偏好可能出现在缺天数的上一轮。
        """
        extraction = self._memory_extractor.extract(
            message=state["message"],
            slots=state["slots"],
            session_context=state["session_context"],
        )
        return extraction.to_dict()

    def _latest_missing_fields(self, *, session_context: dict[str, Any]) -> list[str]:
        final_plan = session_context.get("latest_final_plan") or {}
        missing_fields = final_plan.get("missingFields")
        if not isinstance(missing_fields, list):
            return []
        return [str(item) for item in missing_fields if isinstance(item, str)]

    def _resolve_missing_fields(
        self,
        *,
        task_profile: dict[str, Any],
        structured_constraints: dict[str, Any],
        session_context: dict[str, Any],
    ) -> list[str]:
        """计算本轮仍缺失的关键信息。

        如果上一轮澄清过某字段，会优先检查该字段是否已经补齐；完整规划至少需要目的地
        和天数，轻咨询通常只要求目的地。
        """
        pending_missing_fields = self._latest_missing_fields(session_context=session_context)
        unresolved_pending_fields = [
            field_name
            for field_name in pending_missing_fields
            if structured_constraints.get(field_name) is None
        ]
        if unresolved_pending_fields:
            return unresolved_pending_fields
        if structured_constraints.get("destination") is None:
            return ["destination"]
        if task_profile.get("task_type") == "travel_planning" and structured_constraints.get("days") is None:
            return ["days"]
        return []

    def _build_consulting_response(
        self,
        *,
        resolved_session_id: str,
        user_id: str,
        message: str,
        task_profile: dict[str, Any],
        session_context: dict[str, Any],
        structured_constraints: dict[str, Any],
        memory_context: dict[str, Any],
        retrieval_context: dict[str, Any],
        selected_skills: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """构建轻咨询响应并持久化。

        轻咨询会保留 Context/Memory/RAG/Tool 等调试信息，但不会进入多 Agent 规划，也不会
        写入长期偏好，避免一次天气问答污染用户画像。
        """
        final_plan = self._build_consulting_plan(
            structured_constraints=structured_constraints,
            retrieval_context=retrieval_context,
            tool_results=tool_results,
        )
        final_plan = self._geo_presentation_service.enrich_final_plan(
            final_plan=final_plan,
            structured_constraints=structured_constraints,
        )
        final_plan = self._image_generation_service.enrich_plan_visual_assets(final_plan=final_plan)
        assembled_context = self._context_assembler.assemble(
            user_input=message,
            task_profile=task_profile,
            session_context=session_context,
            structured_constraints=structured_constraints,
            memory_context=memory_context,
            retrieval_context=retrieval_context,
            selected_skills=selected_skills,
            tool_results=tool_results,
        )
        llm_output = {
            "mode": "bypass",
            "llm_summary": final_plan["consultingAnswer"],
        }
        response = {
            "session_id": resolved_session_id,
            "user_input": message,
            "task_profile": task_profile,
            "session_context": session_context,
            "structured_constraints": structured_constraints,
            "memory_context": memory_context,
            "memory_updates": [],
            "retrieval_context": retrieval_context,
            "available_skills": self._tool_service.list_skills(),
            "selected_skills": selected_skills,
            "tool_results": tool_results,
            "agent_outputs": [],
            "assembled_context": assembled_context,
            "final_plan": final_plan,
            "llm_output": llm_output,
        }
        self._session_run_repository.save_run(
            session_id=resolved_session_id,
            user_id=user_id,
            request_text=message,
            response=response,
        )
        return response

    def _build_clarification_response(
        self,
        *,
        resolved_session_id: str,
        user_id: str,
        message: str,
        task_profile: dict[str, Any],
        session_context: dict[str, Any],
        structured_constraints: dict[str, Any],
        missing_fields: list[str],
    ) -> dict[str, Any]:
        """构建澄清响应并持久化。

        澄清响应使用和正常响应一致的数据骨架，方便前端统一渲染；但它会明确标记
        missingFields 和 suggestedReplies，让下一轮输入能够被识别为 clarification recovery。
        """
        primary_missing_field = missing_fields[0]
        clarification_task_profile = {
            "task_type": "travel_consulting",
            "complexity": task_profile["complexity"],
            "needs_rag": False,
            "needs_tools": False,
            "needs_multi_agent": False,
            "intent_summary": "当前信息还不足以继续，需要先确认一个关键条件。",
            "evidence": [
                *task_profile.get("evidence", []),
                self._build_clarification_evidence(primary_missing_field=primary_missing_field),
            ],
        }
        memory_context_model = self._memory_service.load_context(
            user_id=user_id,
            short_term_state=structured_constraints,
        )
        memory_context = {
            "long_term_memory": memory_context_model.long_term_memory,
            "relevant_long_term_memory": [],
            "short_term_state": memory_context_model.short_term_state,
            "selection_reasons": [self._build_clarification_selection_reason(primary_missing_field=primary_missing_field)],
            "dropped_memory_count": len(memory_context_model.long_term_memory),
        }
        retrieval_context = {
            "query": "",
            "query_rewrite": {"source": "none", "query": "", "query_terms": [], "focus_keywords": [], "steps": []},
            "retrieval_steps": [self._build_clarification_retrieval_reason(primary_missing_field=primary_missing_field)],
            "ranking_signals": [],
            "retrieved_documents": [],
            "injected_knowledge": [],
        }
        final_plan = {
            "summary": {
                "destinationCity": structured_constraints["destination"],
                "days": structured_constraints["days"],
                "totalBudget": 0,
                "currency": "CNY",
                "tags": structured_constraints.get("preferences", []),
            },
            "consultingType": "clarification",
            "consultingAnswer": self._build_clarification_answer(
                primary_missing_field=primary_missing_field,
                structured_constraints=structured_constraints,
            ),
            "missingFields": missing_fields,
            "suggestedReplies": self.CLARIFICATION_SUGGESTIONS.get(primary_missing_field, []),
            "weather": [],
            "days": [],
            "budget": {"transport": 0, "accommodation": 0, "food": 0, "tickets": 0},
            "hotelRecommendation": [],
            "hotelOptions": [],
            "attractionRecommendations": [],
            "foodRecommendations": [],
            "dailyGuide": [],
            "stayAdvice": {},
            "budgetInsights": [],
            "tripTips": [],
            "planHighlights": [],
            "planningNarrative": "",
        }
        final_plan = self._geo_presentation_service.enrich_final_plan(
            final_plan=final_plan,
            structured_constraints=structured_constraints,
        )
        final_plan = self._image_generation_service.enrich_plan_visual_assets(final_plan=final_plan)
        assembled_context = self._context_assembler.assemble(
            user_input=message,
            task_profile=clarification_task_profile,
            session_context=session_context,
            structured_constraints=structured_constraints,
            memory_context=memory_context,
            retrieval_context=retrieval_context,
            selected_skills=[],
            tool_results=[],
        )
        response = {
            "session_id": resolved_session_id,
            "user_input": message,
            "task_profile": clarification_task_profile,
            "session_context": session_context,
            "structured_constraints": structured_constraints,
            "memory_context": memory_context,
            "memory_updates": [],
            "retrieval_context": retrieval_context,
            "available_skills": self._tool_service.list_skills(),
            "selected_skills": [],
            "tool_results": [],
            "agent_outputs": [],
            "assembled_context": assembled_context,
            "final_plan": final_plan,
            "llm_output": {
                "mode": "bypass",
                "llm_summary": final_plan["consultingAnswer"],
            },
        }
        self._session_run_repository.save_run(
            session_id=resolved_session_id,
            user_id=user_id,
            request_text=message,
            response=response,
        )
        return response

    def _build_clarification_answer(
        self,
        *,
        primary_missing_field: str,
        structured_constraints: dict[str, Any],
    ) -> str:
        if primary_missing_field == "days":
            destination = structured_constraints.get("destination") or "这个城市"
            return f"目的地已确认是{destination}，但还缺少出行天数。请告诉我是几天行程，比如 2 天、3 天或 4 天，我再继续帮你规划。"
        return "请先告诉我你想去哪个城市，我再继续帮你查天气、推荐景点或规划行程。"

    def _build_clarification_evidence(self, *, primary_missing_field: str) -> str:
        if primary_missing_field == "days":
            return "当前轮已识别到目的地，但旅行规划还缺少天数信息，先向用户确认行程时长。"
        return "当前轮未识别到目的地，先向用户补充确认城市。"

    def _build_clarification_selection_reason(self, *, primary_missing_field: str) -> str:
        if primary_missing_field == "days":
            return "当前缺少出行天数，先等待用户补充具体行程时长。"
        return "当前缺少目的地，先等待用户补充城市信息。"

    def _build_clarification_retrieval_reason(self, *, primary_missing_field: str) -> str:
        if primary_missing_field == "days":
            return "当前缺少出行天数，暂不触发路线规划相关检索。"
        return "当前缺少目的地，暂不触发知识检索。"

    def _build_consulting_plan(
        self,
        *,
        structured_constraints: dict[str, Any],
        retrieval_context: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """把轻量工具结果转换成前端可直接消费的 final_plan。

        这里故意只支持天气和景点等轻能力；真正的多日行程仍交给完整规划链路，避免把
        简单问答和复杂规划混在同一个输出生成过程里。
        """
        destination = structured_constraints["destination"]
        tags = structured_constraints.get("preferences", [])
        tool_result = tool_results[0] if tool_results else None

        if tool_result and tool_result["tool_name"] == "weather.lookup":
            weather = tool_result["output"]
            answer = f"{destination}天气：{weather.get('summary', '暂无数据')}。{weather.get('advice', '')}".strip()
            return {
                "summary": {
                    "destinationCity": destination,
                    "days": 1,
                    "totalBudget": 0,
                    "currency": "CNY",
                    "tags": tags,
                },
                "consultingType": "weather",
                "consultingAnswer": answer,
                "weather": [weather],
                "days": [],
                "budget": {"transport": 0, "accommodation": 0, "food": 0, "tickets": 0},
                "hotelRecommendation": [],
                "hotelOptions": [],
                "attractionRecommendations": [],
                "foodRecommendations": [],
                "dailyGuide": [],
                "stayAdvice": {},
                "budgetInsights": [],
                "tripTips": [weather.get("advice")] if weather.get("advice") else [],
                "planHighlights": [f"{destination} 当前天气：{weather.get('summary', '暂无天气数据')}"],
                "planningNarrative": "",
            }

        if tool_result and tool_result["tool_name"] == "attraction.search":
            attractions = tool_result["output"].get("attractions", [])
            attraction_names = "、".join(item.get("name", "") for item in attractions if item.get("name"))
            knowledge_hint = retrieval_context.get("injected_knowledge", [])
            hint = knowledge_hint[0] if knowledge_hint else ""
            answer = f"{destination}推荐景点：{attraction_names}。{hint}".strip("。")
            if not answer.endswith("。"):
                answer = f"{answer}。"
            return {
                "summary": {
                    "destinationCity": destination,
                    "days": 1,
                    "totalBudget": 0,
                    "currency": "CNY",
                    "tags": tags,
                },
                "consultingType": "attraction",
                "consultingAnswer": answer,
                "weather": [],
                "days": [],
                "budget": {"transport": 0, "accommodation": 0, "food": 0, "tickets": 0},
                "hotelRecommendation": [],
                "hotelOptions": [],
                "attractionRecommendations": [
                    {
                        "name": item.get("name"),
                        "area": item.get("area", "核心城区"),
                        "type": item.get("type", "citywalk"),
                        "typeLabel": item.get("type", "citywalk"),
                        "cost": item.get("cost", 0),
                        "durationHours": item.get("durationHours", 0),
                        "tags": item.get("tags", []),
                        "reason": "适合作为当前问题下可直接参考的点位。",
                    }
                    for item in attractions[:5]
                ],
                "foodRecommendations": [],
                "dailyGuide": [],
                "stayAdvice": {},
                "budgetInsights": [],
                "tripTips": [hint] if hint else [],
                "planHighlights": [f"{destination} 可优先看 {attraction_names}"] if attraction_names else [],
                "planningNarrative": "",
            }

        default_answer = f"当前已识别 {destination} 的旅行咨询需求，但没有匹配到可直接执行的轻量能力。"
        return {
            "summary": {
                "destinationCity": destination,
                "days": 1,
                "totalBudget": 0,
                "currency": "CNY",
                "tags": tags,
            },
            "consultingType": "generic",
            "consultingAnswer": default_answer,
            "weather": [],
            "days": [],
            "budget": {"transport": 0, "accommodation": 0, "food": 0, "tickets": 0},
            "hotelRecommendation": [],
            "hotelOptions": [],
            "attractionRecommendations": [],
            "foodRecommendations": [],
            "dailyGuide": [],
            "stayAdvice": {},
            "budgetInsights": [],
            "tripTips": [],
            "planHighlights": [],
            "planningNarrative": "",
        }
