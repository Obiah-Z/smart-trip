<template>
  <section class="panel developer-pipeline-panel">
    <div class="panel-header">
      <div>
        <p class="panel-kicker">Pipeline</p>
        <h2>{{ traceTitle }}</h2>
      </div>
      <span class="badge">{{ traceEngineLabel }} · {{ completedStageCount }} / {{ stageTrace.length }} stages</span>
    </div>

    <div class="stage-trace-list">
      <article
        v-for="stage in stageTrace"
        :key="stage.key"
        class="stage-trace-card"
        :class="`stage-trace-card-${stage.status}`"
      >
        <div class="stage-trace-marker">
          <span>{{ stage.order }}</span>
        </div>
        <div class="stage-trace-body">
          <div class="stage-trace-head">
            <strong>{{ stage.label }}</strong>
            <span class="chip subtle">{{ stage.statusLabel }}</span>
          </div>
          <p>{{ stage.summary }}</p>
          <div v-if="stage.meta.length" class="stage-trace-meta">
            <span v-for="item in stage.meta" :key="item">{{ item }}</span>
          </div>
        </div>
      </article>
    </div>

    <div class="developer-inspector-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-button"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <div v-if="activeTab === 'selection'" class="developer-inspector-section">
      <h3>selected_skills</h3>
      <div class="agent-list" v-if="selectedSkills.length">
        <article v-for="skill in selectedSkills" :key="skill.skill_id" class="mini-card">
          <div class="agent-head">
            <strong>{{ skill.skill_id }}</strong>
            <span class="chip subtle">{{ skill.source || 'registry' }}</span>
          </div>
          <p>{{ skill.display_name }} · {{ skill.reason }}</p>
        </article>
      </div>
      <p v-else class="muted-text">未选择 Skill，通常是澄清、轻量直答或缺少必要槽位。</p>
    </div>

    <div v-else-if="activeTab === 'memory'" class="developer-inspector-section">
      <h3>memory_injection</h3>
      <div class="keyvalue-list">
        <div class="keyvalue-row">
          <span>long_term_memory</span>
          <strong>{{ memoryContext.long_term_memory?.length || 0 }}</strong>
        </div>
        <div class="keyvalue-row">
          <span>relevant_memory</span>
          <strong>{{ memoryContext.relevant_long_term_memory?.length || 0 }}</strong>
        </div>
        <div class="keyvalue-row">
          <span>short_term_state</span>
          <strong>{{ visibleShortTermFieldCount }}</strong>
        </div>
      </div>
      <ul class="bullet-list" v-if="memoryContext.selection_reasons?.length">
        <li v-for="item in memoryContext.selection_reasons" :key="item">{{ item }}</li>
      </ul>
    </div>

    <div v-else-if="activeTab === 'rag'" class="developer-inspector-section">
      <h3>retrieval_context</h3>
      <div class="keyvalue-list debug-signal-list">
        <div class="keyvalue-row">
          <span>retrieval_mode</span>
          <strong>{{ retrievalModeLabel }}</strong>
        </div>
        <div class="keyvalue-row">
          <span>retrieved_documents</span>
          <strong>{{ retrievedDocuments.length }}</strong>
        </div>
        <div class="keyvalue-row">
          <span>ranking_signals</span>
          <strong>{{ rankingSignalSummary }}</strong>
        </div>
      </div>
      <ul class="bullet-list" v-if="retrievalContext.retrieval_steps?.length">
        <li v-for="item in retrievalContext.retrieval_steps" :key="item">{{ item }}</li>
      </ul>
      <div v-if="retrievedDocuments.length" class="subsection">
        <h3>top_chunks</h3>
        <div class="agent-list">
          <article v-for="document in topRetrievedDocuments" :key="document.id" class="mini-card">
            <div class="agent-head">
              <strong>{{ document.title || document.topic || '未命名 chunk' }}</strong>
              <span class="chip subtle">{{ document.topic || 'generic' }}</span>
            </div>
            <p class="muted-text debug-score-line">
              综合 {{ formatScore(document.score) }}
              · BM25 {{ formatScore(document.bm25_score) }}
              · 向量 {{ formatScore(document.vector_score) }}
              · 融合 {{ formatScore(document.hybrid_score) }}
            </p>
            <p>{{ summarizeDocument(document.content) }}</p>
          </article>
        </div>
      </div>
      <ul class="bullet-list" v-if="retrievalContext.injected_knowledge?.length">
        <li v-for="item in retrievalContext.injected_knowledge" :key="item">{{ item }}</li>
      </ul>
      <p v-else class="muted-text">没有注入知识片段，可能是轻量工具问答或检索未命中。</p>
    </div>

    <div v-else-if="activeTab === 'tools'" class="developer-inspector-section">
      <h3>tool_results</h3>
      <div class="tool-card-grid" v-if="toolResults.length">
        <article v-for="tool in toolResults" :key="tool.tool_name" class="mini-card">
          <h4>{{ tool.display_name || tool.tool_name }}</h4>
          <pre>{{ JSON.stringify(tool.output, null, 2) }}</pre>
        </article>
      </div>
      <p v-else class="muted-text">本轮没有工具执行结果，可能是轻量直答、澄清或技能选择未命中。</p>
    </div>

    <div v-else class="developer-inspector-section">
      <h3>agent_outputs</h3>
      <div class="agent-list" v-if="agentOutputs.length">
        <article v-for="agent in agentOutputs" :key="agent.agent" class="mini-card">
          <div class="agent-head">
            <strong>{{ agentLabel(agent.agent) }}</strong>
          </div>
          <p>{{ agent.summary }}</p>
        </article>
      </div>
      <p v-else class="muted-text">本轮没有启用多 Agent，通常是轻量咨询、澄清或 bypass 链路。</p>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  taskProfile: { type: Object, required: true },
  memoryContext: { type: Object, required: true },
  retrievalContext: { type: Object, required: true },
  selectedSkills: { type: Array, required: true },
  toolResults: { type: Array, required: true },
  agentOutputs: { type: Array, required: true },
  finalPlan: { type: Object, default: () => ({}) },
  assembledContext: { type: Object, default: () => ({}) },
})

