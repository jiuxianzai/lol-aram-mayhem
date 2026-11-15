"""Generate per-playstyle variants (AD / AP / tank / poke / support) from the base DB."""
from __future__ import annotations
import json, re
from pathlib import Path

STYLES = {
    'ad':   {'label': 'AD',   'desc': '攻击力 / 暴击 / 攻速 / 穿甲', 'color': '#f0b35b'},
    'ap':   {'label': 'AP',   'desc': '法强 / 法穿 / 技能爆发',       'color': '#a78bfa'},
    'tank': {'label': '肉',   'desc': '生命 / 双抗 / 开团抗伤',       'color': '#6ee7b7'},
    'poke': {'label': '消耗', 'desc': '远程消耗 / 压血线 / 拉扯',     'color': '#67e8f9'},
    'support': {'label': '辅助', 'desc': '治疗 / 护盾 / 功能装',      'color': '#f9a8d4'},
}

# 玩法开放条件：不满足的玩法不出现在该英雄页面上
# support 只给辅助（build_type=SUPPORT）；tank 只给战士/坦克
STYLE_GATES = {
    'support': lambda champ: champ.get('build_type') == 'SUPPORT',
    'tank': lambda champ: bool({'Fighter', 'Tank'} & set(champ.get('tags') or [])),
}

def style_allowed(champ, style):
    gate = STYLE_GATES.get(style)
    return True if gate is None else bool(gate(champ))

# standard item IDs from DDragon 16.22; all verified against items table
STYLE_ITEMS = {
    'ap':   [6655, 4645, 3089, 3135, 6653, 3157, 3102, 3165, 2503, 3116, 3152, 2420, 4628],
    'ad':   [6672, 3031, 3036, 3071, 3153, 6676, 3032, 3085, 3046, 3033, 3142, 6692, 6333, 3026],
    'tank': [3084, 3068, 3075, 3143, 3110, 2504, 3065, 4401, 8020, 2502, 3083, 3190, 6665, 3047, 3111],
    'poke': [6655, 6653, 4628, 3135, 3089, 3142, 6694, 3042, 3071, 3152, 3116, 3157],
    # 辅助：月石/流水/香炉/救赎/米凯尔/舒瑞娅/帝国指令/海力亚 + 硬辅三件（鸟盾/骑士/基克/眼石/星界据守）
    'support': [6617, 6616, 3504, 3107, 3222, 2065, 4005, 6620, 3190, 3109, 3050, 4643, 3869],
}
STYLE_CORE = {
    'ap':   [6655, 4645, 3089],
    'ad_ranged': [6672, 3031, 3036],
    'ad_melee': [6692, 3071, 6333],
    'ad_assassin': [3142, 6692, 3071],
    # 嚎哭深渊/大乱斗：肉装第一件必须是心之钢，再按对局补日炎/反甲/振奋
    'tank': [3084, 3068, 3075],
    'tank_support': [3084, 3190, 3065],
    'poke_ap': [6655, 6653, 4628],
    'poke_ad': [3142, 6694, 3042],
    # 辅助三条线：软辅（治疗护盾）/ 硬辅（前排保人）/ 法辅（技能消耗）
    'support_enchanter': [6617, 3504, 3107],
    'support_tank': [3190, 3109, 3050],
    'support_caster': [4005, 6620, 6616],
}
BOOTS = {'ap':[3020], 'ad':[3006, 3047], 'tank':[3047, 3111], 'poke':[3020, 3009], 'support':[3158, 3009]}

# 嚎哭深渊专属出门装：守护者系列 + 生命药水（OP.GG 的 starter 常混入峡谷多兰/鞋子）
ARAM_STARTER = {
    'AD': [3184, 2003],
    'AP': [3112, 2003],
    'TANK': [2051, 2003],
    'SUPPORT': [3177, 2003],
}

