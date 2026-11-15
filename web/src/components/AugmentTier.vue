<script setup>
import { computed } from 'vue'
const props = defineProps({
  tier: Object,
  items: { type: Array, default: () => [] },
  open: Boolean,
})
const shown = computed(() => props.open ? props.items : props.items.slice(0, 3))
</script>

<template>
  <div class="tier-col" :class="'tier-' + tier.key">
    <div class="tier-head">
      <span>{{ tier.label }}</span>
      <small>{{ tier.en }}</small>
    </div>
    <ol class="aug-list">
      <li v-for="a in shown" :key="a.name" :class="{ top3: a.rank <= 3 }">
        <div class="aug-line">
          <span class="aug-rank">{{ String(a.rank).padStart(2, '0') }}</span>
          <strong>{{ a.name }}</strong>
        </div>
        <p class="aug-desc">{{ a.desc }}</p>
        <p class="aug-reason">{{ a.reason }}</p>
      </li>
    </ol>
  </div>
</template>
