<template>
  <section class="developer-runtime-snapshot">
    <div class="developer-card-header">
      <div>
        <p class="panel-kicker">Runtime</p>
        <h2>运行快照</h2>
        <p class="stage-copy">只保留链路排查需要的路由、槽位和产物结构，不重复展示用户结果正文。</p>
      </div>
      <span class="badge">{{ taskTypeLabel }}</span>
    </div>

    <div class="developer-snapshot-metrics">
      <article v-for="item in responseCards" :key="item.label" class="developer-mini-metric">
        <span class="metric-label">{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <p v-if="item.helper" class="muted-text">{{ item.helper }}</p>
      </article>
    </div>

    <section class="developer-snapshot-grid">
      <article class="developer-inspector-card">
        <div class="agent-head">
          <strong>请求与路由</strong>
          <span class="chip subtle">{{ taskProfile.complexity || 'unknown' }}</span>
        </div>
        <div class="keyvalue-list">
          <div class="keyvalue-row">
            <span>user_input</span>
            <strong class="debug-inline-value">{{ result.user_input || '空' }}</strong>
          </div>
          <div class="keyvalue-row">
            <span>session_id</span>
            <strong class="debug-inline-value">{{ sessionId || result.session_id || '未创建' }}</strong>
          </div>
          <div class="keyvalue-row">
            <span>session_found</span>
            <strong>{{ formatBoolean(result.session_context?.session_found) }}</strong>
          </div>
          <div class="keyvalue-row">
            <span>intent_summary</span>
            <strong class="debug-inline-value">{{ taskProfile.intent_summary || '暂无' }}</strong>
          </div>
        </div>
      </article>

      <article class="developer-inspector-card">
        <div class="agent-head">
          <strong>Task Profile</strong>
          <span class="chip subtle">{{ responseKind }}</span>
        </div>
        <div class="keyvalue-list">
          <div class="keyvalue-row" v-for="item in taskRows" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>

      <article class="developer-inspector-card">
        <div class="agent-head">
          <strong>结构化约束</strong>
          <span class="chip subtle">{{ constraints.destination || 'destination:null' }}</span>
        </div>
        <div class="keyvalue-list">
          <div class="keyvalue-row" v-for="item in constraintRows" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
        <div v-if="constraintChips.length" class="tag-cloud debug-tag-cloud">
          <span v-for="item in constraintChips" :key="item" class="chip subtle">{{ item }}</span>
        </div>
      </article>

      <article class="developer-inspector-card">
        <div class="agent-head">
          <strong>Final Plan 结构</strong>
          <span class="chip subtle">{{ Object.keys(finalPlan).length }} keys</span>
        </div>
        <div class="keyvalue-list">
          <div class="keyvalue-row" v-for="item in finalPlanRows" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="developer-snapshot-grid developer-snapshot-grid-secondary">
      <article class="developer-inspector-card">
        <div class="agent-head">
          <strong>Memory / RAG / Tool</strong>
          <span class="chip subtle">artifact counts</span>
        </div>
        <div class="keyvalue-list">
          <div class="keyvalue-row" v-for="item in artifactRows" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>

      <article class="developer-inspector-card">
        <div class="agent-head">
          <strong>LLM 输出状态</strong>
          <span class="chip subtle">{{ llmOutput.mode || 'unknown' }}</span>
        </div>
        <div class="keyvalue-list">
          <div class="keyvalue-row">
            <span>model</span>
            <strong class="debug-inline-value">{{ llmOutput.model || '未返回' }}</strong>
          </div>
          <div class="keyvalue-row">
            <span>summary_length</span>
            <strong>{{ llmSummaryLength }}</strong>
          </div>
          <div class="keyvalue-row">
            <span>prompt_sections</span>
            <strong>{{ result.assembled_context?.prompt_sections?.length || 0 }}</strong>
          </div>
          <div class="keyvalue-row">
            <span>raw_json</span>
            <strong>{{ responseSchemaBytes }}</strong>
          </div>
        </div>
      </article>
    </section>

    <details class="raw-details compact developer-raw-details">
      <summary>查看调试结构 JSON</summary>
      <pre>{{ responseSchemaJson }}</pre>
    </details>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  result: { type: Object, required: true },
  sessionId: { type: String, default: '' },
})

