import { createRouter, createWebHistory } from 'vue-router'
import FeedView from './views/FeedView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'feed', component: FeedView, meta: { title: 'Feed' } },
    {
      path: '/insights',
      name: 'insights',
      component: () => import('./views/InsightsView.vue'),
      meta: { title: 'Insights' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title ?? 'Feed')} · HR News Intelligence`
})
