<script setup lang="ts">
defineProps<{ label: string; value: string | number; detail?: string }>()
</script>

<template>
  <article class="metric-card">
    <span>{{ label }}</span>
    <strong>{{ value }}</strong>
    <small v-if="detail">{{ detail }}</small>
  </article>
</template>

<style scoped>
.metric-card { background: white; border: 1px solid #dce5eb; border-radius: 10px; padding: 16px 18px; min-width: 0; box-shadow: 0 4px 12px rgba(30, 54, 74, .04); }
.metric-card span { display: block; color: #647888; font-size: 13px; }
.metric-card strong { display: block; margin-top: 8px; color: #142e43; font-size: 28px; line-height: 1; }
.metric-card small { display: block; margin-top: 8px; color: #8696a3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>