const activeTab = ref('selection')
const visibleShortTermFieldCount = computed(() =>
  Object.keys(memoryContextFields.value).length
)
const retrievedDocuments = computed(() => props.retrievalContext?.retrieved_documents || [])
const topRetrievedDocuments = computed(() => retrievedDocuments.value.slice(0, 3))
const tabs = computed(() => {
  if (props.taskProfile?.task_type === 'travel_consulting') {
    return [
      { key: 'selection', label: 'Skill 选择' },
      { key: 'rag', label: 'RAG' },
      { key: 'tools', label: 'Tools' },
    ]
  }
  return [
    { key: 'selection', label: 'Skill 选择' },
    { key: 'memory', label: 'Memory' },
    { key: 'rag', label: 'RAG' },
    { key: 'tools', label: 'Tools' },
    { key: 'agents', label: 'Agents' },
  ]
})
const activeTabLabel = computed(() => tabs.value.find((tab) => tab.key === activeTab.value)?.label || 'Skill 选择')
const completedStageCount = computed(() => stageTrace.value.filter((stage) => stage.status === 'done').length)
const runtimeContext = computed(() => props.assembledContext?.runtime_context || {})
const langGraphTrace = computed(() => runtimeContext.value.workflow_trace || [])
const hasLangGraphTrace = computed(() => langGraphTrace.value.length > 0)
const traceTitle = computed(() => hasLangGraphTrace.value ? 'LangGraph Trace' : 'Stage Trace')
const traceEngineLabel = computed(() => runtimeContext.value.workflow_engine || 'derived')
const retrievalModeLabel = computed(() => {
  const mode = retrievedDocuments.value[0]?.retrieval_mode || 'bm25'
  if (mode === 'hybrid') return 'Hybrid 检索'
  return 'BM25 检索'
})
const rankingSignalSummary = computed(() => {
  const signals = props.retrievalContext?.ranking_signals || []
  return signals.length ? signals.slice(0, 4).join(' / ') : '暂无'
})
const memoryContextFields = computed(() => {
  const source = props.memoryContext?.short_term_state || {}
  return Object.fromEntries(Object.entries(source).filter(([key]) => !key.startsWith('_')))
})
const finalSummary = computed(() => props.finalPlan?.summary || {})
const outputKind = computed(() => {
  if (props.finalPlan?.consultingType === 'clarification') return 'clarification'
  if (props.taskProfile?.task_type === 'travel_consulting') return 'consulting'
  if (finalSummary.value.destinationCity || (props.finalPlan?.days || []).length) return 'planning'
  return 'unknown'
})
const stageTrace = computed(() => {
  if (hasLangGraphTrace.value) {
    return langGraphTrace.value.map((item, index) => ({
      key: item.node || `workflow-${index}`,
      order: String(index + 1).padStart(2, '0'),
      label: formatWorkflowNodeLabel(item.node),
      status: normalizeStageStatus(item.status),
      statusLabel: item.status || 'unknown',
      summary: item.summary || '该 LangGraph 节点未返回摘要。',
      meta: workflowMetadataItems(item.metadata),
    }))
  }

  const routeDone = Boolean(props.taskProfile?.task_type)
  const shortTermCount = Object.keys(memoryContextFields.value).length
  const relevantMemoryCount = props.memoryContext?.relevant_long_term_memory?.length || 0
  const memoryTouched = shortTermCount > 0 || relevantMemoryCount > 0
  const ragTouched = retrievedDocuments.value.length > 0 || Boolean(props.taskProfile?.needs_rag)
  const skillTouched = props.selectedSkills.length > 0
  const toolTouched = props.toolResults.length > 0 || Boolean(props.taskProfile?.needs_tools)
  const agentTouched = props.agentOutputs.length > 0 || Boolean(props.taskProfile?.needs_multi_agent)
  const outputDone = outputKind.value !== 'unknown'

  return [
    {
      key: 'route',
      order: '01',
      label: 'Route',
      status: routeDone ? 'done' : 'idle',
      statusLabel: props.taskProfile?.task_type || 'waiting',
      summary: props.taskProfile?.intent_summary || '等待任务识别结果。',
      meta: [
        props.taskProfile?.complexity ? `complexity:${props.taskProfile.complexity}` : '',
        boolMeta('rag', props.taskProfile?.needs_rag),
        boolMeta('tools', props.taskProfile?.needs_tools),
        boolMeta('multi_agent', props.taskProfile?.needs_multi_agent),
      ].filter(Boolean),
    },
    {
      key: 'memory',
      order: '02',
      label: 'Memory',
      status: memoryTouched ? 'done' : 'bypass',
      statusLabel: memoryTouched ? 'injected' : 'bypass',
      summary: memoryTouched
        ? `注入 ${relevantMemoryCount} 条相关长期记忆，短期状态 ${shortTermCount} 个字段。`
        : '没有可注入的相关 Memory，使用当前请求继续处理。',
      meta: [
        `long:${props.memoryContext?.long_term_memory?.length || 0}`,
        `relevant:${relevantMemoryCount}`,
        `short:${shortTermCount}`,
      ],
    },
    {
      key: 'rag',
      order: '03',
      label: 'RAG',
      status: ragTouched ? (retrievedDocuments.value.length ? 'done' : 'warn') : 'bypass',
      statusLabel: ragTouched ? retrievalModeLabel.value : 'bypass',
      summary: retrievedDocuments.value.length
        ? `召回 ${retrievedDocuments.value.length} 个知识片段，Top chunk: ${retrievedDocuments.value[0]?.title || retrievedDocuments.value[0]?.topic || '未命名'}。`
        : ragTouched
          ? '任务声明需要检索，但当前没有召回片段，需要检查 query rewrite 或索引。'
          : '本轮没有触发知识检索。',
      meta: [
        `docs:${retrievedDocuments.value.length}`,
        `signals:${(props.retrievalContext?.ranking_signals || []).length}`,
        `steps:${(props.retrievalContext?.retrieval_steps || []).length}`,
      ],
    },
    {
      key: 'skills',
      order: '04',
      label: 'Skills',
      status: skillTouched ? 'done' : 'bypass',
      statusLabel: skillTouched ? `${props.selectedSkills.length} selected` : 'none',
      summary: skillTouched
        ? props.selectedSkills.map((skill) => skill.skill_id).join(' / ')
        : '没有选择业务 Skill，通常是澄清、轻问答或缺少必要槽位。',
      meta: props.selectedSkills.slice(0, 3).map((skill) => skill.source || 'registry'),
    },
    {
      key: 'tools',
      order: '05',
      label: 'Tools',
      status: toolTouched ? (props.toolResults.length ? 'done' : 'warn') : 'bypass',
      statusLabel: toolTouched ? `${props.toolResults.length} results` : 'bypass',
      summary: props.toolResults.length
        ? props.toolResults.map((tool) => tool.display_name || tool.tool_name).join(' / ')
        : toolTouched
          ? '任务声明需要工具，但没有工具结果，需要检查 skill 执行或 sandbox。'
          : '本轮没有触发工具调用。',
      meta: props.toolResults.slice(0, 3).map((tool) => tool.tool_name),
    },
    {
      key: 'agents',
      order: '06',
      label: 'Agents',
      status: agentTouched ? (props.agentOutputs.length ? 'done' : 'warn') : 'bypass',
      statusLabel: agentTouched ? `${props.agentOutputs.length} outputs` : 'bypass',
      summary: props.agentOutputs.length
        ? props.agentOutputs.map((agent) => agentLabel(agent.agent)).join(' -> ')
        : agentTouched
          ? '任务声明需要多 Agent，但没有 Agent 输出，需要检查编排入口。'
          : '本轮走轻量链路或单链路处理。',
      meta: props.agentOutputs.slice(0, 4).map((agent) => agent.agent),
    },
    {
      key: 'output',
      order: '07',
      label: 'Output',
      status: outputDone ? 'done' : 'warn',
      statusLabel: outputKind.value,
      summary: outputDone
        ? outputSummary.value
        : '没有识别到可用输出结构，需要检查 final_plan 或 consultingType。',
      meta: [
        `days:${(props.finalPlan?.days || []).length}`,
        `missing:${(props.finalPlan?.missingFields || []).length}`,
        `type:${props.finalPlan?.consultingType || 'plan'}`,
      ],
    },
  ]
})
const outputSummary = computed(() => {
  if (outputKind.value === 'clarification') {
    return `澄清输出，缺失字段：${(props.finalPlan?.missingFields || []).join(' / ') || 'unknown'}。`
  }
  if (outputKind.value === 'consulting') {
    return `轻咨询输出：${props.finalPlan?.consultingType || 'general'}。`
  }
  if (outputKind.value === 'planning') {
    return `生成 ${finalSummary.value.destinationCity || '未知目的地'} ${finalSummary.value.days || (props.finalPlan?.days || []).length || '-'} 天方案。`
  }
  return '未知输出。'
})

