<script setup>
import { watch, nextTick, ref } from 'vue'
const props = defineProps({
  champions: Array, activeId: String, ddragon: String,
  favorites: { type: Array, default: () => [] },
  highlightIndex: { type: Number, default: 0 },
  empty: { type: String, default: '没有匹配的英雄' },
})
defineEmits(['select', 'favorite'])
const wrap = ref(null)
const favSet = () => new Set(props.favorites)

watch(() => props.highlightIndex, async () => {
  await nextTick()
  wrap.value?.querySelector('.champ-row.highlight')?.scrollIntoView({ block: 'nearest' })
})
</script>

<template>
  <div class="champ-list" ref="wrap">
    <div v-if="!champions.length" class="rail-empty">{{ empty }}</div>
    <div
      v-for="(c, i) in champions"
      :key="c.id"
      class="champ-row"
      :class="{ active: c.id === activeId, highlight: i === highlightIndex }"
      role="button"
      tabindex="0"
      @click="$emit('select', c.id)"
      @keydown.enter="$emit('select', c.id)"
    >
      <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragon}/img/champion/${c.id}.png`" :alt="c.name" loading="lazy" @error="$event.target.style.opacity=0" />
      <div class="champ-text">
        <div class="champ-name">{{ c.name }}</div>
        <div class="champ-title">{{ c.title }} · {{ c.archetype }}</div>
      </div>
      <button
        class="star"
        :class="{ on: favSet().has(c.id) }"
        :title="favSet().has(c.id) ? '取消收藏' : '收藏'"
        :aria-label="(favSet().has(c.id) ? '取消收藏' : '收藏') + c.name"
        @click.stop="$emit('favorite', c.id)"
      ><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.2 14.7 8.7 20.8 9.6 16.4 13.9 17.5 19.9 12 17 6.5 19.9 7.6 13.9 3.2 9.6 9.3 8.7Z"/></svg></button>
    </div>
  </div>
</template>
