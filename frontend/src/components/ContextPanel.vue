<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="panel-kicker">Prompt</p>
        <h2>Prompt Context 片段</h2>
      </div>
      <span class="badge">{{ sections.length }} sections</span>
    </div>

    <div class="context-stack">
      <article v-for="section in sections" :key="section.title" class="context-card">
        <h3>{{ section.title }}</h3>
        <pre>{{ section.body }}</pre>
      </article>
    </div>

  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Object, required: true },
  taskProfile: { type: Object, required: true },
})

const sections = computed(() =>
  (props.data.prompt_sections || []).map((section, index) => {
    const [title, ...body] = section.split('\n')
    return {
      title: title.replace(/^\[|\]$/g, '') || `Section ${index + 1}`,
      body: body.join('\n'),
    }
  })
)
</script>
