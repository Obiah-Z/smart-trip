<template>
  <section class="panel result-panel">
    <div class="panel-header">
      <div>
        <p class="panel-kicker">Plan</p>
        <h2>{{ isConsultingMode ? '回答已经整理好了' : '方案已经整理好了' }}</h2>
      </div>
      <span class="badge">{{ destinationLabel }}{{ !isConsultingMode ? ` / ${summary.days || 0} 天` : '' }}</span>
    </div>

    <section v-if="isConsultingMode" class="consulting-hero">
      <div class="consulting-answer-card">
        <p class="panel-kicker">Answer</p>
        <h3>{{ consultingTitle }}</h3>
        <p class="consulting-answer">{{ consultingAnswer }}</p>
      </div>
      <div class="consulting-sidecards">
        <article v-for="card in consultingCards" :key="card.title" class="metric-card">
          <span class="metric-label">{{ card.title }}</span>
          <strong>{{ card.value }}</strong>
          <p v-if="card.extra" class="muted-text">{{ card.extra }}</p>
        </article>
      </div>
    </section>

    <template v-if="!isConsultingMode">
      <div v-if="displaySummary || planningNarrative" class="subsection result-summary-section">
        <h3>一句话总结</h3>
        <div
          class="summary-card summary-markdown result-summary-card"
          v-html="displaySummary ? displaySummaryHtml : planningNarrativeHtml"
        ></div>
      </div>

      <div class="overview-metrics">
        <article class="metric-card">
          <span class="metric-label">预计总花费</span>
          <strong>{{ formatCurrency(summary.totalBudget) }}</strong>
        </article>
        <article class="metric-card">
          <span class="metric-label">推荐住宿</span>
          <strong>{{ primaryHotel?.name || '待生成' }}</strong>
        </article>
        <article class="metric-card">
          <span class="metric-label">行程关键词</span>
          <strong>{{ summaryTagsText }}</strong>
        </article>
        <article class="metric-card">
          <span class="metric-label">出行节奏</span>
          <strong>{{ paceLabel }}</strong>
        </article>
      </div>

      <div class="subsection focus-summary-section" v-if="taskProfile">
        <h3>这份方案会重点照顾</h3>
        <div class="tag-cloud">
          <span class="chip" v-for="item in planFocusChips" :key="item">{{ item }}</span>
        </div>
        <p class="muted-text">{{ userFacingIntentSummary }}</p>
      </div>

      <div v-if="planHighlights.length" class="subsection">
        <h3>先看这几个重点</h3>
        <div class="highlight-strip">
          <article v-for="item in planHighlights" :key="item" class="highlight-pill">
            <p>{{ item }}</p>
          </article>
        </div>
      </div>

      <div v-if="tripSnapshotCards.length" class="subsection">
        <h3>先感受这趟旅行的样子</h3>
        <div class="trip-snapshot-grid">
          <article v-for="card in tripSnapshotCards" :key="card.key" class="snapshot-card">
            <div class="snapshot-card-media recommendation-media" :class="{ 'is-loading': card.loading && !card.imageUrl }">
              <img
                v-if="card.imageUrl"
                :src="card.imageUrl"
                :alt="card.imageAlt"
                class="recommendation-media-image"
                :srcset="card.imageSrcSet"
                sizes="(max-width: 960px) 100vw, 360px"
                :loading="card.imageLoading"
                :fetchpriority="card.imageFetchPriority"
                decoding="async"
              />
              <div v-else class="recommendation-media-placeholder">
                <span>{{ card.placeholder }}</span>
              </div>
              <span v-if="card.imageLabel" class="visual-media-badge">{{ card.imageLabel }}</span>
              <span class="snapshot-card-kicker">{{ card.kicker }}</span>
            </div>
            <div class="snapshot-card-body">
              <div class="recommendation-head">
                <strong>{{ card.title }}</strong>
                <span class="chip subtle">{{ card.badge }}</span>
              </div>
              <p class="snapshot-card-summary">{{ card.summary }}</p>
              <p class="muted-text compact-copy">{{ card.meta }}</p>
              <div v-if="card.chips.length" class="inline-chip-row compact-chip-row">
                <span class="chip subtle" v-for="chip in card.chips" :key="chip">{{ chip }}</span>
              </div>
            </div>
          </article>
        </div>
      </div>

      <div class="result-grid result-grid-expanded result-primary-grid">
        <section class="result-block">
          <h3>按天安排</h3>
          <div v-if="mapData && dayTabs.length" class="map-sync-banner">
            <div class="map-sync-copy">
              <span class="chip subtle">地图联动</span>
              <strong>{{ mapSelectionLabel }}</strong>
              <p class="muted-text compact-copy">{{ mapSelectionHint }}</p>
            </div>
            <button
              v-if="selectedMapDay !== 'all'"
              class="day-link-button day-link-button-secondary"
              type="button"
              @click="focusMapDay('all')"
            >
              切回全程
            </button>
          </div>
          <div class="day-guide-list" v-if="dailyGuide.length">
            <article
              v-for="day in dailyGuide"
              :key="day.day"
              class="day-guide-card"
              :class="{ 'day-guide-card-active': selectedMapDay === day.day }"
            >
              <div class="day-guide-head">
                <span class="day-chip">Day {{ day.day }}</span>
                <strong>{{ day.theme || `第 ${day.day} 天` }}</strong>
                <button
                  class="day-link-button"
                  :class="{ active: isMapFocusedDay(day.day) }"
                  type="button"
                  @click="focusMapDay(day.day)"
                >
                  {{ isMapFocusedDay(day.day) ? '已联动' : '看地图' }}
                </button>
              </div>
              <p class="muted-text compact-copy">{{ day.note }}</p>
              <div class="inline-chip-row" v-if="day.highlights?.length">
                <span class="chip subtle" v-for="item in day.highlights" :key="item">{{ item }}</span>
              </div>
              <p>{{ day.activities?.join(' -> ') || '暂无安排' }}</p>
              <div class="day-guide-meta">
                <span>{{ day.area || '区域待定' }}</span>
                <span>{{ day.estimatedDurationHours ? `${day.estimatedDurationHours} 小时左右` : '时长待定' }}</span>
                <span>{{ day.estimatedTickets ? `门票约 ${formatCurrency(day.estimatedTickets)}` : '门票压力较低' }}</span>
              </div>
              <p v-if="isMapFocusedDay(day.day)" class="map-inline-status">地图已同步高亮这一天的路线与点位。</p>
              <component
                :is="activeMapComponent"
                v-if="isMapFocusedDay(day.day) && mapData"
                class="inline-map-panel"
                :data="mapData"
                :selected-day="day.day"
                :display-mode="mapDisplayMode"
                :marker-visuals="mapMarkerVisuals"
                :compact="true"
                :focus-only="true"
                @fallback="handleAmapFallback"
              />
              <p v-if="day.mealHint" class="muted-text compact-copy">{{ day.mealHint }}</p>
            </article>
          </div>
          <div class="itinerary-list" v-else-if="days.length">
            <article v-for="day in days" :key="day.day" class="itinerary-item">
              <span class="day-chip">Day {{ day.day }}</span>
              <p>{{ day.activities?.join(' -> ') || day.route?.join(' -> ') || '暂无安排' }}</p>
              <button
                class="day-link-button"
                :class="{ active: isMapFocusedDay(day.day) }"
                type="button"
                @click="focusMapDay(day.day)"
              >
                {{ isMapFocusedDay(day.day) ? '已联动' : '看地图' }}
              </button>
              <p v-if="isMapFocusedDay(day.day)" class="map-inline-status">地图已同步高亮这一天的路线与点位。</p>
              <component
                :is="activeMapComponent"
                v-if="isMapFocusedDay(day.day) && mapData"
                class="inline-map-panel"
                :data="mapData"
                :selected-day="day.day"
                :display-mode="mapDisplayMode"
                :marker-visuals="mapMarkerVisuals"
                :compact="true"
                :focus-only="true"
                @fallback="handleAmapFallback"
              />
            </article>
          </div>
          <p v-else class="muted-text">暂时还没有整理出可展示的按天安排。</p>
        </section>

        <div class="side-stack">
          <section class="result-block">
            <h3>住宿建议</h3>
            <div class="recommendation-grid recommendation-grid-single" v-if="hotelShowcaseCards.length">
              <article
                v-for="item in hotelShowcaseCards"
                :key="item.key"
                class="recommendation-card recommendation-card-rich"
                :class="{ 'recommendation-card-featured': item.featured }"
              >
                <div class="recommendation-media" :class="{ 'is-loading': item.loading && !item.imageUrl }">
                  <img
                    v-if="item.imageUrl"
                    :src="item.imageUrl"
                    :alt="item.imageAlt"
                    class="recommendation-media-image"
                    :srcset="item.imageSrcSet"
                    sizes="(max-width: 960px) 100vw, 360px"
                    :loading="item.imageLoading"
                    :fetchpriority="item.imageFetchPriority"
                    decoding="async"
                  />
                  <div v-else class="recommendation-media-placeholder">
                    <span>{{ item.placeholder }}</span>
                  </div>
                  <span v-if="item.imageLabel" class="visual-media-badge">{{ item.imageLabel }}</span>
                </div>
                <div class="recommendation-head">
                  <strong>{{ item.title }}</strong>
                  <div class="recommendation-head-side">
                    <span class="chip">{{ item.priceLabel }}</span>
                    <span class="chip subtle">{{ item.badge }}</span>
                  </div>
                </div>
                <p class="recommendation-meta-line">{{ item.meta }}</p>
                <p class="recommendation-summary">{{ item.summary }}</p>
                <div class="inline-chip-row compact-chip-row" v-if="item.chips.length">
                  <span class="chip subtle" v-for="chip in item.chips" :key="chip">{{ chip }}</span>
                </div>
                <p v-if="item.supporting" class="muted-text compact-copy recommendation-supporting">{{ item.supporting }}</p>
              </article>
            </div>
            <p v-else class="muted-text">系统还没有拿到住宿结果。</p>
          </section>

          <details class="result-block budget-collapse">
            <summary class="budget-collapse-summary">
              <div>
                <span class="metric-label">花费分配</span>
                <strong>{{ budgetSummaryLine }}</strong>
              </div>
              <span class="budget-collapse-action">展开明细</span>
            </summary>
            <div class="budget-collapse-body">
              <div class="budget-list">
                <div class="budget-row">
                  <span>交通</span>
                  <strong>{{ formatCurrency(budget.transport) }}</strong>
                </div>
                <div class="budget-row">
                  <span>住宿</span>
                  <strong>{{ formatCurrency(budget.accommodation) }}</strong>
                </div>
                <div class="budget-row">
                  <span>餐饮</span>
                  <strong>{{ formatCurrency(budget.food) }}</strong>
                </div>
                <div class="budget-row">
                  <span>门票</span>
                  <strong>{{ formatCurrency(budget.tickets) }}</strong>
                </div>
              </div>
              <div class="insight-list" v-if="budgetInsights.length">
                <article v-for="item in budgetInsights" :key="item.label" class="mini-card">
                  <span class="metric-label">{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                  <p>{{ item.detail }}</p>
                </article>
              </div>
            </div>
          </details>
        </div>
      </div>

      <section
        v-if="mapData || shouldShowVisualHero"
        class="subsection visual-map-section"
      >
        <div class="section-title-row">
          <div>
            <h3>图片与位置预览</h3>
            <p class="muted-text compact-copy">图片用来快速感受目的地氛围，地图用来判断住宿、景点和路线是否顺路。</p>
          </div>
        </div>
        <div
          class="visual-map-layout"
          :class="{ 'visual-map-layout-single': !mapData || !shouldShowVisualHero }"
        >
          <div v-if="shouldShowVisualHero" class="visual-hero-card visual-hero-card-compact">
            <div class="visual-hero-media" :class="{ 'is-loading': heroImageLoading && !heroImageUrl }">
              <img
                v-if="heroImageUrl"
                :src="heroImageUrl"
                :alt="heroImageAlt"
                class="visual-hero-image"
                :srcset="heroImageSrcSet"
                sizes="(max-width: 960px) 100vw, 420px"
                loading="lazy"
                fetchpriority="low"
                decoding="async"
              />
              <div v-else class="visual-hero-placeholder">
                <span>{{ heroImageLoading ? '正在生成城市氛围图...' : '等待生成城市氛围图' }}</span>
              </div>
              <span v-if="heroImageLabel" class="visual-media-badge">{{ heroImageLabel }}</span>
            </div>
            <div class="visual-hero-copy">
              <p class="panel-kicker">Visual</p>
              <h3>{{ destinationLabel }} 目的地印象</h3>
              <p class="muted-text">{{ heroIntroText }}</p>
              <div class="tag-cloud">
                <span class="chip subtle" v-for="item in visualHeroChips" :key="item">{{ item }}</span>
              </div>
              <p v-if="heroImageError" class="muted-text visual-error-copy">{{ heroImageError }}</p>
            </div>
          </div>

          <div v-if="mapData" class="map-overview-card">
            <div v-if="dayTabs.length" class="map-day-switch map-day-switch-compact">
              <button
                class="tab-button"
                :class="{ active: selectedMapDay === 'all' }"
                type="button"
                @click="focusMapDay('all')"
              >
                全程
              </button>
              <button
                v-for="day in dayTabs"
                :key="day"
                class="tab-button"
                :class="{ active: selectedMapDay === day }"
                type="button"
                @click="focusMapDay(day)"
              >
                Day {{ day }}
              </button>
            </div>
            <component
              :is="activeMapComponent"
              class="overview-map-panel"
              :data="mapData"
              :selected-day="selectedMapDay"
              :display-mode="mapDisplayMode"
              :marker-visuals="mapMarkerVisuals"
              :compact="true"
              @fallback="handleAmapFallback"
            />
            <div v-if="amapFailed" class="inline-chip-row">
              <p class="muted-text compact-copy">
                {{ amapFailureMessage || '高德地图当前不可用，已自动切回本地预览，不影响继续查看方案。' }}
              </p>
              <button class="day-link-button" type="button" @click="retryAmap">重试地图</button>
            </div>
          </div>
        </div>
      </section>

      <div class="result-grid result-grid-expanded">
        <section class="result-block">
          <h3>值得优先看的点</h3>
          <div class="recommendation-grid" v-if="attractionShowcaseCards.length">
            <article v-for="item in attractionShowcaseCards" :key="item.key" class="recommendation-card recommendation-card-rich">
              <div class="recommendation-media" :class="{ 'is-loading': item.loading && !item.imageUrl }">
                <img
                  v-if="item.imageUrl"
                  :src="item.imageUrl"
                  :alt="item.imageAlt"
                  class="recommendation-media-image"
                  :srcset="item.imageSrcSet"
                  sizes="(max-width: 960px) 100vw, 360px"
                  :loading="item.imageLoading"
                  :fetchpriority="item.imageFetchPriority"
                  decoding="async"
                />
                <div v-else class="recommendation-media-placeholder">
                  <span>{{ item.placeholder }}</span>
                </div>
                <span v-if="item.imageLabel" class="visual-media-badge">{{ item.imageLabel }}</span>
              </div>
              <div class="recommendation-head">
                <strong>{{ item.title }}</strong>
                <div class="recommendation-head-side">
                  <span class="chip">{{ item.badge }}</span>
                </div>
              </div>
              <p class="recommendation-meta-line">{{ item.meta }}</p>
              <p class="recommendation-summary">{{ item.summary }}</p>
              <div class="inline-chip-row compact-chip-row" v-if="item.chips.length">
                <span class="chip subtle" v-for="chip in item.chips" :key="chip">{{ chip }}</span>
              </div>
            </article>
          </div>
          <p v-else class="muted-text">当前还没有可单独展开的景点推荐。</p>
        </section>

        <section class="result-block">
          <h3>吃什么更顺路</h3>
          <div class="recommendation-grid" v-if="foodShowcaseCards.length">
            <article v-for="item in foodShowcaseCards" :key="item.key" class="recommendation-card recommendation-card-rich">
              <div class="recommendation-media" :class="{ 'is-loading': item.loading && !item.imageUrl }">
                <img
                  v-if="item.imageUrl"
                  :src="item.imageUrl"
                  :alt="item.imageAlt"
                  class="recommendation-media-image"
                  :srcset="item.imageSrcSet"
                  sizes="(max-width: 960px) 100vw, 360px"
                  :loading="item.imageLoading"
                  :fetchpriority="item.imageFetchPriority"
                  decoding="async"
                />
                <div v-else class="recommendation-media-placeholder">
                  <span>{{ item.placeholder }}</span>
                </div>
                <span v-if="item.imageLabel" class="visual-media-badge">{{ item.imageLabel }}</span>
              </div>
              <div class="recommendation-head">
                <strong>{{ item.title }}</strong>
                <div class="recommendation-head-side">
                  <span class="chip subtle">{{ item.badge }}</span>
                </div>
              </div>
              <p class="recommendation-meta-line">{{ item.meta }}</p>
              <p class="recommendation-summary">{{ item.summary }}</p>
              <div class="inline-chip-row compact-chip-row" v-if="item.chips.length">
                <span class="chip subtle" v-for="chip in item.chips" :key="chip">{{ chip }}</span>
              </div>
              <p v-if="item.supporting" class="muted-text compact-copy recommendation-supporting">{{ item.supporting }}</p>
            </article>
          </div>
          <p v-else class="muted-text">这轮结果里没有单独抽出餐饮点，如果你愿意，我可以继续细化到早餐、正餐或夜宵。</p>
        </section>
      </div>

      <div class="subsection" v-if="tripTips.length">
        <h3>出行提醒</h3>
        <div class="trip-tips-list">
          <article v-for="item in tripTips" :key="item" class="mini-card">
            <p>{{ item }}</p>
          </article>
        </div>
      </div>
    </template>

    <div class="subsection" v-if="isConsultingMode && displaySummary">
      <h3>补充说明</h3>
      <div class="summary-card summary-markdown" v-html="displaySummaryHtml"></div>
    </div>

    <details v-if="showEvidenceDetails" class="raw-details user-details">
      <summary>查看推荐依据</summary>
      <div class="subsection">
        <h3>{{ isConsultingMode ? '回答依据' : '方案依据' }}</h3>
        <p class="muted-text">{{ userFacingEvidenceSummary }}</p>
      </div>
    </details>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import AmapTripMapPanel from './AmapTripMapPanel.vue'
import { resetAmapLoader } from '../lib/amap'
import { resolveAssetUrl } from '../lib/api'
import TripMapPanel from './TripMapPanel.vue'

const TAG_LABELS = {
  local_food: '本地特色',
  quiet_hotel: '安静住宿',
  lively_hotel: '热闹商圈',
  comfortable_hotel: '住得更舒服',
  design_hotel: '设计感住宿',
  family_friendly: '亲子友好',
  metro_access: '交通方便',
  citywalk: '街区漫步',
  night_walk: '夜游氛围',
  culture: '人文体验',
  heritage: '历史感',
  museum: '博物馆',
  nature: '自然风景',
  relaxed: '慢节奏',
  classic: '经典打卡',
  food: '顺路吃点好的',
  garden: '园林风格',
  lakeview: '景观感强',
  riverfront: '临江散步',
  indoor: '雨天友好',
  street: '街区氛围',
  design: '设计街区',
  park: '公园散步',
  tea: '茶文化',
}

const TYPE_LABELS = {
  citywalk: '城市漫步',
  culture: '人文古迹',
  museum: '博物馆',
  nature: '自然风景',
  relaxed: '慢游休闲',
  food: '在地美食',
}

const props = defineProps({
  data: { type: Object, required: true },
  showEvidenceDetails: {
    type: Boolean,
    default: true,
  },
})

const taskProfile = computed(() => props.data.taskProfile || null)
const finalPlan = computed(() => props.data.finalPlan || {})
const summary = computed(() => finalPlan.value.summary || {})
const budget = computed(() => finalPlan.value.budget || {})
const days = computed(() => finalPlan.value.days || [])
const dailyGuide = computed(() => finalPlan.value.dailyGuide || [])
const hotelOptions = computed(() => finalPlan.value.hotelOptions || finalPlan.value.hotelRecommendation || [])
const primaryHotel = computed(() => hotelOptions.value[0] || null)
const attractionRecommendations = computed(() => finalPlan.value.attractionRecommendations || [])
const foodRecommendations = computed(() => finalPlan.value.foodRecommendations || [])
const budgetInsights = computed(() => finalPlan.value.budgetInsights || [])
const tripTips = computed(() => finalPlan.value.tripTips || [])
const planHighlights = computed(() => finalPlan.value.planHighlights || [])
const stayAdvice = computed(() => finalPlan.value.stayAdvice || {})
const planningNarrative = computed(() => finalPlan.value.planningNarrative || '')
const mapData = computed(() => finalPlan.value.visual?.map || null)
const llmSummary = computed(() => props.data.llmOutput?.llm_summary || '')
const displaySummary = computed(() => sanitizeSummaryText(llmSummary.value))
const displaySummaryHtml = computed(() => renderSummaryMarkdown(displaySummary.value))
const planningNarrativeHtml = computed(() => renderSummaryMarkdown(planningNarrative.value))
const selectedMapDay = ref('all')
const amapFailed = ref(false)
const amapFailureMessage = ref('')
const isConsultingMode = computed(() => taskProfile.value?.task_type === 'travel_consulting')
const destinationLabel = computed(() => summary.value.destinationCity || '待确认目的地')
const summaryTagsText = computed(() => summary.value.tags?.length ? summary.value.tags.join(' / ') : '按你的要求整理')
const budgetSummaryLine = computed(() => {
  const total = formatCurrency(summary.value.totalBudget)
  const parts = []
  if (typeof budget.value.accommodation === 'number') parts.push(`住宿 ${formatCurrency(budget.value.accommodation)}`)
  if (typeof budget.value.transport === 'number') parts.push(`交通 ${formatCurrency(budget.value.transport)}`)
  return parts.length ? `${total} · ${parts.join(' / ')}` : total
})
const paceLabel = computed(() => {
  const tags = summary.value.tags || []
  if (tags.includes('intensive')) return '紧凑'
  if (tags.includes('relaxed')) return '轻松'
  return '均衡'
})
const consultingType = computed(() => finalPlan.value.consultingType || 'generic')
const consultingAnswer = computed(() => finalPlan.value.consultingAnswer || llmSummary.value || '暂无结果')
const mapDisplayMode = computed(() => (isConsultingMode.value ? 'consulting' : 'planning'))
const activeMapComponent = computed(() => {
  const hasAmapKey = Boolean(import.meta.env.VITE_AMAP_JS_KEY)
  const provider = String(import.meta.env.VITE_MAP_PROVIDER || '').trim().toLowerCase()
  const shouldUseAmap = hasAmapKey && provider !== 'local_preview' && !amapFailed.value
  return shouldUseAmap ? AmapTripMapPanel : TripMapPanel
})
const visualAssets = computed(() => finalPlan.value.visualAssets || {})
const heroAsset = computed(() => visualAssets.value.hero || null)
const heroImageUrl = computed(() => resolveVisualImageUrl(heroAsset.value))
const heroImageSrcSet = computed(() => resolveVisualImageSrcSet(heroAsset.value))
const heroImageLabel = computed(() => heroAsset.value?.label || '')
const heroImageLoading = computed(() => false)
const heroImageError = computed(() => '')
const attractionVisuals = computed(() => visualAssets.value.attractions || {})
const hotelVisuals = computed(() => visualAssets.value.hotels || {})
const foodVisuals = computed(() => visualAssets.value.foods || {})
const mapMarkerVisuals = computed(() => {
  const visualMap = {}
  collectMapMarkerVisuals(visualMap, attractionVisuals.value, '景点')
  collectMapMarkerVisuals(visualMap, hotelVisuals.value, '住宿')
  collectMapMarkerVisuals(visualMap, foodVisuals.value, '餐饮')
  return visualMap
})

const hotelShowcaseCards = computed(() => hotelOptions.value.slice(0, 3).map((item, index) => buildHotelCard(item, index)))
const attractionShowcaseCards = computed(() => attractionRecommendations.value.slice(0, 6).map((item, index) => buildAttractionCard(item, index)))
const foodShowcaseCards = computed(() => foodRecommendations.value.slice(0, 4).map((item, index) => buildFoodCard(item, index)))

const tripSnapshotCards = computed(() => {
  const cards = []
  if (primaryHotel.value) {
    cards.push(buildHotelCard(primaryHotel.value, 0, { compact: true, kicker: '住哪里' }))
  }
  if (attractionRecommendations.value[0]) {
    cards.push(buildAttractionCard(attractionRecommendations.value[0], 0, { compact: true, kicker: '先玩什么' }))
  }
  if (foodRecommendations.value[0]) {
    cards.push(buildFoodCard(foodRecommendations.value[0], 0, { compact: true, kicker: '吃什么' }))
  }
  return cards.map((card, index) => ({
    ...card,
    imageLoading: index === 0 ? 'eager' : 'lazy',
    imageFetchPriority: index === 0 ? 'high' : 'low',
  }))
})

const visualHeroChips = computed(() => {
  const chips = []
  if (summary.value.days) chips.push(`${summary.value.days} 天行程`)
  if (paceLabel.value) chips.push(`${paceLabel.value}节奏`)
  chips.push(...(summary.value.tags || []).slice(0, 3))
  return chips.length ? chips : ['按当前方案生成']
})

const heroIntroText = computed(() => {
  if (heroImageUrl.value) {
    return '这张图会作为你当前方案的目的地氛围参考，用于更直观地感受这趟旅行的场景调性。'
  }
  return '当前结果页不再实时生图，后续会直接接入本地预生成图片素材。'
})

const shouldShowVisualHero = computed(() => {
  if (isConsultingMode.value) return false
  return Boolean(destinationLabel.value && destinationLabel.value !== '待确认目的地' && heroImageUrl.value)
})

const heroImageAlt = computed(() => `${destinationLabel.value} 旅行氛围图`)
const dayTabs = computed(() => {
  const source = dailyGuide.value.length ? dailyGuide.value : days.value
  return source
    .map((item) => item?.day)
    .filter((item, index, array) => typeof item === 'number' && array.indexOf(item) === index)
})
const planFocusChips = computed(() => {
  const chips = []
  if (taskProfile.value?.complexity === 'complex') chips.push('预算与偏好一起考虑')
  if (primaryHotel.value?.name) chips.push('住宿已纳入推荐')
  if (dailyGuide.value.length || days.value.length) chips.push('按天拆分安排')
  if ((summary.value.tags || []).length) chips.push(...summary.value.tags.slice(0, 3))
  return chips.length ? chips : ['按你的要求整理']
})
const userFacingIntentSummary = computed(() => {
  if (isConsultingMode.value) return '这次回答更适合直接解决一个具体问题。'
  return '这份方案会优先围绕你的预算、出行天数、节奏和住宿餐饮偏好来安排，并把更适合直接参考的信息单独展开。'
})
const userFacingEvidenceSummary = computed(() => {
  if (isConsultingMode.value) {
    return '回答会结合当前识别到的城市、问题类型和可直接使用的信息来源来整理。'
  }
  return '方案综合参考了你的预算、节奏、住宿与餐饮偏好，以及系统整理出的景点、天气、酒店与路线结果。'
})
const consultingTitle = computed(() => {
  if (consultingType.value === 'weather') return '天气快览'
  if (consultingType.value === 'attraction') return '景点推荐'
  if (consultingType.value === 'clarification') return '还需要补充一个信息'
  return '咨询结果'
})
const consultingCards = computed(() => {
  if (consultingType.value === 'weather') {
    const weather = finalPlan.value.weather?.[0] || {}
    return [
      { title: '回答类型', value: '天气查询', extra: '' },
      { title: '适用城市', value: destinationLabel.value, extra: weather.summary || '' },
    ]
  }
  if (consultingType.value === 'attraction') {
    return [
      { title: '适用城市', value: destinationLabel.value, extra: '' },
      { title: '推荐数量', value: `${attractionRecommendations.value.length || 0} 个点位`, extra: attractionRecommendations.value[0]?.reason || '' },
    ]
  }
  if (consultingType.value === 'clarification') {
    const missingFields = finalPlan.value.missingFields || []
    const missingLabel = missingFields.includes('days') ? '出行天数' : '目的地城市'
    const suggestions = finalPlan.value.suggestedReplies?.join(' / ') || '深圳 / 北京 / 上海 / 成都'
    return [
      { title: '当前缺少', value: missingLabel, extra: consultingAnswer.value },
      { title: '可直接回复', value: suggestions, extra: '' },
    ]
  }
  return [{ title: '适用城市', value: destinationLabel.value, extra: consultingAnswer.value }]
})
const mapSelectionLabel = computed(() => {
  if (selectedMapDay.value === 'all') {
    return isConsultingMode.value ? '当前展示推荐点分布' : '当前展示全程路线'
  }
  return `当前展示 Day ${selectedMapDay.value}`
})
const mapSelectionHint = computed(() => {
  if (selectedMapDay.value === 'all') {
    return isConsultingMode.value
      ? '适合先看哪些点更集中、区域是否顺路。'
      : '适合先整体判断路线密度、住宿位置和景点分布。'
  }
  return '点击后的地图已经切到对应天数，不用滚动页面也能先在这里确认联动状态。'
})

watch(
  dayTabs,
  (tabs) => {
    if (!tabs.length) {
      selectedMapDay.value = 'all'
      return
    }
    if (selectedMapDay.value !== 'all' && !tabs.includes(selectedMapDay.value)) {
      selectedMapDay.value = 'all'
    }
  },
  { immediate: true }
)

watch(
  () => mapData.value,
  () => {
    amapFailed.value = false
    amapFailureMessage.value = ''
  }
)

function handleAmapFallback(error) {
  amapFailed.value = true
  if (error instanceof Error && error.message) {
    amapFailureMessage.value = `高德地图当前不可用：${error.message}，已切回本地预览。`
    return
  }
  amapFailureMessage.value = '高德地图当前不可用，已自动切回本地预览，不影响继续查看方案。'
}

function retryAmap() {
  resetAmapLoader()
  amapFailed.value = false
  amapFailureMessage.value = ''
}

async function focusMapDay(day) {
  selectedMapDay.value = day
  await nextTick()
}

function isMapFocusedDay(day) {
  return selectedMapDay.value === day
}

function formatCurrency(value) {
  if (typeof value !== 'number') {
    return '待定'
  }
  return `¥${value}`
}

function formatTagLabel(value) {
  const key = String(value || '').trim()
  if (!key) return ''
  return TAG_LABELS[key] || key.replaceAll('_', ' ')
}

function formatTypeLabel(value) {
  const key = String(value || '').trim()
  if (!key) return '推荐地点'
  return TYPE_LABELS[key] || key
}

function joinMeta(parts) {
  return parts.filter(Boolean).join(' · ')
}

function formatPricePerNight(value) {
  return typeof value === 'number' ? `${formatCurrency(value)}/晚` : '价格待定'
}

function buildHotelCard(item, index, options = {}) {
  const visual = hotelVisuals.value[item.name] || {}
  const chips = mapTagList(item.tags, options.compact ? 3 : 4)
  const badge = item.quiet ? '安静优先' : chips[0] || '住宿推荐'
  const summaryText =
    index === 0 && stayAdvice.value.reason
      ? stayAdvice.value.reason
      : buildHotelSummary(item)
  return {
    key: `hotel-${item.name}-${index}`,
    title: item.name,
    badge,
    priceLabel: formatPricePerNight(item.pricePerNight),
    meta: joinMeta([
      item.area || '区域待定',
      item.rating ? `评分 ${item.rating}` : '',
      typeof item.comfortScore === 'number' ? `舒适度 ${item.comfortScore}` : '',
    ]),
    summary: summaryText,
    supporting: visual.error || '',
    chips,
    imageUrl: resolveVisualImageUrl(visual),
    imageSrcSet: resolveVisualImageSrcSet(visual),
    fullImageUrl: resolveAssetUrl(visual.url || visual.imageUrl || ''),
    imageLabel: visual.label || '',
    imageAlt: `${item.name} 住宿示意图`,
    imageLoading: options.eager ? 'eager' : 'lazy',
    imageFetchPriority: options.eager ? 'high' : 'low',
    placeholder: '暂未生成住宿图',
    loading: Boolean(visual.loading),
    featured: index === 0,
    kicker: options.kicker || '',
  }
}

function buildAttractionCard(item, index, options = {}) {
  const visual = attractionVisuals.value[item.name] || {}
  return {
    key: `attraction-${item.name}-${index}`,
    title: item.name,
    badge: item.typeLabel || formatTypeLabel(item.type),
    meta: joinMeta([
      item.area || '区域待定',
      typeof item.durationHours === 'number' ? `${item.durationHours} 小时` : '',
      typeof item.cost === 'number' ? (item.cost > 0 ? `门票 ${formatCurrency(item.cost)}` : '多数免费或低门槛') : '',
    ]),
    summary: item.reason || buildAttractionSummary(item),
    chips: mapTagList(item.tags, options.compact ? 3 : 4),
    imageUrl: resolveVisualImageUrl(visual),
    imageSrcSet: resolveVisualImageSrcSet(visual),
    fullImageUrl: resolveAssetUrl(visual.url || visual.imageUrl || ''),
    imageLabel: visual.label || '',
    imageAlt: `${item.name} 景点示意图`,
    imageLoading: options.eager ? 'eager' : 'lazy',
    imageFetchPriority: options.eager ? 'high' : 'low',
    placeholder: '暂未生成景点图',
    loading: Boolean(visual.loading),
    kicker: options.kicker || '',
  }
}

function buildFoodCard(item, index, options = {}) {
  const visual = foodVisuals.value[item.name] || {}
  return {
    key: `food-${item.name}-${index}`,
    title: item.name,
    badge: item.style || '顺路用餐',
    meta: joinMeta([
      item.area || '区域待定',
      typeof item.estimatedCost === 'number' ? (item.estimatedCost > 0 ? `额外花费 ${formatCurrency(item.estimatedCost)}` : '通常无需额外门票') : '顺路补给友好',
    ]),
    summary: item.reason || buildFoodSummary(item),
    supporting: item.knowledgeTip || visual.error || '',
    chips: mapTagList(item.tags, options.compact ? 3 : 4),
    imageUrl: resolveVisualImageUrl(visual),
    imageSrcSet: resolveVisualImageSrcSet(visual),
    fullImageUrl: resolveAssetUrl(visual.url || visual.imageUrl || ''),
    imageLabel: visual.label || '',
    imageAlt: `${item.name} 餐饮示意图`,
    imageLoading: options.eager ? 'eager' : 'lazy',
    imageFetchPriority: options.eager ? 'high' : 'low',
    placeholder: '暂未生成餐饮图',
    loading: Boolean(visual.loading),
    kicker: options.kicker || '',
  }
}

function buildHotelSummary(item) {
  const fragments = []
  if (item.quiet) {
    fragments.push('更适合回到酒店后安静休息，减少夜间噪音干扰。')
  } else {
    fragments.push('更适合喜欢下楼就能接上商圈或夜生活氛围的人。')
  }
  if (typeof item.comfortScore === 'number') {
    fragments.push(item.comfortScore >= 85 ? '住宿舒适度偏高，住得会更放松。' : '住宿体验稳妥，适合把预算留给白天行程。')
  }
  return fragments.join('')
}

function buildAttractionSummary(item) {
  const typeLabel = item.typeLabel || formatTypeLabel(item.type)
  return `${typeLabel}体验更集中在 ${item.area || '核心片区'}，适合作为这趟行程里优先安排的一站。`
}

function buildFoodSummary(item) {
  return `${item.area || '这一片'}更适合顺路安排一顿本地口味，不需要专门绕远也能吃到氛围感。`
}

function mapTagList(tags, limit = 4) {
  if (!Array.isArray(tags)) return []
  return tags
    .map(formatTagLabel)
    .filter(Boolean)
    .slice(0, limit)
}

function resolveVisualImageUrl(visual) {
  if (!visual) return ''
  return resolveAssetUrl(visual.thumbnailUrl || visual.url || visual.imageUrl || '')
}

function collectMapMarkerVisuals(target, source, fallbackLabel) {
  if (!source || typeof source !== 'object') return
  for (const [rawName, visual] of Object.entries(source)) {
    const name = String(rawName || '').trim()
    if (!name || !visual) continue
    const imageUrl = resolveVisualImageUrl(visual)
    if (!imageUrl) continue
    target[name] = {
      imageUrl,
      imageSrcSet: resolveVisualImageSrcSet(visual),
      imageAlt: `${name} ${fallbackLabel}图片`,
      label: visual.label || fallbackLabel,
    }
  }
}

function resolveVisualImageSrcSet(visual) {
  if (!visual) return ''
  if (visual.thumbnailSrcSet) {
    return String(visual.thumbnailSrcSet)
      .split(',')
      .map((part) => {
        const [url, width] = part.trim().split(/\s+/)
        return url && width ? `${resolveAssetUrl(url)} ${width}` : ''
      })
      .filter(Boolean)
      .join(', ')
  }
  const thumbnailUrls = visual.thumbnailUrls || {}
  return Object.entries(thumbnailUrls)
    .map(([width, url]) => {
      const normalizedUrl = resolveAssetUrl(url)
      return normalizedUrl ? `${normalizedUrl} ${width}w` : ''
    })
    .filter(Boolean)
    .join(', ')
}

function sanitizeSummaryText(value) {
  if (!value) return ''
  return value
    .split(/\n#{1,6}\s*最终计划/)
    .shift()
    .split(/\n\*\*最终计划\*\*/)
    .shift()
    .split(/\n最终计划[:：]/)
    .shift()
    .replace(/```(?:json)?[\s\S]*?```/g, '')
    .split('```')[0]
    .trim()
}

function renderSummaryMarkdown(value) {
  const normalized = sanitizeSummaryText(value)
  if (!normalized) return ''

  const lines = normalized.replace(/\r\n/g, '\n').split('\n')
  const html = []
  let paragraph = []
  let listItems = []

  const flushParagraph = () => {
    if (!paragraph.length) return
    html.push(`<p>${renderInlineMarkdown(paragraph.join('<br />'))}</p>`)
    paragraph = []
  }

  const flushList = () => {
    if (!listItems.length) return
    html.push(`<ul>${listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join('')}</ul>`)
    listItems = []
  }

  lines.forEach((rawLine) => {
    const line = rawLine.trim()
    if (!line) {
      flushParagraph()
      flushList()
      return
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      flushParagraph()
      flushList()
      const level = Math.min(headingMatch[1].length, 4)
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`)
      return
    }

    const listMatch = line.match(/^[-*]\s+(.+)$/)
    if (listMatch) {
      flushParagraph()
      listItems.push(listMatch[1])
      return
    }

    const orderedListMatch = line.match(/^\d+\.\s+(.+)$/)
    if (orderedListMatch) {
      flushParagraph()
      listItems.push(orderedListMatch[1])
      return
    }

    flushList()
    paragraph.push(escapeHtml(line))
  })

  flushParagraph()
  flushList()
  return html.join('')
}

function renderInlineMarkdown(value) {
  return value
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/(^|[\s(])\*([^*]+)\*(?=[\s).,，。！？!?:：]|$)/g, '$1<em>$2</em>')
    .replace(/(^|[\s(])_([^_]+)_(?=[\s).,，。！？!?:：]|$)/g, '$1<em>$2</em>')
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}
</script>
