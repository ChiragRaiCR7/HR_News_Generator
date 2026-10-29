<script setup lang="ts">
// Horizontal bar list: one series, values printed beside each bar, so it reads without color or hover.
import { computed } from 'vue'

const props = defineProps<{ items: { label: string; value: number; detail?: string }[]; unit: string }>()
const max = computed(() => Math.max(1, ...props.items.map((i) => i.value)))
</script>

<template>
  <ol class="bars">
    <li v-for="item in items" :key="item.label" :title="`${item.label}: ${item.value} ${unit}`">
      <span class="label">{{ item.label }}</span>
      <span class="track" aria-hidden="true"><span class="fill" :style="{ inlineSize: `${(item.value / max) * 100}%` }"></span></span>
      <span class="value num">{{ item.value }}<span class="visually-hidden"> {{ unit }}</span></span>
      <span v-if="item.detail" class="detail num">{{ item.detail }}</span>
    </li>
  </ol>
</template>

<style scoped>
.bars {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--space-2);
}
li {
  display: grid;
  grid-template-columns: minmax(6rem, 11rem) minmax(0, 1fr) 2.5rem;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-sm);
}
li:has(.detail) {
  grid-template-columns: minmax(6rem, 11rem) minmax(0, 1fr) 2.5rem 4.5rem;
}
.label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.track {
  block-size: 0.625rem;
}
.fill {
  display: block;
  block-size: 100%;
  min-inline-size: 2px;
  border-radius: 0 4px 4px 0;
  background: var(--accent);
}
.value {
  text-align: end;
  color: var(--ink-1);
  font-weight: 550;
}
.detail {
  text-align: end;
  color: var(--ink-3);
}
</style>