# (name, 3 augment names ordered by tier ideally) — all verified in DB
PACKAGE_DEFS = {
    'ap_burst': ('法系爆发三件套', ['大法师','魔法飞弹','尤里卡'], '大法师返还CD、魔法飞弹补真伤、尤里卡把法强转成技能急速。'),
    'haste': ('技能急速三件套', ['循环往复','无限循环往复','终极循环往复'], '三件都提供技能/终极急速，技能循环拉满。'),
    'crit': ('暴击三件套', ['珠光护手','暴击律动','升级：无尽之刃'], '技能可暴击+暴击叠攻速+无尽升级，暴击收益互相放大。'),
    'onhit': ('攻速特效三件套', ['双生火焰','灵巧','台风'], '攻速、额外飞弹和攻击特效叠加，站桩输出上限高。'),
    'tank': ('前排三件套', ['巨像的勇气','蛋白粉奶昔','歌利亚巨人'], '控制触发护盾、治疗护盾强度随双抗成长、歌利亚给生命和适应之力。'),
    'support': ('治疗护盾三件套', ['急救用具','信念者的强化','活力焕发'], '治疗/护盾强度叠加，并让治疗附带额外收益。'),
    'stats': ('属性三件套', ['属性！','属性叠属性！','属性叠属性叠属性！'], '三件都给属性铁砧，越叠越全面。'),
    'snowball': ('雪球三件套', ['史上最大雪球','雪球扭蛋机','神圣雪球'], '三件都强化雪球/标记，开团和追击能力大幅提升。'),
}
STYLE_PACKAGES = {
    'ap': ['ap_burst','haste','stats','snowball'],
    'ad': ['crit','onhit','haste','stats'],
    'tank': ['tank','support','stats','snowball'],
    'poke': ['ap_burst','haste','stats','snowball'],
    'support': ['support','haste','stats','snowball'],
}

STYLE_ITEMS_FALLBACK = {
    'vs_tank': {'ap':[3135,6653], 'ad':[3036,3033], 'tank':[3068,3075], 'poke':[3135,4628], 'support':[4005,6620]},
    'vs_ad':   {'ap':[3157,2420], 'ad':[3026,6333], 'tank':[3143,3075], 'poke':[3157,2420], 'support':[3190,3109]},
    'vs_ap':   {'ap':[3102,2504], 'ad':[3156,3111], 'tank':[2504,3065], 'poke':[3102,2504], 'support':[3222,3190]},
    'vs_poke': {'ap':[3152,3116], 'ad':[3142,3742], 'tank':[3190,3742], 'poke':[3142,3152], 'support':[2065,6616]},
}

def parse_range(v):
    if isinstance(v, list):
        nums = [x for x in v if isinstance(x,(int,float))]
        return max(nums) if nums else 0
    try: return float(v)
    except Exception: return 0

def load_items(con):
    out = {}
    for r in con.execute('select * from items'):
        d = dict(r); d['tags'] = json.loads(d['tags']); d['stats'] = json.loads(d['stats_json'])
        out[d['id']] = d
    return out

def load_augments(con):
    out = []
    for r in con.execute('select * from augments where disabled=0'):
        d = dict(r); d['tags'] = json.loads(d['tags'])
        out.append(d)
    return out

def assess_styles(champ, items):
    tags = set(champ['tags']); spells = champ['spells']
    core = champ.get('core',[[]])[0] if champ.get('core') else []
    core_tags = set()
    for i in core: core_tags |= set(items.get(i,{}).get('tags',[]))
    max_range = max([parse_range(s.get('range')) for s in spells] + [champ.get('attackrange',0)])
    has_cc = any(s['flags']['hard_cc'] for s in spells)
    has_heal = any(s['flags']['heal'] or s['flags']['shield'] for s in spells)
    ap_core = sum(1 for i in core if set(items.get(i,{}).get('tags',[])) & {'SpellDamage','MagicPenetration'})
    ad_core = sum(1 for i in core if set(items.get(i,{}).get('tags',[])) & {'Damage','CriticalStrike','ArmorPenetration','AttackSpeed','LifeSteal'})
    tank_core = sum(1 for i in core if set(items.get(i,{}).get('tags',[])) & {'Health','Armor','SpellBlock'})
    n = max(len(core),1)
    scores = {}
    # AD
    s = 18
    if 'Marksman' in tags: s += 32
    if 'Fighter' in tags: s += 26
    if 'Assassin' in tags: s += 20
    s += 26*ad_core/n
    if any(t in core_tags for t in ('CriticalStrike','AttackSpeed')): s += 8
    if champ.get('range_type') != 'melee': s += 6
    scores['ad'] = s
    # AP
    s = 18
    if 'Mage' in tags: s += 34
    if 'Support' in tags: s += 14
    if 'Assassin' in tags: s += 8
    s += 28*ap_core/n
    if any('法术强度' in (sp.get('desc') or '') for sp in spells): s += 8
    if any('魔法伤害' in (sp.get('desc') or '') for sp in spells): s += 4
    scores['ap'] = s
    # tank
    s = 16
    if 'Tank' in tags: s += 36
    if 'Fighter' in tags: s += 22
    if 'Support' in tags: s += 8
    s += 24*tank_core/n
    if has_cc: s += 10
    if has_heal: s += 4
    if champ.get('range_type') == 'melee': s += 8
    scores['tank'] = s
    # poke
    s = 10
    if max_range >= 900: s += 28
    elif max_range >= 700: s += 20
    elif max_range >= 550: s += 10
    if 'Mage' in tags: s += 22
    if 'Marksman' in tags: s += 18
    if ap_core or ad_core: s += 8
    scores['poke'] = s
    # support：只有辅助英雄有实际数据支撑，其余英雄分数天然压低（且会被 STYLE_GATES 过滤掉）
    s = 6
    if champ.get('build_type') == 'SUPPORT': s += 40
    if 'Support' in tags: s += 12
    if has_heal: s += 16
    if has_cc: s += 6
    if any(set(items.get(i,{}).get('tags',[])) & {'ManaRegen','AbilityHaste','Aura'} for i in core): s += 10
    if 'Tank' in tags: s += 8
    scores['support'] = s
    base = champ.get('build_type','')
    base_map = {'AD':'ad','AP':'ap','TANK':'tank','SUPPORT':'support'}
    for k,v in list(scores.items()):
        if base_map.get(base) == k: scores[k] = v + 18
        scores[k] = int(max(5, min(98, round(v))))
    return scores

