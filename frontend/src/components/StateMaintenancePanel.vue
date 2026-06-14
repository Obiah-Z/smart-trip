<template>
  <section class="developer-state-panel">
    <div class="developer-card-header">
      <div>
        <p class="panel-kicker">State</p>
        <h2>状态维护</h2>
        <p class="stage-copy">
          Agent 状态会持续累积用户需求、结构化约束、历史会话、工具结果、规划草案和用户否定项，避免模型只看最近一轮输入。
        </p>
      </div>
      <span class="badge">{{ workflowEngineLabel }}</span>
    </div>

    <div class="state-maintenance-brief">
      <p>
        例如用户先说“想去成都玩三天”，后续补充“不吃辣，带老人，别太累”，这些信息应该进入同一个任务状态，
        并持续影响景点选择、餐饮建议、住宿位置和行程节奏。
      </p>
    </div>

    <div class="state-maintenance-grid">
      <article class="developer-inspector-card state-maintenance-card">
        <div class="agent-head">
          <strong>当前任务输入</strong>
          <span class="chip subtle">{{ sessionFoundLabel }}</span>
        </div>
        <div class="keyvalue-list">
          <div class="keyvalue-row">
            <span>user_input</span>
            <strong class="debug-inline-value">{{ result.user_input || '空' }}</strong>
          </div>
          <div class="keyvalue-row">
            <span>initial_request</span>
            <strong class="debug-inline-value">{{ sessionContext.initial_request_text || '未记录' }}</strong>
          </div>
          <div class="keyvalue-row">
            <span>history_messages</span>
            <strong>{{ historyMessages.length }} 条</strong>
          </div>
        </div>
      </article>

      <article class="developer-inspector-card state-maintenance-card">
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
      </article>

      <article class="developer-inspector-card state-maintenance-card">
        <div class="agent-head">
          <strong>偏好与否定项</strong>
          <span class="chip subtle">{{ preferenceSignalCount }} signals</span>
        </div>
        <div class="state-chip-cloud" v-if="preferenceSignals.length">
          <span v-for="item in preferenceSignals" :key="item" class="chip subtle">{{ item }}</span>
        </div>
        <p v-else class="muted-text">本轮还没有明确偏好或排除项。</p>
      </article>

      <article class="developer-inspector-card state-maintenance-card">
        <div class="agent-head">
          <strong>Memory 注入</strong>
          <span class="chip subtle">{{ relevantMemory.length }} active</span>
        </div>
        <div class="keyvalue-list">
          <div class="keyvalue-row">
            <span>long_term_memory</span>
            <strong>{{ longTermMemory.length }} 条</strong>
          </div>
          <div class="keyvalue-row">
            <span>relevant_memory</span>
            <strong>{{ relevantMemory.length }} 条</strong>
          </div>
          <div class="keyvalue-row">
            <span>memory_writeback</span>
            <strong>{{ memoryUpdates.length }} 条</strong>
          </div>
          <div class="keyvalue-row">
            <span>short_term_state</span>
            <strong>{{ shortTermFieldCount }} fields</strong>
          </div>
        </div>
      </article>

      <article class="developer-inspector-card state-maintenance-card">
        <div class="agent-head">
          <strong>工具与外部证据</strong>
          <span class="chip subtle">{{ selectedSkills.length }} skills</span>
        </div>
        <div class="keyvalue-list">
          <div class="keyvalue-row">
            <span>selected_skills</span>
            <strong class="debug-inline-value">{{ skillNames || 'none' }}</strong>
          </div>
          <div class="keyvalue-row">
            <span>tool_results</span>
            <strong class="debug-inline-value">{{ toolNames || 'none' }}</strong>
          </div>
          <div class="keyvalue-row">
            <span>rag_chunks</span>
            <strong>{{ retrievedDocuments.length }} chunks</strong>
          </div>
        </div>
      </article>

      <article class="developer-inspector-card state-maintenance-card">
        <div class="agent-head">
          <strong>规划草案与执行阶段</strong>
          <span class="chip subtle">{{ agentOutputs.length }} agents</span>
        </div>
        <div class="keyvalue-list">
          <div class="keyvalue-row">
            <span>final_plan_days</span>
            <strong>{{ finalPlanDays.length }} 天</strong>
          </div>
          <div class="keyvalue-row">
            <span>hotels</span>
            <strong>{{ hotelOptions.length }} 个</strong>
          </div>
          <div class="keyvalue-row">
            <span>workflow_stage</span>
            <strong class="debug-inline-value">{{ latestWorkflowStage }}</strong>
          </div>
        </div>
      </article>
    </div>

    <details class="raw-details compact developer-raw-details state-maintenance-raw">
      <summary>查看状态投影 JSON</summary>
      <pre>{{ stateProjectionJson }}</pre>
    </details>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  result: { type: Object, required: true },
})

