<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import HomeView from './components/HomeView.vue'
import DetailView from './components/DetailView.vue'

const data = ref(null)
const loading = ref(true)
const error = ref('')
const view = ref('home')
const activeId = ref('Ahri')
const favorites = ref([])
const searchSignal = ref(0)
const FAV_KEY = 'mayhem-favorites-v1'

onMounted(async () => {
  try {
    const raw = localStorage.getItem(FAV_KEY)
    if (raw) favorites.value = JSON.parse(raw)
  } catch {}
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}data/lol.json`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    data.value = await res.json()
    applyRoute()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
  window.addEventListener('keydown', onGlobalKey)
  window.addEventListener('popstate', applyRoute)
  window.addEventListener('hashchange', applyRoute)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKey)
  window.removeEventListener('popstate', applyRoute)
  window.removeEventListener('hashchange', applyRoute)
})

watch(favorites, v => {
  try { localStorage.setItem(FAV_KEY, JSON.stringify(v)) } catch {}
}, { deep: true })

const champion = computed(() => data.value?.champions.find(c => c.id === activeId.value))
const report = computed(() => data.value?.reports[activeId.value])
const styleMeta = computed(() => data.value?.styles || {})
const patch = computed(() => data.value?.patch || '')
const ddragon = computed(() => data.value?.ddragon || '')
const favoriteSet = computed(() => new Set(favorites.value))

function applyRoute() {
  if (!data.value) return
  const m = location.hash.match(/^#\/champion\/([^/?#]+)/)
  if (m) {
    const id = decodeURIComponent(m[1])
    if (data.value.reports[id]) {
      activeId.value = id
      view.value = 'detail'
      return
    }
  }
  view.value = 'home'
}

function openChampion(id) {
  if (!data.value?.reports[id]) return
  activeId.value = id
  view.value = 'detail'
  const hash = '#/champion/' + encodeURIComponent(id)
  if (location.hash !== hash) history.pushState(null, '', hash)
  jumpTop()
}

function goHome() {
  view.value = 'home'
  if (location.hash !== '#/') history.pushState(null, '', '#/')
  jumpTop()
}

function jumpTop() {
  const html = document.documentElement
  const prev = html.style.scrollBehavior
  html.style.scrollBehavior = 'auto'
  window.scrollTo(0, 0)
  html.style.scrollBehavior = prev
}

function toggleFavorite(id) {
  const i = favorites.value.indexOf(id)
  if (i >= 0) favorites.value.splice(i, 1)
  else favorites.value.push(id)
}

function onGlobalKey(e) {
  const tag = document.activeElement?.tagName
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)
  if (typing) return
  if (e.key === '/' || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k')) {
    e.preventDefault()
    if (view.value === 'detail') goHome()
    searchSignal.value++
  }
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <button class="brand" @click="goHome" aria-label="返回英雄库">
        <span class="brand-mark">M</span>
        <span class="brand-name">MAYHEM LAB</span>
      </button>
      <div class="topbar-mid" v-if="view === 'detail' && champion">
        <button class="back-btn" @click="goHome">← 英雄库</button>
        <span class="crumb">{{ champion.title }}</span>
      </div>
      <div v-else class="topbar-mid">
        <span class="top-count">{{ data?.champions.length || 173 }} 英雄</span>
        <span class="top-sep"></span>
        <span class="top-count">A–Z 拼音</span>
      </div>
      <div class="topbar-right">
        <span class="patch-pill">PATCH {{ patch }}</span>
      </div>
    </header>

    <div v-if="loading" class="state-screen">
      <div class="loader"></div>
      <p>正在载入 173 位英雄与 255 个海克斯…</p>
    </div>
    <div v-else-if="error" class="state-screen">
      <p class="error">数据加载失败：{{ error }}</p>
      <p class="hint">请确认已运行 <code>python3 scripts/export_web.py</code>，并通过 Vite 启动页面。</p>
    </div>

    <HomeView
      v-else-if="view === 'home'"
      :champions="data.champions"
      :favorites="favorites"
      :ddragon="ddragon"
      :patch="patch"
      :focus-signal="searchSignal"
      @select="openChampion"
      @favorite="toggleFavorite"
    />
    <DetailView
      v-else-if="champion && report"
      :champion="champion"
      :report="report"
      :style-meta="styleMeta"
      :patch="patch"
      :ddragon="ddragon"
      :favorites="favorites"
      @favorite="toggleFavorite"
    />
  </div>
</template>
