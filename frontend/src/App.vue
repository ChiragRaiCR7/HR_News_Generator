<script setup lang="ts">
import { onMounted } from 'vue'
import Icon from './components/Icon.vue'
import RefreshPanel from './components/RefreshPanel.vue'
import { loadStatus, status } from './lib/status'

onMounted(loadStatus)
</script>

<template>
  <a class="skip" href="#main">Skip to content</a>
  <header class="masthead">
    <div class="wrap bar">
      <p class="brand">
        <span class="mark" aria-hidden="true">N</span>
        HR News <span class="brand-light">Intelligence</span>
      </p>
      <nav aria-label="Primary">
        <RouterLink to="/" class="tab">Feed</RouterLink>
        <RouterLink to="/insights" class="tab">Insights</RouterLink>
      </nav>
    </div>
  </header>

  <main id="main" class="wrap">
    <h1 class="visually-hidden">HR News Intelligence</h1>
    <p v-if="status.healthError" class="notice error server-down" role="alert">
      <Icon name="alert" /> Cannot reach the API server ({{ status.healthError }}). Start the backend and reload.
    </p>
    <RefreshPanel />
    <RouterView />
  </main>

  <footer class="wrap footer">
    <p>
      Search by SerpAPI · analysis by Google Gemini
      <template v-if="status.health"> ({{ status.health.model }})</template>. Summaries are machine-written; open the
      source before you act on one.
    </p>
  </footer>
</template>

<style scoped>
.wrap {
  inline-size: min(100% - 2rem, 76rem);
  margin-inline: auto;
}
.skip {
  position: absolute;
  inset-inline-start: 1rem;
  inset-block-start: -3rem;
  padding: 0.5rem 1rem;
  background: var(--ink-1);
  color: var(--surface-1);
  border-radius: var(--radius);
  z-index: 10;
}
.skip:focus {
  inset-block-start: 0.5rem;
}
.masthead {
  border-block-end: 1px solid var(--rule-strong);
  background: var(--surface-1);
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-block-size: 3.75rem;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--text-xl);
  font-weight: 650;
  letter-spacing: -0.01em;
}
.brand-light {
  font-weight: 400;
  color: var(--ink-2);
}
.mark {
  display: grid;
  place-items: center;
  inline-size: 1.75rem;
  block-size: 1.75rem;
  border-radius: 6px;
  background: var(--accent);
  color: var(--surface-1);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  font-weight: 700;
}
nav {
  display: flex;
  gap: var(--space-1);
  align-self: stretch;
}
.tab {
  display: inline-flex;
  align-items: center;
  padding-inline: var(--space-3);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink-2);
  text-decoration: none;
  border-block-end: 2px solid transparent;
  margin-block-end: -1px;
  transition: color 150ms;
}
.tab:hover {
  color: var(--ink-1);
}
.tab.router-link-exact-active {
  color: var(--ink-1);
  border-block-end-color: var(--accent);
}
.server-down {
  margin-block-start: var(--space-4);
}
.footer {
  padding-block: var(--space-6) var(--space-5);
  font-size: var(--text-xs);
  color: var(--ink-3);
}
@media (max-width: 30rem) {
  .brand-light {
    display: none;
  }
}
</style>