def viability_label(score):
    if score >= 75: return '推荐', '本英雄的主流/强势玩法，装备与海克斯池最完整。'
    if score >= 55: return '可玩', '有加成或装备支持，能玩；需要更注意节奏。'
    if score >= 35: return '偏娱乐', '加成/机制不完全匹配，建议顺风局或熟练后玩。'
    return '不推荐', '缺乏核心加成，纯娱乐；不要在高强度局硬玩。'

def style_fit(a, style):
    tags = set(a['tags'])
    if style == 'ap':
        s = 0
        if 'AP' in tags: s += 3
        if 'haste' in tags: s += 1
        if 'poke' in tags: s += 1
        if 'execute' in tags: s += 1
        if 'sustain' in tags: s += 0
        if tags & {'AD','crit','onhit','AS'}: s -= 5 if 'AP' not in tags else 2
        if 'tank' in tags and 'AP' not in tags: s -= 1
        return s
    if style == 'ad':
        s = 0
        if tags & {'AD','crit','AS','onhit'}: s += 3
        if 'execute' in tags: s += 1
        if 'haste' in tags: s += 1
        if 'AP' in tags: s -= 5 if not (tags & {'AD','crit','AS','onhit'}) else 2
        if 'tank' in tags: s -= 1
        return s
    if style == 'tank':
        s = 0
        if 'tank' in tags: s += 3
        if 'sustain' in tags: s += 2
        if 'utility' in tags: s += 1
        if 'haste' in tags: s += 1
        if tags & {'crit','onhit','AS'}: s -= 3
        if 'AP' in tags or 'AD' in tags: s -= 1
        return s
    if style == 'poke':
        s = 0
        if 'poke' in tags: s += 3
        if 'AP' in tags or 'AD' in tags: s += 1
        if 'haste' in tags: s += 2
        if 'execute' in tags: s += 1
        if tags & {'onhit','crit','AS'}: s -= 3
        if 'tank' in tags: s -= 2
        return s
    if style == 'support':
        s = 0
        if 'enchanter' in tags: s += 3
        if 'sustain' in tags: s += 3
        if 'utility' in tags: s += 2
        if 'haste' in tags: s += 2
        if 'tank' in tags: s += 2
        if 'mobility' in tags: s += 1
        if 'gold' in tags: s += 1
        if tags & {'crit','onhit','AS'}: s -= 4
        if 'AD' in tags and not (tags & {'enchanter','sustain','utility'}): s -= 2
        return s
    return 0

