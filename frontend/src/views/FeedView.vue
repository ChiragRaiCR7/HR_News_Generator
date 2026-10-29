<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ArticleItem from '../components/ArticleItem.vue'
import Icon from '../components/Icon.vue'
import { api, type Article, type NameCount } from '../lib/api'
import { activeFilterCount, filtersToParams, filtersToQuery, parseFilters, SENTIMENTS, type FeedFilters } from '../lib/filters'
import { plural } from '../lib/format'
import { status } from '../lib/status'

const PAGE_SIZE = 20
// Filters start expanded beside the list on wide screens, collapsed above it on narrow ones.
const wideLayout = window.matchMedia('(min-width: 60rem)').matches
const SEARCH_DEBOUNCE_MS = 300

const route = useRoute()
const router = useRouter()
const filters = computed(() => parseFilters(route.query))

const items = ref<Article[]>([])
const total = ref(0)
const sources = ref<NameCount[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const error = ref<string | null>(null)
const searchText = ref(filters.value.q)
let controller: AbortController | undefined
let searchTimer: ReturnType<typeof setTimeout> | undefined

function update(patch: Partial<FeedFilters>) {
  void router.replace({ query: filtersToQuery({ ...filters.value, ...patch }) })
}

function toggle<T>(list: readonly T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => update({ q: searchText.value }), SEARCH_DEBOUNCE_MS)
}

async function load(append = false) {
  controller?.abort()
  controller = new AbortController()
  append ? (loadingMore.value = true) : (loading.value = true)
  error.value = null
  try {
    const page = await api.articles(
      { ...filtersToParams(filters.value), limit: PAGE_SIZE, offset: append ? items.value.length : 0 },
      controller.signal,
    )
    items.value = append ? [...items.value, ...page.items] : page.items
    total.value = page.total
  } catch (e) {
    if ((e as Error).name !== 'AbortError') error.value = (e as Error).message
  } finally {
    loading.value = loadingMore.value = false
  }
}

async function loadSources() {
  try {
    sources.value = await api.sources()
  } catch {
    // The source filter is optional; the feed still works without it.
  }
}

watch(filters, () => void load(), { deep: true })
watch(
  () => route.query.q,
  (q) => {
    if (typeof q !== 'string' || q !== searchText.value.trim()) searchText.value = typeof q === 'string' ? q : ''
  },
)
watch(
  () => status.dataVersion,
  () => {
    void load()
    void loadSources()
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  controller?.abort()
  clearTimeout(searchTimer)
})

const activeCount = computed(() => activeFilterCount(filters.value))
const hasMore = computed(() => items.value.length < total.value)
</script>

<template>
  <div class="feed">
    <aside class="filters" aria-labelledby="filters-title">
      <details class="filters-details" :open="wideLayout">
        <summary>
          <h2 id="filters-title"><Icon name="filter" /> Filters</h2>
          <span v-if="activeCount" class="count">{{ activeCount }} active</span>
        </summary>
        <form class="filter-form" role="search" @submit.prevent>
          <div class="field">
            <label for="q">Search</label>
            <div class="search-box">
              <Icon name="search" />
              <input
                id="q"
                v-model="searchText"
                type="search"
                name="q"
                maxlength="200"
                autocomplete="off"
                spellcheck="false"
                placeholder="Title, snippet, or summary"
                @input="onSearch"
              />
            </div>
          </div>

          <fieldset>
            <legend>Sort by</legend>
            <label v-for="option in ['newest', 'relevance'] as const" :key="option" class="choice">
              <input type="radio" name="sort" :checked="filters.sort === option" @change="update({ sort: option })" />
              {{ option === 'newest' ? 'Newest' : 'Most relevant' }}
            </label>
          </fieldset>

          <fieldset>
            <legend>Sentiment</legend>
            <label v-for="s in SENTIMENTS" :key="s" class="choice">
              <input
                type="checkbox"
                name="sentiment"
                :value="s"
                :checked="filters.sentiment.includes(s)"
                @change="update({ sentiment: toggle(filters.sentiment, s) })"
              />
              <span class="swatch" :data-sentiment="s" aria-hidden="true"></span>
              {{ s[0]!.toUpperCase() + s.slice(1) }}
            </label>
          </fieldset>

          <div class="field">
            <label for="min-relevance">Minimum relevance</label>
            <select
              id="min-relevance"
              name="min"
              :value="filters.minRelevance ?? ''"
              @change="update({ minRelevance: Number(($event.target as HTMLSelectElement).value) || null })"
            >
              <option value="">Any</option>
              <option v-for="n in [9, 8, 7, 6, 5, 4, 3, 2]" :key="n" :value="n">{{ n }}+ out of 10</option>
            </select>
          </div>

          <fieldset v-if="sources.length">
            <legend>Source</legend>
            <div class="source-list">
              <label v-for="s in sources" :key="s.name" class="choice">
                <input
                  type="checkbox"
                  name="source"
                  :value="s.name"
                  :checked="filters.source.includes(s.name)"
                  @change="update({ source: toggle(filters.source, s.name) })"
                />
                <span class="source-name">{{ s.name }}</span>
                <span class="num muted">{{ s.count }}</span>
              </label>
            </div>
          </fieldset>

          <button v-if="activeCount" type="button" class="button ghost" @click="router.replace({ query: {} })">
            <Icon name="x" /> Clear filters
          </button>
        </form>
      </details>
    </aside>

    <section class="results" aria-labelledby="results-title" :aria-busy="loading">
      <header class="results-head">
        <h2 id="results-title">Articles</h2>
        <p class="muted" role="status">
          <template v-if="!loading">{{ plural(total, 'article') }}{{ activeCount ? ' match' : '' }}</template>
        </p>
      </header>

      <p v-if="error" class="notice error" role="alert">
        <Icon name="alert" /> Could not load articles: {{ error }}
        <button type="button" class="button ghost" @click="load()">Retry</button>
      </p>

      <ol v-else-if="loading" class="skeleton" aria-hidden="true">
        <li v-for="n in 5" :key="n"><span></span><span></span><span></span></li>
      </ol>

      <div v-else-if="items.length === 0" class="empty">
        <template v-if="activeCount">
          <h3>No articles match these filters</h3>
          <p>Loosen a filter or clear them to see everything collected so far.</p>
          <button type="button" class="button" @click="router.replace({ query: {} })">Clear filters</button>
        </template>
        <template v-else>
          <h3>No articles yet</h3>
          <p>
            Enter the HR topics you follow above and choose <strong>Refresh news</strong>. Articles are kept between
            refreshes, so this feed becomes your searchable history.
          </p>
        </template>
      </div>

      <template v-else>
        <ol class="list">
          <li v-for="article in items" :key="article.id"><ArticleItem :article="article" /></li>
        </ol>
        <button v-if="hasMore" type="button" class="button more" :disabled="loadingMore" @click="load(true)">
          {{ loadingMore ? 'Loading…' : `Show more (${total - items.length} left)` }}
        </button>
      </template>
    </section>
  </div>
