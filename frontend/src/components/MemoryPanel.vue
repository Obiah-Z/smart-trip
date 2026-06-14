<template>
  <section class="panel memory-panel">
    <div class="panel-header">
      <div>
        <p class="panel-kicker">Memory</p>
        <h2>Memory Store</h2>
      </div>
      <span class="badge">{{ memories.length }} records</span>
    </div>

    <div class="memory-form">
      <input :value="draft.key" placeholder="偏好字段" @input="$emit('update:draft', { ...draft, key: $event.target.value })" />
      <input :value="draft.value" placeholder="偏好内容" @input="$emit('update:draft', { ...draft, value: $event.target.value })" />
      <input :value="draft.scope" placeholder="偏好分组" @input="$emit('update:draft', { ...draft, scope: $event.target.value })" />
      <button class="secondary" @click="$emit('save')">保存偏好</button>
    </div>

    <div class="subsection">
      <div class="memory-section-head">
        <h3>active_memory_projection</h3>
        <span class="chip subtle">{{ activeMemoryCards.length }} items</span>
      </div>
      <div class="memory-summary-grid" v-if="activeMemoryCards.length">
        <article v-for="item in activeMemoryCards" :key="item.key" class="memory-summary-card">
          <span class="metric-label">{{ item.label }}</span>
          <strong>{{ item.displayValue }}</strong>
          <span class="memory-meta">{{ item.explanation }}</span>
        </article>
      </div>
      <p class="muted-text" v-else>当前用户没有长期 Memory，链路会只使用本轮输入和短期状态。</p>
    </div>

    <div class="subsection" v-if="memoryProfiles.length">
      <div class="memory-section-head">
        <h3>memory_profiles</h3>
        <span class="chip subtle">{{ memoryProfiles.length }} profiles</span>
      </div>
      <div class="memory-summary-grid">
        <article v-for="item in memoryProfiles" :key="item.key" class="memory-summary-card">
          <span class="metric-label">{{ item.label }}</span>
          <strong>{{ item.displayValue }}</strong>
          <span class="memory-meta">{{ item.explanation }}</span>
        </article>
      </div>
    </div>

    <details class="memory-collapse" :open="Boolean(latestUpdates.length)">
      <summary class="memory-collapse-summary">
        <span>memory_writeback</span>
        <span class="chip subtle">{{ latestUpdates.length }} items</span>
      </summary>
      <div class="subsection collapse-body">
        <p class="muted-text" v-if="!latestUpdates.length">本轮没有触发长期 Memory 写回。</p>
        <div class="memory-list" v-else>
          <article v-for="item in latestUpdates" :key="`${item.key}-${item.value}`" class="memory-item memory-item-highlight">
            <div class="memory-topline">
              <strong>{{ displayLabel(item.key) }}</strong>
              <span class="chip subtle">{{ item.scope }}</span>
            </div>
            <p>{{ displayValue(item.key, item.value) }}</p>
            <span class="memory-meta">{{ explainValue(item.key, item.value) }}</span>
          </article>
        </div>
      </div>
    </details>

    <details class="memory-collapse">
      <summary class="memory-collapse-summary">
        <span>all_memory_records</span>
        <span class="chip subtle">{{ memories.length }} items</span>
      </summary>
      <div class="subsection collapse-body">
        <p class="muted-text">这里展示当前 user_id 下的长期 Memory 记录；与本轮写回冲突的旧值会弱化显示。</p>
        <div class="memory-list" v-if="memories.length">
          <article
            v-for="item in memories"
            :key="`${item.key}-${item.updated_at}`"
            class="memory-item"
            :class="{ 'memory-item-dim': isOverridden(item) }"
          >
            <div class="memory-topline">
              <strong>{{ displayLabel(item.key) }}</strong>
              <span class="chip subtle">{{ item.scope }}</span>
            </div>
            <p>{{ displayValue(item.key, item.value) }}</p>
            <span class="memory-meta">
              {{ isOverridden(item) ? '已被本轮新值覆盖' : explainValue(item.key, item.value) }}
            </span>
            <span class="memory-meta">{{ formatTime(item.updated_at) }}</span>
          </article>
        </div>
        <p v-else class="muted-text">当前 user_id 没有长期 Memory 记录。</p>
      </div>
    </details>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  draft: { type: Object, required: true },
  memories: { type: Array, required: true },
  latestUpdates: { type: Array, required: true },
})

defineEmits(['update:draft', 'save'])