def pick_augments(con, champ, style, items, global_pool, freq):
    base = {'Silver':[], 'Gold':[], 'Prismatic':[]}
    for r in con.execute('''select a.*, ca.rank from champion_augments ca join augments a on a.id=ca.augment_id
                            where ca.champion_id=? and a.disabled=0 order by case ca.tier when 'Silver' then 0 when 'Gold' then 1 else 2 end, ca.rank''', (champ['id'],)):
        a = dict(r); a['tags'] = json.loads(a['tags']); a['base_rank'] = r['rank']
        base[a['tier']].append(a)
    out = {}
    for tier in ('Silver','Gold','Prismatic'):
        cands = []
        for a in base[tier]:
            f = style_fit(a, style)
            if f < -2: continue
            cands.append((100 - a['base_rank']*2 + f*8, a))
        existing = {a['id'] for _,a in cands}
        for a in global_pool:
            if a['tier'] != tier or a['id'] in existing: continue
            f = style_fit(a, style)
            if f <= 0: continue
            cands.append((20 + f*8 + min(freq.get(a['id'],0),20)*0.2, a))
        cands.sort(key=lambda x: (-x[0], x[1]['name_zh']))
        chosen = []
        seen = set()
        for _,a in cands:
            if a['id'] in seen: continue
            seen.add(a['id']); chosen.append(a)
            if len(chosen) == 10: break
        out[tier] = chosen
    return out

def reason_for(champ, a, style):
    label = STYLES[style]['label']
    tags = {'AP':'法强','AD':'攻击力','AS':'攻速','crit':'暴击','onhit':'攻击特效','tank':'坦度','sustain':'续航',
            'enchanter':'治疗/护盾','haste':'技能急速','mobility':'移速/位移','poke':'远程消耗','execute':'斩杀',
            'utility':'控制/功能','damage':'伤害','gold':'经济','quest':'任务','snowball':'雪球'}
    ts = [tags[t] for t in a['tags'] if t in tags][:4]
    return f"契合{label}玩法：" + ('/'.join(ts) if ts else '泛用强化') + '。'

ENCHANTER_ITEMS = {6617, 3504, 6616, 3107, 3222, 2065}   # 月石/香炉/流水/救赎/米凯尔/舒瑞娅
TANK_SUPPORT_ITEMS = {3190, 3109, 3050, 4643, 3869}      # 鸟盾/骑士之誓/基克/眼石/星界据守

def support_core_key(champ):
    """按该英雄真实的 OP.GG 核心装 + 标签判断是软辅 / 硬辅 / 法辅。"""
    tags = set(champ.get('tags') or [])
    core = (champ.get('core') or [[]])[0]
    core = set(core or [])
    if core & TANK_SUPPORT_ITEMS:
        return 'support_tank'
    if core & ENCHANTER_ITEMS:
        return 'support_enchanter'
    if 'Tank' in tags:
        return 'support_tank'
    return 'support_caster'

def aram_starter(champ, items):
    """嚎哭深渊出门：守护者系列 + 药水；找不到时退回该类型通用出门。"""
    ids = ARAM_STARTER.get(champ.get('build_type', ''), ARAM_STARTER['AD'])
    names = [items[i]['name_zh'] for i in ids if i in items]
    return names or ['守护者号角', '生命药水']


