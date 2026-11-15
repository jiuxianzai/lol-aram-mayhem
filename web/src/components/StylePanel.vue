<script setup>
import { ref } from 'vue'
import AugmentTier from './AugmentTier.vue'
const props = defineProps({ variant: Object, meta: Object, ddragon: String })
const showAllAugments = ref(false)
const tiers = [
  { key: 'silver', label: '白银', en: 'SILVER' },
  { key: 'gold', label: '黄金', en: 'GOLD' },
  { key: 'prismatic', label: '棱彩', en: 'PRISMATIC' },
]
const firstCore = (v) => v.builds.core?.[0]?.items || []
const firstCoreIds = (v) => v.builds.core?.[0]?.ids || []
const itemIcon = (id) => id ? `https://ddragon.leagueoflegends.com/cdn/${props.ddragon}/img/item/${id}.png` : ''
const bootIcon = (v) => itemIcon(v.builds.boots_ids?.[0])
</script>

<template>
  <article :id="'style-' + variant.style" class="style-panel anchor">
    <header class="panel-head">
      <div class="panel-kicker">PLAYSTYLE / {{ meta.label }}</div>
      <div class="panel-title">
        <h2>{{ meta.label }} 玩法</h2>
        <span class="score-badge">{{ variant.score }}</span>
        <span class="viability" :class="variant.viability">{{ variant.viability }}</span>
      </div>
      <p class="viability-note">{{ variant.viability_note }}</p>
    </header>

    <div v-if="variant.score < 35" class="warn-banner">
      该英雄的 {{ meta.label }} 玩法强度较低，以下内容仅作娱乐参考。
    </div>

    <!-- 出装优先：先给核心顺序，再给分支 -->
    <section :id="variant.style + '-builds'" class="block anchor build-block">
      <div class="section-title"><span>出装</span><small>{{ meta.label }} 方案</small></div>
      <div class="core-build-hero">
        <div class="core-build-main">
          <div class="build-label">核心顺序</div>
          <div class="core-build-items">
            <template v-for="(item, i) in firstCore(variant)" :key="i">
              <span class="build-item"><img v-if="firstCoreIds(variant)[i]" :src="itemIcon(firstCoreIds(variant)[i])" :alt="item" loading="lazy" />{{ item }}</span>
              <span v-if="i < firstCore(variant).length - 1" class="build-arrow">→</span>
            </template>
          </div>
        </div>
        <div class="core-build-side">
          <div><span>鞋子</span><b><img v-if="bootIcon(variant)" :src="bootIcon(variant)" alt="" loading="lazy" />{{ variant.builds.boots[0] || '—' }}</b></div>
          <div><span>出门</span><b>{{ variant.builds.starter.join(' + ') || '—' }}</b></div>
        </div>
      </div>

      <div class="build-alts" v-if="variant.builds.core.length > 1">
        <span class="muted-label">备选</span>
        <span v-for="(c, i) in variant.builds.core.slice(1)" :key="i" class="alt-build">{{ c.items.join(' → ') }}</span>
      </div>

      <div class="branch-grid">
        <div v-for="(b, key) in variant.builds.branches" :key="key" class="branch">
          <div class="branch-title">{{ b.title }}</div>
          <div class="branch-items">
            <template v-for="(n, i) in b.items" :key="n">
              <span class="branch-item"><img v-if="b.item_ids?.[i]" :src="itemIcon(b.item_ids[i])" alt="" loading="lazy" />{{ n }}</span>
              <span v-if="i < b.items.length - 1" class="plus">+</span>
            </template>
            <span v-if="!b.items.length">—</span>
          </div>
          <div v-if="b.boots" class="branch-boots">鞋：{{ b.boots }}</div>
          <p>{{ b.note }}</p>
        </div>
      </div>
    </section>

    <section :id="variant.style + '-augments'" class="block anchor">
      <div class="section-title aug-title">
        <span>海克斯推荐</span>
        <small>同英雄池 + {{ meta.label }} 适配重排</small>
        <button class="aug-expand" :class="{ open: showAllAugments }" @click="showAllAugments = !showAllAugments">
          {{ showAllAugments ? '收起 4–10' : '展开 4–10（三档一起）' }}
          <span class="aug-expand-caret" aria-hidden="true">⌄</span>
        </button>
      </div>
      <div class="tier-grid">
        <AugmentTier v-for="t in tiers" :key="t.key" :tier="t" :items="variant.augments[t.key]" :open="showAllAugments" />
      </div>
    </section>

    <section :id="variant.style + '-packages'" class="block anchor">
      <div class="section-title"><span>联动组合</span><small>成套海克斯可遇不可求</small></div>
      <div class="package-grid">
        <div v-for="p in variant.synergy_packages" :key="p.name" class="package-card">
          <div class="package-name">{{ p.name }}</div>
          <div class="package-pieces">
            <span v-for="a in p.augments" :key="a.id" class="piece">{{ a.name }}</span>
          </div>
          <p>{{ p.why }}</p>
          <div class="package-fit">{{ p.fit }}</div>
        </div>
      </div>
    </section>

    <div class="two-col">
      <section :id="variant.style + '-combos'" class="block anchor">
        <div class="section-title"><span>连招</span><small>按实战距离与 CD 调整</small></div>
        <div v-for="c in variant.combos" :key="c.name" class="combo">
          <div class="combo-name">{{ c.name }}</div>
          <div class="combo-seq">{{ c.sequence }}</div>
          <p>{{ c.note }}</p>
        </div>
      </section>
      <section :id="variant.style + '-spikes'" class="block anchor">
        <div class="section-title"><span>强势期与进场</span><small>什么时候能打</small></div>
        <ul class="spike-list">
          <li v-for="s in variant.power_spikes" :key="s">{{ s }}</li>
        </ul>
        <p class="engage">{{ variant.engage }}</p>
      </section>
    </div>

    <section :id="variant.style + '-skills'" class="block anchor">
      <div class="section-title"><span>技能加点</span><small>1–18 级</small></div>
      <div class="skill-priority">{{ variant.skill_order.priority }}</div>
      <div class="skill-order">
        <span v-for="(s, i) in variant.skill_order.order" :key="i" :class="'skill-' + s.slot">{{ s.slot }}</span>
      </div>
    </section>
  </article>
</template>
