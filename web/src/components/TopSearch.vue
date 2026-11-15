<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { searchChampions } from '../search.js'

const props = defineProps({
  champions: { type: Array, default: () => [] },
  favorites: { type: Array, default: () => [] },
  ddragon: String,
  focusSignal: { type: Number, default: 0 },
})
const emit = defineEmits(['select'])

const query = ref('')
const open = ref(false)
const cursor = ref(0)
const inputEl = ref(null)
const wrapEl = ref(null)
const favSet = computed(() => new Set(props.favorites))
const results = computed(() => searchChampions(props.champions, query.value, favSet.value).slice(0, 8))

function focus() {
  open.value = true
  inputEl.value?.focus()
  inputEl.value?.select()
}
defineExpose({ focus })

watch(() => props.focusSignal, () => nextTick(focus))
watch(results, () => { cursor.value = 0 })

function choose(c) {
  if (!c) return
  emit('select', c.id)
  query.value = ''
  open.value = false
  inputEl.value?.blur()
}

function onKeydown(e) {
  if (e.key === 'Escape') {
    if (query.value) query.value = ''
    else { open.value = false; inputEl.value?.blur() }
    return
  }
  if (!results.value.length) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    cursor.value = (cursor.value + 1) % results.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    cursor.value = (cursor.value - 1 + results.value.length) % results.value.length
  } else if (e.key === 'Enter') {
    e.preventDefault()
    choose(results.value[cursor.value])
  }
}

function onDocPointer(e) {
  if (wrapEl.value && !wrapEl.value.contains(e.target)) open.value = false
}
function onDocFocus(e) {
  if (wrapEl.value && !wrapEl.value.contains(e.target)) open.value = false
}
document.addEventListener('pointerdown', onDocPointer)
document.addEventListener('focusin', onDocFocus)
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocPointer)
  document.removeEventListener('focusin', onDocFocus)
})
</script>

<template>
  <div ref="wrapEl" class="top-search">
    <span class="top-search-icon" aria-hidden="true">⌕</span>
    <input
      ref="inputEl"
      v-model="query"
      type="search"
      placeholder="搜索英雄，Enter 直接打开"
      autocomplete="off"
      spellcheck="false"
      aria-label="搜索英雄"
      @focus="open = true"
      @keydown="onKeydown"
    />
    <kbd v-if="!query" class="top-search-kbd">/</kbd>
    <button v-else class="top-search-clear" @click="query = ''; open = true" aria-label="清空">×</button>

    <div v-if="open && query" class="top-search-panel">
      <template v-if="results.length">
        <button
          v-for="(c, i) in results"
          :key="c.id"
          class="top-search-row"
          :class="{ active: i === cursor }"
          @mouseenter="cursor = i"
          @click="choose(c)"
        >
          <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragon}/img/champion/${c.id}.png`" :alt="c.title" loading="lazy" />
          <span class="top-search-name">{{ c.title }}<em>{{ c.name }}</em></span>
          <span class="top-search-meta">{{ c.archetype }}</span>
        </button>
        <div class="top-search-foot">↑↓ 选择 · Enter 打开 · Esc 清空</div>
      </template>
      <div v-else class="top-search-empty">没有找到“{{ query }}”，试试中文名 / 拼音 / 外号</div>
    </div>
  </div>
</template>
