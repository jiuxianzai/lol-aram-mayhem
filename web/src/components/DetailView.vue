<script setup>
import { ref, computed, watch, onMounted, onActivated, onDeactivated, onBeforeUnmount, nextTick } from 'vue'
import StylePanel from './StylePanel.vue'
import OutlineNav from './OutlineNav.vue'
import CombatBar from './CombatBar.vue'

const props = defineProps({
  champion: Object,
  report: Object,
  styleMeta: Object,
  patch: String,
  ddragon: String,
  favorites: { type: Array, default: () => [] },
})
const emit = defineEmits(['favorite'])

const activeStyle = ref('')
const activeAnchor = ref('')
let scrollRaf = 0
const styleOrder = ['ad', 'ap', 'tank', 'poke', 'support']
const orderedStyles = computed(() => {
  const a = props.report?.style_assessment || {}
  return styleOrder
    .filter(k => a[k])
    .sort((x, y) => (a[y].score - a[x].score) || (styleOrder.indexOf(x) - styleOrder.indexOf(y)))
})
const favoriteSet = computed(() => new Set(props.favorites))
const activeVariant = computed(() => {
  const key = activeStyle.value
  const variant = props.report?.variants?.[key]
  return variant ? { key, meta: props.styleMeta[key], variant } : null
})
const combat = computed(() => activeVariant.value)

function resetStyles() {
  const assessment = props.report?.style_assessment || {}
  const ranked = styleOrder
    .filter(k => assessment[k])
    .sort((a, b) => assessment[b].score - assessment[a].score)
  activeStyle.value = ranked[0] || ''
  nextTick(updateActiveAnchor)
}

function selectStyle(key) {
  if (activeStyle.value === key) return
  activeStyle.value = key
  nextTick(updateActiveAnchor)
}

function jumpTo(id) {
  const el = document.getElementById(id)
  if (!el) return
  const top = el.getBoundingClientRect().top + window.scrollY - 128
  window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  activeAnchor.value = id
}

function champImg(id) {
  return `https://ddragon.leagueoflegends.com/cdn/${props.ddragon}/img/champion/${id}.png`
}

function updateActiveAnchor() {
  const els = [...document.querySelectorAll('.anchor')]
  if (!els.length) return
  let current = ''
  for (const el of els) {
    if (el.getBoundingClientRect().top <= 160) current = el.id
  }
  activeAnchor.value = current || els[0].id
}
function onScroll() {
  cancelAnimationFrame(scrollRaf)
  scrollRaf = requestAnimationFrame(updateActiveAnchor)
}
function attach() { window.addEventListener('scroll', onScroll, { passive: true }) }
function detach() {
  window.removeEventListener('scroll', onScroll)
  cancelAnimationFrame(scrollRaf)
}

watch(() => props.champion?.id, () => { resetStyles(); window.scrollTo(0, 0) })
watch(activeStyle, async () => { await nextTick(); updateActiveAnchor() })

onMounted(() => { resetStyles(); attach() })
onActivated(() => { attach(); nextTick(updateActiveAnchor) })
onDeactivated(detach)
onBeforeUnmount(detach)
</script>

<template>
  <div class="detail-page" :class="{ 'no-outline': !activeVariant }">
    <section class="detail-main">
      <div class="champion-hero">
        <img class="hero-portrait" :src="champImg(champion.id)" :alt="champion.name" @error="$event.target.style.opacity=0" />
        <div class="hero-copy">
          <div class="eyebrow">ARAM: MAYHEM / 嚎哭深渊 / {{ champion.damage_type }} · {{ champion.range_type === 'melee' ? '近战' : '远程' }}</div>
          <h1>{{ champion.name }} <span>{{ champion.title }}</span></h1>
          <div class="hero-meta">
            <span class="archetype">{{ champion.archetype }}</span>
            <span v-for="t in champion.tags" :key="t" class="tag">{{ t }}</span>
          </div>
        </div>
        <button class="hero-fav" :class="{ on: favoriteSet.has(champion.id) }" @click="emit('favorite', champion.id)">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.2 14.7 8.7 20.8 9.6 16.4 13.9 17.5 19.9 12 17 6.5 19.9 7.6 13.9 3.2 9.6 9.3 8.7Z"/></svg>
          <span>{{ favoriteSet.has(champion.id) ? '已收藏' : '收藏' }}</span>
        </button>
      </div>

      <div class="style-board">
        <div class="section-title">
          <span>这把想玩什么？</span>
          <small>点标签切换玩法</small>
        </div>
        <div class="style-tabs" role="tablist" aria-label="玩法">
          <button
            v-for="key in orderedStyles"
            :key="key"
            class="style-tab"
            :class="{ active: activeStyle === key }"
            role="tab"
            :aria-selected="activeStyle === key"
            @click="selectStyle(key)"
          >
            <span class="style-tab-name">{{ styleMeta[key]?.label }}</span>
            <span class="style-tab-score">{{ report.style_assessment[key]?.score }}</span>
            <span class="style-tab-label" :class="report.style_assessment[key]?.label">{{ report.style_assessment[key]?.label }}</span>
          </button>
        </div>
        <p v-if="activeStyle" class="style-desc-line">{{ styleMeta[activeStyle]?.desc }}</p>
      </div>

      <CombatBar
        v-if="combat"
        :champion="champion"
        :item="combat"
        :ddragon="ddragon"
        :active-anchor="activeAnchor"
        @jump="jumpTo"
      />

      <div v-if="activeVariant" class="mobile-outline">
        <OutlineNav :variants="[activeVariant]" :style-meta="styleMeta" :active-anchor="activeAnchor" mobile @jump="jumpTo" />
      </div>

      <div v-if="activeVariant" class="variant-stack">
        <StylePanel
          :key="activeVariant.key"
          :variant="activeVariant.variant"
          :meta="activeVariant.meta"
          :ddragon="ddragon"
        />
      </div>
      <div v-else class="empty-styles">
        该英雄暂无可用玩法数据。
      </div>

      <footer class="data-foot">
        <p>模式：海克斯大乱斗（ARAM: Mayhem）· 嚎哭深渊 ｜ Patch {{ patch }} / DDragon {{ ddragon }}</p>
        <p>海克斯排序来自 OP.GG 同英雄页面，不是纯胜率；玩法方案由英雄机制、装备池与同英雄海克斯池生成。</p>
      </footer>
    </section>

    <aside class="outline-rail" v-if="activeVariant">
      <OutlineNav :variants="[activeVariant]" :style-meta="styleMeta" :active-anchor="activeAnchor" @jump="jumpTo" />
    </aside>
  </div>
</template>
