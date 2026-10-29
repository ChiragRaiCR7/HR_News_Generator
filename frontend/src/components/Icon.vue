<script setup lang="ts">
// Lucide icon paths (ISC license), drawn at one stroke weight. Decorative unless labelled by context.
const PATHS = {
  refresh: ['M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8', 'M3 3v5h5', 'M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16', 'M16 16h5v5'],
  external: ['M15 3h6v6', 'M10 14 21 3', 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6'],
  search: ['m21 21-4.34-4.34', 'M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16z'],
  up: ['m18 15-6-6-6 6'],
  down: ['m6 9 6 6 6-6'],
  minus: ['M5 12h14'],
  alert: ['M12 9v4', 'M12 17h.01', 'M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z'],
  check: ['M20 6 9 17l-5-5'],
  filter: ['M22 3H2l8 9.46V19l4 2v-8.54L22 3z'],
  x: ['M18 6 6 18', 'm6 6 12 12'],
} as const

defineProps<{ name: keyof typeof PATHS; size?: number }>()
</script>

<template>
  <svg
    class="icon"
    :width="size ?? 16"
    :height="size ?? 16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="d in PATHS[name]" :key="d" :d="d" />
  </svg>
</template>
