<script setup lang="ts">
import type { Sentiment } from '../lib/api'
import Icon from './Icon.vue'

// Sentiment always ships icon + word, never color alone.
const ICONS = { positive: 'up', neutral: 'minus', negative: 'down' } as const
defineProps<{ sentiment: Sentiment }>()
</script>

<template>
  <span class="sentiment" :data-sentiment="sentiment">
    <Icon :name="ICONS[sentiment]" :size="14" />
    {{ sentiment[0]!.toUpperCase() + sentiment.slice(1) }}
  </span>
</template>

<style scoped>
.sentiment {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.125rem 0.5rem 0.125rem 0.375rem;
  border-radius: 999px;
  font-size: var(--text-xs);
  font-weight: 550;
  color: var(--sentiment-ink);
  background: color-mix(in oklab, var(--sentiment-color) 14%, transparent);
}
.sentiment[data-sentiment='positive'] {
  --sentiment-color: var(--positive);
  --sentiment-ink: var(--positive-ink);
}
.sentiment[data-sentiment='neutral'] {
  --sentiment-color: var(--neutral);
  --sentiment-ink: var(--neutral-ink);
}
.sentiment[data-sentiment='negative'] {
  --sentiment-color: var(--negative);
  --sentiment-ink: var(--negative-ink);
}
.icon {
  color: var(--sentiment-color);
}
</style>
