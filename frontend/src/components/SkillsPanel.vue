<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="panel-kicker">Skills / MCP</p>
        <h2>可用技能</h2>
      </div>
      <span class="badge">{{ skills.length }} 个</span>
    </div>

    <div class="memory-list" v-if="skills.length">
      <article v-for="skill in skills" :key="skill.skill_id" class="memory-item">
        <div class="memory-topline">
          <strong>{{ skill.display_name }}</strong>
          <span class="chip subtle">{{ skill.provider }}</span>
        </div>
        <p>{{ skill.description }}</p>
        <details class="raw-details compact">
          <summary>{{ skill.skill_id }}</summary>
          <pre>{{ JSON.stringify(skill.input_schema, null, 2) }}</pre>
          <div class="subsection">
            <h3>Example Payload</h3>
            <pre>{{ JSON.stringify(skill.example_payload, null, 2) }}</pre>
          </div>
          <div class="subsection">
            <h3>Sandbox Policy</h3>
            <pre>{{ JSON.stringify(skill.sandbox_policy || {}, null, 2) }}</pre>
          </div>
          <div class="subsection">
            <h3>Paths</h3>
            <pre>{{ JSON.stringify({ doc_path: skill.doc_path, script_path: skill.script_path }, null, 2) }}</pre>
          </div>
        </details>
      </article>
    </div>
    <p v-else class="muted-text">当前未加载到技能清单。</p>
  </section>
</template>

<script setup>
defineProps({
  skills: { type: Array, required: true },
})
</script>
