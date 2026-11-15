<script setup>
import { computed } from 'vue'
const props = defineProps({
  champion: Object,
  item: Object,
  ddragon: String,
  activeAnchor: { type: String, default: '' },
})
const variant = computed(() => props.item.variant)
const core = computed(() => variant.value.builds.core?.[0] || { items: [], ids: [] })
const icon = (id) => id ? `https://ddragon.leagueoflegends.com/cdn/${props.ddragon}/img/item/${id}.png` : ''
const isActive = (key) => props.activeAnchor?.startsWith(props.item.key + '-') || props.activeAnchor === 'style-' + props.item.key
</script>

<template>
  <div class="combat-bar" :class="{ current: isActive('') }">
    <div class="combat-champ">
      <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragon}/img/champion/${champion.id}.png`" :alt="champion.name" />
      <div>
        <b>{{ champion.title }}</b>
        <span>{{ item.meta.label }} · {{ variant.viability }}</span>
      </div>
    </div>
    <div class="combat-build">
      <span class="combat-label">核心</span>
      <div class="combat-items">
        <span v-for="(name, i) in core.items" :key="name" class="combat-item">
          <img v-if="core.ids?.[i]" :src="icon(core.ids[i])" :alt="name" loading="lazy" />
          {{ name }}
        </span>
      </div>
    </div>
    <div class="combat-skill">
      <span class="combat-label">加点</span>
      <b>{{ variant.skill_order.priority }}</b>
    </div>
    <div class="combat-links">
      <a :href="'#' + item.key + '-builds'" :class="{ active: activeAnchor === item.key + '-builds' }">出装</a>
      <a :href="'#' + item.key + '-augments'" :class="{ active: activeAnchor === item.key + '-augments' }">海克斯</a>
      <a :href="'#' + item.key + '-combos'" :class="{ active: activeAnchor === item.key + '-combos' }">连招</a>
    </div>
  </div>
</template>