</template>

<style scoped>
.feed {
  display: grid;
  gap: var(--space-5);
  padding-block: var(--space-4);
}
@media (min-width: 60rem) {
  .feed {
    grid-template-columns: 16rem minmax(0, 1fr);
    align-items: start;
  }
  .filters {
    position: sticky;
    inset-block-start: var(--space-4);
  }
}
.filters-details > summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  cursor: pointer;
  min-block-size: 2.75rem;
}
.filters-details > summary h2 {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0;
  font-size: var(--text-base);
}
.count {
  font-size: var(--text-xs);
  color: var(--accent-ink);
  font-weight: 600;
}
.filter-form {
  display: grid;
  gap: var(--space-4);
  padding-block-start: var(--space-2);
}
.field {
  display: grid;
  gap: var(--space-1);
}
.field > label,
legend {
  font-size: var(--text-sm);
  font-weight: 600;
}
fieldset {
  border: 0;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.125rem;
}
legend {
  padding: 0;
  margin-block-end: var(--space-1);
}
.choice {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-block-size: 2rem;
  font-size: var(--text-sm);
  cursor: pointer;
}
.source-list {
  display: grid;
  max-block-size: 16rem;
  overflow-y: auto;
  padding-inline-end: var(--space-2);
}
.source-name {
  flex: 1;
  min-inline-size: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.swatch {
  inline-size: 0.625rem;
  block-size: 0.625rem;
  border-radius: 2px;
}
.swatch[data-sentiment='positive'] {
  background: var(--positive);
}
.swatch[data-sentiment='neutral'] {
  background: var(--neutral);
}
.swatch[data-sentiment='negative'] {
  background: var(--negative);
}
.search-box {
  position: relative;
}
.search-box .icon {
  position: absolute;
  inset-inline-start: 0.75rem;
  inset-block-start: 50%;
  translate: 0 -50%;
  color: var(--ink-3);
  pointer-events: none;
}
.search-box input {
  padding-inline-start: 2.25rem;
}
.results-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  border-block-end: 1px solid var(--rule-strong);
  padding-block-end: var(--space-2);
}
.results-head h2 {
  margin: 0;
  font-size: var(--text-base);
}
.results-head p {
  margin: 0;
  font-size: var(--text-sm);
}
.list,
.skeleton {
  list-style: none;
  margin: 0;
  padding: 0;
}
.skeleton li {
  display: grid;
  gap: var(--space-2);
  padding-block: var(--space-4);
  border-block-end: 1px solid var(--rule);
}
.skeleton span {
  block-size: 0.875rem;
  border-radius: 4px;
  background: var(--surface-2);
}
.skeleton span:first-child {
  block-size: 1.25rem;
  inline-size: 70%;
}
.skeleton span:last-child {
  inline-size: 45%;
}
.empty {
  padding-block: var(--space-6);
  max-inline-size: 46ch;
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
.more {
  margin-block-start: var(--space-4);
}
</style>
