<template>
  <section class="result-block map-panel" :class="{ 'map-panel-compact': compact }" v-if="mapData">
    <div class="map-panel-head">
      <div>
        <h3>{{ mapData.title || '位置预览' }}</h3>
        <p class="muted-text compact-copy">{{ mapData.subtitle }}</p>
      </div>
      <div class="map-head-side">
        <span class="chip subtle">{{ displayModeLabel }}</span>
        <span class="chip subtle">{{ markerCountLabel }}</span>
      </div>
    </div>

    <div v-if="!compact && displayMode === 'consulting'" class="map-mode-banner map-mode-banner-consulting">
      <div>
        <strong>推荐点分布视图</strong>
        <p class="muted-text compact-copy">更适合先判断这些点集中在哪些片区，值不值得继续往酒店、路线或半日安排细化。</p>
      </div>
    </div>
    <div v-else-if="!compact" class="map-mode-banner">
      <div>
        <strong>{{ selectedDay === 'all' ? '全程路线视图' : `Day ${selectedDay} 路线视图` }}</strong>
        <p class="muted-text compact-copy">优先看住宿、景点与餐饮点是否顺路，再判断当天是否过满。</p>
      </div>
    </div>

    <div v-if="!compact" class="map-legend">
      <span class="legend-item">
        <span class="legend-dot legend-dot-city"></span>
        城市中心
      </span>
      <span class="legend-item">
        <span class="legend-dot legend-dot-hotel"></span>
        住宿
      </span>
      <span class="legend-item">
        <span class="legend-dot legend-dot-attraction"></span>
        景点
      </span>
      <span class="legend-item">
        <span class="legend-dot legend-dot-food"></span>
        餐饮
      </span>
    </div>

    <div v-if="!compact && diagnosticsSummary" class="map-diagnostics">
      <span class="chip subtle">{{ diagnosticsSummary }}</span>
    </div>

    <div class="map-surface" :class="{ 'map-surface-compact': compact }" v-if="visibleProjectedMarkers.length">
      <svg class="map-svg" viewBox="0 0 1000 620" preserveAspectRatio="none" aria-label="行程位置预览图">
        <defs>
          <linearGradient id="mapBgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#eefbf6" />
            <stop offset="55%" stop-color="#f7fffb" />
            <stop offset="100%" stop-color="#fff7eb" />
          </linearGradient>
        </defs>

        <rect x="0" y="0" width="1000" height="620" rx="28" fill="url(#mapBgGradient)" />
        <path class="map-river" d="M120 120 C260 160, 360 80, 520 128 S760 240, 920 214" />
        <path class="map-river map-river-soft" d="M60 450 C220 420, 320 500, 520 454 S770 350, 950 392" />

        <g
          v-for="route in displayedRoutes"
          :key="route.day || route.label"
          :class="{ 'map-route-group-muted': selectedDay !== 'all' && route.day !== selectedDay }"
        >
          <polyline
            class="map-route-line"
            :points="buildPolyline(route)"
            :stroke="route.color || '#3bb58f'"
          />
        </g>

        <g
          v-for="item in visibleProjectedMarkers"
          :key="item.id"
          class="map-marker-hit-area"
          @mouseenter="hoveredMarkerId = item.id"
          @mouseleave="hoveredMarkerId = ''"
          @focusin="hoveredMarkerId = item.id"
          @focusout="hoveredMarkerId = ''"
          tabindex="0"
        >
          <line
            class="map-marker-guide"
            :class="{ 'map-marker-guide-muted': !item.isActive }"
            :x1="item.x"
            :x2="item.x"
            :y1="item.y"
            :y2="item.y + 26"
          />
          <circle
            class="map-marker-circle"
            :class="[`map-marker-${item.type}`, { 'map-marker-muted': !item.isActive }]"
            :cx="item.x"
            :cy="item.y"
            :r="item.type === 'hotel' ? 13 : 11"
          />
          <text class="map-marker-day" :class="{ 'map-marker-day-muted': !item.isActive }" :x="item.x" :y="item.y + 4">
            {{ item.day ? `D${item.day}` : markerAbbr(item.type) }}
          </text>
          <g :class="{ 'map-label-muted': !item.isActive }" :transform="labelTransform(item)">
            <rect class="map-label-card" width="176" height="56" rx="14" />
            <text class="map-label-title" x="14" y="22">{{ truncate(item.name, 12) }}</text>
            <text class="map-label-meta" x="14" y="40">{{ item.typeLabel }} · {{ truncate(item.area || '核心区', 10) }}</text>
          </g>
        </g>
      </svg>
      <div
        v-if="hoveredMarkerVisual"
        class="map-marker-preview"
        :class="{ 'map-marker-preview-compact': compact }"
        :style="hoveredMarkerPreviewStyle"
      >
        <img
          :src="hoveredMarkerVisual.imageUrl"
          :srcset="hoveredMarkerVisual.imageSrcSet || undefined"
          sizes="120px"
          :alt="hoveredMarkerVisual.imageAlt"
          loading="lazy"
          decoding="async"
        />
        <div>
          <strong>{{ hoveredMarkerVisual.name }}</strong>
          <span>{{ hoveredMarkerVisual.area }}</span>
        </div>
      </div>
    </div>

    <div class="map-marker-list" :class="{ 'map-marker-list-compact': compact }" v-if="topMarkers.length">
      <article v-for="item in topMarkers" :key="item.id" class="mini-card map-marker-card">
        <div class="recommendation-head">
          <strong>{{ item.name }}</strong>
          <span class="chip subtle">{{ item.typeLabel }}</span>
        </div>
        <p class="muted-text compact-copy">
          {{ item.area || '核心城区' }}
          <span v-if="item.day"> · Day {{ item.day }}</span>
        </p>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  data: {
    type: Object,
    default: () => ({}),
  },
  displayMode: {
    type: String,
    default: 'planning',
  },
  selectedDay: {
    type: [Number, String],
    default: 'all',
  },
  compact: {
    type: Boolean,
    default: false,
  },
  focusOnly: {
    type: Boolean,
    default: false,
  },
  markerVisuals: {
    type: Object,
    default: () => ({}),
  },
})

