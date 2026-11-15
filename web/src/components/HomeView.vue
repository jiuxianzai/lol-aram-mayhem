<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, onActivated, onDeactivated, nextTick } from 'vue'
import { compareKey, searchChampions } from '../search.js'

const props = defineProps({
  champions: { type: Array, default: () => [] },
  favorites: { type: Array, default: () => [] },
  ddragon: String,
  patch: String,
  focusSignal: { type: Number, default: 0 },
})
const emit = defineEmits(['select', 'favorite'])

const query = ref('')
const inputEl = ref(null)
const activeLetter = ref('')
const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')
const dragging = ref(false)
let scrollRaf = 0
let manualUntil = 0

const favSet = computed(() => new Set(props.favorites))
const results = computed(() => searchChampions(props.champions, query.value, favSet.value))

const favList = computed(() =>
  props.champions.filter(c => favSet.value.has(c.id)).sort(compareKey)
)
const available = computed(() => new Set(props.champions.map(c => c.initial)))
const letterList = computed(() => {
  const base = [...letters]
  if (available.value.has('#')) base.push('#')
  return base
})
const sortedAll = computed(() => [...props.champions].sort(compareKey))
const groups = computed(() => {
  const map = new Map()
  for (const c of sortedAll.value) {
    if (!map.has(c.initial)) map.set(c.initial, [])
    map.get(c.initial).push(c)
  }
  return [...map.entries()].map(([letter, items]) => ({ letter, items }))
})

function topStyle(c) {
  return Object.entries(c.styles).sort((a, b) => b[1].score - a[1].score)[0] || ['ad', { label: 'AD', score: 0 }]
}

function focusSearch() {
  inputEl.value?.focus()
  inputEl.value?.select()
}

watch(() => props.focusSignal, () => nextTick(focusSearch))
watch(query, async () => {
  try { sessionStorage.setItem(QUERY_KEY, query.value) } catch {}
  if (query.value) activeLetter.value = ''
  else {
    await nextTick()
    activeLetter.value = groups.value[0]?.letter || ''
    updateActiveLetter()
  }
})

function jump(letter) {
  if (!available.value.has(letter)) return
  activeLetter.value = letter
  manualUntil = Date.now() + 700
  const el = document.getElementById('letter-' + letter)
  if (el) {
    const html = document.documentElement
    const prev = html.style.scrollBehavior
    html.style.scrollBehavior = 'auto'
    el.scrollIntoView({ block: 'start' })
    html.style.scrollBehavior = prev
  }
}

function updateActiveLetter() {
  if (query.value || Date.now() < manualUntil) return
  const els = [...document.querySelectorAll('.letter-group')]
  let current = ''
  for (const el of els) {
    if (el.getBoundingClientRect().top <= 88) current = el.dataset.letter
  }
  if (current) activeLetter.value = current
}

function onScroll() {
  cancelAnimationFrame(scrollRaf)
  scrollRaf = requestAnimationFrame(updateActiveLetter)
}

function startDrag(e) {
  dragging.value = true
  const key = e.target.closest?.('.alpha-key')
  if (key) jump(key.dataset.letter)
}
function moveDrag(e) {
  if (!dragging.value) return
  const el = document.elementFromPoint(e.clientX, e.clientY)
  const key = el?.closest?.('.alpha-key')
  if (key && key.dataset.letter !== activeLetter.value) jump(key.dataset.letter)
}
function stopDrag() { dragging.value = false }
function clearManual() { manualUntil = 0 }

const SCROLL_KEY = 'mayhem-home-scroll'
const QUERY_KEY = 'mayhem-home-query'
let savedScroll = 0
let restorePending = false

function attach() {
  window.addEventListener('scroll', onScrollPassive, { passive: true })
  window.addEventListener('pointerup', stopDrag)
  window.addEventListener('pointercancel', stopDrag)
  window.addEventListener('wheel', clearManual, { passive: true })
  window.addEventListener('touchstart', clearManual, { passive: true })
}
function detach() {
  window.removeEventListener('scroll', onScrollPassive)
  window.removeEventListener('pointerup', stopDrag)
  window.removeEventListener('pointercancel', stopDrag)
  window.removeEventListener('wheel', clearManual)
  window.removeEventListener('touchstart', clearManual)
}
function onScrollPassive() {
  savedScroll = window.scrollY
  onScroll()
}

onMounted(() => {
  activeLetter.value = groups.value[0]?.letter || ''
  try {
    const q = sessionStorage.getItem(QUERY_KEY)
    if (q) query.value = q
    savedScroll = Number(sessionStorage.getItem(SCROLL_KEY) || 0) || 0
  } catch {}
  // 首屏（直接刷新）不恢复滚动，只在从详情返回时恢复
  if (savedScroll > 0) restorePending = true
  attach()
  if (props.focusSignal) nextTick(focusSearch)
  if (restorePending) {
    restorePending = false
    nextTick(() => window.scrollTo(0, savedScroll))
  }
})
onActivated(() => {
  attach()
  if (savedScroll > 0) nextTick(() => window.scrollTo(0, savedScroll))
})
onDeactivated(() => {
  detach()
  try {
    sessionStorage.setItem(SCROLL_KEY, String(savedScroll))
    sessionStorage.setItem(QUERY_KEY, query.value)
  } catch {}
})
onBeforeUnmount(detach)
</script>