const LABEL_MAP = {
  hotel_style: '住宿风格',
  preference_quiet_hotel: '安静住宿偏好',
  preference_local_food: '本地特色餐饮',
  preference_food: '餐饮偏好',
  preference_culture: '文化偏好',
  preference_nature: '自然偏好',
  preference_museum: '博物馆偏好',
  preference_citywalk: 'Citywalk 偏好',
  preference_metro: '地铁出行偏好',
  preference_high_speed_rail: '高铁出行偏好',
  preference_family: '亲子偏好',
  travel_pace: '行程节奏',
  'profile:accommodation': '住宿画像',
  'profile:food': '餐饮画像',
  'profile:interests': '兴趣画像',
  'profile:transport': '交通画像',
  'profile:pace': '节奏画像',
  'profile:traveler': '出行人群画像',
}

const VALUE_MAP = {
  prefer_quiet_location: '偏安静区域',
  prefer_lively_location: '偏热闹区域',
  quiet_hotel: '希望安静',
  avoid_quiet_hotel: '不想太安静',
  local_food: '想吃本地特色',
  avoid_local_food: '不想吃本地特色',
  food: '愿意重点安排餐饮',
  avoid_food: '不想重点安排餐饮',
  culture: '偏文化体验',
  nature: '偏自然景点',
  metro: '偏地铁出行',
  high_speed_rail: '偏高铁出行',
  relaxed: '轻松',
  balanced: '均衡',
  intensive: '紧凑',
}

const EXPLANATION_MAP = {
  hotel_style: {
    prefer_quiet_location: '后续更偏向安静住宿区域。',
    prefer_lively_location: '后续更偏向商圈或热闹住宿区域。',
  },
  preference_quiet_hotel: {
    quiet_hotel: '会优先筛选安静型酒店。',
    avoid_quiet_hotel: '不会优先筛选安静型酒店。',
  },
  preference_local_food: {
    local_food: '路线和推荐会偏向本地特色餐饮。',
    avoid_local_food: '路线会尽量避开本地特色餐饮。',
  },
  preference_food: {
    food: '会把餐饮作为重点安排项。',
    avoid_food: '不会把餐饮作为重点安排项。',
  },
  travel_pace: {
    relaxed: '行程节奏会更松一些。',
    balanced: '行程节奏保持均衡。',
    intensive: '行程节奏会更紧凑一些。',
  },
  'profile:accommodation': {
    __default: '住宿维度已沉淀为稳定画像。',
  },
  'profile:food': {
    __default: '餐饮维度已沉淀为稳定画像。',
  },
  'profile:interests': {
    __default: '兴趣维度已沉淀为稳定画像。',
  },
  'profile:transport': {
    __default: '交通维度已沉淀为稳定画像。',
  },
  'profile:pace': {
    __default: '节奏维度已沉淀为稳定画像。',
  },
  'profile:traveler': {
    __default: '出行人群维度已沉淀为稳定画像。',
  },
}

const latestUpdateMap = computed(() => {
  const map = new Map()
  for (const item of props.latestUpdates) {
    map.set(item.key, item.value)
  }
  return map
})

const activeMemoryCards = computed(() => {
  const source = props.latestUpdates.length
    ? props.latestUpdates
    : props.memories.map((item) => ({ key: item.key, value: item.value, scope: item.scope }))

  return source.map((item) => ({
    key: item.key,
    label: displayLabel(item.key),
    displayValue: displayValue(item.key, item.value),
    explanation: explainValue(item.key, item.value),
  }))
})

const memoryProfiles = computed(() => {
  return props.memories
    .filter((item) => String(item.key || '').startsWith('profile:'))
    .map((item) => {
      const parsed = safeParse(item.value)
      return {
        key: item.key,
        label: displayLabel(item.key),
        displayValue: profileDisplayValue(parsed),
        explanation: profileExplanation(item.key, parsed),
      }
    })
})

function displayLabel(key) {
  return LABEL_MAP[key] || key
}

function displayValue(key, value) {
  if (String(key || '').startsWith('profile:')) {
    const parsed = safeParse(value)
    return profileDisplayValue(parsed)
  }
  return VALUE_MAP[value] || value
}

function explainValue(key, value) {
  if (String(key || '').startsWith('profile:')) {
    return profileExplanation(key, safeParse(value))
  }
  return EXPLANATION_MAP[key]?.[value] || '该偏好会参与后续旅行规划。'
}

function profileDisplayValue(parsed) {
  const activeValues = parsed?.active_values || []
  if (!activeValues.length) {
    return '未激活'
  }
  return activeValues.join(' / ')
}

function profileExplanation(key, parsed) {
  const activeValues = parsed?.active_values || []
  if (!activeValues.length) {
    return '该维度目前没有稳定偏好。'
  }
  return `${activeValues.length} 条稳定信号，后续会优先沿用。`
}

function safeParse(value) {
  if (typeof value !== 'string') {
    return null
  }
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

function isOverridden(item) {
  if (!latestUpdateMap.value.has(item.key)) {
    return false
  }
  return latestUpdateMap.value.get(item.key) !== item.value
}

function formatTime(value) {
  if (!value) {
    return ''
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}
</script>
