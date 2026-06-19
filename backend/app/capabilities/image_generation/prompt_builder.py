from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.config.settings import Settings


AssetGroup = Literal["hero", "attractions", "hotels", "foods"]


ASSET_GROUP_LABELS: dict[AssetGroup, str] = {
    "hero": "目的地氛围图",
    "attractions": "景点示意图",
    "hotels": "住宿示意图",
    "foods": "餐饮示意图",
}

ASSET_GROUP_DEFAULTS: dict[AssetGroup, dict[str, str]] = {
    "hero": {"style": "travel_editorial", "aspect": "landscape"},
    "attractions": {"style": "travel_editorial", "aspect": "square"},
    "hotels": {"style": "hotel_editorial", "aspect": "square"},
    "foods": {"style": "food_editorial", "aspect": "square"},
}

ASPECT_SIZE_MAP = {
    "landscape": "1536x1024",
    "square": "1024x1024",
    "portrait": "1024x1536",
}

STYLE_LABELS = {
    "travel_editorial": "写实旅行编辑风格",
    "hotel_editorial": "精品酒店空间摄影风格",
    "food_editorial": "旅行餐饮编辑风格",
}

SUBJECT_TYPE_LABELS = {
    "nature": "自然风景",
    "culture": "人文古迹",
    "museum": "博物馆",
    "citywalk": "城市漫步",
    "food": "本地餐饮",
    "hotel": "酒店住宿",
    "hotel_area": "住宿片区",
    "relaxed": "慢游休闲",
}

PREFERENCE_LABELS = {
    "relaxed": "轻松慢游",
    "balanced": "节奏均衡",
    "intensive": "紧凑高效",
    "quiet_hotel": "安静住宿",
    "lively_hotel": "热闹商圈",
    "comfortable_hotel": "更重视住宿舒适度",
    "local_food": "本地特色美食",
    "avoid_local_food": "不安排本地特色",
    "avoid_food": "弱化餐饮安排",
    "culture": "文化体验",
    "nature": "自然景观",
    "citywalk": "街区漫步",
    "museum": "博物馆体验",
    "family": "亲子友好",
    "rainy_day": "雨天可替代",
    "night_walk": "夜游氛围",
    "slow_travel": "慢节奏停留",
    "lakeview": "湖景氛围",
    "design_hotel": "设计感住宿",
    "budget_friendly": "预算友好",
    "metro_access": "交通便利",
    "night_market": "夜市烟火感",
    "snack": "小吃街区",
    "heritage": "老城历史感",
    "tea": "茶文化氛围",
}


@dataclass(frozen=True)
class TripImagePromptInput:
    asset_group: AssetGroup
    destination: str
    subject_name: str
    subject_type: str | None = None
    area: str | None = None
    style: str | None = None
    aspect: str | None = None
    time_of_day: str | None = None
    weather_hint: str | None = None
    user_preferences: list[str] = field(default_factory=list)
    size: str | None = None
    tags: list[str] = field(default_factory=list)
    content_hint: str | None = None
    extra_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BuiltTripImagePrompt:
    asset_group: AssetGroup
    prompt: str
    size: str
    style: str
    aspect: str
    label: str


@dataclass(frozen=True)
class AttractionImagePromptInput:
    destination: str
    attraction_name: str
    attraction_type: str | None = None
    area: str | None = None
    style: str = "travel_editorial"
    aspect: str = "landscape"
    time_of_day: str | None = None
    weather_hint: str | None = None
    user_preferences: list[str] = field(default_factory=list)
    size: str | None = None


class TripImagePromptBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, input_data: TripImagePromptInput) -> BuiltTripImagePrompt:
        defaults = ASSET_GROUP_DEFAULTS[input_data.asset_group]
        style = (input_data.style or defaults["style"]).strip().lower()
        aspect = (input_data.aspect or defaults["aspect"]).strip().lower()
        size = (input_data.size or ASPECT_SIZE_MAP.get(aspect) or self._settings.image_default_size).strip()

        prompt_lines = self._build_prompt_lines(
            input_data=input_data,
            style=style,
            aspect=aspect,
            size=size,
        )
        return BuiltTripImagePrompt(
            asset_group=input_data.asset_group,
            prompt="\n".join(prompt_lines).strip(),
            size=size,
            style=style,
            aspect=aspect,
            label=ASSET_GROUP_LABELS[input_data.asset_group],
        )

    def _build_prompt_lines(
        self,
        *,
        input_data: TripImagePromptInput,
        style: str,
        aspect: str,
        size: str,
    ) -> list[str]:
        style_label = STYLE_LABELS.get(style, style)
        type_label = SUBJECT_TYPE_LABELS.get(str(input_data.subject_type or "").strip().lower(), input_data.subject_type or "综合场景")
        preference_hint = self._join_labels([*input_data.user_preferences, *input_data.tags])
        common_lines = [
            self._header_line(asset_group=input_data.asset_group),
            f"目的地：{input_data.destination}",
            f"主体：{input_data.subject_name}",
            f"类型：{type_label}",
            f"区域：{input_data.area or '城市核心片区'}",
            f"时间氛围：{input_data.time_of_day or self._default_time_of_day(input_data.asset_group)}",
            f"天气参考：{input_data.weather_hint or '适合出行的清爽天气'}",
            f"风格要求：{style_label}",
            f"构图比例：{aspect}，适合 {size} 输出尺寸",
        ]
        if preference_hint:
            common_lines.append(f"用户偏好：{preference_hint}")
        if input_data.content_hint:
            common_lines.append(f"内容补充：{input_data.content_hint}")

        common_lines.extend(
            [
                "",
                "要求：",
                *self._group_requirements(input_data.asset_group),
                "不要出现文字、水印、logo、二维码、票价信息、地图界面或宣传海报排版。",
                "不要做成明显的广告KV或商业宣传图，更像旅行规划页面中的真实参考配图。",
            ]
        )
        return common_lines

    def _header_line(self, asset_group: AssetGroup) -> str:
        if asset_group == "hero":
            return "请生成一张用于智能旅行规划页面的目的地封面氛围图。"
        if asset_group == "hotels":
            return "请生成一张用于智能旅行规划页面的住宿空间示意图。"
        if asset_group == "foods":
            return "请生成一张用于智能旅行规划页面的餐饮与街区氛围示意图。"
        return "请生成一张用于智能旅行规划页面的旅行景点氛围图。"

    def _group_requirements(self, asset_group: AssetGroup) -> list[str]:
        if asset_group == "hero":
            return [
                "1. 画面要能代表整座城市的旅行气质，优先呈现城市标志性景观与可游逛氛围。",
                "2. 保持封面主视觉构图，层次清晰、通透自然，适合作为结果页首屏视觉参考。",
                "3. 不要做成拼贴海报，避免多个景点生硬并列，尽量是一个完整场景。",
                "4. 允许少量远景人物，但不要出现人物大头自拍或夸张摆拍。",
            ]
        if asset_group == "hotels":
            return [
                "1. 重点表现酒店客房、大堂或窗景的舒适度、整洁度与入住氛围。",
                "2. 更像真实精品酒店空间摄影，避免夸张样板房或地产效果图质感。",
                "3. 如果有安静、舒适、湖景、设计感等偏好，要通过空间与光线体现出来。",
                "4. 不要展示品牌文字、前台招牌、价格海报或宣传物料。",
            ]
        if asset_group == "foods":
            return [
                "1. 重点呈现本地餐饮、街区烟火气或顺路用餐场景，而不是纯商品棚拍。",
                "2. 食物与环境都要可见，既能看出美食，也能感受到所在街区氛围。",
                "3. 如果是夜市、小吃街或老城步行街，要体现人间烟火和出行场景感。",
                "4. 不要出现菜单文字、店招特写、水印或过度商业摆盘。",
            ]
        return [
            "1. 突出景点本身的空间感、代表性视角和旅行到达感。",
            "2. 更像旅行编辑选图或产品详情头图，而不是明信片或景区广告。",
            "3. 画面明亮、干净、有真实旅行感，适合作为结果页视觉参考。",
            "4. 避免人物大头自拍视角，优先使用场景化、环境化构图。",
        ]

    def _default_time_of_day(self, asset_group: AssetGroup) -> str:
        if asset_group == "hero":
            return "清晨或傍晚的柔和光线"
        if asset_group == "hotels":
            return "下午柔光或夜晚暖光"
        if asset_group == "foods":
            return "傍晚或入夜后的用餐时段"
        return "白天光线通透时段"

    def _join_labels(self, values: list[str]) -> str:
        labels: list[str] = []
        for item in values:
            normalized = str(item or "").strip().lower()
            if not normalized:
                continue
            labels.append(PREFERENCE_LABELS.get(normalized, normalized))
        deduped = list(dict.fromkeys(labels))
        return "、".join(deduped)


class AttractionImagePromptBuilder:
    def __init__(self, settings: Settings) -> None:
        self._delegate = TripImagePromptBuilder(settings)

    def build(self, input_data: AttractionImagePromptInput) -> BuiltTripImagePrompt:
        return self._delegate.build(
            TripImagePromptInput(
                asset_group="attractions",
                destination=input_data.destination,
                subject_name=input_data.attraction_name,
                subject_type=input_data.attraction_type,
                area=input_data.area,
                style=input_data.style,
                aspect=input_data.aspect,
                time_of_day=input_data.time_of_day,
                weather_hint=input_data.weather_hint,
                user_preferences=input_data.user_preferences,
                size=input_data.size,
            )
        )
