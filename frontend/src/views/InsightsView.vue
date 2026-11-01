<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BarList from '../components/BarList.vue'
import Icon from '../components/Icon.vue'
import { api, type Insights } from '../lib/api'
import { SENTIMENTS } from '../lib/filters'
import { plural, shortDay } from '../lib/format'
import { status } from '../lib/status'

const WINDOWS = [7, 30, 90] as const
const route = useRoute()
const router = useRouter()
const days = computed(() => {
  const n = Number(route.query.days)
  return (WINDOWS as readonly number[]).includes(n) ? n : 30
})

const data = ref<Insights | null>(null)
const error = ref<string | null>(null)
const loading = ref(true)
let controller: AbortController | undefined

async function load() {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = null
  try {
    data.value = await api.insights(days.value, controller.signal)
  } catch (e) {
    if ((e as Error).name !== 'AbortError') error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

watch([days, () => status.dataVersion], () => void load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())

const sentimentTotal = computed(() => {
  const s = data.value?.sentiment
  return s ? s.positive + s.neutral + s.negative + s.unanalyzed : 0
})
const sentimentParts = computed(() =>
  data.value ? [...SENTIMENTS, 'unanalyzed' as const].map((key) => ({ key, count: data.value!.sentiment[key] })) : [],
)
const histogramMax = computed(() => Math.max(1, ...(data.value?.relevance_histogram ?? [])))
// Fill days with no articles so the columns form a true timeline.
const daily = computed(() => {
  const rows = data.value?.daily ?? []
  if (rows.length < 2) return rows
  const counts = new Map(rows.map((d) => [d.date, d.count]))
  const out: { date: string; count: number }[] = []
  const end = new Date(`${rows[rows.length - 1]!.date}T00:00:00Z`)
  for (let day = new Date(`${rows[0]!.date}T00:00:00Z`); day <= end; day.setUTCDate(day.getUTCDate() + 1)) {
    const key = day.toISOString().slice(0, 10)
    out.push({ date: key, count: counts.get(key) ?? 0 })
  }
  return out
})
const dailyMax = computed(() => Math.max(1, ...daily.value.map((d) => d.count)))
const pct = (n: number, total: number) => (total ? Math.round((n / total) * 100) : 0)
const label = (key: string) => key[0]!.toUpperCase() + key.slice(1)

const lede = computed(() => {
  const d = data.value
  if (!d) return ''
  const parts = [`${plural(d.total, 'article')} in the last ${d.days} days`]
  if (d.total) parts.push(`${d.analyzed.toLocaleString()} analyzed`)
  if (d.avg_relevance !== null) parts.push(`average relevance ${d.avg_relevance.toFixed(1)} of 10`)
  return parts.join(', ') + '.'
})
</script>

<template>
  <div class="insights">
    <header class="head">
      <div>
        <h2 class="title">Insights</h2>
        <p class="lede" aria-live="polite">{{ loading && !data ? 'Loading…' : lede }}</p>
      </div>
      <fieldset class="segmented">
        <legend class="visually-hidden">Time window</legend>
        <label v-for="w in WINDOWS" :key="w">
          <input
            type="radio"
            name="days"
            :value="w"
            :checked="days === w"
            @change="router.replace({ query: w === 30 ? {} : { days: String(w) } })"
          />
          <span>{{ w }} days</span>
        </label>
      </fieldset>
    </header>

    <p v-if="error" class="notice error" role="alert">
      <Icon name="alert" /> Could not load insights: {{ error }}
      <button type="button" class="button ghost" @click="load()">Retry</button>
    </p>

    <div v-else-if="data && data.total === 0" class="empty">
      <h3>Nothing in this window yet</h3>
      <p>
        Insights summarize the articles collected by your refreshes. Run a refresh, or widen the window to 90 days.
      </p>
      <RouterLink class="button" to="/">Go to the feed</RouterLink>
    </div>

    <div v-else-if="data" class="grid" :class="{ stale: loading }">
      <figure class="panel span-2">
        <figcaption>
          <h3>Sentiment</h3>
          <p>What the coverage implies for employees and HR practice.</p>
        </figcaption>
        <div class="stack" aria-hidden="true">
          <span
            v-for="p in sentimentParts.filter((p) => p.count)"
            :key="p.key"
            :data-sentiment="p.key"
            :style="{ flexGrow: p.count }"
            :title="`${label(p.key)}: ${p.count} (${pct(p.count, sentimentTotal)}%)`"
          ></span>
        </div>
        <ul class="legend">
          <li v-for="p in sentimentParts" :key="p.key">
            <span class="swatch" :data-sentiment="p.key" aria-hidden="true"></span>
            {{ label(p.key) }}
            <strong class="num">{{ p.count }}</strong>
            <span class="muted num">{{ pct(p.count, sentimentTotal) }}%</span>
          </li>
        </ul>
      </figure>

      <figure class="panel">
        <figcaption>
          <h3>Relevance distribution</h3>
          <p>Analyzed articles by relevance score.</p>
        </figcaption>
        <ol class="columns" aria-label="Articles per relevance score">
          <li
            v-for="(count, i) in data.relevance_histogram"
            :key="i"
            :title="`Score ${i + 1}: ${plural(count, 'article')}`"
          >
            <span class="col-value num">{{ count || '' }}</span>
            <span class="col" :style="{ blockSize: `${(count / histogramMax) * 100}%` }" aria-hidden="true"></span>
            <span class="col-label num"><span class="visually-hidden">Score </span>{{ i + 1 }}</span>
            <span class="visually-hidden">: {{ plural(count, 'article') }}</span>
          </li>
        </ol>
      </figure>

      <figure class="panel">
        <figcaption>
          <h3>Volume</h3>
          <p>Articles per day, by publish date.</p>
        </figcaption>
        <ol class="columns daily" aria-label="Articles per day">
          <li v-for="d in daily" :key="d.date" :title="`${shortDay(d.date)}: ${plural(d.count, 'article')}`">
            <span class="col" :style="{ blockSize: `${(d.count / dailyMax) * 100}%` }" aria-hidden="true"></span>
            <span class="visually-hidden">{{ shortDay(d.date) }}: {{ plural(d.count, 'article') }}</span>
          </li>
        </ol>
        <p v-if="daily.length" class="axis muted num" aria-hidden="true">
          <span>{{ shortDay(daily[0]!.date) }}</span>
          <span>{{ shortDay(daily[daily.length - 1]!.date) }}</span>
        </p>
      </figure>

      <figure class="panel">
        <figcaption>
          <h3>Top themes</h3>
          <p>Most frequent topics the analysis extracted.</p>
        </figcaption>
        <BarList
          v-if="data.top_themes.length"
          :items="data.top_themes.map((t) => ({ label: t.name, value: t.count }))"
          unit="articles"
        />
        <p v-else class="muted">Themes appear once articles are analyzed.</p>
      </figure>

      <figure class="panel">
        <figcaption>
          <h3>Top sources</h3>
          <p>Article count, with average relevance on the right.</p>
        </figcaption>
        <BarList
          :items="
            data.top_sources.map((s) => ({
              label: s.name,
              value: s.count,
              detail: s.avg_relevance === null ? '–' : `${s.avg_relevance.toFixed(1)} avg`,
            }))
          "
          unit="articles"
        />
      </figure>
    </div>
  </div>
</template>

<style scoped>
.insights {
  padding-block: var(--space-4);
  display: grid;
  gap: var(--space-5);
}
.head {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  justify-content: space-between;
  gap: var(--space-4);
}
.title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--text-2xl);
  font-weight: 600;
}
.lede {
  margin: var(--space-1) 0 0;
  color: var(--ink-2);
  font-size: var(--text-lg);
}
.segmented {
  display: inline-flex;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  padding: 2px;
  margin: 0;
}
.segmented label {
  position: relative;
  cursor: pointer;
}
.segmented input {
  position: absolute;
  opacity: 0;
  inset: 0;
  cursor: pointer;
}
.segmented span {
  display: block;
  padding: 0.375rem 0.875rem;
  border-radius: calc(var(--radius) - 2px);
  font-size: var(--text-sm);
  font-weight: 550;
  color: var(--ink-2);
}
.segmented input:checked + span {
  background: var(--ink-1);
  color: var(--surface-1);
}
.segmented input:focus-visible + span {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}
.grid {
  display: grid;
  gap: var(--space-5) var(--space-6);
  transition: opacity 200ms;
}
.grid.stale {
  opacity: 0.6;
}
@media (min-width: 56rem) {
  .grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .span-2 {
    grid-column: span 2;
  }
}
.panel {
  margin: 0;
  display: grid;
  gap: var(--space-3);
  align-content: start;
  padding-block-start: var(--space-3);
  border-block-start: 1px solid var(--rule-strong);
}
figcaption h3 {
  margin: 0;
  font-size: var(--text-base);
}
figcaption p {
  margin: 0.125rem 0 0;
  font-size: var(--text-sm);
  color: var(--ink-3);
}
.stack {
  display: flex;
  gap: 2px;
  block-size: 1.5rem;
}
.stack span {
  min-inline-size: 4px;
}
.stack span:first-child {
  border-radius: 4px 0 0 4px;
}
.stack span:last-child {
  border-radius: 0 4px 4px 0;
}
[data-sentiment='positive'] {
  background: var(--positive);
}
[data-sentiment='neutral'] {
  background: var(--neutral);
}
[data-sentiment='negative'] {
  background: var(--negative);
}
[data-sentiment='unanalyzed'] {
  background: var(--unanalyzed);
}
.legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-5);
  font-size: var(--text-sm);
}
.legend li {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
.swatch {
  inline-size: 0.75rem;
  block-size: 0.75rem;
  border-radius: 2px;
}
.columns {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(0, 1fr);
  gap: 2px;
  block-size: 9rem;
  align-items: end;
}
.columns li {
  display: flex;
  flex-direction: column;
  justify-content: end;
  align-items: center;
  block-size: 100%;
  gap: 0.25rem;
}
.col {
  inline-size: 100%;
  max-inline-size: 2.5rem;
  min-block-size: 1px;
  border-radius: 4px 4px 0 0;
  background: var(--accent);
}
.col-value {
  font-size: var(--text-xs);
  color: var(--ink-2);
}
.col-label {
  font-size: var(--text-xs);
  color: var(--ink-3);
}
.daily {
  block-size: 7.5rem;
}
.axis {
  display: flex;
  justify-content: space-between;
  margin: 0;
  font-size: var(--text-xs);
}
.empty {
  max-inline-size: 46ch;
  padding-block: var(--space-6);
}
.empty h3 {
  font-family: var(--font-serif);
  font-size: var(--text-xl);
  margin: 0 0 var(--space-2);
}
.empty p {
  color: var(--ink-2);
  margin: 0 0 var(--space-4);
}
</style>