const result = computed(() => props.result || {})
const taskProfile = computed(() => result.value.task_profile || {})
const constraints = computed(() => result.value.structured_constraints || {})
const finalPlan = computed(() => result.value.final_plan || {})
const summary = computed(() => finalPlan.value.summary || {})
const budget = computed(() => finalPlan.value.budget || {})
const llmOutput = computed(() => result.value.llm_output || {})
const selectedSkills = computed(() => result.value.selected_skills || [])
const toolResults = computed(() => result.value.tool_results || [])
const agentOutputs = computed(() => result.value.agent_outputs || [])
const retrievedDocuments = computed(() => result.value.retrieval_context?.retrieved_documents || [])
const memoryUpdates = computed(() => result.value.memory_updates || [])
const hotelOptions = computed(() => finalPlan.value.hotelOptions || finalPlan.value.hotelRecommendation || [])
const dailyGuide = computed(() => finalPlan.value.dailyGuide || [])
const days = computed(() => finalPlan.value.days || [])
const mapData = computed(() => finalPlan.value.visual?.map || {})
const visualAssets = computed(() => finalPlan.value.visualAssets || {})

const taskTypeLabel = computed(() => {
  if (taskProfile.value.task_type === 'travel_consulting') return '咨询链路'
  if (taskProfile.value.task_type === 'travel_planning') return '规划链路'
  return '未知链路'
})

const responseKind = computed(() => {
  if (finalPlan.value.consultingType) return `consulting:${finalPlan.value.consultingType}`
  return summary.value.destinationCity ? 'planning:final_plan' : 'unknown'
})

const llmSummaryLength = computed(() => String(llmOutput.value.llm_summary || '').length)

const responseCards = computed(() => [
  {
    label: '响应类型',
    value: responseKind.value,
    helper: taskProfile.value.task_type || '未识别 task_type',
  },
  {
    label: '目的地 / 天数',
    value: `${constraints.value.destination || summary.value.destinationCity || '-'} / ${constraints.value.days || summary.value.days || '-'} 天`,
    helper: constraints.value._followup_replan ? 'follow-up replan' : 'current turn',
  },
  {
    label: '预算',
    value: formatCurrency(constraints.value.budget || summary.value.totalBudget),
    helper: budgetSummary.value,
  },
  {
    label: '输出结构',
    value: `${Object.keys(finalPlan.value).length} keys`,
    helper: `days ${days.value.length} / hotels ${hotelOptions.value.length}`,
  },
  {
    label: '链路产物',
    value: `${selectedSkills.value.length} skills / ${toolResults.value.length} tools`,
    helper: `${retrievedDocuments.value.length} chunks / ${agentOutputs.value.length} agents`,
  },
])

const taskRows = computed(() => [
  { label: 'task_type', value: taskProfile.value.task_type || '-' },
  { label: 'complexity', value: taskProfile.value.complexity || '-' },
  { label: 'needs_rag', value: formatBoolean(taskProfile.value.needs_rag) },
  { label: 'needs_tools', value: formatBoolean(taskProfile.value.needs_tools) },
  { label: 'needs_multi_agent', value: formatBoolean(taskProfile.value.needs_multi_agent) },
])

const constraintRows = computed(() => [
  { label: 'destination', value: constraints.value.destination || 'null' },
  { label: 'days', value: constraints.value.days ?? 'null' },
  { label: 'budget', value: formatCurrency(constraints.value.budget) },
  { label: 'pace', value: constraints.value.pace || 'balanced' },
  { label: 'excluded', value: listCount(constraints.value.excluded_attractions) },
  { label: 'expanded_excluded', value: listCount(constraints.value.expanded_excluded_attractions) },
])

const constraintChips = computed(() => [
  ...(constraints.value.preferences || []).map((item) => `pref:${item}`),
  ...(constraints.value.excluded_attractions || []).map((item) => `exclude:${item}`),
  ...(constraints.value.expanded_excluded_attractions || []).map((item) => `expanded:${item}`),
])