def style_builds(champ, style, items, base_builds):
    base_type = {'AD':'ad','AP':'ap','TANK':'tank','SUPPORT':'support'}.get(champ.get('build_type',''), '')
    if style == base_type and base_builds.get('core'):
        # 辅助玩法只保留 1 条真实核心序列，再补 1 条功能装选，避免三行几乎重复
        n_base = 1 if style == 'support' else 3
        core = [c['items'] for c in base_builds['core'][:n_base]]
        core_ids = [c['ids'] for c in base_builds['core'][:n_base]]
        boots = base_builds.get('boots', [])[:3]
        starter = aram_starter(champ, items)
        if style == 'support':
            # OP.GG 的核心序列常常是“辅助装 + 神话 + 肉/法装”，再补一条纯功能装备选
            alt = STYLE_CORE[support_core_key(champ)]
            core.append([items[i]['name_zh'] for i in alt if i in items])
            core_ids.append(alt)
    else:
        if style == 'ap':
            core_ids = [STYLE_CORE['ap']]
        elif style == 'tank':
            core_ids = [STYLE_CORE['tank_support'] if champ.get('build_type')=='SUPPORT' else STYLE_CORE['tank']]
        elif style == 'poke':
            core_ids = [STYLE_CORE['poke_ap'] if champ.get('damage_type')=='AP' else STYLE_CORE['poke_ad']]
        elif style == 'support':
            core_ids = [STYLE_CORE[support_core_key(champ)]]
        else:
            if champ.get('archetype') in ('ad_assassin',): core_ids = [STYLE_CORE['ad_assassin']]
            elif champ.get('range_type') == 'melee': core_ids = [STYLE_CORE['ad_melee']]
            else: core_ids = [STYLE_CORE['ad_ranged']]
        core = [[items[i]['name_zh'] for i in seq if i in items] for seq in core_ids]
        boots = [items[i]['name_zh'] for i in BOOTS.get(style, []) if i in items][:3]
        starter = aram_starter(champ, items)
    # 肉玩法统一以心之钢起手（含 OP.GG 真实序列里没出心之钢的英雄）
    if style == 'tank' and core and core_ids:
        if '心之钢' not in core[0]:
            seq = [3084] + [i for i in core_ids[0] if i != 3084][:2]
            core = [[items[i]['name_zh'] for i in seq if i in items]]
            core_ids = [seq]
    branches = {}
    for key, bystyle in STYLE_ITEMS_FALLBACK.items():
        picks = [i for i in bystyle.get(style, []) if i in items]
        # prefer items already in champion pool, then global
        pool = set(champ.get('pool', []))
        picks.sort(key=lambda i: (0 if i in pool else 1))
        picks = picks[:2]
        branches[key] = {
            'title': {'vs_tank':'对面肉多','vs_ad':'对面AD多','vs_ap':'对面AP多','vs_poke':'对面长手多'}[key],
            'items': [items[i]['name_zh'] for i in picks],
            'boots': {'vs_ad':'铁板靴','vs_ap':'水银之靴'}.get(key) if style in ('ad','tank','support') else None,
            'note': {
                'vs_tank': {'ap':'虚空/兰德里，优先百分比与法穿。','ad':'多米尼克/凡性的提醒，补百分比穿透和减疗。','tank':'心之钢先叠层，再补日炎/反甲，靠灼烧和减疗磨前排。','poke':'虚空/视界专注，先把前排血线压下去。','support':'帝国指令/海力亚，靠持续伤害配合队友磨血，别自己贴脸。'}[style],
                'vs_ad': {'ap':'中娅/护臂，活着才有输出。','ad':'守护天使/死亡之舞，防物理爆发。','tank':'兰顿/反甲，减攻速和暴击伤害。','poke':'中娅/护臂，被贴脸时保命。','support':'钢铁烈阳之匣/骑士之誓，先保住C位再谈输出。'}[style],
                'vs_ap': {'ap':'女妖/败魔，防先手控制与法术爆发。','ad':'大饮魔刀/水银靴，补魔抗和免控。','tank':'败魔/振奋/自然之力，先扛第一轮。','poke':'女妖/败魔，别被先手秒。','support':'米凯尔的祝福/鸟盾，解控与团队魔抗优先。'}[style],
                'vs_poke': {'ap':'火箭腰带/瑞莱，补位移和黏人。','ad':'幽梦/亡者板甲，补移速开团。','tank':'鸟盾/亡者板甲，帮队友吃第一波。','poke':'幽梦/火箭腰带，用移速躲消耗。','support':'舒瑞娅的战歌/流水法杖，用移速帮队友进出消耗。'}[style],
            }[key]
        }
    return {'starter': starter, 'boots': boots, 'core': [{'items':c, 'ids':ids} for c,ids in zip(core, core_ids)], 'branches': branches}

def style_packages(champ, recs, style, aug_by_name):
    allrecs = sum([recs[t] for t in ('Silver','Gold','Prismatic')], [])
    names = {a['name_zh'] for a in allrecs}
    top10 = {a['name_zh'] for t in recs for a in recs[t][:10]}
    out = []
    for key in STYLE_PACKAGES.get(style, ['haste','stats']):
        name, parts, why = PACKAGE_DEFS[key]
        pieces = [aug_by_name.get(n) for n in parts]
        if any(p is None for p in pieces): continue
        inpool = [p for p in pieces if p['name_zh'] in names]
        intop = [p for p in pieces if p['name_zh'] in top10]
        fit = ('本玩法推荐池中三件都出现，优先追。' if len(inpool)>=3 else
               ('本玩法推荐池中出现2件，可追第3件。' if len(inpool)==2 else
                ('本玩法推荐池中只出现1件，不建议硬追。' if len(inpool)==1 else '本玩法推荐池未出现，仅作全局参考。')))
        out.append({'name':name, 'augments':[{'name':p['name_zh'],'tier':p['tier'],'id':p['id']} for p in pieces],
                    'why':why, 'fit':fit, 'in_pool':len(inpool), 'in_top10':[p['name_zh'] for p in intop],
                    'condition':'海克斯随机，优先拿已出现的部件。'})
    out.sort(key=lambda x:(-x['in_pool'], -len(x['in_top10'])))
    out = [x for x in out if x['in_pool']>=1]
    if len(out) < 2:
        for key in ('stats','snowball'):
            name, parts, why = PACKAGE_DEFS[key]
            if any(x['name']==name for x in out): continue
            pieces=[aug_by_name.get(n) for n in parts]
            if any(p is None for p in pieces): continue
            out.append({'name':name,'augments':[{'name':p['name_zh'],'tier':p['tier'],'id':p['id']} for p in pieces],
                        'why':why,'fit':'本玩法推荐池未出现，仅作全局参考。','in_pool':0,'in_top10':[],
                        'condition':'海克斯随机，优先拿已出现的部件。'})
            if len(out)>=2: break
    return out[:3]

