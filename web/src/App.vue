<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import HomeView from './components/HomeView.vue'
import DetailView from './components/DetailView.vue'
import TopSearch from './components/TopSearch.vue'
import SettingsDrawer from './components/SettingsDrawer.vue'

const data = ref(null)
const loading = ref(true)
const error = ref('')
const view = ref('home')
const activeId = ref('Ahri')
const favorites = ref([])
const searchSignal = ref(0)
const settingsOpen = ref(false)
const topSearchRef = ref(null)
const FAV_KEY = 'mayhem-favorites-v1'
const FS_KEY = 'mayhem-fontscale-v1'
const FS_STEPS = [1.15, 1.25, 1.35, 1.5, 1.65]
const fsLevel = ref(2)
const fsValue = computed(() => FS_STEPS[fsLevel.value])

function applyFontScale() {
  document.documentElement.style.setProperty('--fs', String(fsValue.value))
}
function bumpFont(delta) {
  fsLevel.value = Math.min(FS_STEPS.length - 1, Math.max(0, fsLevel.value + delta))
}
function resetFont() { fsLevel.value = 2 }

onMounted(async () => {
  try {
    const raw = localStorage.getItem(FAV_KEY)
    if (raw) favorites.value = JSON.parse(raw)
  } catch {}
  try {
    const rawFs = localStorage.getItem(FS_KEY)
    if (rawFs !== null) {
      const lv = Number(rawFs)
      if (Number.isInteger(lv) && lv >= 0 && lv < FS_STEPS.length) fsLevel.value = lv
    }
  } catch {}
  applyFontScale()
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

watch(fsLevel, lv => {
  applyFontScale()
  try { localStorage.setItem(FS_KEY, String(lv)) } catch {}
})

watch(favorites, v => {
  try { localStorage.setItem(FAV_KEY, JSON.stringify(v)) } catch {}
}, { deep: true })

const champion = computed(() => data.value?.champions.find(c => c.id === activeId.value))
const report = computed(() => data.value?.reports[activeId.value])
const styleMeta = computed(() => data.value?.styles || {})
const patch = computed(() => data.value?.patch || '')
const ddragon = computed(() => data.value?.ddragon || '')

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

function scrollTopInstant() {
  const html = document.documentElement
  const prev = html.style.scrollBehavior
  html.style.scrollBehavior = 'auto'
  window.scrollTo(0, 0)
  html.style.scrollBehavior = prev
}

function openChampion(id) {
  if (!data.value?.reports[id]) return
  activeId.value = id
  view.value = 'detail'
  const hash = '#/champion/' + encodeURIComponent(id)
  if (location.hash !== hash) history.pushState(null, '', hash)
  scrollTopInstant()
}

function goHome() {
  view.value = 'home'
  if (location.hash !== '#/') history.pushState(null, '', '#/')
}

function toggleFavorite(id) {
  const i = favorites.value.indexOf(id)
  if (i >= 0) favorites.value.splice(i, 1)
  else favorites.value.push(id)
}

function openSearch() {
  topSearchRef.value?.focus()
}

function onGlobalKey(e) {
  const tag = document.activeElement?.tagName
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)
  if (e.key === 'Escape' && settingsOpen.value) {
    settingsOpen.value = false
    return
  }
  if (typing) return
  if (e.key === '/' || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k')) {
    e.preventDefault()
    openSearch()
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
      <button v-if="view === 'detail'" class="back-btn topbar-back" @click="goHome">
        <span aria-hidden="true">←</span> 英雄库
      </button>

      <TopSearch
        ref="topSearchRef"
        :champions="data?.champions || []"
        :favorites="favorites"
        :ddragon="ddragon"
        :focus-signal="searchSignal"
        @select="openChampion"
      />

      <div class="topbar-right">
        <span class="patch-pill">PATCH {{ patch }}</span>
        <button class="settings-btn" :class="{ on: settingsOpen }" aria-label="打开设置" title="设置" @click="settingsOpen = true">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z" />
            <path d="M19.4 13a7.9 7.9 0 0 0 .05-2l1.35-1.04-1.9-3.3-1.6.63a7.6 7.6 0 0 0-1.73-1L15.3 4.5h-3.8l-.27 1.79a7.6 7.6 0 0 0-1.73 1l-1.6-.63-1.9 3.3L7.35 11a7.9 7.9 0 0 0 0 2l-1.35 1.04 1.9 3.3 1.6-.63c.52.42 1.1.76 1.73 1l.27 1.79h3.8l.27-1.79c.63-.24 1.2-.58 1.73-1l1.6.63 1.9-3.3L19.4 13Z" />
          </svg>
        </button>
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

    <KeepAlive v-else>
      <HomeView
        v-if="view === 'home'"
        :champions="data.champions"
        :favorites="favorites"
        :ddragon="ddragon"
        :patch="patch"
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
    </KeepAlive>

    <SettingsDrawer
      :open="settingsOpen"
      :fs-level="fsLevel"
      :fs-steps="FS_STEPS"
      :patch="patch"
      :ddragon="ddragon"
      :champion-count="data?.champions.length || 0"
      @close="settingsOpen = false"
      @bump="bumpFont"
      @reset="resetFont"
    />
  </div>
</template>
