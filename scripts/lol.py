#!/usr/bin/env python3
"""Query the local LoL ARAM: Mayhem database.

Usage:
  python3 lol.py resolve "狐狸"
  python3 lol.py report "Ahri"
  python3 lol.py augments "Garen" --tier Gold
  python3 lol.py search "魔法飞弹"
  python3 lol.py list
  python3 lol.py status
"""
from __future__ import annotations
import argparse, json, re, sqlite3, sys, unicodedata
from pathlib import Path

# Windows 控制台默认可能不是 UTF-8，直接输出中文会 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'

def current_db() -> Path:
    cur = json.loads((DATA/'current.json').read_text())
    return DATA / cur['db']

def connect():
    con = sqlite3.connect(current_db())
    con.row_factory = sqlite3.Row
    return con

def norm(s: str) -> str:
    s = unicodedata.normalize('NFKC', s or '').lower()
    return re.sub(r"[\s'’._·\-—()（）\[\]【】]+", '', s)

def fuzzy(a: str, b: str) -> float:
    # simple Levenshtein ratio, no extra dependency
    if not a or not b: return 0.0
    if a == b: return 1.0
    m, n = len(a), len(b)
    if abs(m-n) > max(m,n)*0.5: return 0.0
    prev = list(range(n+1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[-1]+1, prev[j]+1, prev[j-1]+(ca != cb)))
        prev = cur
    return 1 - prev[-1]/max(m,n)

def resolve(con, query: str, limit: int = 8):
    q = norm(query)
    if not q: return []
    rows = con.execute('select * from champions').fetchall()
    out = []
    for r in rows:
        aliases = [r['id'], r['name_zh'], r['title_zh'], r['name_en'], r['title_en']] + json.loads(r['aliases'])
        best = 0.0; hit = ''
        pf_tokens = r['pinyin_full'].split() if r['pinyin_full'] else []
        pi_tokens = r['pinyin_initials'].split() if r['pinyin_initials'] else []
        for a in aliases:
            if not a: continue
            na = norm(a)
            if not na: continue
            sc = 0.0
            if q == na: sc = 100
            elif q in pf_tokens: sc = 96
            elif q in pi_tokens: sc = 92
            elif len(q) >= 2 and any(t.startswith(q) for t in pf_tokens): sc = 84 + min(len(q), 6)
            elif len(q) >= 2 and any(t.startswith(q) for t in pi_tokens): sc = 80 + min(len(q), 6)
            elif len(q) >= 2 and na.startswith(q): sc = 82 + min(len(q), 6)
            elif len(q) >= 2 and q in na: sc = 72 + min(len(q), 6)
            else:
                fr = fuzzy(q, na)
                if fr >= 0.72: sc = 40 + fr*30
            if sc > best:
                best, hit = sc, a
        if best >= 40:
            out.append((best, r, hit))
    # 精确中文/英文名优先
    out.sort(key=lambda x: (-x[0], x[1]['name_zh']))
    seen = set(); res = []
    for sc, r, hit in out:
        if r['id'] in seen: continue
        seen.add(r['id'])
        res.append({'id': r['id'], 'name': r['name_zh'], 'title': r['title_zh'], 'name_en': r['name_en'],
                    'archetype': r['archetype_label'], 'score': round(sc,1), 'matched': hit})
        if len(res) >= limit: break
    return res

