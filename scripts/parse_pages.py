import json,re,os
from pathlib import Path
from lxml import html
W = Path(os.environ.get('LOL_SOURCE_DIR', Path.home()/'.cache'/'lol-aram-mayhem'/'16.22.1'))
slugs=json.load(open(W/'slugs.json'))
en=json.load(open(W/'data_en_champion.json'))['data']
byid={k.lower():k for k in en}
out={}
missing=[]
for slug in slugs:
    cid=byid.get(slug)
    if not cid:
        missing.append(slug); continue
    # augments
    doc=html.parse(str(W/'cache'/f'{slug}_augments.html'))
    names=[e.text_content().strip() for e in doc.xpath('//strong[contains(@class,"text-sm")]')]
    # dedupe preserving order
    seen=set(); aug=[]
    for n in names:
        if n and n not in seen:
            seen.add(n); aug.append(n)
    # items
    doc=html.parse(str(W/'cache'/f'{slug}_items.html'))
    sections=[]
    for sec in doc.xpath('//section'):
        h=sec.xpath('.//div[contains(@class,"text-sm") and contains(@class,"font-bold")]')
        title=' '.join(h[0].text_content().strip().split()) if h else ''
        if title not in ('核心装备','鞋子','出门装','装备'): continue
        table=sec.xpath('.//table[1]')
        if not table: continue
        rows=[]
        for tr in table[0].xpath('.//tr'):
            imgs=tr.xpath('.//img[contains(@src,"/item/")]')
            seq=[]
            for im in imgs:
                src=im.get('src',''); m=re.search(r'/item/(\d+)\.png',src)
                if m: seq.append({'id':int(m.group(1)),'name':im.get('alt','')})
            if seq: rows.append(seq)
        sections.append({'title':title,'rows':rows})
    # skills
    doc=html.parse(str(W/'cache'/f'{slug}_skills.html'))
    order=[]
    priority=''
    for sec in doc.xpath('//section'):
        h=sec.xpath('.//div[contains(@class,"text-sm") and contains(@class,"font-bold")]')
        title=' '.join(h[0].text_content().strip().split()) if h else ''
        if title=='技能加点':
            srcs=sec.xpath('.//img[contains(@src,"/spell/")]/@src')
            letters=[re.search(r'([QWE])\.png',s).group(1) for s in srcs if re.search(r'([QWE])\.png',s)]
            if letters and not order: order=letters[:18]
            txt=sec.text_content()
            m=re.search(r'技能加点([QWER\s　]+)',txt)
            if m:
                seqs=re.findall(r'[QWE]{3}',m.group(1))
                if seqs and not priority: priority=seqs[0]
            break
    out[cid]={'slug':slug,'augment_order':aug,'item_sections':sections,'skill_order':order,'skill_priority':priority}
    if not aug or not sections or not order:
        print('WARN',cid,len(aug),len(sections),len(order))
json.dump(out,open(W/'parsed_pages.json','w'),ensure_ascii=False,indent=1)
print('champions',len(out),'missing slugs',missing)
from collections import Counter
print('aug counts',Counter(len(v['augment_order']) for v in out.values()))
print('core rows',Counter(len([s for s in v['item_sections'] if s['title']=='核心装备'][0]['rows']) for v in out.values()))
