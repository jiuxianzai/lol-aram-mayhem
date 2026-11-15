<script setup>
defineProps({
  open: Boolean,
  fsLevel: Number,
  fsSteps: Array,
  patch: String,
  ddragon: String,
  championCount: Number,
})
const emit = defineEmits(['close', 'bump', 'reset'])
const labels = ['小', '标准', '大', '更大', '最大']
</script>

<template>
  <transition name="drawer">
    <div v-if="open" class="drawer-root">
      <div class="drawer-mask" @click="emit('close')"></div>
      <aside class="drawer" role="dialog" aria-label="设置">
        <header class="drawer-head">
          <span>设置</span>
          <button class="drawer-close" @click="emit('close')" aria-label="关闭设置">×</button>
        </header>

        <section class="drawer-block">
          <div class="drawer-label">字号</div>
          <p class="drawer-hint">全站文字统一缩放，选择会保存在本机。</p>
          <div class="fs-row">
            <button class="fs-btn" :disabled="fsLevel === 0" @click="emit('bump', -1)" aria-label="缩小字号">A−</button>
            <div class="fs-track">
              <div class="fs-track-bar"><i :style="{ width: ((fsLevel / (fsSteps.length - 1)) * 100) + '%' }"></i></div>
              <div class="fs-track-labels"><span v-for="(l, i) in labels" :key="l" :class="{ on: i === fsLevel }">{{ l }}</span></div>
            </div>
            <button class="fs-btn" :disabled="fsLevel === fsSteps.length - 1" @click="emit('bump', 1)" aria-label="放大字号">A+</button>
          </div>
          <div class="fs-value">当前 {{ Math.round(fsSteps[fsLevel] * 100) }}%<button class="fs-reset" @click="emit('reset')">恢复默认</button></div>
        </section>

        <section class="drawer-block">
          <div class="drawer-label">数据</div>
          <dl class="drawer-data">
            <div><dt>版本</dt><dd>Patch {{ patch }} / DDragon {{ ddragon }}</dd></div>
            <div><dt>英雄</dt><dd>{{ championCount }} 位</dd></div>
            <div><dt>模式</dt><dd>海克斯大乱斗 · 嚎哭深渊</dd></div>
          </dl>
        </section>

        <section class="drawer-block">
          <div class="drawer-label">快捷键</div>
          <div class="drawer-keys">
            <div><kbd>/</kbd><span>搜索英雄</span></div>
            <div><kbd>⌘K</kbd><span>搜索英雄</span></div>
            <div><kbd>Esc</kbd><span>关闭搜索 / 抽屉</span></div>
          </div>
        </section>
      </aside>
    </div>
  </transition>
</template>