const hoveredMarkerId = ref('')
const mapData = computed(() => props.data || null)
const markers = computed(() => mapData.value?.markers || [])
const routes = computed(() => mapData.value?.routes || [])
const bounds = computed(() => mapData.value?.bounds || null)
const diagnostics = computed(() => mapData.value?.diagnostics || null)
const selectedDay = computed(() => props.selectedDay)
const displayMode = computed(() => props.displayMode || 'planning')
const displayModeLabel = computed(() => (displayMode.value === 'consulting' ? '咨询地图' : '行程地图'))
const compact = computed(() => props.compact)
const focusOnly = computed(() => props.focusOnly)
const markerVisuals = computed(() => props.markerVisuals || {})

const projectedMarkers = computed(() => {
  if (!bounds.value) return []
  const width = 1000
  const height = 620
  const leftPadding = 86
  const rightPadding = 86
  const topPadding = 74
  const bottomPadding = 96
  const usableWidth = width - leftPadding - rightPadding
  const usableHeight = height - topPadding - bottomPadding
  const lngSpan = Math.max(0.0001, bounds.value.max_lng - bounds.value.min_lng)
  const latSpan = Math.max(0.0001, bounds.value.max_lat - bounds.value.min_lat)

  return markers.value.map((item, index) => {
    const x = leftPadding + ((item.lng - bounds.value.min_lng) / lngSpan) * usableWidth
    const y = topPadding + (1 - (item.lat - bounds.value.min_lat) / latSpan) * usableHeight
    const labelOffsetY = index % 2 === 0 ? -68 : 20
    const labelOffsetX = index % 3 === 0 ? -24 : 18
    return {
      ...item,
      x: clamp(x, 52, width - 228),
      y: clamp(y, 58, height - 112),
      labelX: clamp(x + labelOffsetX, 18, width - 194),
      labelY: clamp(y + labelOffsetY, 18, height - 70),
      isActive: isMarkerActive(item),
    }
  })
})

