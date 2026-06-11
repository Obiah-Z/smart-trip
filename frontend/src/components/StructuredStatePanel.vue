<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="panel-kicker">Slots</p>
        <h2>结构化槽位</h2>
      </div>
      <span class="badge">{{ destinationLabel }}</span>
    </div>

    <div v-if="isConsultingMode" class="constraint-grid compact-constraint-grid">
      <article class="mini-card">
        <span class="metric-label">destination</span>
        <strong>{{ destinationLabel }}</strong>
      </article>
      <article class="mini-card">
        <span class="metric-label">consulting_type</span>
        <strong>{{ consultingTypeLabel }}</strong>
      </article>
    </div>

    <div v-else class="constraint-grid">
      <article class="mini-card">
        <span class="metric-label">destination</span>
        <strong>{{ destinationLabel }}</strong>
      </article>
      <article class="mini-card">
        <span class="metric-label">days</span>
        <strong>{{ data.days ? `${data.days} 天` : '待确认' }}</strong>
      </article>
      <article class="mini-card">
        <span class="metric-label">budget</span>
        <strong>{{ data.budget ? `¥${data.budget}` : '未指定' }}</strong>
      </article>
      <article class="mini-card">
        <span class="metric-label">pace</span>
        <strong>{{ paceLabel }}</strong>
      </article>
    </div>

    <div class="subsection" v-if="displayPreferences.length">
      <h3>preferences</h3>
      <div class="tag-cloud" :class="{ 'compact-tag-cloud': isConsultingMode }">
        <span v-for="item in displayPreferences" :key="item" class="chip">{{ displayPreference(item) }}</span>
      </div>
    </div>

    <p v-if="isConsultingMode && !displayPreferences.length" class="muted-text">
      当前请求没有抽取到可注入偏好，咨询链路会按轻量问答处理。
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Object, required: true },
  taskProfile: { type: Object, required: true },
})

const PREFERENCE_LABELS = {
  food: '重点餐饮',
  local_food: '本地特色',
  avoid_food: '少安排餐饮',
  avoid_local_food: '不吃本地特色',
  quiet_hotel: '安静酒店',
  lively_hotel: '热闹酒店',
  comfortable_hotel: '更重视住宿舒适度',
  culture: '文化体验',
  nature: '自然景点',
  metro: '地铁出行',
  high_speed_rail: '高铁出行',
}

const isConsultingMode = computed(() => props.taskProfile?.task_type === 'travel_consulting')
const destinationLabel = computed(() => props.data.destination || '待确认目的地')
const displayPreferences = computed(() => (props.data.preferences || []).filter((item) => !String(item).startsWith('_')))
const paceLabel = computed(() => {
  if (props.data.pace === 'relaxed') return '轻松'
  if (props.data.pace === 'intensive') return '紧凑'
  return '均衡'
})
const consultingTypeLabel = computed(() => {
  if (!props.data.destination) return '等待补充城市'
  if (!props.data.days && props.taskProfile?.intent_summary?.includes('关键条件')) return '等待补充天数'
  if (displayPreferences.value.includes('culture') || displayPreferences.value.includes('nature')) {
    return '偏好导向咨询'
  }
  return '轻量旅行问答'
})

function displayPreference(value) {
  return PREFERENCE_LABELS[value] || value
}
</script>
