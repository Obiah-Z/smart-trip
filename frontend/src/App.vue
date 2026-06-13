<template>
  <main class="app-shell" :class="{ 'has-floating-composer': showFloatingComposer }">
    <header class="hero">
      <div class="hero-brand">
        <div class="hero-title-row">
          <span class="brand-mark">ST</span>
          <div class="brand-copy">
            <strong>Smart Trip</strong>
            <span>{{ activeView === 'user' ? '智能旅行规划平台' : 'AI Workflow Console' }}</span>
          </div>
        </div>
      </div>

      <nav class="view-switch" aria-label="界面模式切换">
        <button
          v-for="view in viewModes"
          :key="view.key"
          class="view-switch-button"
          :class="{ active: activeView === view.key }"
          type="button"
          @click="activeView = view.key"
        >
          <span class="view-switch-label">{{ view.label }}</span>
          <span class="view-switch-copy">{{ view.description }}</span>
        </button>
      </nav>

      <div class="hero-pills">
        <div class="hero-pill">
          <span class="status-label">{{ activeView === 'user' ? 'Mode' : 'User' }}</span>
          <strong>{{ activeView === 'user' ? 'User View' : userId }}</strong>
        </div>
        <div class="hero-pill">
          <span class="status-label">Status</span>
          <strong>{{ loading ? 'Running' : result ? 'Ready' : 'Idle' }}</strong>
        </div>
        <div class="hero-pill hero-pill-session" :title="sessionDisplayId">
          <span class="status-label">Session</span>
          <div class="status-value-row">
            <strong>{{ sessionStatusLabel }}</strong>
            <span class="status-meta">{{ sessionHeaderId }}</span>
          </div>
        </div>
      </div>
    </header>

    <div v-if="errorMessage" class="error-banner">{{ errorMessage }}</div>

    <template v-if="activeView === 'user'">
      <template v-if="result">
        <section class="stage-block result-stage user-result-stage">
          <div class="user-result-toolbar" :class="{ 'user-result-toolbar-followup': isFollowupReplan }">
            <div class="user-result-toolbar-main">
              <span class="chip subtle">{{ isFollowupReplan ? '续接上一轮' : '当前结果' }}</span>
              <p>{{ sessionNoticeText }}</p>
            </div>
            <span class="badge">{{ isConsultingMode ? '即时回答' : '可直接使用' }}</span>
          </div>

          <ResultPanel
            :data="{ finalPlan: result.final_plan, llmOutput: result.llm_output, taskProfile: result.task_profile }"
            :show-evidence-details="false"
          />
        </section>

        <section class="stage-block history-stage compact-stage history-stage-secondary">
          <div class="stage-header">
            <div>
              <p class="panel-kicker">Recent</p>
              <h2>最近结果</h2>
              <p class="stage-copy">回看历史会话，或打开原有会话继续追问。</p>
            </div>
            <span class="badge">历史会话</span>
          </div>

          <SessionHistoryPanel
            :items="sessionHistory"
            :loading="sessionHistoryLoading"
            :deleting-id="deletingSessionId"
            @refresh="loadSessionHistory"
            @open="openHistoryItem"
            @delete="removeHistoryItem"
          />
        </section>

        <section class="floating-followup-bar" aria-label="继续调整当前方案">
          <div class="floating-followup-inner">
            <div class="floating-followup-head">
              <div class="floating-followup-title">Refine Plan</div>
              <div class="floating-followup-meta">
                <span class="chip subtle">{{ sessionStatusLabel }}</span>
                <span class="floating-followup-session">会话 {{ sessionHeaderId === '等待生成' ? '生成中' : sessionHeaderId }}</span>
                <button class="secondary" type="button" :disabled="loading" @click="startNewTrip">开始新旅程</button>
              </div>
            </div>

            <div class="followup-chip-row floating-followup-chips">
              <button
                v-for="item in floatingFollowupSuggestions"
                :key="item"
                class="followup-chip"
                type="button"
                :disabled="loading"
                @click="applyFollowupSuggestion(item)"
              >
                {{ item }}
              </button>
            </div>

            <div class="floating-followup-form">
              <label class="floating-followup-field">
                <span class="sr-only">继续补充需求</span>
                <textarea
                  ref="followupInputRef"
                  v-model="message"
                  rows="1"
                  :placeholder="followupPlaceholder"
                  @keydown.ctrl.enter.prevent="runDemo"
                  @keydown.meta.enter.prevent="runDemo"
                ></textarea>
              </label>
              <div class="floating-followup-actions">
                <p class="floating-followup-hint">Ctrl + Enter 可快速发送</p>
                <button class="primary compact-submit" type="button" :disabled="loading" @click="runDemo">
                  {{ loading ? '处理中...' : isConsultingMode ? '继续追问' : '更新方案' }}
                </button>
              </div>
            </div>
          </div>
        </section>
      </template>

      <section v-else class="stage-block input-stage user-entry-stage">
        <div class="start-panel-layout">
          <div class="start-panel-main">
            <div class="stage-header start-panel-header">
              <div>
                <p class="panel-kicker">Start</p>
                <h2>说说你的旅行想法</h2>
                <p class="stage-copy">直接告诉我目的地、天数、预算、节奏和偏好，我会先整理出可直接使用的旅行建议。</p>
              </div>
              <span class="badge">用户视图</span>
            </div>

            <RequestForm
              :user-id="userId"
              :message="message"
              :loading="loading"
              title="这次想怎么出行"
              badge="开始整理"
              description="支持自然语言输入，例如目的地、预算、天数、节奏、住宿要求、是否想吃本地特色。"
              message-label="你的旅行需求"
              message-placeholder="比如：帮我规划一个杭州三日游，预算 3000，节奏轻松一点，酒店尽量安静。"
              submit-label="开始生成"
              :show-user-id="false"
              :compact="true"
              @update:user-id="userId = $event"
              @update:message="message = $event"
              @submit="runDemo"
            />
          </div>

          <aside class="start-example-panel" aria-label="示例问题">
            <div class="start-example-head">
              <p class="panel-kicker">Examples</p>
              <h3>你也可以这样问</h3>
              <p class="muted-text">选择一个示例后可以直接生成，也可以先改成自己的需求。</p>
            </div>
            <div class="start-example-list">
              <button
                v-for="item in userExamplePrompts"
                :key="item"
                class="start-example-card"
                type="button"
                :disabled="loading"
                @click="applyFollowupSuggestion(item)"
              >
                {{ item }}
              </button>
            </div>
          </aside>
        </div>

        <div class="subsection user-entry-history">
          <SessionHistoryPanel
            :items="sessionHistory"
            :loading="sessionHistoryLoading"
            :deleting-id="deletingSessionId"
            @refresh="loadSessionHistory"
            @open="openHistoryItem"
            @delete="removeHistoryItem"
          />
        </div>
      </section>
    </template>

    <template v-else>
      <section class="stage-block developer-console-stage">
        <div class="stage-header developer-stage-header">
          <div>
            <p class="panel-kicker">Developer</p>
            <h2>开发调试面板</h2>
            <p class="stage-copy">面向链路排查的控制台视图，只保留复现、路由、上下文、检索、工具和 Agent 调试信息。</p>
          </div>
          <span class="badge">Debug Mode</span>
        </div>

        <div class="developer-status-grid developer-overview-grid">
          <article v-for="item in developerStatusCards" :key="item.label" class="metric-card">
            <span class="metric-label">{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <p v-if="item.helper" class="muted-text">{{ item.helper }}</p>
          </article>
        </div>

        <section class="developer-command-grid developer-command-grid-single">
          <div class="developer-runtime-column">
            <DevResponsePanel v-if="result" :result="result" :session-id="sessionId" />
            <article v-else class="developer-runtime-placeholder">
              <div>
                <p class="panel-kicker">Runtime</p>
                <h3>等待运行结果</h3>
                <p class="muted-text">发送一次请求后，这里会显示任务路由、核心槽位、产物数量和模型输出状态。</p>
              </div>
              <span class="badge">No Snapshot</span>
            </article>
          </div>
        </section>

        <details class="developer-memory-drawer">
          <summary class="developer-drawer-summary">
            <span>Memory Debug</span>
            <span class="chip subtle">{{ memories.length }} records / {{ result?.memory_updates?.length || 0 }} writes</span>
          </summary>
          <MemoryPanel
            :draft="memoryDraft"
            :memories="memories"
            :latest-updates="result?.memory_updates || []"
            @update:draft="memoryDraft = $event"
            @save="saveMemory"
          />
        </details>
      </section>

      <template v-if="result">
        <section class="stage-block developer-debug-stage">
          <div class="stage-header developer-stage-header">
            <div>
              <p class="panel-kicker">Trace</p>
              <h2>结构化状态与执行过程</h2>
              <p class="stage-copy">按 Route、Memory、RAG、Skill、Tool、Agent、Output 的顺序检查本轮链路是否符合预期。</p>
            </div>
            <span class="badge">Runtime Trace</span>
          </div>

          <section class="developer-trace-layout">
            <PipelinePanel
              :task-profile="result.task_profile"
              :memory-context="result.memory_context"
              :retrieval-context="result.retrieval_context"
              :selected-skills="result.selected_skills"
              :tool-results="result.tool_results"
              :agent-outputs="result.agent_outputs"
              :final-plan="result.final_plan"
              :assembled-context="result.assembled_context"
            />
          </section>
        </section>

        <section class="stage-block developer-context-stage">
          <div class="stage-header">
            <div>
              <p class="panel-kicker">Context</p>
              <h2>注入模型的上下文</h2>
              <p class="stage-copy">这里可以检查系统最终给模型拼装了哪些段落，便于排查上下文冲突、遗漏或污染问题。</p>
            </div>
            <span class="badge">Prompt Context</span>
          </div>

          <ContextPanel :data="result.assembled_context" :task-profile="result.task_profile" />
        </section>
      </template>

      <section v-else class="stage-block developer-empty-stage">
        <div class="stage-header">
          <div>
            <p class="panel-kicker">Waiting</p>
            <h2>等待一次调试运行</h2>
            <p class="stage-copy">发送一次请求后，这里会出现结构化约束、技能选择、工具输出、Agent 摘要和最终 Context，方便直接检查整条执行链路。</p>
          </div>
          <span class="badge">No Trace Yet</span>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import ContextPanel from './components/ContextPanel.vue'
import DevResponsePanel from './components/DevResponsePanel.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import PipelinePanel from './components/PipelinePanel.vue'
import RequestForm from './components/RequestForm.vue'
import ResultPanel from './components/ResultPanel.vue'
import SessionHistoryPanel from './components/SessionHistoryPanel.vue'
import { createDemoPlan, deleteSession, getSession, listMemory, listSessions, upsertMemory } from './lib/api'

const DEFAULT_MESSAGE = '帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色'

const userId = ref('demo-user')
const message = ref(DEFAULT_MESSAGE)
const loading = ref(false)
const errorMessage = ref('')
const result = ref(null)
const sessionId = ref('')
const sessionHistory = ref([])
const sessionHistoryLoading = ref(false)
const deletingSessionId = ref('')
const memories = ref([])
const memoryDraft = ref({ key: 'hotel_style', value: 'prefer_quiet_location', scope: 'travel_preference' })
const followupInputRef = ref(null)
const activeView = ref('user')
const viewModes = [
  { key: 'user', label: '用户视图', description: '只看结果与继续追问' },
  { key: 'developer', label: '开发调试', description: '查看状态、过程与上下文' },
]
const userExamplePrompts = [
  '帮我规划一个杭州三日游，预算3000，节奏轻松一点，酒店尽量安静，想吃本地特色',
  '杭州天气怎么样',
  '推荐几个北京适合第一次去的景点',
  '帮我规划一个深圳周末两日游，预算2500',
]
const isConsultingMode = computed(() => result.value?.task_profile?.task_type === 'travel_consulting')
const isClarificationMode = computed(() => result.value?.final_plan?.consultingType === 'clarification')
const isFollowupReplan = computed(() => result.value?.structured_constraints?._followup_replan === true)
const showFloatingComposer = computed(() => activeView.value === 'user' && Boolean(result.value))
const sessionStatusLabel = computed(() => {
  if (loading.value) return '处理中'
  if (!sessionId.value) return '新会话'
  if (isFollowupReplan.value) return '已续接会话'
  return result.value ? '会话进行中' : '新会话'
})
const sessionDisplayId = computed(() => sessionId.value || '尚未创建 session')
const sessionHeaderId = computed(() => {
  if (!sessionId.value) return '等待生成'
  if (sessionId.value.length <= 18) return sessionId.value
  return `${sessionId.value.slice(0, 8)}...${sessionId.value.slice(-6)}`
})
const sessionNoticeText = computed(() => {
  const missingFields = result.value?.final_plan?.missingFields || []
  if (isClarificationMode.value) {
    if (missingFields.includes('days')) {
      return '目的地已经确认，当前只差出行天数。你只要补一句 2 天、3 天或 4 天，系统就会继续沿着上一轮需求生成方案。'
    }
    return '当前信息还不够完整，系统会先确认关键缺失项。你只要补充一个城市名，就能继续之前的需求。'
  }
  if (isFollowupReplan.value) {
    const constraints = result.value?.structured_constraints || {}
    return `系统沿用了上一轮已确认的 ${constraints.destination || '目的地'}、${constraints.days || '-'} 天和既有偏好，只对你这轮补充的预算或住宿要求重新计算。`
  }
  return '当前建议是根据你这一次输入直接整理的；如果继续补充预算、节奏或住宿要求，我会沿着同一轮方案继续调整。'
})
const followupSuggestions = computed(() => {
  if (isClarificationMode.value) {
    return result.value?.final_plan?.suggestedReplies || ['深圳', '北京', '上海', '成都']
  }
  if (isConsultingMode.value) {
    return [
      '顺便推荐 3 个适合第一次去的景点',
      '再看看明天的天气',
      '住在哪个区域最方便',
      '按一天路线帮我串起来',
    ]
  }

  return [
    '把预算提高到 10000，主要提升住宿舒适度',
    '节奏改成更轻松一点',
    '酒店住得更舒服一些',
    '想多安排一些本地特色餐厅',
  ]
})
const floatingFollowupSuggestions = computed(() => followupSuggestions.value.slice(0, 3))
const followupPlaceholder = computed(() => {
  if (isClarificationMode.value) {
    if ((result.value?.final_plan?.missingFields || []).includes('days')) {
      return '直接回复出行天数即可继续，比如：3天。'
    }
    return '直接回复一个城市名即可继续，比如：深圳。'
  }
  if (isConsultingMode.value) {
    return '比如：那明天的天气呢？或者顺便推荐几个适合第一次去的景点。'
  }
  return '比如：把预算提高到 10000，主要提升住宿舒适度；或者节奏改成更轻松一点。'
})
const developerStatusCards = computed(() => {
  const selectedSkillCount = result.value?.selected_skills?.length || 0
  const toolCount = result.value?.tool_results?.length || 0
  const agentCount = result.value?.agent_outputs?.length || 0
  const taskType = result.value?.task_profile?.task_type
  const topRetrievedDocument = result.value?.retrieval_context?.retrieved_documents?.[0] || null
  const retrievalMode = topRetrievedDocument?.retrieval_mode || 'bm25'
  const taskTypeLabel = !result.value
    ? '待运行'
    : taskType === 'travel_consulting'
      ? '旅行咨询'
      : '旅行规划'

  return [
    {
      label: '会话 ID',
      value: sessionHeaderId.value,
      helper: sessionStatusLabel.value,
    },
    {
      label: '任务类型',
      value: taskTypeLabel,
      helper: result.value?.task_profile?.complexity || '尚未分析',
    },
    {
      label: 'LLM 模式',
      value: result.value?.llm_output?.mode || 'waiting',
      helper: result.value?.llm_output?.model || '当前还没有模型摘要返回',
    },
    {
      label: '检索模式',
      value: retrievalMode === 'hybrid' ? 'Hybrid' : 'BM25',
      helper: topRetrievedDocument ? `${result.value?.retrieval_context?.retrieved_documents?.length || 0} 个知识片段已排序` : '当前还没有检索结果',
    },
    {
      label: '技能 / 工具',
      value: `${selectedSkillCount} / ${toolCount}`,
      helper: '已选技能 / 已执行工具',
    },
    {
      label: 'Agent 阶段',
      value: agentCount ? `${agentCount} 步` : 'bypass',
      helper: agentCount ? 'planner / retriever / executor / reviewer' : '轻量直答或等待运行',
    },
  ]
})

async function loadMemory() {
  memories.value = await listMemory(userId.value)
}

async function loadSessionHistory() {
  sessionHistoryLoading.value = true
  try {
    sessionHistory.value = await listSessions({ userId: userId.value, limit: 12 })
  } catch (error) {
    errorMessage.value = error.message || '暂时没能加载最近记录'
  } finally {
    sessionHistoryLoading.value = false
  }
}

async function runDemo() {
  const currentMessage = message.value.trim()
  if (!currentMessage) {
    errorMessage.value = result.value ? '请先输入你想继续调整的内容' : '请先输入你的旅行需求'
    return
  }

  loading.value = true
  errorMessage.value = ''
  try {
    result.value = await createDemoPlan({
      user_id: userId.value,
      session_id: sessionId.value || undefined,
      message: currentMessage,
    })
    sessionId.value = result.value?.session_id || sessionId.value
    await loadMemory()
    await loadSessionHistory()
    message.value = ''
    await nextTick()
    if (activeView.value === 'user') {
      followupInputRef.value?.focus?.()
    }
  } catch (error) {
    errorMessage.value = error.message || '暂时没能生成旅行建议'
  } finally {
    loading.value = false
  }
}

async function saveMemory() {
  errorMessage.value = ''
  try {
    await upsertMemory(userId.value, memoryDraft.value)
    await loadMemory()
  } catch (error) {
    errorMessage.value = error.message || '暂时没能保存偏好'
  }
}

async function openHistoryItem(item) {
  errorMessage.value = ''
  try {
    const payload = await getSession(item.session_id)
    sessionId.value = payload.session_id
    result.value = payload.response
    message.value = ''
    await nextTick()
    if (activeView.value === 'user') {
      window.scrollTo({ top: 0, behavior: 'smooth' })
      followupInputRef.value?.focus?.()
    }
  } catch (error) {
    errorMessage.value = error.message || '暂时没能打开这条记录'
  }
}

async function removeHistoryItem(item) {
  deletingSessionId.value = item.session_id
  errorMessage.value = ''
  try {
    await deleteSession(item.session_id)
    if (sessionId.value === item.session_id) {
      result.value = null
      sessionId.value = ''
    }
    await loadSessionHistory()
  } catch (error) {
    errorMessage.value = error.message || '暂时没能删除这条记录'
  } finally {
    deletingSessionId.value = ''
  }
}

function startNewTrip() {
  result.value = null
  sessionId.value = ''
  errorMessage.value = ''
  message.value = DEFAULT_MESSAGE
  if (typeof window !== 'undefined') {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

function applyFollowupSuggestion(value) {
  message.value = value
  nextTick(() => {
    followupInputRef.value?.focus?.()
  })
}

onMounted(async () => {
  await loadMemory()
  await loadSessionHistory()
})

watch(userId, async () => {
  await loadMemory()
  await loadSessionHistory()
})
</script>
