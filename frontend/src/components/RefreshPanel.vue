<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { parseKeywords } from '../lib/filters'
import { fullDate, plural, timeAgo } from '../lib/format'
import { startRefresh, status } from '../lib/status'
import Icon from './Icon.vue'

const DEFAULT_KEYWORDS = 'HR trends, talent acquisition, employee engagement'

const keywords = ref(DEFAULT_KEYWORDS)
let keywordsEdited = false
// Prefill with the last run's keywords once they load, unless the reader already typed.
watch(
  () => status.latestRun?.keywords,
  (last) => {
    if (last?.length && !keywordsEdited) keywords.value = last.join(', ')
  },
  { immediate: true },
)

function onKeywordsInput(event: Event) {
  keywordsEdited = true
  ;(event.target as HTMLInputElement).setCustomValidity('')
}
const maxResults = ref(15)
const analyze = ref(true)
const submitError = ref<string | null>(null)
const submitting = ref(false)

const run = computed(() => status.latestRun)
const running = computed(() => run.value?.status === 'running')
const searchReady = computed(() => status.health?.serpapi_configured ?? false)

const progress = computed(() => {
  const r = run.value
  if (!r || r.status !== 'running' || r.phase === 'fetching' || r.to_analyze === 0) return null
  return { value: r.analyzed + r.analysis_failed, max: r.to_analyze }
})

const phaseLabel = computed(() => {
  const r = run.value
  if (!r || r.status !== 'running') return ''
  if (r.phase === 'fetching') return `Searching ${plural(r.keywords.length, 'keyword')}…`
  return `Analyzing ${r.analyzed + r.analysis_failed} of ${r.to_analyze} articles…`
})

const outcome = computed(() => {
  const r = run.value
  if (!r || r.status === 'running') return null
  if (r.status === 'failed') return { tone: 'error', text: r.error ?? 'The refresh failed.' }
  const parts = [`${plural(r.fetched, 'article')} found`, `${r.new} new`]
  if (r.analyze && r.to_analyze) parts.push(`${r.analyzed} analyzed`)
  return { tone: r.status === 'partial' ? 'warn' : 'ok', text: parts.join(' · ') }
})

async function submit(event: Event) {
  const form = event.target as HTMLFormElement
  const input = form.elements.namedItem('keywords') as HTMLInputElement
  const parsed = parseKeywords(keywords.value)
  input.setCustomValidity(
    parsed.length === 0 ? 'Enter at least one keyword.' : parsed.length > 10 ? 'Use at most 10 keywords.' : '',
  )
  if (!form.reportValidity() || submitting.value) return
  submitting.value = true
  submitError.value = await startRefresh({ keywords: parsed, max_results: maxResults.value, analyze: analyze.value })
  submitting.value = false
}
</script>

<template>
  <section class="refresh" aria-labelledby="refresh-title">
    <h2 id="refresh-title" class="visually-hidden">Refresh news</h2>
    <form class="refresh-form" novalidate @submit.prevent="submit">
      <div class="field keywords">
        <div class="label-row">
          <label for="keywords">Keywords</label>
          <span id="keywords-hint" class="hint">Comma-separated, up to 10</span>
        </div>
        <input
          id="keywords"
          v-model="keywords"
          name="keywords"
          type="search"
          required
          maxlength="1000"
          autocomplete="off"
          spellcheck="false"
          enterkeyhint="go"
          aria-describedby="keywords-hint"
          @input="onKeywordsInput"
        />
      </div>
      <div class="field results">
        <label for="max-results">Results <output for="max-results" class="num">{{ maxResults }}</output></label>
        <input id="max-results" v-model.number="maxResults" name="max_results" type="range" min="5" max="50" step="5" />
      </div>
      <label class="switch">
        <input v-model="analyze" name="analyze" type="checkbox" role="switch" />
        <span>AI analysis</span>
      </label>
      <button class="button primary" type="submit" :disabled="running || submitting || !searchReady">
        <Icon name="refresh" :class="{ spinning: running }" />
        {{ running ? 'Refreshing…' : 'Refresh news' }}
      </button>
    </form>

    <div class="run-status">
      <template v-if="running">
        <label for="run-progress" class="phase">{{ phaseLabel }}</label>
        <progress id="run-progress" :value="progress?.value" :max="progress?.max ?? 1"></progress>
      </template>
      <p v-else-if="!searchReady && status.health" class="notice warn" role="status">
        <Icon name="alert" /> News search is off. Add <code>SERPAPI_KEY</code> to <code>backend/.env</code> and restart
        the server.
      </p>
      <div role="status" class="announce">
        <p v-if="submitError" class="notice error"><Icon name="alert" /> {{ submitError }}</p>
        <p v-else-if="outcome" class="notice" :class="outcome.tone">
          <Icon :name="outcome.tone === 'ok' ? 'check' : 'alert'" />
          <span>
            {{ outcome.text }}
            <time v-if="run?.finished_at" :datetime="run.finished_at" :title="fullDate(run.finished_at)">
              · {{ timeAgo(run.finished_at) }}</time
            >
          </span>
        </p>
      </div>
      <ul v-if="!running && run?.warnings.length" class="warnings">
        <li v-for="w in run.warnings" :key="w">{{ w }}</li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.refresh {
  display: grid;
  gap: var(--space-3);
  padding-block: var(--space-4);
  border-block-end: 1px solid var(--rule);
}
.refresh-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-3);
  align-items: end;
}
@media (min-width: 52rem) {
  .refresh-form {
    grid-template-columns: minmax(0, 1fr) 11rem auto auto;
  }
}
.field {
  display: grid;
  gap: var(--space-1);
}
.field label {
  font-size: var(--text-sm);
  font-weight: 550;
  display: flex;
  justify-content: space-between;
}
.hint {
  font-size: var(--text-xs);
  color: var(--ink-3);
}
.label-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-2);
}
.results input {
  inline-size: 100%;
  block-size: 2.75rem;
}
.switch {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-block-size: 2.75rem;
  font-size: var(--text-sm);
  font-weight: 550;
  cursor: pointer;
}
.switch input {
  inline-size: 1.125rem;
  block-size: 1.125rem;
}
.run-status {
  min-block-size: 1.75rem;
  display: grid;
  gap: var(--space-2);
}
.phase {
  font-size: var(--text-sm);
  color: var(--ink-2);
}
.warnings {
  margin: 0;
  padding-inline-start: 1.5rem;
  font-size: var(--text-sm);
  color: var(--ink-2);
}
.spinning {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    rotate: 360deg;
  }
}
@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation-duration: 4s;
  }
}
</style>