def build_variant(con, champ, style, items, global_pool, freq, aug_by_name, base_builds, base_combos, base_spikes, base_engage):
    scores = assess_styles(champ, items)
    score = scores.get(style, 20)
    label, note = viability_label(score)
    recs = pick_augments(con, champ, style, items, global_pool, freq)
    aug = {k.lower(): [] for k in recs}
    for tier in ('Silver','Gold','Prismatic'):
        for rank,a in enumerate(recs[tier],1):
            aug[tier.lower()].append({'rank':rank,'name':a['name_zh'],'name_en':a.get('name_en',''),
                                      'desc':a['desc_zh'],'reason':reason_for(champ,a,style),'tags':a['tags']})
    combos = []
    for c in base_combos:
        c2 = dict(c); c2['note'] = c['note'] + ' ' + {
            'ap':'按AP爆发打：技能命中优先，R留调整/收割。',
            'ad':'连招之间尽量穿插普攻，别只丢技能。',
            'tank':'这套偏开团/抗伤，别追着后排打到脱节。',
            'poke':'先用远程技能压血，等关键控制交掉再进场。',
            'support':'以保C位为主，控制留给敌方进场，别自己去开团。',
        }[style]
        combos.append(c2)
    spikes = list(base_spikes)
    spikes.append({
        'ap':'偏AP：1件套（卢登/火箭腰带）循环起步，2件套（影焰/帽子）爆发，3件套秒后排。',
        'ad':'偏AD：1件套（海妖/星蚀）输出起步，2件套（无尽/黑切）团战强势，3件套接管。',
        'tank':'偏肉：心之钢先叠层数，1件套即可接团，2件套（日炎/反甲）最肉，3件套靠控制与魔抗装站住。',
        'poke':'偏消耗：1件套（卢登/幽梦）压血线，2件套（视界/赛瑞尔达）进入强势，3件套远程压制。',
        'support':'偏辅助：1件套（月石/鸟盾）保人能力成型，2件套（香炉/救赎/骑士）团队收益最高，3件套（米凯尔/流水）补齐解控与移速。',
    }[style])
    engage = base_engage + ' ' + {
        'ap':'AP玩法更脆，等敌方关键控制交掉再进场，一套打完先退。',
        'ad':'AD玩法要持续普攻，站位在前排射程边缘，不要第一个吃控制。',
        'tank':'肉玩法承担开团/拆火，等队友能跟再开，不要一个人追后排。',
        'poke':'消耗玩法先压血线，不要为了补伤害走到近战位。',
        'support':'辅助玩法站后排、跟住C位，技能优先给被集火的队友，控制留给敌方突进。',
    }[style]
    if score < 35:
        combos.insert(0, {'name':'玩法提醒','sequence':'—','note':f'该英雄的{STYLES[style]["label"]}玩法强度较低（{label}），以下内容仅作娱乐参考。'})
    return {
        'style': style, 'label': STYLES[style]['label'], 'score': score, 'viability': label, 'viability_note': note,
        'augments': aug,
        'priority_augments': [{'tier':t,'name':recs[t][0]['name_zh'],'reason':reason_for(champ,recs[t][0],style)} for t in ('Silver','Gold','Prismatic')],
        'synergy_packages': style_packages(champ, recs, style, aug_by_name),
        'combos': combos, 'power_spikes': spikes, 'engage': engage,
        'builds': style_builds(champ, style, items, base_builds),
    }
