#!/usr/bin/env python3
"""Export a compact JSON for the Vue web app."""
import json, re, sqlite3, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'scripts'/'vendor'))
import lol, variants as V
from pypinyin import lazy_pinyin


def add_item_ids(v, name_to_id):
    b = v.get('builds') or {}
    b['starter_ids'] = [name_to_id.get(n) for n in b.get('starter', [])]
    b['boots_ids'] = [name_to_id.get(n) for n in b.get('boots', [])]
    for br in (b.get('branches') or {}).values():
        br['item_ids'] = [name_to_id.get(n) for n in br.get('items', [])]
    for core in b.get('core', []):
        core.setdefault('ids', [])

def clean_text(s):
    if not isinstance(s, str): return s
    s = re.sub(r'%i:[^%]+%', '', s)
    s = re.sub(r'@[^@]{1,80}@', '（数值）', s)
    s = s.replace('{{SpellName}}', '该技能').replace('{{Item_Keyword_OnHit}}', '攻击特效')
    s = s.replace('{{', '').replace('}}', '')
    s = re.sub(r'；{2,}', '；', s)
    s = re.sub(r'\s+', ' ', s).strip('； ')
    return s

def clean_tree(o):
    if isinstance(o, dict): return {k: clean_tree(v) for k,v in o.items()}
    if isinstance(o, list): return [clean_tree(v) for v in o]
    return clean_text(o)

def main():
    con = lol.connect()
    name_to_id = {r[0]: r[1] for r in con.execute('select name_zh, id from items')}
    champs = []
    reports = {}
    for c in con.execute('select * from champions order by name_en'):
        cid = c['id']
        rep = lol.champion_report(con, cid, 'all')
        if not rep: continue
        title_syllables = lazy_pinyin(c['title_zh'] or c['name_zh'] or cid)
        title_pinyin = ' '.join(title_syllables).lower()
        initial = title_pinyin[0].upper() if title_pinyin and title_pinyin[0].isalpha() else '#'
        search = '|'.join([cid, c['name_zh'], c['title_zh'], c['name_en'],
                           c['pinyin_full'] or '', c['pinyin_initials'] or '',
                           *json.loads(c['aliases'])]).lower()
        champs.append({
            'id': cid, 'name': c['name_zh'], 'title': c['title_zh'], 'name_en': c['name_en'],
            'archetype': c['archetype_label'], 'damage_type': c['damage_type'], 'range_type': c['range_type'],
            'aliases': json.loads(c['aliases']), 'pinyin': (c['pinyin_full'] or '') + ' ' + (c['pinyin_initials'] or ''),
            'initial': initial, 'sort_key': title_pinyin, 'search': search,
            'styles': {k: {'score': v['score'], 'label': v['label']} for k,v in rep['style_assessment'].items()},
        })
        for v in rep['variants'].values():
            add_item_ids(v, name_to_id)
        reports[cid] = clean_tree({
            'champion': rep['champion'],
            'style_assessment': rep['style_assessment'],
            'variants': rep['variants'],
        })
        if len(champs) % 25 == 0: print('exported', len(champs), flush=True)
    out = {
        'patch': rep['patch'], 'ddragon': rep['ddragon'], 'built_at': rep['built_at'],
        'styles': V.STYLES, 'champions': champs, 'reports': reports,
        'sources': rep['sources'],
    }
    path = ROOT/'web'/'public'/'data'/'lol.json'
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(',',':')))
    print('WROTE', path, path.stat().st_size, 'champs', len(champs))

if __name__ == '__main__':
    main()
