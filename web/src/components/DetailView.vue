<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
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

const selectedStyles = ref([])
const activeStyle = ref('')
const showAll = ref(false)
const activeAnchor = ref('')
let scrollRaf = 0
const styleOrder = ['ad', 'ap', 'tank', 'poke', 'support']
// 按当前英雄的评分从高到低排，辅助英雄的「辅助」自然排在最前
const orderedStyles = computed(() => {
  const a = props.report?.style_assessment || {}
  return styleOrder
    .filter(k => a[k])
    .sort((x, y) => (a[y].score - a[x].score) || (styleOrder.indexOf(x) - styleOrder.indexOf(y)))
})
const favoriteSet = computed(() => new Set(props.favorites))

const selectedVariants = computed(() => {
  if (!props.report) return []
  return selectedStyles.value
    .map(key => ({ key, meta: props.styleMeta[key], variant: props.report.variants[key] }))
    .filter(x => x.variant)
})
const displayedVariants = computed(() => {
  const all = selectedVariants.value
  if (!all.length) return []
  if (showAll.value) return all
  const one = all.find(x => x.key === activeStyle.value)
  return one ? [one] : [all[0]]
})
const combat = computed(() => displayedVariants.value[0] || null)

function resetStyles() {
  const assessment = props.report?.style_assessment || {}
  const ranked = styleOrder
    .filter(k => assessment[k])
    .sort((a, b) => assessment[b].score - assessment[a].score)
  const good = ranked.filter(k => assessment[k].score >= 55).slice(0, 2)
  selectedStyles.value = good.length ? good : ranked.slice(0, 1)
  activeStyle.value = selectedStyles.value[0] || ''
  showAll.value = false
  nextTick(updateActiveAnchor)
}

function toggleStyle(key) {
  const i = selectedStyles.value.indexOf(key)
  if (i >= 0) {
    selectedStyles.value.splice(i, 1)
    if (activeStyle.value === key) activeStyle.value = selectedStyles.value[0] || ''
  } else {
    selectedStyles.value.push(key)
    activeStyle.value = key
  }
}

function champImg(id) {
  return `https://ddragon.leagueoflegends.com/cdn/${props.ddragon}/img/champion/${id}.png`
}

function updateActiveAnchor() {
  const els = [...document.querySelectorAll('.anchor')]
  if (!els.length) return
  let current = ''
  for (const el of els) {
    if (el.getBoundingClientRect().top <= 120) current = el.id
  }
  activeAnchor.value = current || els[0].id
}
function onScroll() {
  cancelAnimationFrame(scrollRaf)
  scrollRaf = requestAnimationFrame(updateActiveAnchor)
}

watch(() => props.report?.champion?.id, resetStyles)
watch(() => selectedStyles.value.join(','), async () => {
  if (activeStyle.value && !selectedStyles.value.includes(activeStyle.value)) {
    activeStyle.value = selectedStyles.value[0] || ''
  }
  await nextTick()
  updateActiveAnchor()
})
watch(displayedVariants, async () => { await nextTick(); updateActiveAnchor() })

onMounted(() => {
  resetStyles()
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('hashchange', () => { activeAnchor.value = location.hash.replace('#', '') })
})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
  cancelAnimationFrame(scrollRaf)
})
</script>

<template>
  <div class="detail-page" :class="{ 'no-outline': !displayedVariants.length }">
    <section class="detail-main">
      <div class="champion-hero">
        <img class="hero-portrait" :src="champImg(champion.id)" :alt="champion.name" @error="$event.target.style.opacity=0" />
        <div class="hero-copy">
          <div class="eyebrow">ARAM: MAYHEM / {{ champion.damage_type }} · {{ champion.range_type === 'melee' ? '近战' : '远程' }}</div>
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
          <small>可多选，下面会分别展开完整方案</small>
        </div>
        <div class="style-grid">
          <button
            v-for="key in orderedStyles"
            :key="key"
            class="style-card"
            :class="{ active: selectedStyles.includes(key) }"
            @click="toggleStyle(key)"
          >
            <div class="style-card-top">
              <span class="check">{{ selectedStyles.includes(key) ? '✓' : '' }}</span>
              <strong>{{ styleMeta[key]?.label }}</strong>
              <span class="style-score">{{ report.style_assessment[key]?.score }}</span>
            </div>
            <div class="style-desc">{{ styleMeta[key]?.desc }}</div>
            <div class="style-label">{{ report.style_assessment[key]?.label }}</div>
            <div class="score-bar"><i :style="{ width: (report.style_assessment[key]?.score || 0) + '%' }"></i></div>
          </button>
        </div>
      </div>

      <div v-if="selectedVariants.length" class="view-bar">
        <div class="view-tabs" v-if="selectedVariants.length > 1">
          <button
            v-for="item in selectedVariants"
            :key="item.key"
            :class="{ active: !showAll && activeStyle === item.key }"
            @click="activeStyle = item.key; showAll = false"
          >{{ item.meta.label }} <em>{{ item.variant.score }}</em></button>
        </div>
        <button v-if="selectedVariants.length > 1" class="ghost-btn" @click="showAll = !showAll">
          {{ showAll ? '只看当前' : '并排全部' }}
        </button>
      </div>

      <CombatBar v-if="combat" :champion="champion" :item="combat" :ddragon="ddragon" :active-anchor="activeAnchor" />

      <div v-if="displayedVariants.length" class="mobile-outline">
        <OutlineNav :variants="displayedVariants" :style-meta="styleMeta" :active-anchor="activeAnchor" mobile />
      </div>

      <div v-if="displayedVariants.length" class="variant-stack">
        <StylePanel
          v-for="item in displayedVariants"
          :key="item.key"
          :variant="item.variant"
          :meta="item.meta"
          :ddragon="ddragon"
        />
      </div>
      <div v-else class="empty-styles">
        至少选择一个玩法，才能生成对应海克斯 / 出装 / 连招。
      </div>

      <footer class="data-foot">
        <p>数据：Patch {{ patch }} / DDragon {{ ddragon }} ｜ 海克斯排序来自 OP.GG 同英雄页面，不是纯胜率。</p>
        <p>玩法方案由英雄机制、装备池与同英雄海克斯池生成；低推荐度玩法仅作娱乐参考。</p>
      </footer>
    </section>

    <aside class="outline-rail" v-if="displayedVariants.length">
      <OutlineNav :variants="displayedVariants" :style-meta="styleMeta" :active-anchor="activeAnchor" />
    </aside>
  </div>
</template>
