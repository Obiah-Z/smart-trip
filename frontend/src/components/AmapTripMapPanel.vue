<template>
  <section class="result-block map-panel" :class="{ 'map-panel-compact': compact }" v-if="mapData">
    <div class="map-panel-head">
      <div>
        <h3>{{ mapData.title || '高德地图预览' }}</h3>
        <p class="muted-text compact-copy">{{ mapSubtitle }}</p>
      </div>
      <div class="map-head-side">
        <span class="chip subtle">{{ displayModeLabel }}</span>
        <span class="chip subtle">{{ markerCountLabel }}</span>
      </div>
    </div>

    <div v-if="!compact && displayMode === 'consulting'" class="map-mode-banner map-mode-banner-consulting">
      <div>
        <strong>推荐点分布视图</strong>
        <p class="muted-text compact-copy">当前更适合先看点位分布和区域聚合，方便继续追问“住哪更顺路”或“半天去哪几个点”。</p>
      </div>
    </div>
    <div v-else-if="!compact" class="map-mode-banner">
      <div>
        <strong>{{ selectedDay === 'all' ? '全程路线视图' : `Day ${selectedDay} 路线视图` }}</strong>
        <p class="muted-text compact-copy">高德地图会优先展示整段路线和关键点位，方便快速判断每天是否顺路。</p>
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

    <div class="amap-shell" :class="{ 'amap-shell-compact': compact }">
      <div ref="mapContainerRef" class="amap-canvas"></div>
      <div v-if="loading" class="map-status">正在加载高德地图...</div>
      <div v-if="errorMessage" class="map-status map-status-error">{{ errorMessage }}</div>
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { loadAmap } from '../lib/amap'

const emit = defineEmits(['fallback'])

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
})

const mapContainerRef = ref(null)
const mapInstance = shallowRef(null)
const currentOverlays = shallowRef([])
const resizeObserver = shallowRef(null)
const loading = ref(true)
const errorMessage = ref('')
let resizeFrameId = 0

