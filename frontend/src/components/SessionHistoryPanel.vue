<template>
  <section class="panel session-history-panel">
    <div class="panel-header">
      <div>
        <p class="panel-kicker">History</p>
        <h2>最近结果</h2>
      </div>
      <div class="session-history-actions">
        <span class="badge">{{ items.length }} 条</span>
        <button class="secondary" type="button" :disabled="loading" @click="$emit('refresh')">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <p class="muted-text">
      这里保留这个用户最近生成过的问答和行程结果。你可以重新打开继续追问，或者删除不再需要的记录。
    </p>

    <div v-if="loading && !items.length" class="history-empty-state">正在加载最近记录...</div>
    <div v-else-if="!items.length" class="history-empty-state">还没有最近记录。先生成一次结果，这里就会出现。</div>

    <div v-else class="session-history-grid">
      <article v-for="item in items" :key="item.session_id" class="history-result-card">
        <div class="history-result-topline">
          <span class="chip">{{ item.destination || '未确认城市' }}</span>
          <span class="chip subtle">{{ item.task_type === 'travel_planning' ? '旅行规划' : '旅行问答' }}</span>
        </div>
        <h3>{{ historyTitle(item) }}</h3>
        <p class="history-result-summary">{{ historySummary(item) }}</p>
        <div class="history-result-meta">
          <span>{{ formatDate(item.created_at) }}</span>
          <span>{{ item.days ? `${item.days} 天` : '即时结果' }}</span>
        </div>
        <div class="history-result-actions">
          <button class="secondary" type="button" @click="$emit('open', item)">重新打开</button>
          <button class="secondary danger-button" type="button" :disabled="deletingId === item.session_id" @click="$emit('delete', item)">
            {{ deletingId === item.session_id ? '删除中...' : '删除' }}
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  deletingId: {
    type: String,
    default: '',
  },
})

defineEmits(['refresh', 'open', 'delete'])

function historyTitle(item) {
  if (item.task_type === 'travel_planning') {
    return `${item.destination || '这次旅程'} ${item.days || ''} 天方案`
  }
  return item.destination ? `${item.destination} 相关问答` : '最近一次咨询'
}

function historySummary(item) {
  return item.summary || item.request_text || '暂无摘要'
}

function formatDate(value) {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
</script>
