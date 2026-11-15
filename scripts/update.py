#!/usr/bin/env python3
"""Fetch the latest Data Dragon version and build a new versioned SQLite snapshot.

Usage:
  python3 scripts/update.py                 # latest
  python3 scripts/update.py --version 16.23.1
  python3 scripts/update.py --from-cache --version 16.22.1
"""
from __future__ import annotations
import argparse, json, os, sqlite3, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT/'scripts'
DATA = ROOT/'data'

def run(cmd, env=None):
    print('+', ' '.join(map(str,cmd)), flush=True)
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        raise SystemExit(r.returncode)

def validate(db: Path, expected_champs: int | None = None):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    errs = []
    n = con.execute('select count(*) from champions').fetchone()[0]
    if expected_champs and n != expected_champs: errs.append(f'champions {n} != {expected_champs}')
    bad = con.execute('''select champion_id,tier,count(*) c from champion_augments group by champion_id,tier having c!=10''').fetchall()
    if bad: errs.append(f'{len(bad)} champion-tier rows not 10')
    orphan = con.execute('''select count(*) from champion_augments ca left join augments a on a.id=ca.augment_id where a.id is null''').fetchone()[0]
    if orphan: errs.append(f'{orphan} orphan augment refs')
    empty = con.execute("select count(*) from augments where desc_zh=''").fetchone()[0]
    if empty: errs.append(f'{empty} augments without desc')
    items = con.execute('select count(*) from items').fetchone()[0]
    meta = {r['key']: r['value'] for r in con.execute('select * from meta')}
    con.close()
    return errs, {'champions': n, 'items': items, 'meta': meta}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default=None)
    ap.add_argument('--from-cache', action='store_true')
    ap.add_argument('--source', default=None, help='已有原始数据目录（配合 --from-cache）')
    args = ap.parse_args()
    env = os.environ.copy()
    if args.version:
        version = args.version
    else:
        import urllib.request
        with urllib.request.urlopen('https://ddragon.leagueoflegends.com/api/versions.json', timeout=30) as r:
            version = json.loads(r.read())[0]
    patch = '.'.join(version.split('.')[:2])
    source = Path(args.source) if args.source else Path.home()/'.cache'/'lol-aram-mayhem'/version
    if not args.from_cache:
        run([sys.executable, str(SCRIPTS/'fetch_sources.py'), '--version', version, '--out', str(source)])
    env['LOL_SOURCE_DIR'] = str(source)
    env['LOL_PATCH'] = patch
    env['LOL_DDRAGON'] = version
    run([sys.executable, str(SCRIPTS/'parse_pages.py')], env=env)
    old_current = (DATA/'current.json').read_text() if (DATA/'current.json').exists() else None
    run([sys.executable, str(SCRIPTS/'build_db.py')], env=env)
    db = DATA/version/'lol.db'
    try:
        expected = len(json.loads((source/'championFull_zh.json').read_text())['data'])
    except Exception:
        expected = None
    errs, info = validate(db, expected)
    if errs:
        if old_current: (DATA/'current.json').write_text(old_current)
        print('VALIDATION FAILED:', errs, file=sys.stderr)
        raise SystemExit(1)
    print('OK', version, info)
    # refresh the web JSON snapshot (does not rebuild dist)
    try:
        run([sys.executable, str(SCRIPTS/'export_web.py')], env=env)
        print('WEB DATA REFRESHED; run `cd web && npm run build` to update dist.')
    except SystemExit as e:
        print('WARN: web export failed; run scripts/export_web.py manually.', file=sys.stderr)

if __name__ == '__main__':
    main()
