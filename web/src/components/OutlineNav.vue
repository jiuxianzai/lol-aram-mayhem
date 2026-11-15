<script setup>
const props = defineProps({ variants: Array, styleMeta: Object, mobile: Boolean, activeAnchor: { type: String, default: '' } })
const sections = [
  { key: 'builds', label: '出装' },
  { key: 'augments', label: '海克斯' },
  { key: 'packages', label: '联动' },
  { key: 'combos', label: '连招' },
  { key: 'spikes', label: '强势/进场' },
  { key: 'skills', label: '加点' },
]
const styleActive = (key) => props.activeAnchor === 'style-' + key || props.activeAnchor.startsWith(key + '-')
const linkActive = (key, s) => props.activeAnchor === key + '-' + s
</script>

<template>
  <nav class="outline" :class="{ mobile }">
    <div v-if="!mobile" class="outline-head">
      <span>大纲</span>
      <small>OUTLINE</small>
    </div>
    <div v-for="item in variants" :key="item.key" class="outline-group">
      <a class="outline-style" :class="{ active: styleActive(item.key) }" :href="'#style-' + item.key">
        <i></i>{{ styleMeta[item.key]?.label }}<em>{{ item.variant.score }}</em>
      </a>
      <a
        v-for="s in sections"
        :key="s.key"
        class="outline-link"
        :class="{ active: linkActive(item.key, s.key) }"
        :href="'#' + item.key + '-' + s.key"
      >{{ s.label }}</a>
    </div>
  </nav>
</template>