function agentLabel(value) {
  if (value === 'planner_agent') return '需求拆解'
  if (value === 'retriever_agent') return '信息整理'
  if (value === 'executor_agent') return '方案生成'
  if (value === 'reviewer_agent') return '结果检查'
  return value
}

function formatScore(value) {
  if (typeof value !== 'number') return '-'
  return value.toFixed(3)
}

function summarizeDocument(value) {
  if (!value) return '暂无片段内容'
  if (value.length <= 120) return value
  return `${value.slice(0, 120)}...`
}

function boolMeta(label, value) {
  if (value === true) return `${label}:true`
  if (value === false) return `${label}:false`
  return ''
}

function formatWorkflowNodeLabel(value) {
  const labels = {
    prepare_request: 'Prepare Request',
    resolve_constraints: 'Resolve Constraints',
    build_clarification_response: 'Clarification Response',
    load_memory: 'Load Memory',
    retrieve_knowledge: 'Retrieve Knowledge',
    run_skills: 'Run Skills',
    build_consulting_response: 'Consulting Response',
    assemble_context: 'Assemble Context',
    run_agents: 'Run Agents',
    enrich_and_summarize: 'Enrich & Summarize',
    persist_planning_response: 'Persist Response',
  }
  return labels[value] || value || 'Workflow Node'
}

function normalizeStageStatus(value) {
  if (['done', 'bypass', 'warn', 'idle'].includes(value)) return value
  return value ? 'done' : 'idle'
}

function workflowMetadataItems(metadata) {
  if (!metadata || typeof metadata !== 'object') return []
  return Object.entries(metadata)
    .flatMap(([key, value]) => {
      if (Array.isArray(value)) return value.length ? [`${key}:${value.join('/')}`] : []
      if (value === null || value === undefined || value === '') return []
      return [`${key}:${value}`]
    })
    .slice(0, 5)
}
</script>