const mapData = computed(() => props.data || null)
const markers = computed(() => mapData.value?.markers || [])
const routes = computed(() => mapData.value?.routes || [])
const diagnostics = computed(() => mapData.value?.diagnostics || null)
const selectedDay = computed(() => props.selectedDay)
const displayMode = computed(() => props.displayMode || 'planning')
const displayModeLabel = computed(() => (displayMode.value === 'consulting' ? '咨询地图' : '行程地图'))
const compact = computed(() => props.compact)
const focusOnly = computed(() => props.focusOnly)
const displayedRoutes = computed(() => {
  if (selectedDay.value === 'all') return routes.value
  return routes.value.filter((item) => item.day === selectedDay.value)
})
const activeMarkers = computed(() =>
  markers.value.filter((item) => {
    if (selectedDay.value === 'all') return true
    if (item.day === selectedDay.value) return true
    return item.type === 'hotel' || item.type === 'city_center'
  })
)
const visibleMarkers = computed(() => (focusOnly.value ? activeMarkers.value : markers.value))
const topMarkers = computed(() => visibleMarkers.value.slice(0, compact.value ? 4 : 6))
const markerCountLabel = computed(() => {
  if (selectedDay.value === 'all') return `${markers.value.length || 0} 个位置点`
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
const mapSubtitle = computed(() => {
  if (errorMessage.value) return '高德地图加载失败时会自动回退到本地预览。'
  return mapData.value?.subtitle || '已切换为高德地图渲染，点位和路线会优先使用真实地图能力。'
})

onMounted(async () => {
  await initializeMap()
  setupResizeObserver()
})

watch(
  [markers, displayedRoutes, selectedDay],
  () => {
    if (!mapInstance.value) return
    renderOverlays()
  },
  { deep: true }
)

watch(
  () => mapData.value,
  async () => {
    if (mapInstance.value || !mapContainerRef.value) return
    await initializeMap()
  }
)

onBeforeUnmount(() => {
  clearOverlays()
  teardownResizeObserver()
  if (mapInstance.value) {
    mapInstance.value.destroy()
    mapInstance.value = null
  }
})

async function initializeMap() {
  loading.value = true
  errorMessage.value = ''
  try {
    const AMap = await loadAmap()
    if (!mapContainerRef.value) return
    const center = mapData.value?.center || { lng: 116.3974, lat: 39.9093 }
    mapInstance.value = new AMap.Map(mapContainerRef.value, {
      viewMode: '3D',
      zoom: Number(mapData.value?.zoom || 11),
      center: [Number(center.lng), Number(center.lat)],
      resizeEnable: true,
      mapStyle: 'amap://styles/normal',
    })
    mapInstance.value.addControl(new AMap.Scale())
    mapInstance.value.addControl(new AMap.ToolBar({ position: 'RB' }))
    renderOverlays()
    await nextTick()
    resizeMap()
  } catch (error) {
    const detail = error instanceof Error && error.message ? `：${error.message}` : ''
    errorMessage.value = `高德地图加载失败，已回退到本地预览${detail}`
    emit('fallback', error)
  } finally {
    loading.value = false
  }
}

function renderOverlays() {
  if (!mapInstance.value || !window.AMap) return
  const AMap = window.AMap
  resizeMap()
  clearOverlays()

  const overlays = []
  for (const item of visibleMarkers.value) {
    const marker = new AMap.Marker({
      position: [Number(item.lng), Number(item.lat)],
      offset: new AMap.Pixel(-12, -12),
      content: buildMarkerContent(item),
      title: item.name,
    })
    marker.on('click', () => {
      const infoWindow = new AMap.InfoWindow({
        offset: new AMap.Pixel(0, -18),
        content: `
          <div class="amap-infowindow">
            <strong>${escapeHtml(item.name)}</strong>
            <div>${escapeHtml(item.typeLabel || item.type || '')}</div>
            <div>${escapeHtml(item.area || '核心城区')}</div>
          </div>
        `,
      })
      infoWindow.open(mapInstance.value, marker.getPosition())
    })
    overlays.push(marker)
  }

  for (const route of displayedRoutes.value) {
    if (!route.points?.length) continue
    overlays.push(
      new AMap.Polyline({
        path: route.points.map((point) => [Number(point.lng), Number(point.lat)]),
        strokeColor: route.color || '#3bb58f',
        strokeWeight: 6,
        strokeOpacity: 0.78,
        strokeStyle: 'solid',
        lineJoin: 'round',
        lineCap: 'round',
        showDir: true,
      })
    )
  }

  mapInstance.value.add(overlays)
  currentOverlays.value = overlays
  if (overlays.length) {
    mapInstance.value.setFitView(overlays, false, [80, 80, 80, 80], Number(mapData.value?.zoom || 11))
  }
}

function setupResizeObserver() {
  if (typeof ResizeObserver === 'undefined' || !mapContainerRef.value || resizeObserver.value) return
  const resizeTarget = mapContainerRef.value.closest('.map-overview-card') || mapContainerRef.value.parentElement
  if (!resizeTarget) return

  resizeObserver.value = new ResizeObserver(() => {
    resizeMap()
  })
  resizeObserver.value.observe(resizeTarget)
  resizeObserver.value.observe(mapContainerRef.value)
}

function teardownResizeObserver() {
  if (resizeObserver.value) {
    resizeObserver.value.disconnect()
    resizeObserver.value = null
  }
  if (resizeFrameId) {
    cancelAnimationFrame(resizeFrameId)
    resizeFrameId = 0
  }
}

function resizeMap() {
  if (resizeFrameId) cancelAnimationFrame(resizeFrameId)
  resizeFrameId = requestAnimationFrame(() => {
    resizeFrameId = 0
    mapInstance.value?.resize?.()
  })
}

function clearOverlays() {
  if (!mapInstance.value || !currentOverlays.value.length) return
  mapInstance.value.remove(currentOverlays.value)
  currentOverlays.value = []
}

function buildMarkerContent(item) {
  const label = item.day ? `D${item.day}` : markerAbbr(item.type)
  const background = markerColor(item.type)
  const opacity = isMarkerActive(item) ? 1 : 0.35
  return `
    <div style="
      width:24px;
      height:24px;
      border-radius:999px;
      background:${background};
      color:#fff;
      border:3px solid rgba(255,255,255,0.92);
      display:flex;
      align-items:center;
      justify-content:center;
      font-size:11px;
      font-weight:700;
      box-shadow:0 8px 16px rgba(31,93,74,0.18);
      opacity:${opacity};
    ">${escapeHtml(label)}</div>
  `
}

function markerColor(type) {
  if (type === 'city_center') return '#88a4b8'
  if (type === 'hotel') return '#2f9d74'
  if (type === 'food') return '#ef6f6c'
  return '#f59e0b'
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

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}
</script>
