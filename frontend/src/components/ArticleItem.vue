<script setup lang="ts">
import { computed } from 'vue'
import type { Article } from '../lib/api'
import { fullDate, safeHref, timeAgo } from '../lib/format'
import Icon from './Icon.vue'
import SentimentBadge from './SentimentBadge.vue'

const props = defineProps<{ article: Article }>()

const href = computed(() => safeHref(props.article.url))
const when = computed(() => props.article.published_at ?? props.article.first_seen_at)
const STATUS_LABEL = {
  pending: 'Analysis pending',
  failed: 'Analysis failed',
  skipped: 'Not analyzed',
  done: '',
} as const
</script>

<template>
  <article class="item" :aria-labelledby="`title-${article.id}`">
    <div class="score" :data-band="article.relevance === null ? 'none' : article.relevance >= 8 ? 'high' : article.relevance >= 5 ? 'mid' : 'low'">
      <template v-if="article.relevance !== null">
        <span class="num">{{ article.relevance }}</span>
        <span class="visually-hidden">out of 10 relevance</span>
      </template>
      <span v-else aria-hidden="true">–</span>
    </div>
    <div class="body">
      <h3 :id="`title-${article.id}`" class="title">
        <a v-if="href" :href="href" target="_blank" rel="noopener noreferrer">
          {{ article.title }}<Icon name="external" :size="14" class="ext" />
          <span class="visually-hidden">(opens in a new tab)</span>
        </a>
        <template v-else>{{ article.title }}</template>
      </h3>
      <p class="meta">
        <span class="source">{{ article.source }}</span>
        <time :datetime="when" :title="fullDate(when)">{{ timeAgo(when) }}</time>
        <span class="keyword">via “{{ article.keyword }}”</span>
      </p>
      <p v-if="article.summary" class="summary">{{ article.summary }}</p>
      <p v-else-if="article.snippet" class="summary snippet">{{ article.snippet }}</p>
      <div class="tags">
        <SentimentBadge v-if="article.sentiment" :sentiment="article.sentiment" />
        <span v-else class="status" :title="article.analysis_error ?? undefined">
          {{ STATUS_LABEL[article.analysis_status] }}
        </span>
        <ul v-if="article.themes.length" class="themes" aria-label="Themes">
          <li v-for="theme in article.themes" :key="theme">{{ theme }}</li>
        </ul>
      </div>
    </div>
  </article>
</template>

<style scoped>
.item {
  display: grid;
  grid-template-columns: 2.75rem minmax(0, 1fr);
  gap: var(--space-3);
  padding-block: var(--space-4);
  border-block-end: 1px solid var(--rule);
}
.score {
  display: grid;
  place-items: center;
  inline-size: 2.75rem;
  block-size: 2.75rem;
  border-radius: var(--radius);
  font-size: var(--text-lg);
  font-weight: 650;
  color: var(--ink-3);
  background: var(--surface-2);
}
.score[data-band='high'] {
  color: var(--accent-ink);
  background: color-mix(in oklab, var(--accent) 16%, var(--surface-1));
}
.score[data-band='mid'] {
  color: var(--ink-1);
}
.body {
  display: grid;
  gap: var(--space-1);
  min-inline-size: 0;
}
.title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--text-lg);
  font-weight: 600;
  line-height: 1.3;
  text-wrap: pretty;
}
.title a {
  color: inherit;
  text-decoration-color: transparent;
  text-underline-offset: 0.2em;
  transition: text-decoration-color 150ms;
}
.title a:hover {
  text-decoration-color: var(--accent);
}
.ext {
  display: inline;
  margin-inline-start: 0.35em;
  vertical-align: -0.05em;
  color: var(--ink-3);
}
.meta {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0 var(--space-2);
  font-size: var(--text-sm);
  color: var(--ink-3);
}
.meta > * + *::before {
  content: '·';
  margin-inline-end: var(--space-2);
}
.source {
  color: var(--ink-2);
  font-weight: 550;
}
.summary {
  margin: var(--space-1) 0 0;
  max-inline-size: 72ch;
  color: var(--ink-2);
}
.snippet {
  color: var(--ink-3);
}
.tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-block-start: var(--space-1);
}
.status {
  font-size: var(--text-xs);
  color: var(--ink-3);
  font-style: italic;
}
.themes {
  display: contents;
  list-style: none;
}
.themes li {
  font-size: var(--text-xs);
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--rule);
  color: var(--ink-2);
}
</style>
