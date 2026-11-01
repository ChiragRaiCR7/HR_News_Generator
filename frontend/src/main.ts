import '@fontsource-variable/geist'
import '@fontsource-variable/source-serif-4'
import './styles.css'
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'

createApp(App).use(router).mount('#app')