const finalPlanRows = computed(() => [
  { label: 'summary', value: summary.value.destinationCity ? `${summary.value.destinationCity} / ${summary.value.days || '-'} 天` : '未生成' },
  { label: 'consultingType', value: finalPlan.value.consultingType || '-' },
  { label: 'missingFields', value: listCount(finalPlan.value.missingFields) },
  { label: 'days', value: `${days.value.length} items` },
  { label: 'dailyGuide', value: `${dailyGuide.value.length} items` },
  { label: 'hotelOptions', value: `${hotelOptions.value.length} items` },
  { label: 'attractions', value: `${(finalPlan.value.attractionRecommendations || []).length} items` },
  { label: 'foods', value: `${(finalPlan.value.foodRecommendations || []).length} items` },
  { label: 'map', value: `${(mapData.value.markers || []).length} markers / ${(mapData.value.routes || []).length} routes` },
])

const artifactRows = computed(() => [
  { label: 'memory_updates', value: `${memoryUpdates.value.length} items` },
  { label: 'long_term_memory', value: `${(result.value.memory_context?.long_term_memory || []).length} items` },
  { label: 'relevant_memory', value: `${(result.value.memory_context?.relevant_long_term_memory || []).length} items` },
  { label: 'retrieved_documents', value: `${retrievedDocuments.value.length} chunks` },
  { label: 'selected_skills', value: selectedSkills.value.map((item) => item.skill_id).join(' / ') || 'none' },
  { label: 'tool_results', value: toolResults.value.map((item) => item.tool_name).join(' / ') || 'none' },
  { label: 'agent_outputs', value: agentOutputs.value.map((item) => item.agent).join(' / ') || 'none' },
])

const budgetSummary = computed(() => {
  const parts = []
  for (const [key, value] of Object.entries(budget.value)) {
    if (typeof value === 'number') parts.push(`${key}:${value}`)
  }
  return parts.length ? parts.join(' / ') : '未返回预算拆分'
})

const responseSchema = computed(() => ({
  response_keys: Object.keys(result.value),
  task_profile: taskProfile.value,
  structured_constraints: constraints.value,
  final_plan_shape: {
    keys: Object.keys(finalPlan.value),
    summary_keys: Object.keys(summary.value),
    consulting_type: finalPlan.value.consultingType || null,
    missing_fields: finalPlan.value.missingFields || [],
    counts: {
      days: days.value.length,
      dailyGuide: dailyGuide.value.length,
      hotelOptions: hotelOptions.value.length,
      attractionRecommendations: (finalPlan.value.attractionRecommendations || []).length,
      foodRecommendations: (finalPlan.value.foodRecommendations || []).length,
      tripTips: (finalPlan.value.tripTips || []).length,
      planHighlights: (finalPlan.value.planHighlights || []).length,
      mapMarkers: (mapData.value.markers || []).length,
      mapRoutes: (mapData.value.routes || []).length,
      visualAssetGroups: Object.keys(visualAssets.value).length,
    },
  },
  artifact_counts: {
    memory_updates: memoryUpdates.value.length,
    selected_skills: selectedSkills.value.length,
    tool_results: toolResults.value.length,
    agent_outputs: agentOutputs.value.length,
    retrieved_documents: retrievedDocuments.value.length,
    prompt_sections: result.value.assembled_context?.prompt_sections?.length || 0,
  },
  llm_output: {
    mode: llmOutput.value.mode || null,
    model: llmOutput.value.model || null,
    summary_length: llmSummaryLength.value,
  },
}))

const responseSchemaJson = computed(() => JSON.stringify(responseSchema.value, null, 2))
const responseSchemaBytes = computed(() => `${responseSchemaJson.value.length} chars`)

function formatBoolean(value) {
  if (value === true) return 'true'
  if (value === false) return 'false'
  return 'unknown'
}

function formatCurrency(value) {
  if (typeof value !== 'number' || Number.isNaN(value) || value <= 0) return '未指定'
  return `¥${value}`
}

function listCount(value) {
  if (!Array.isArray(value) || !value.length) return '0 items'
  return `${value.length} items`
}
</script>
