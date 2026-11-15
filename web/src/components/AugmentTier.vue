<script setup>
import { ref, computed } from 'vue'
const props = defineProps({ tier: Object, items: Array })
const open = ref(false)
const shown = computed(() => open.value ? props.items : props.items.slice(0, 3))
</script>

<template>
  <div class="tier-col">
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
    <button v-if="items.length > 3" class="tier-more" @click="open = !open">
      {{ open ? '收起' : `展开 4–${items.length}` }}
    </button>
  </div>
</template>
