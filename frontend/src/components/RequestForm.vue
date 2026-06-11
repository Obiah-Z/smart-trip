<template>
  <section class="request-panel" :class="{ panel: !compact, 'request-panel-compact': compact }">
    <div class="panel-header">
      <h2>{{ title }}</h2>
      <span class="badge">{{ badge }}</span>
    </div>
    <label v-if="showUserId" class="field">
      <span>{{ userLabel }}</span>
      <input :value="userId" @input="$emit('update:userId', $event.target.value)" />
    </label>
    <label class="field">
      <span>{{ messageLabel }}</span>
      <textarea
        :value="message"
        :rows="rows"
        :placeholder="messagePlaceholder"
        @input="$emit('update:message', $event.target.value)"
      ></textarea>
    </label>
    <p class="muted-text">{{ description }}</p>
    <div class="actions">
      <button class="primary" :disabled="loading" @click="$emit('submit')">
        {{ loading ? '正在整理方案...' : submitLabel }}
      </button>
    </div>
  </section>
</template>

<script setup>
defineProps({
  userId: String,
  message: String,
  loading: Boolean,
  title: {
    type: String,
    default: '告诉我你的旅行要求',
  },
  badge: {
    type: String,
    default: '开始规划',
  },
  description: {
    type: String,
    default: '直接用自然语言描述就可以，例如目的地、预算、节奏、住宿要求、是否想吃本地特色等。',
  },
  userLabel: {
    type: String,
    default: '旅程名称',
  },
  messageLabel: {
    type: String,
    default: '你想怎么出行',
  },
  messagePlaceholder: {
    type: String,
    default: '比如：帮我规划一个杭州三日游，预算 3000，节奏轻松一点，酒店尽量安静。',
  },
  submitLabel: {
    type: String,
    default: '生成旅行建议',
  },
  rows: {
    type: Number,
    default: 5,
  },
  showUserId: {
    type: Boolean,
    default: true,
  },
  compact: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['update:userId', 'update:message', 'submit'])
</script>