const displayedRoutes = computed(() => {
  if (selectedDay.value === 'all') return routes.value
  return routes.value.filter((item) => item.day === selectedDay.value)
})
const activeMarkers = computed(() => projectedMarkers.value.filter((item) => item.isActive))
const visibleProjectedMarkers = computed(() => (focusOnly.value ? activeMarkers.value : projectedMarkers.value))
const hoveredMarker = computed(() => visibleProjectedMarkers.value.find((item) => item.id === hoveredMarkerId.value) || null)
const hoveredMarkerVisual = computed(() => {
  const marker = hoveredMarker.value
  if (!marker) return null
  const visual = markerVisuals.value[marker.name]
  if (!visual?.imageUrl) return null
  return {
    ...visual,
    name: marker.name,
    area: marker.area || marker.typeLabel || '核心城区',
  }
})
const hoveredMarkerPreviewStyle = computed(() => {
  const marker = hoveredMarker.value
  if (!marker) return {}
  const width = 1000
  const height = 620
  const left = `${(marker.x / width) * 100}%`
  const topOffset = compact.value ? 104 : 118
  const top = `${(Math.max(28, marker.y - topOffset) / height) * 100}%`
  const translateX = marker.x > width - 190 ? '-96%' : marker.x < 190 ? '-4%' : '-50%'
  return {
    left,
    top,
    transform: `translate(${translateX}, 0)`,
  }
})
const topMarkers = computed(() => {
  if (focusOnly.value) return activeMarkers.value.slice(0, compact.value ? 4 : 6)
  if (!activeMarkers.value.length) return projectedMarkers.value.slice(0, compact.value ? 4 : 6)
  return activeMarkers.value.slice(0, compact.value ? 4 : 6)
})
const markerCountLabel = computed(() => {
  if (selectedDay.value === 'all') {
    return `${markers.value.length || 0} 个位置点`
  }
  return `Day ${selectedDay.value} · ${activeMarkers.value.length || 0} 个点`
})
const diagnosticsSummary = computed(() => {
  if (!diagnostics.value?.total_markers) return ''
  const markerParts = []
  const routeParts = []

  if (diagnostics.value.registry_count) markerParts.push(`注册 ${diagnostics.value.registry_count}`)
  if (diagnostics.value.amap_cache_count) markerParts.push(`高德缓存 ${diagnostics.value.amap_cache_count}`)
  if (diagnostics.value.amap_poi_count) markerParts.push(`高德POI ${diagnostics.value.amap_poi_count}`)
  if (diagnostics.value.amap_tip_count) markerParts.push(`输入提示 ${diagnostics.value.amap_tip_count}`)
  if (diagnostics.value.amap_geocode_count) markerParts.push(`地理编码 ${diagnostics.value.amap_geocode_count}`)
  if (diagnostics.value.generated_count) markerParts.push(`兜底推断 ${diagnostics.value.generated_count}`)

  if (diagnostics.value.walking_route_count) routeParts.push(`真实步行路线 ${diagnostics.value.walking_route_count}`)
  if (diagnostics.value.route_cache_count) routeParts.push(`路线缓存 ${diagnostics.value.route_cache_count}`)
  if (diagnostics.value.fallback_route_count) routeParts.push(`直连线 ${diagnostics.value.fallback_route_count}`)

  const markerText = markerParts.length ? `点位：${markerParts.join(' / ')}` : '点位：待解析'
  const routeText = routeParts.length ? `路线：${routeParts.join(' / ')}` : '路线：待生成'
  return `${markerText}；${routeText}`
})

function buildPolyline(route) {
  if (!bounds.value || !route?.points?.length) return ''
  const width = 1000
  const height = 620
  const leftPadding = 86
  const rightPadding = 86
  const topPadding = 74
  const bottomPadding = 96
  const usableWidth = width - leftPadding - rightPadding
  const usableHeight = height - topPadding - bottomPadding
  const lngSpan = Math.max(0.0001, bounds.value.max_lng - bounds.value.min_lng)
  const latSpan = Math.max(0.0001, bounds.value.max_lat - bounds.value.min_lat)

  return route.points
    .map((point) => {
      const x = leftPadding + ((point.lng - bounds.value.min_lng) / lngSpan) * usableWidth
      const y = topPadding + (1 - (point.lat - bounds.value.min_lat) / latSpan) * usableHeight
      return `${clamp(x, 52, width - 228)},${clamp(y, 58, height - 112)}`
    })
    .join(' ')
}

function labelTransform(item) {
  return `translate(${item.labelX} ${item.labelY})`
}

function markerAbbr(type) {
  if (type === 'city_center') return '城'
  if (type === 'hotel') return '住'
  if (type === 'food') return '吃'
  return '玩'
}

function isMarkerActive(item) {
  if (selectedDay.value === 'all') return true
  if (item.day === selectedDay.value) return true
  return item.type === 'hotel' || item.type === 'city_center'
}

function truncate(value, maxLength) {
  if (!value) return ''
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}
</script>