const result = computed(() => props.result || {})
const sessionContext = computed(() => result.value.session_context || {})
const constraints = computed(() => result.value.structured_constraints || {})
const memoryContext = computed(() => result.value.memory_context || {})
const retrievalContext = computed(() => result.value.retrieval_context || {})
const finalPlan = computed(() => result.value.final_plan || {})
const summary = computed(() => finalPlan.value.summary || {})
const runtimeContext = computed(() => result.value.assembled_context?.runtime_context || {})
const workflowTrace = computed(() => runtimeContext.value.workflow_trace || [])
const selectedSkills = computed(() => result.value.selected_skills || [])
const toolResults = computed(() => result.value.tool_results || [])
const agentOutputs = computed(() => result.value.agent_outputs || [])
const longTermMemory = computed(() => memoryContext.value.long_term_memory || [])
const relevantMemory = computed(() => memoryContext.value.relevant_long_term_memory || [])
const memoryUpdates = computed(() => result.value.memory_updates || [])
const retrievedDocuments = computed(() => retrievalContext.value.retrieved_documents || [])
const historyMessages = computed(() => sessionContext.value.history_messages || [])
const finalPlanDays = computed(() => finalPlan.value.days || [])
const hotelOptions = computed(() => finalPlan.value.hotelOptions || finalPlan.value.hotelRecommendation || [])
const shortTermState = computed(() => memoryContext.value.short_term_state || constraints.value || {})
const shortTermFieldCount = computed(() =>
  Object.keys(shortTermState.value).filter((key) => !key.startsWith('_')).length
)

const workflowEngineLabel = computed(() => runtimeContext.value.workflow_engine || 'state projection')
const sessionFoundLabel = computed(() => sessionContext.value.session_found ? 'session resumed' : 'new session')
const skillNames = computed(() => selectedSkills.value.map((item) => item.skill_id || item.name).filter(Boolean).join(' / '))
const toolNames = computed(() => toolResults.value.map((item) => item.tool_name || item.name).filter(Boolean).join(' / '))
const latestWorkflowStage = computed(() => {
  const latest = workflowTrace.value[workflowTrace.value.length - 1]
  if (!latest) return '暂无 trace'
  return `${latest.node || 'unknown'}:${latest.status || 'unknown'}`
})

const constraintRows = computed(() => [
  { label: 'destination', value: constraints.value.destination || 'null' },
  { label: 'days', value: constraints.value.days ?? 'null' },
  { label: 'budget', value: formatCurrency(constraints.value.budget || summary.value.totalBudget) },
  { label: 'pace', value: constraints.value.pace || 'balanced' },
  { label: 'followup_replan', value: formatBoolean(constraints.value._followup_replan) },
  { label: 'task_type', value: result.value.task_profile?.task_type || 'unknown' },
])

const preferenceSignals = computed(() => [
  ...(constraints.value.preferences || []).map((item) => `pref:${item}`),
  ...(constraints.value.excluded_attractions || []).map((item) => `exclude:${item}`),
  ...(constraints.value.expanded_excluded_attractions || []).map((item) => `expanded:${item}`),
  ...(memoryUpdates.value || []).map((item) => `write:${item.key || item.name || 'memory'}`),
].slice(0, 18))

const preferenceSignalCount = computed(() =>
  (constraints.value.preferences || []).length
  + (constraints.value.excluded_attractions || []).length
  + (constraints.value.expanded_excluded_attractions || []).length
  + memoryUpdates.value.length
)

const stateProjection = computed(() => ({
  user_input: result.value.user_input || '',
  session_context: {
    session_found: Boolean(sessionContext.value.session_found),
    initial_request_text: sessionContext.value.initial_request_text || '',
    history_messages: historyMessages.value,
    baseline_constraints: sessionContext.value.session_baseline_constraints || {},
  },
  structured_constraints: constraints.value,
  memory_state: {
    short_term_state: shortTermState.value,
    relevant_long_term_memory: relevantMemory.value,
    memory_writeback: memoryUpdates.value,
  },
  evidence_state: {
    selected_skills: selectedSkills.value.map((item) => item.skill_id || item.name).filter(Boolean),
    tool_results: toolResults.value.map((item) => item.tool_name || item.name).filter(Boolean),
    retrieved_documents: retrievedDocuments.value.length,
  },
  planning_state: {
    final_plan_days: finalPlanDays.value.length,
    hotels: hotelOptions.value.length,
    agents: agentOutputs.value.map((item) => item.agent || item.name).filter(Boolean),
    latest_workflow_stage: latestWorkflowStage.value,
  },
}))

const stateProjectionJson = computed(() => JSON.stringify(stateProjection.value, null, 2))

function formatBoolean(value) {
  return value === true ? 'true' : 'false'
}

function formatCurrency(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '未指定'
  return `¥${value}`
}
</script>