<template>
  <div class="home">
    <section class="home-hero">
      <div class="home-kicker">CHAMPION LIBRARY / {{ patch }}</div>
      <div class="home-title-row">
        <h1>英雄库</h1>
        <span class="home-count">{{ champions.length }} 位英雄</span>
      </div>
      <p class="home-sub">收藏常用英雄，按拼音首字母查找；搜索支持中文、英文、外号与拼音。</p>
      <label class="home-search">
        <span class="search-icon">⌕</span>
        <input
          ref="inputEl"
          v-model="query"
          placeholder="搜索英雄 / 外号 / 拼音，例如：狐狸、yaso、石头人"
          autocomplete="off"
        />
        <button v-if="query" class="search-clear" @click="query = ''" aria-label="清空">×</button>
        <kbd v-else class="search-kbd">/</kbd>
      </label>
      <div class="home-stats">
        <span><b>{{ favorites.length }}</b> 常用</span>
        <span class="dot-sep"></span>
        <span>A–Z 拼音排序</span>
        <span class="dot-sep"></span>
        <span>点击字母快速定位</span>
      </div>
    </section>

    <template v-if="!query">
      <section class="home-section">
        <div class="home-section-head">
          <div><h2>收藏</h2><span>置顶显示</span></div>
          <span class="section-count">{{ favList.length }}</span>
        </div>
        <div v-if="favList.length" class="champ-grid">
          <div
            v-for="c in favList"
            :key="c.id"
            class="champ-card"
            role="button"
            tabindex="0"
            @click="emit('select', c.id)"
            @keydown.enter="emit('select', c.id)"
          >
            <div class="champ-card-img">
              <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragon}/img/champion/${c.id}.png`" :alt="c.title" loading="lazy" />
              <button class="card-star on" @click.stop="emit('favorite', c.id)" :title="'取消收藏'" :aria-label="'取消收藏' + c.title"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.2 14.7 8.7 20.8 9.6 16.4 13.9 17.5 19.9 12 17 6.5 19.9 7.6 13.9 3.2 9.6 9.3 8.7Z"/></svg></button>
            </div>
            <div class="champ-card-info"><b>{{ c.title }}</b><span>{{ c.name }}</span></div>
            <div class="champ-card-meta">{{ topStyle(c)[1].label }} {{ topStyle(c)[1].score }}</div>
          </div>
        </div>
        <div v-else class="fav-empty">
          还没有收藏。点英雄卡右上角的 <b>☆</b>，常用英雄会固定在这里。
        </div>
      </section>

      <section class="home-section all-section">
        <div class="home-section-head">
          <div><h2>全部英雄</h2><span>按本名拼音首字母 A–Z</span></div>
          <span class="section-count">{{ champions.length }}</span>
        </div>
        <div v-for="g in groups" :id="'letter-' + g.letter" :key="g.letter" class="letter-group" :data-letter="g.letter">
          <div class="letter-head"><b>{{ g.letter }}</b><span>{{ g.items.length }}</span></div>
          <div class="champ-grid">
            <div
              v-for="c in g.items"
              :key="c.id"
              class="champ-card"
              role="button"
              tabindex="0"
              @click="emit('select', c.id)"
              @keydown.enter="emit('select', c.id)"
            >
              <div class="champ-card-img">
                <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragon}/img/champion/${c.id}.png`" :alt="c.title" loading="lazy" />
                <button class="card-star" :class="{ on: favSet.has(c.id) }" @click.stop="emit('favorite', c.id)" :title="favSet.has(c.id) ? '取消收藏' : '收藏'" :aria-label="(favSet.has(c.id) ? '取消收藏' : '收藏') + c.title"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.2 14.7 8.7 20.8 9.6 16.4 13.9 17.5 19.9 12 17 6.5 19.9 7.6 13.9 3.2 9.6 9.3 8.7Z"/></svg></button>
              </div>
              <div class="champ-card-info"><b>{{ c.title }}</b><span>{{ c.name }}</span></div>
              <div class="champ-card-meta">{{ topStyle(c)[1].label }} {{ topStyle(c)[1].score }}</div>
            </div>
          </div>
        </div>
      </section>
    </template>

    <template v-else>
      <section class="home-section search-results">
        <div class="home-section-head">
          <div><h2>搜索结果</h2><span>“{{ query }}”</span></div>
          <span class="section-count">{{ results.length }}</span>
        </div>
        <div v-if="results.length" class="champ-grid">
          <div
            v-for="c in results"
            :key="c.id"
            class="champ-card"
            role="button"
            tabindex="0"
            @click="emit('select', c.id)"
            @keydown.enter="emit('select', c.id)"
          >
            <div class="champ-card-img">
              <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragon}/img/champion/${c.id}.png`" :alt="c.title" loading="lazy" />
              <button class="card-star" :class="{ on: favSet.has(c.id) }" @click.stop="emit('favorite', c.id)" :title="favSet.has(c.id) ? '取消收藏' : '收藏'" :aria-label="(favSet.has(c.id) ? '取消收藏' : '收藏') + c.title"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.2 14.7 8.7 20.8 9.6 16.4 13.9 17.5 19.9 12 17 6.5 19.9 7.6 13.9 3.2 9.6 9.3 8.7Z"/></svg></button>
            </div>
            <div class="champ-card-info"><b>{{ c.title }}</b><span>{{ c.name }}</span></div>
            <div class="champ-card-meta">{{ topStyle(c)[1].label }} {{ topStyle(c)[1].score }}</div>
          </div>
        </div>
        <div v-else class="empty-search">
          没有找到“{{ query }}”。试试本名、称号、拼音或外号，例如 `阿狸`、`yaso`、`石头人`。
        </div>
      </section>
    </template>

    <div v-if="!query" class="alpha-bar" @pointerdown="startDrag" @pointermove="moveDrag">
      <button
        v-for="l in letterList"
        :key="l"
        class="alpha-key"
        :class="{ active: activeLetter === l, disabled: !available.has(l) }"
        :data-letter="l"
        @click="jump(l)"
      >{{ l }}</button>
    </div>
  </div>
</template>