def champion_report(con, cid: str, styles=None):
    c = con.execute('select * from champions where id=?', (cid,)).fetchone()
    if not c: return None
    g = json.loads(con.execute('select payload_json from champion_guides where champion_id=?', (cid,)).fetchone()[0])
    aug = {'silver': [], 'gold': [], 'prismatic': []}
    key = {'Silver':'silver','Gold':'gold','Prismatic':'prismatic'}
    for r in con.execute('''select ca.tier, ca.rank, ca.reason, a.name_zh, a.name_en, a.desc_zh, a.desc_en, a.tags
                            from champion_augments ca join augments a on a.id=ca.augment_id
                            where ca.champion_id=? order by case ca.tier when 'Silver' then 0 when 'Gold' then 1 else 2 end, ca.rank''', (cid,)):
        aug[key[r['tier']]].append({'rank': r['rank'], 'name': r['name_zh'], 'name_en': r['name_en'],
                                    'desc': r['desc_zh'] or r['desc_en'], 'reason': r['reason'],
                                    'tags': json.loads(r['tags'])})
    spells = json.loads(c['spells_json'])
    slot_name = {s['slot']: s['name'] for s in spells}
    order = json.loads(con.execute('select order_json from champion_skills where champion_id=?',(cid,)).fetchone()[0])
    priority = con.execute('select priority from champion_skills where champion_id=?',(cid,)).fetchone()[0]
    prio = ' > '.join(f"{x} {slot_name.get(x,x)}" for x in priority) if priority else ''
    meta = {r['key']: r['value'] for r in con.execute('select * from meta')}
    base = {
        'patch': meta.get('patch'), 'ddragon': meta.get('ddragon'), 'built_at': meta.get('built_at'),
        'sources': {k: meta.get(k) for k in ('source_opgg','source_wiki','source_ddragon','source_cdragon') if meta.get(k)},
        'champion': {'id': c['id'], 'name': c['name_zh'], 'title': c['title_zh'], 'name_en': c['name_en'],
                     'tags': json.loads(c['tags']), 'partype': c['partype'], 'attackrange': c['attackrange'],
                     'archetype': c['archetype_label'], 'damage_type': c['damage_type'],
                     'build_type': c['build_type'], 'range_type': c['range_type'],
                     'aliases': json.loads(c['aliases']), 'spells': spells, 'passive': json.loads(c['passive_json'])},
        'augments': aug,
        'priority_augments': g.get('priority_augments', []),
        'synergy_packages': g.get('synergy_packages', []),
        'combos': g.get('combos', []),
        'power_spikes': g.get('power_spikes', []),
        'engage': g.get('engage', ''),
        'builds': g.get('builds', {}),
        'skill_order': {'priority': prio, 'order': [{'slot': x, 'name': slot_name.get(x,x)} for x in order]},
        'tips': g.get('tips', []),
        'notes': [
            '海克斯排名来自 OP.GG 同英雄 ARAM: Mayhem 页面（16.22），是按综合表现的同英雄排序，不是纯胜率。',
            '海克斯档位以 LoL Wiki / CommunityDragon 当前数据交叉核对；已过滤当前版本禁用与明显不适配的海克斯。',
            '出装为 OP.GG 16.22 同英雄核心装序列；分支装按英雄类型与护甲/魔抗/穿透需求给出，均为当前版本存在的装备。',
            '成套海克斯可遇不可求；先拿当前强势件，不要为了凑套放弃节奏。'
        ]
    }
    if styles:
        import variants as V
        items = V.load_items(con)
        global_pool = V.load_augments(con)
        freq = {r[0]: r[1] for r in con.execute('select augment_id,count(*) from champion_augments group by augment_id')}
        aug_by_name = {a['name_zh']: a for a in global_pool}
        core_row = con.execute("select items_json from champion_builds where champion_id=? and kind='core' and rank=1", (cid,)).fetchone()
        core = json.loads(core_row[0]) if core_row else []
        pool = [r[0] for r in con.execute('select item_id from champion_items where champion_id=? order by rank', (cid,))]
        champ_data = {
            'id': c['id'], 'tags': json.loads(c['tags']), 'spells': spells,
            'build_type': c['build_type'], 'damage_type': c['damage_type'], 'range_type': c['range_type'],
            'archetype': c['archetype'], 'attackrange': c['attackrange'], 'partype': c['partype'],
            'core': [core] if core else [], 'pool': pool,
        }
        styles = [x.strip().lower() for x in (styles if isinstance(styles, (list,tuple)) else styles.split(',')) if x.strip()]
        # 玩法按英雄类型过滤：肉只给战士/坦克，辅助只给辅助英雄
        allowed = [k for k in V.STYLES if V.style_allowed(champ_data, k)]
        if 'all' in styles: styles = allowed
        styles = [x for x in styles if x in allowed]
        base['styles'] = V.STYLES
        base['style_assessment'] = {k: {'score': v, 'label': V.viability_label(v)[0], 'note': V.viability_label(v)[1]}
                                    for k,v in V.assess_styles(champ_data, items).items() if k in allowed}
        base['variants'] = {}
        for st in styles:
            v = V.build_variant(
                con, champ_data, st, items, global_pool, freq, aug_by_name,
                base['builds'], base['combos'], base['power_spikes'], base['engage'])
            v['skill_order'] = base['skill_order']
            base['variants'][st] = v
    return base

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['resolve','report','augments','search','list','status'])
    ap.add_argument('query', nargs='?', default='')
    ap.add_argument('--tier', choices=['Silver','Gold','Prismatic','silver','gold','prismatic'], default=None)
    ap.add_argument('--limit', type=int, default=8)
    ap.add_argument('--compact', action='store_true')
    ap.add_argument('--styles', default=None, help='逗号分隔: ad,ap,tank,poke,support 或 all（肉只对战士/坦克开放，辅助只对辅助英雄开放）')
    args = ap.parse_args()
    con = connect()
    if args.command == 'status':
        meta = {r['key']: r['value'] for r in con.execute('select * from meta')}
        counts = {t: con.execute(f'select count(*) from {t}').fetchone()[0] for t in ('champions','augments','items','champion_augments')}
        print(json.dumps({'meta': meta, 'counts': counts, 'db': str(current_db())}, ensure_ascii=False, indent=None if args.compact else 2))
        return
    if args.command == 'list':
        rows = con.execute('select id,name_zh,title_zh,archetype_label from champions order by name_zh').fetchall()
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=None if args.compact else 2))
        return
    if args.command == 'resolve':
        print(json.dumps(resolve(con, args.query, args.limit), ensure_ascii=False, indent=None if args.compact else 2))
        return
    if args.command == 'search':
        q = f"%{args.query}%"
        rows = con.execute('''select name_zh,name_en,tier,desc_zh from augments where name_zh like ? or name_en like ?
                              union all select name_zh,name_en,'装备',plaintext from items where name_zh like ? or name_en like ? limit 30''', (q,q,q,q)).fetchall()
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=None if args.compact else 2))
        return
    # report
    cands = resolve(con, args.query, args.limit)
    if not cands:
        print(json.dumps({'error':'not_found','query':args.query,'hint':'试试中文名、英文名、拼音或常用外号'}, ensure_ascii=False, indent=2))
        sys.exit(1)
    # exact / single
    exact = [x for x in cands if x['score'] >= 100]
    pick = exact[0] if len(exact) == 1 else (cands[0] if len(cands) == 1 else None)
    if pick is None:
        print(json.dumps({'ambiguous': True, 'query': args.query, 'candidates': cands,
                          'instruction':'让用户从候选中选择，再用选定英雄的 id/中文名重试。'}, ensure_ascii=False, indent=2))
        sys.exit(2)
    rep = champion_report(con, pick['id'], args.styles)
    if args.command == 'augments':
        tier = args.tier.capitalize() if args.tier else None
        data = rep['augments']
        if tier: data = {tier.lower(): data[tier.lower()]}
        print(json.dumps({'patch': rep['patch'], 'champion': rep['champion'], 'augments': data}, ensure_ascii=False, indent=None if args.compact else 2))
        return
    print(json.dumps(rep, ensure_ascii=False, indent=None if args.compact else 2))

if __name__ == '__main__':
    main()
