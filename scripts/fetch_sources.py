#!/usr/bin/env python3
"""Download raw sources for one Data Dragon version into the local cache."""
from __future__ import annotations
import argparse, json, os, re, sys, time, random, subprocess, urllib.request, urllib.parse, concurrent.futures
from pathlib import Path

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'
DD = 'https://ddragon.leagueoflegends.com'
CD = 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global'
WIKI = 'https://wiki.leagueoflegends.com/en-us'
OPGG = 'https://op.gg/zh-cn/lol/modes/aram-mayhem'

def get(url: str, path: Path, min_size=200, retries=4):
    if path.exists() and path.stat().st_size >= min_size:
        return path.stat().st_size
    path.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if len(data) < min_size:
                raise RuntimeError(f'too small {len(data)}')
            path.write_bytes(data)
            return len(data)
        except Exception as e:
            last = e
            # curl fallback: some wikis / sites reject urllib's TLS fingerprint
            try:
                tmp = path.with_suffix(path.suffix + '.tmp')
                r = subprocess.run(['curl','-sSL','--max-time','60','-A',UA,'-o',str(tmp),'-w','%{http_code}',url],
                                   capture_output=True, text=True)
                if r.stdout.strip() == '200' and tmp.exists() and tmp.stat().st_size >= min_size:
                    tmp.replace(path)
                    return path.stat().st_size
                if tmp.exists(): tmp.unlink()
            except Exception as e2:
                last = f'{e} / curl: {e2}'
            time.sleep(0.8 * (a + 1) + random.random() * 0.4)
    raise RuntimeError(f'FAIL {url}: {last}')

def get_json(url, path):
    get(url, path, min_size=20)

def latest_version():
    with urllib.request.urlopen(urllib.request.Request(f'{DD}/api/versions.json', headers={'User-Agent': UA}), timeout=30) as r:
        return json.loads(r.read())[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default=None, help='Data Dragon version, e.g. 16.22.1')
    ap.add_argument('--out', default=None)
    ap.add_argument('--skip-tips', action='store_true')
    args = ap.parse_args()
    version = args.version or latest_version()
    root = Path(args.out) if args.out else Path.home()/'.cache'/'lol-aram-mayhem'/version
    root.mkdir(parents=True, exist_ok=True)
    print('version', version, '->', root)
    jobs = [
        (f'{DD}/cdn/{version}/data/zh_CN/championFull.json', root/'championFull_zh.json'),
        (f'{DD}/cdn/{version}/data/en_US/champion.json', root/'data_en_champion.json'),
        (f'{DD}/cdn/{version}/data/zh_CN/champion.json', root/'data_zh_champion.json'),
        (f'{DD}/cdn/{version}/data/zh_CN/item.json', root/'data_zh_CN_item.json'),
        (f'{DD}/cdn/{version}/data/en_US/item.json', root/'data_en_item.json'),
        (f'{CD}/default/v1/cherry-augments.json', root/'default_cherry-augments.json'),
        (f'{CD}/zh_cn/v1/cherry-augments.json', root/'zh_cn_cherry-augments.json'),
        (f'{CD}/zh_cn/v1/augment-lists.json', root/'zh_cn_augment-lists.json'),
        (f'{CD}/zh_cn/v1/items.json', root/'cdragon_items_zh.json'),
        (f'https://raw.communitydragon.org/latest/game/zh_cn/data/menu/en_us/lol.stringtable.json', root/'lol_zh.stringtable.json'),
        (f'{WIKI}/Module:MayhemAugmentData/data?action=raw', root/'mayhem_augments.lua'),
        (f'{WIKI}/ARAM:_Mayhem/Augments?action=raw', root/'mayhem_augments_page.txt'),
    ]
    for url, path in jobs:
        try:
            n = get(url, path, min_size=500)
            print('ok', path.name, n)
        except Exception as e:
            print('WARN', path.name, e, file=sys.stderr)
    # op.gg champion list
    main_html = root/'opgg_main.html'
    get(f'{OPGG}', main_html, min_size=100000)
    html = main_html.read_text(errors='ignore')
    slugs = sorted(set(re.findall(r'href="/lol/modes/aram-mayhem/([a-z0-9]+)/build"', html)))
    if not slugs:
        slugs = sorted(set(re.findall(r'href="/zh-cn/lol/modes/aram-mayhem/([a-z0-9]+)/build"', html)))
    if not slugs:
        raise RuntimeError('cannot find champion slugs on op.gg page')
    (root/'slugs.json').write_text(json.dumps(slugs, ensure_ascii=False))
    print('champions', len(slugs))
    tasks = [(s, p) for s in slugs for p in ('augments','items','skills')]
    def one(t):
        s, p = t
        path = root/'cache'/f'{s}_{p}.html'
        try:
            n = get(f'{OPGG}/{s}/{p}', path, min_size=300000)
            return (s, p, 'ok', n)
        except Exception as e:
            return (s, p, 'FAIL', str(e))
    fails = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for i, r in enumerate(ex.map(one, tasks), 1):
            if r[2] != 'ok':
                fails.append(r)
            if i % 40 == 0: print('pages', i, '/', len(tasks), 'fails', len(fails))
    if fails:
        raise RuntimeError(f'{len(fails)} op.gg pages failed; first={fails[:3]}')
    if not args.skip_tips:
        # English champion names for wiki strategy pages
        en = json.loads((root/'data_en_champion.json').read_text())
        names = {k: v['name'] for k, v in en['data'].items()}
        tips_dir = root/'strategy_cache'; tips_dir.mkdir(exist_ok=True)
        def tip(item):
            cid, name = item
            path = tips_dir/f'{cid}.txt'
            if path.exists() and path.stat().st_size > 100: return (cid, 'cached')
            page = name.replace(' ', '_')
            url = f'{WIKI}/' + urllib.parse.quote(page, safe="_'!()") + '/Strategy?action=raw'
            try:
                get(url, path, min_size=100, retries=2)
                return (cid, 'ok')
            except Exception:
                return (cid, '404')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            list(ex.map(tip, names.items()))
    print('DONE', root)

if __name__ == '__main__':
    main()
