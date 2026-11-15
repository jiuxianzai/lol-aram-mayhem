import json, re, os, sqlite3, sys, unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'vendor'))
from pypinyin import lazy_pinyin, Style

W = Path(os.environ.get('LOL_SOURCE_DIR', Path.home()/'.cache'/'lol-aram-mayhem'/'16.22.1'))
PATCH = os.environ.get('LOL_PATCH', '16.22')
DDRAGON = os.environ.get('LOL_DDRAGON', '16.22.1')
OUT = Path(__file__).resolve().parent.parent / 'data' / DDRAGON
DB_PATH = OUT / 'lol.db'

# ---------------- helpers ----------------
def clean_wiki(s):
    s = s.replace('\\"', '"')
    s = re.sub(r'<br\s*/?>', '；', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r"'''?", '', s)
    s = re.sub(r'\{\{as\|([^{}]*)\}\}', r'\1', s)
    s = re.sub(r'\{\{fd\|([^{}]*)\}\}', r'\1', s)
    s = re.sub(r'\{\{pp\|([^{}|]*)(?:\|[^{}]*)?\}\}', r'\1', s)
    s = re.sub(r'\{\{tip\|([^{}|]*)(?:\|[^{}]*)?\}\}', r'\1', s)
    s = re.sub(r'\{\{sbc\|([^{}|]*)(?:\|[^{}]*)?\}\}', r'\1', s)
    s = re.sub(r'\{\{ai\|([^{}|]*)(?:\|[^{}]*)?\}\}', r'\1', s)
    s = re.sub(r'\{\{ci\|([^{}|]*)(?:\|[^{}]*)?\}\}', r'\1', s)
    s = re.sub(r'\{\{ii\|([^{}|]*)(?:\|[^{}]*)?\}\}', r'\1', s)
    s = re.sub(r'\{\{si\|([^{}|]*)(?:\|[^{}]*)?\}\}', r'\1', s)
    s = re.sub(r'\{\{ri\|([^{}|]*)(?:\|[^{}]*)?\}\}', r'\1', s)
    s = re.sub(r'\[\[[^\]|]+\|([^\]]+)\]\]', r'\1', s)
    s = re.sub(r'\[\[([^\]]+)\]\]', r'\1', s)
    s = re.sub(r'\{\{[^{}]*\}\}', '', s)
    s = re.sub(r'@[A-Za-z0-9_.]+@', '（数值）', s)
    s = s.replace('%i:cooldown%', '').replace('%i:scale', '')
    s = re.sub(r'\s+', ' ', s).strip(' ；')
    return s

def clean_html(s):
    s = re.sub(r'<br\s*/?>', '；', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'@[A-Za-z0-9_.]+@', '（数值）', s)
    s = re.sub(r'\s+', ' ', s).strip(' ；')
    return s

# ---------------- augment master ----------------
def load_wiki_augments():
    s = (W/'mayhem_augments.lua').read_text()
    starts = list(re.finditer(r'\n\t\["([^"]+)"\] = \{', s))
    out = []
    for i, m in enumerate(starts):
        end = starts[i+1].start() if i+1 < len(starts) else len(s)
        chunk = s[m.end():end]
        tier = re.search(r'\["tier"\] = "([^"]+)"', chunk)
        desc = re.search(r'\["description"\] = "((?:[^"\\]|\\.)*)"', chunk)
        out.append({'name_en': m.group(1), 'tier': tier.group(1) if tier else None,
                    'desc_en_raw': desc.group(1) if desc else '',
                    'disabled': 'currently disabled' in chunk.lower()})
    return out

def build_augment_master():
    wiki = load_wiki_augments()
    en = json.load(open(W/'default_cherry-augments.json'))
    zh = {x['augmentNameId']: x for x in json.load(open(W/'zh_cn_cherry-augments.json'))}
    st = json.load(open(W/'lol_zh.stringtable.json'))['entries']
    norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
    by_en = {}
    for x in en:
        by_en.setdefault(norm(x['nameTRA']), x)
    alias_zh = {
        'Quest: Steel Your Heart': '钢化你心', "Quest: Urf's Champion": '海牛阿福的勇士',
        "Quest: Wooglet's Witchcap": '沃格勒特的巫师帽', "Quest: Icathia's Fall": '艾卡西亚的陷落',
        'Quest: Sneakerhead': '王中王，靴中靴', 'Pentakill: HEAVY': '重型', 'Pentakill: POWER': '力量',
        'Pentakill: THRASH': '鞭挞', 'Pentakill: DOOM': '厄运', 'Guilty Pleasure': '恶趣味',
        'Yowch, My Coins!': '哎哟，我的硬币！'
    }
    # wiki by normalized english -> record
    wiki_by_norm = {}
    for w in wiki:
        rec = by_en.get(norm(w['name_en']))
        zhname = alias_zh.get(w['name_en']) or (zh[rec['augmentNameId']]['nameTRA'] if rec else None)
        if not zhname: continue
        w['name_zh'] = zhname
        if rec: w['id'] = rec['augmentNameId']; w['rarity'] = rec['rarity']
        else: w['id'] = 'wiki:' + w['name_en']; w['rarity'] = None
        w['desc_en'] = clean_wiki(w['desc_en_raw'])
        wiki_by_norm[norm(w['name_en'])] = w

    # all names used by op.gg
    parsed = json.load(open(W/'parsed_pages.json'))
    used_names = sorted({n for c in parsed.values() for n in c['augment_order'] if n != '强化!'})
    zh_by_name = {}
    for x in en:
        z = zh.get(x['augmentNameId'])
        if z and z['nameTRA'] not in zh_by_name:
            zh_by_name[z['nameTRA']] = x
    # prefer ARAM_ id if duplicate
    for n, x in list(zh_by_name.items()):
        cands = [y for y in en if zh.get(y['augmentNameId'], {}).get('nameTRA') == n]
        cands.sort(key=lambda y: (0 if y['augmentNameId'].startswith('ARAM_') else 1, y['id']))
        if cands: zh_by_name[n] = cands[0]

    name_keys = {}
    for k, v in st.items():
        if isinstance(v, str) and k.endswith('_name') and v.strip():
            name_keys.setdefault(v.strip(), []).append(k)

    def desc_from_keys(aid, zhname):
        slug = aid.lower().replace('aram_', '').replace('quest_', '')
        cands = []
        for base in [f'kiwi_aram_{slug}', f'kiwi_{slug}', f'kiwi_augment_{slug}', f'augment_{slug}', f'cherry_{slug}']:
            cands += [base + '_summary', base + '_tooltip', base + '_desc']
        for k in cands:
            if k in st and isinstance(st[k], str) and st[k].strip():
                return st[k]
        # by localized name
        for k in name_keys.get(zhname, []):
            base = k[:-5]
            for suf in ('_summary', '_tooltip', '_desc'):
                if base + suf in st and isinstance(st[base+suf], str) and st[base+suf].strip():
                    return st[base+suf]
        return None

    manual = {
        '信念者的强化': '给友方英雄治疗或护盾后使其获得8秒祝福；被祝福的友军伤害敌人时你叠“虔诚”，满50层释放大范围冲击波，造成魔法伤害并斩杀生命值低于治疗/护盾强度25%的敌人。',
        '冰雪爆裂': '你的雪球获得技能急速；再次施放雪球造成更高魔法伤害、击飞目标并击退周围敌人。',
        '力量': '你的W技能获得20技能急速，伤害、治疗和护盾效果提高10%。',
        '重型': '你的Q技能获得20技能急速，伤害、治疗和护盾效果提高10%。',
        '鞭挞': '你的E技能获得20技能急速，伤害、治疗和护盾效果提高10%。',
        '厄运': '你的R技能获得20技能急速，伤害、治疗和护盾效果提高10%。',
        '升级：中娅': '中娅沙漏冷却降低；凝滞期间可以移动并获得移速。',
        '升级：收集者': '收集者每次处决敌人都会提高处决阈值，并提供额外金币。',
        '升级：无尽之刃': '获得金币；装备无尽之刃后，暴击会提供随机的额外暴击伤害。',
        '升级：献祭': '璀璨回响/日炎圣盾的献祭每跳提供金币。',
        '和我一起困在这里': '使用大招后获得伤害减免，随后嘲讽附近敌人；额外获得终极技能急速。',
        '咏叹奏鸣': '周期性自动交替施放坚毅咏叹调（治疗+护盾光环）和迅捷奏鸣曲（移速光环）。',
        '多重射击': '完成任务可让你指定技能的飞弹数量增加，并改为锥形发射。',
        '大法师': '施放技能时，返还另一个随机技能30%基础冷却时间。',
        '扳机炼狱': '获得“悍勇本色”评价体系；达到S评价时自动施放炼狱扳机，对周围敌人疯狂射击。',
        '杀意翻涌': '朝生命值低于40%的敌人移动时获得60%移速。',
        '沃格勒特的巫师帽': '获得无用大棒；任务：持有灭世者的死亡之帽和中娅沙漏，完成后合成沃格勒特的巫师帽。',
        '海牛阿福的勇士': '任务：参与18次击杀；奖励：金铲铲。',
        '濒死悟道': '攻击或技能命中敌方英雄叠层，满层后阵亡时复活，并获得适应之力、移速和全能吸血（当前版本禁用）。',
        '灵魄炸弹': '给友军治疗/护盾时积攒灵魄炸弹；满层后投向生命值最低的友军，治疗并护盾附近友军。',
        '炽燃利息': '英雄身上的灼烧和持续伤害会按造成伤害生成金币。',
        '电涌力场': '施放大招后生成领域，提供技能急速和移速，并额外发射飞弹（当前版本禁用）。',
        '男爵之手': '获得25%适应之力，并大幅强化附近友方小兵。',
        '舞会女王': '周期性自动获得洛的大招效果：加速并魅惑碰撞到的敌人。',
        '蛋白粉奶昔': '获得治疗和护盾强度，数值随额外护甲和魔抗提高。',
        '贪欲束缚': '用技能定身或缚地敌方英雄时造成额外魔法伤害并治疗自己。',
        '转得我眩晕了': '一个召唤师技能被替换为“骄行荡寇”：钩住地形摆荡，并自动攻击最近敌人。',
        '过度延伸者': '强化加农炮发射器：射程、飞行速度和伤害大幅提高，并可使用回城。',
        '钢化你心': '任务：持有心之钢且层数达到要求；奖励：心之钢层数乘以倍数。',
        '飞身踢': '攻击和技能会处决低生命值敌人，将其击退并引发爆炸，同时治疗自己。',
        '魄罗爆破手': '周期性召集魄罗；伤害敌人时发射所有魄罗，每个造成最大生命值真实伤害，5只时击退。',
        '？？？': '敌人消失信号会发射飞弹到标记位置，对敌人造成基于已损失生命值的魔法伤害并治疗友军。',
        '卡皮巴拉空投': None,
    }

    master = []
    for zhname in used_names:
        rec = zh_by_name.get(zhname)
        if not rec:
            continue
        aid = rec['augmentNameId']
        wen = rec['nameTRA']
        wrec = wiki_by_norm.get(norm(wen))
        tier = (wrec['tier'] if wrec and wrec.get('tier') else None) or rec['rarity'].replace('k', '')
        if tier not in ('Silver', 'Gold', 'Prismatic'):
            continue
        desc_en = wrec['desc_en'] if wrec else ''
        raw_zh = manual.get(zhname) if manual.get(zhname) is not None else desc_from_keys(aid, zhname)
        if not raw_zh:
            # try wiki english as last resort
            raw_zh = ''
        desc_zh = clean_html(raw_zh) if raw_zh else ''
        if not desc_zh and desc_en:
            desc_zh = desc_en  # will be translated at runtime if needed
        disabled = bool(wrec and wrec.get('disabled'))
        # known disabled from wiki even if name mapping differs
        if zhname in {'王中王，靴中靴', '大师铸就', '无尽大杀四方', '自然即是治愈', '轻拍背部', '鲨鱼诱饵', '鲨鱼暴风', '冰雪爆裂', '牙仙子', '濒死悟道', '灵魄炸弹', '软弹啪叽抓', '电涌力场'}:
            disabled = True
        tags = set()
        d = (desc_en + ' ' + desc_zh).lower()
        def has(*ks): return any(k in d for k in ks)
        if has('ability power', '法术强度', '法强'): tags.add('AP')
        if has('attack damage', '攻击力', '额外ad'): tags.add('AD')
        if has('attack speed', '攻击速度', '攻速'): tags.add('AS')
        if has('critical', '暴击'): tags.add('crit')
        if has('on-hit', 'on hit', '攻击特效', '普攻'): tags.add('onhit')
        if has('maximum health', '最大生命值', 'bonus health', '额外生命值', 'armor', '护甲', 'magic resistance', '魔抗', 'resistances'): tags.add('tank')
        if has('heal', '治疗', 'omnivamp', '全能吸血', 'life steal', '生命偷取', 'regeneration', '回复'): tags.add('sustain')
        if has('heal and shield power', '治疗和护盾强度'): tags.add('enchanter')
        if has('ability haste', '技能急速', 'cooldown', '冷却'): tags.add('haste')
        if has('movement speed', '移动速度', 'dash', '冲刺', 'blink', '闪现', 'ghost', '位移'): tags.add('mobility')
        if has('missile', '飞弹', 'range', '射程', 'poke', '消耗'): tags.add('poke')
        if has('execute', '处决', '斩杀'): tags.add('execute')
        if has('stun', '眩晕', 'root', '定身', 'charm', '魅惑', 'fear', '恐惧', 'silence', '沉默', 'knock', '击飞', 'taunt', '嘲讽', 'slow', '减速', 'suppress', '压制'): tags.add('utility')
        if has('gold', '金币'): tags.add('gold')
        if has('quest', '任务'): tags.add('quest')
        if has('snowball', '雪球', 'mark', '标记'): tags.add('snowball')
        if has('damage', '伤害'): tags.add('damage')
        master.append({'id': aid, 'name_zh': zhname, 'name_en': wen, 'tier': tier,
                       'desc_zh': desc_zh, 'desc_en': desc_en, 'tags': sorted(tags),
                       'disabled': disabled, 'icon': rec.get('augmentSmallIconPath', '')})
    # dedupe by zh name, prefer ARAM_
    dedup = {}
    for a in master:
        if a['name_zh'] not in dedup or (a['id'].startswith('ARAM_') and not dedup[a['name_zh']]['id'].startswith('ARAM_')):
            dedup[a['name_zh']] = a
    master = list(dedup.values())
    return master

# ---------------- champion data ----------------
ALIASES = {
'Aatrox':['剑魔'], 'Ahri':['阿狸','狐狸','九尾','九尾狐'], 'Akali':['阿卡丽','丽'],
'Alistar':['牛头','老牛'], 'Amumu':['木乃伊','阿木木'], 'Anivia':['冰鸟','艾尼维亚'],
'Annie':['火女','安妮'], 'Aphelios':['厄斐琉斯','月男'], 'Ashe':['寒冰','艾希'],
'AurelionSol':['龙王','奥瑞利安索尔'], 'Azir':['沙皇','阿兹尔'], 'Bard':['巴德'],
'Belveth':['卑尔维斯','虚空女皇'], 'Blitzcrank':['机器人','布里茨'], 'Brand':['火男','布兰德'],
'Braum':['布隆'], 'Briar':['贝蕾亚'], 'Caitlyn':['女警','凯特琳'],
'Camille':['青钢影','卡蜜尔'], 'Cassiopeia':['蛇女','卡西奥佩娅'], 'Chogath':['虫子','大虫子','科加斯'],
'Corki':['飞机','库奇'], 'Darius':['诺手','德莱厄斯'], 'Diana':['皎月','黛安娜'],
'Draven':['德莱文'], 'DrMundo':['蒙多','祖安狂人'], 'Ekko':['艾克'], 'Elise':['蜘蛛','伊莉丝'],
'Evelynn':['寡妇','伊芙琳'], 'Ezreal':['EZ','伊泽瑞尔','探险家'], 'Fiddlesticks':['稻草人','费德提克'],
'Fiora':['剑姬','菲奥娜'], 'Fizz':['小鱼人','菲兹'], 'Galio':['加里奥'],
'Gangplank':['船长','普朗克'], 'Garen':['盖伦','草丛伦'], 'Gnar':['纳尔'],
'Gragas':['酒桶','古拉加斯'], 'Graves':['男枪','格雷福斯'], 'Gwen':['格温'],
'Hecarim':['人马','赫卡里姆'], 'Heimerdinger':['大头','黑默丁格'], 'Hwei':['彗','画家'],
'Illaoi':['触手妈','俄洛伊'], 'Irelia':['刀妹','女刀','艾瑞莉娅'], 'Ivern':['翠神','艾翁'],
'Janna':['风女','迦娜'], 'JarvanIV':['皇子','嘉文四世'], 'Jax':['武器','武器大师','贾克斯'],
'Jayce':['杰斯'], 'Jhin':['烬','戏命师'], 'Jinx':['金克丝'], 'Kaisa':['卡莎'],
'Kalista':['滑板鞋','卡莉丝塔'], 'Karma':['扇子妈','卡尔玛'], 'Karthus':['死歌','卡尔萨斯'],
'Kassadin':['卡萨丁','虚空行者'], 'Katarina':['卡特','卡特琳娜'], 'Kayle':['天使','凯尔'],
'Kayn':['凯隐'], 'Kennen':['凯南'], 'Khazix':['螳螂','卡兹克'], 'Kindred':['千珏'],
'Kled':['克烈'], 'Kogmaw':['大嘴','克格莫'], 'KSante':['K桑','奎桑提'],
'Leblanc':['妖姬','乐芙兰'], 'LeeSin':['瞎子','盲僧','李青'], 'Leona':['日女','蕾欧娜'],
'Lillia':['莉莉娅'], 'Lissandra':['冰女','丽桑卓'], 'Lucian':['卢锡安','奥巴马'],
'Lulu':['露露','璐璐'], 'Lux':['光辉','拉克丝'], 'Malphite':['石头人','墨菲特'],
'Malzahar':['蚂蚱','玛尔扎哈'], 'Maokai':['大树','茂凯'], 'MasterYi':['剑圣','易大师'],
'Mel':['梅尔'], 'Milio':['米利欧'], 'MissFortune':['女枪','赏金','好运姐','厄运小姐'],
'MonkeyKing':['猴子','悟空','孙悟空'], 'Mordekaiser':['铁男','莫德凯撒'], 'Morgana':['莫甘娜'],
'Naafiri':['纳亚菲利'], 'Nami':['娜美'], 'Nasus':['狗头','内瑟斯'], 'Nautilus':['泰坦','诺提勒斯'],
'Neeko':['妮蔻'], 'Nidalee':['豹女','奈德丽'], 'Nilah':['尼菈'], 'Nocturne':['梦魇','魔腾'],
'Nunu':['雪人','努努'], 'Olaf':['奥拉夫','狂战士'], 'Orianna':['发条','奥莉安娜'],
'Ornn':['奥恩'], 'Pantheon':['潘森','斯巴达'], 'Poppy':['波比'], 'Pyke':['派克'],
'Qiyana':['奇亚娜','元素女皇'], 'Quinn':['奎因','鸟人'], 'Rakan':['洛'],
'Rammus':['龙龟','拉莫斯'], 'RekSai':['挖掘机','雷克塞'], 'Rell':['芮尔'],
'Renata':['烈娜塔'], 'Renekton':['鳄鱼','雷克顿'], 'Rengar':['狮子狗','雷恩加尔'],
'Riven':['锐雯','瑞文'], 'Rumble':['兰博'], 'Ryze':['瑞兹','流浪'],
'Samira':['莎弥拉'], 'Sejuani':['猪妹','瑟庄妮'], 'Senna':['赛娜'], 'Seraphine':['萨勒芬妮','酸辣粉'],
'Sett':['腕豪','瑟提'], 'Shaco':['小丑','萨科'], 'Shen':['慎','腰子'], 'Shyvana':['龙女','希瓦娜'],
'Singed':['炼金','辛吉德'], 'Sion':['亡灵','塞恩'], 'Sivir':['轮子妈','希维尔'],
'Skarner':['蝎子','斯卡纳'], 'Smolder':['斯莫德','小火龙'], 'Sona':['琴女','娑娜'],
'Soraka':['奶妈','索拉卡','星妈'], 'Swain':['乌鸦','斯维因'], 'Sylas':['塞拉斯','偷男'],
'Syndra':['辛德拉','球女'], 'TahmKench':['塔姆','河流之王'], 'Taliyah':['岩雀','塔莉垭'],
'Talon':['男刀','泰隆'], 'Taric':['塔里克'], 'Teemo':['提莫','提百万'], 'Thresh':['锤石'],
'Tristana':['小炮','崔丝塔娜'], 'Trundle':['巨魔','特朗德尔'], 'Tryndamere':['蛮王','泰达米尔'],
'TwistedFate':['卡牌','崔斯特'], 'Twitch':['老鼠','图奇'], 'Udyr':['乌迪尔'],
'Urgot':['螃蟹','厄加特'], 'Varus':['韦鲁斯','维鲁斯'], 'Vayne':['薇恩'],
'Veigar':['小法','维迦'], 'Velkoz':['大眼','维克兹'], 'Vex':['薇古丝'], 'Vi':['蔚'],
'Viego':['佛耶戈','破败王'], 'Viktor':['维克托','三只手'], 'Vladimir':['吸血鬼','弗拉基米尔'],
'Volibear':['狗熊','沃利贝尔'], 'Warwick':['狼人','沃里克'], 'Xayah':['霞'], 'Xerath':['泽拉斯'],
'XinZhao':['赵信','菊花信'], 'Yasuo':['亚索','快乐风男'], 'Yone':['永恩'], 'Yorick':['掘墓','约里克'],
'Yuumi':['猫咪','悠米'], 'Zac':['扎克'], 'Zed':['劫'], 'Zeri':['泽丽'],
'Ziggs':['炸弹人','吉格斯'], 'Zilean':['时光','基兰'], 'Zoe':['佐伊'], 'Zyra':['婕拉'],
'Locke':['洛克'], 'Yunara':['芸阿娜'], 'Zaahen':['亚恒'], 'Ambessa':['安蓓萨'], 'Aurora':['阿萝拉'],
}

SPELL_ORDER = ['Q','W','E','R']

def pinyin_pair(s):
    return ''.join(lazy_pinyin(s)), ''.join(lazy_pinyin(s, style=Style.FIRST_LETTER))

def extract_tips(cid):
    path = W/'strategy_cache'/f'{cid}.txt'
    if not path.exists(): return []
    s = path.read_text(errors='ignore')
    tips = []
    for header in [';Playing As', ';Ability Usage']:
        m = re.search(re.escape(header)+r'[^\n]*\n(.*?)(?=\n;|\n==)', s, re.S)
        if not m: continue
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line.startswith('*'): continue
            t = clean_wiki(line.lstrip('*').strip())
            t = re.sub(r'\s+', ' ', t)
            if len(t) < 18: continue
            low = t.lower()
            if any(k in low for k in ['minion', 'lane', 'tower', 'recall', 'ward', 'jungle', 'gank', 'farm']):
                continue
            if t not in tips: tips.append(t)
    # keep useful length
    tips = [t for t in tips if len(t) <= 320]
    return tips[:8]

def parse_items():
    zh = json.load(open(W/'data_zh_CN_item.json'))['data']
    en = json.load(open(W/'data_en_item.json'))['data']
    items = {}
    for k, v in zh.items():
        iid = int(k)
        items[iid] = {
            'id': iid, 'name_zh': v.get('name',''), 'name_en': en.get(k,{}).get('name',''),
            'plaintext': clean_html(v.get('plaintext','')),
            'desc_zh': clean_html(v.get('description','')),
            'tags': v.get('tags',[]), 'stats': v.get('stats',{}),
            'gold': v.get('gold',{}).get('total',0), 'boots': 'Boots' in v.get('tags',[]),
        }
    return items

def spell_flags(desc):
    d = desc.lower()
    hard = ['stun','root','charm','fear','taunt','suppress','knock','airborne','sleep','ground','眩晕','定身','魅惑','恐惧','嘲讽','压制','击飞','睡眠','缚地']
    soft = ['slow','减速']
    dash = ['dash','blink','leap','charge','teleport','冲刺','突进','闪烁','跃向','传送']
    shield = ['shield','护盾']
    heal = ['heal','治疗','回复']
    execute = ['execute','处决','斩杀']
    stealth = ['stealth','invisible','隐身']
    asbuff = ['attack speed','攻速']
    return {
        'hard_cc': any(k in d for k in hard), 'slow': any(k in d for k in soft),
        'dash': any(k in d for k in dash), 'shield': any(k in d for k in shield),
        'heal': any(k in d for k in heal), 'execute': any(k in d for k in execute),
        'stealth': any(k in d for k in stealth), 'asbuff': any(k in d for k in asbuff),
    }

def build_champions():
    full = json.load(open(W/'championFull_zh.json'))['data']
    en = json.load(open(W/'data_en_champion.json'))['data']
    parsed = json.load(open(W/'parsed_pages.json'))
    items = parse_items()
    out = {}
    for cid, c in full.items():
        if cid not in parsed: continue
        p = parsed[cid]
        spells = []
        img2slot = {}
        for i, sp in enumerate(c.get('spells', [])):
            slot = SPELL_ORDER[i]
            d = clean_html(sp.get('description',''))
            spells.append({'slot': slot, 'id': sp.get('id',''), 'name': sp.get('name',''),
                           'desc': d, 'image': sp.get('image',{}).get('full',''),
                           'cooldown': sp.get('cooldown',''), 'cost': sp.get('cost',''),
                           'range': sp.get('range',''), 'flags': spell_flags(d)})
            img2slot[sp.get('image',{}).get('full','')] = slot
        # skill order by images
        order = []
        for s in p.get('skill_order', []):
            if s in 'QWER': order.append(s)
        if not order:
            # rebuild from image filenames if parse stored letters? parse_pages already filtered only letters; use raw cache
            doc = __import__('lxml.html', fromlist=['html'])
            tree = doc.parse(str(W/'cache'/f"{p['slug']}_skills.html"))
            for sec in tree.xpath('//section'):
                h = sec.xpath('.//div[contains(@class,"text-sm") and contains(@class,"font-bold")]')
                title = ' '.join(h[0].text_content().strip().split()) if h else ''
                if title == '技能加点':
                    srcs = sec.xpath('.//img[contains(@src,"/spell/")]/@src')
                    for src in srcs:
                        fn = src.split('/spell/')[-1].split('?')[0]
                        if fn in img2slot: order.append(img2slot[fn])
                    break
        priority = p.get('skill_priority') or 'QWE'
        if not order:
            # generic: R at 6/11/16, then priority
            seq = []
            lvl = 1
            for level in range(1, 19):
                if level in (6,11,16): seq.append('R')
                else: seq.append(priority[(level-1) % 3])
            order = seq
        # items
        sections = {s['title']: s['rows'] for s in p.get('item_sections', [])}
        core = []
        seen = set()
        for row in sections.get('核心装备', []):
            ids = tuple(x['id'] for x in row)
            if ids in seen: continue
            seen.add(ids)
            core.append([x['id'] for x in row])
            if len(core) >= 5: break
        boots = [x['id'] for x in (sections.get('鞋子',[[]])[0] if sections.get('鞋子') else [])][:5]
        starter = [x['id'] for x in (sections.get('出门装',[[]])[0] if sections.get('出门装') else [])][:6]
        pool = []
        for row in sections.get('装备', []):
            for x in row:
                if x['id'] not in pool: pool.append(x['id'])
        # archetype
        core_ids = core[0] if core else []
        core_tags = set()
        for iid in core_ids:
            core_tags |= set(items.get(iid, {}).get('tags', []))
        tags = set(c.get('tags', []))
        info = c.get('info', {})
        ad_score = len([i for i in core_ids if set(items.get(i,{}).get('tags',[])) & {'Damage','CriticalStrike','ArmorPenetration','AttackSpeed','LifeSteal'}])
        ap_score = len([i for i in core_ids if set(items.get(i,{}).get('tags',[])) & {'SpellDamage','MagicPenetration'}])
        tank_score = len([i for i in core_ids if set(items.get(i,{}).get('tags',[])) & {'Health','Armor','SpellBlock'}])
        crit_score = len([i for i in core_ids if 'CriticalStrike' in items.get(i,{}).get('tags',[])])
        as_score = len([i for i in core_ids if 'AttackSpeed' in items.get(i,{}).get('tags',[])])
        hard_cc = any(sp['flags']['hard_cc'] for sp in spells)
        mobility = any(sp['flags']['dash'] for sp in spells)
        has_heal_shield = any(sp['flags']['heal'] or sp['flags']['shield'] for sp in spells)
        atkrange = c.get('stats', {}).get('attackrange', 0)
        if ap_score > ad_score: dmg = 'AP'
        elif ad_score > ap_score: dmg = 'AD'
        else: dmg = 'AP' if info.get('magic',0) > info.get('attack',0) else 'AD'
        if 'Support' in tags and not ('Marksman' in tags):
            if 'Assassin' in tags:
                arch = 'ap_assassin' if dmg == 'AP' else 'ad_assassin'; btype = dmg
            elif 'Tank' in tags:
                arch = 'engage_support'; btype = 'SUPPORT'
            elif has_heal_shield or 'heal and shield' in ' '.join(items.get(i,{}).get('desc_zh','') for i in core_ids):
                arch = 'enchanter'; btype = 'SUPPORT'
            elif tank_score >= 2 or hard_cc:
                arch = 'engage_support'; btype = 'SUPPORT'
            else:
                arch = 'mage_support'; btype = 'SUPPORT'
        elif 'Marksman' in tags:
            btype = 'AD'
            if crit_score >= 2: arch = 'crit_adc'
            elif as_score >= 2: arch = 'onhit_adc'
            else: arch = 'caster_adc'
        elif 'Tank' in tags:
            arch = 'engage_tank' if hard_cc else 'tank'; btype = 'TANK'
        elif 'Assassin' in tags:
            arch = 'ap_assassin' if dmg == 'AP' else 'ad_assassin'; btype = dmg
        elif 'Fighter' in tags:
            btype = dmg
            if crit_score >= 2: arch = 'melee_carry'
            elif hard_cc and mobility: arch = 'diver'
            else: arch = 'bruiser'
        elif 'Mage' in tags:
            btype = 'AP'
            if atkrange >= 600: arch = 'poke_mage'
            elif tank_score >= 2: arch = 'battle_mage'
            else: arch = 'burst_mage'
        else:
            arch = 'bruiser'; btype = dmg
        # aliases / pinyin
        name_zh = c.get('name',''); title_zh = c.get('title','')
        name_en = en.get(cid,{}).get('name', cid)
        aliases = []
        for x in [name_zh, title_zh, name_en, cid] + ALIASES.get(cid, []):
            if x and x not in aliases: aliases.append(x)
        pf1, pi1 = pinyin_pair(name_zh); pf2, pi2 = pinyin_pair(title_zh)
        alias_pf = []; alias_pi = []
        for a in aliases:
            x, y = pinyin_pair(a)
            if x: alias_pf.append(x)
            if y: alias_pi.append(y)
        pf_all = ' '.join(dict.fromkeys([pf1, pf2] + alias_pf))
        pi_all = ' '.join(dict.fromkeys([pi1, pi2] + alias_pi))
        out[cid] = {
            'id': cid, 'name_zh': name_zh, 'title_zh': title_zh, 'name_en': name_en,
            'title_en': en.get(cid,{}).get('title',''), 'tags': c.get('tags',[]), 'partype': c.get('partype',''),
            'attackrange': atkrange, 'stats': c.get('stats',{}), 'info': info,
            'spells': spells, 'passive': {'name': c.get('passive',{}).get('name',''), 'desc': clean_html(c.get('passive',{}).get('description',''))},
            'aliases': aliases, 'pinyin_full': pf_all, 'pinyin_initials': pi_all,
            'archetype': arch, 'build_type': btype, 'damage_type': dmg,
            'range_type': 'long' if atkrange >= 550 else ('ranged' if atkrange >= 350 else 'melee'),
            'core': core, 'boots': boots, 'starter': starter, 'pool': pool,
            'skill_order': order, 'skill_priority': priority,
            'tips': extract_tips(cid),
        }
    return out, items

ARCH_LABEL = {
'crit_adc':'暴击射手','onhit_adc':'攻击特效射手','caster_adc':'技能型射手','melee_carry':'近战暴击核心',
'poke_mage':'远程消耗法师','burst_mage':'爆发法师','battle_mage':'法坦/持续输出法师',
'ad_assassin':'AD刺客','ap_assassin':'AP刺客','engage_tank':'开团坦克','tank':'前排坦克',
'bruiser':'战士/重装','diver':'突进战士','enchanter':'软辅/治疗护盾','engage_support':'硬辅/开团','mage_support':'法师辅助'
}
TAG_CN = {'AP':'法强','AD':'攻击力','AS':'攻速','crit':'暴击','onhit':'攻击特效','tank':'坦度',
'sustain':'续航','enchanter':'治疗/护盾','haste':'技能急速','mobility':'移速/位移','poke':'远程消耗',
'execute':'斩杀','utility':'控制/功能','damage':'伤害','gold':'经济','quest':'任务','snowball':'雪球'}

THEMES = {
'haste': {'name':'技能急速循环','tags':{'haste'},'why':'三件都压缩技能CD，让核心技能转得更快，适合持续拉扯和多次进场。'},
'crit': {'name':'暴击平A流','tags':{'crit'},'why':'围绕暴击率/暴击伤害叠加，成型后普攻和技能暴击都能吃满收益。'},
'onhit': {'name':'攻击特效流','tags':{'onhit','AS'},'why':'攻速与攻击特效互相放大，适合持续站桩输出。'},
'ap': {'name':'法强爆发流','tags':{'AP'},'why':'法强与技能伤害叠加，配合短CD技能打爆发。'},
'ad': {'name':'攻击力爆发流','tags':{'AD'},'why':'攻击力与技能加成叠加，提升单套爆发的上限。'},
'tank': {'name':'前排坦度流','tags':{'tank'},'why':'生命/双抗/护盾叠加，提升开团和抗压容错。'},
'sustain': {'name':'续航容错流','tags':{'sustain','enchanter'},'why':'治疗/护盾/吸血叠加，适合长时间拉锯。'},
'execute': {'name':'残血收割流','tags':{'execute'},'why':'斩杀与残血增益叠加，专门扩大收割雪球。'},
'poke': {'name':'远程消耗流','tags':{'poke'},'why':'射程/飞弹/消耗效果叠加，团战前先压低血线。'},
}
ARCH_THEMES = {
'crit_adc':['crit','onhit','sustain'], 'onhit_adc':['onhit','crit','sustain'], 'caster_adc':['ad','haste','execute'],
'melee_carry':['crit','sustain','haste'], 'poke_mage':['poke','ap','haste'], 'burst_mage':['ap','execute','haste'],
'battle_mage':['ap','tank','sustain'], 'ad_assassin':['ad','execute','haste'], 'ap_assassin':['ap','execute','haste'],
'engage_tank':['tank','sustain','haste'], 'tank':['tank','sustain','haste'], 'bruiser':['ad','tank','sustain'],
'diver':['ad','execute','sustain'], 'enchanter':['sustain','haste','tank'], 'engage_support':['tank','sustain','haste'],
'mage_support':['ap','poke','haste'],
}

POWER_OVERRIDES = {
'Kayle':['6级：获得远程形态，开始能安全输出','11级：火焰波提升清线与团战AOE','16级：永久远程+高攻速，进入大核期'],
'Kassadin':['6级：R成型，机动性和进场能力质变','11级：R伤害/频率提升，开始秒后排','16级：R高伤短CD，后期最强'],
'Vladimir':['1件套：法强/吸血成型，能持续换血','2件套：团战续航质变','3件套：后排爆发与生存兼备'],
'Smolder':['1件套：Q开始稳定叠层','2件套：Q进化，射程/伤害质变','3件套：后期接管比赛'],
'AurelionSol':['1件套：星尘开始叠层','2件套：黑洞/规模成型','3件套：团战大核'],
'Veigar':['1件套：Q叠层，法强开始滚雪球','2件套：单套爆发可秒脆皮','3件套：后期法强怪物'],
'Nasus':['1件套：Q叠层+前排装','2件套：单挑/抗压成型','3件套：后排噩梦'],
'Senna':['1件套：灵魂/射程开始成长','2件套：暴击/治疗成型','3件套：后期射程压制'],
'Chogath':['1件套：R层数开始堆叠','2件套：血量/抗性成型','3件套：前排巨兽'],
'Sion':['1件套：W层数/血量成型','2件套：开团与抗压兼备','3件套：后排搅局'],
'Thresh':['1件套：灵魂/护甲成长','2件套：坦度与控制成型','3件套：团战先手/保排'],
'Yuumi':['1件套：奶盾量成型','2件套：团战附着价值质变','3件套：后期保核'],
'Jinx':['1件套：暴击/攻速起步','2件套：飓风+无尽进入团战强势','3件套：远程炮台接管'],
'Kaisa':['1件套：进化Q','2件套：进化E，机动/输出质变','3件套：后排杀手'],
'Vayne':['1件套：攻速/真实伤害起步','2件套：单挑强势','3件套：前排杀手'],
'Azir':['1件套：攻速/法强起步','2件套：沙兵输出成型','3件套：团战持续输出'],
'Ryze':['1件套：蓝量/法强成型','2件套：技能循环质变','3件套：持续输出'],
'Cassiopeia':['1件套：毒/法强成型','2件套：持续输出质变','3件套：近身爆发'],
}

ENGAGE = {
'engage_tank':'你是主开团点：等队友能跟伤害、敌方关键位移/闪现交掉后再R/闪现开；不要一个人越过前排。',
'tank':'以反手为主：敌方突进进来后用控制拆火；己方先开到再跟进，不要盲目追后排。',
'ad_assassin':'后手侧翼：等敌方控制/护盾/治疗交掉，再从侧翼或草丛切入后排；没有退路时不先手。',
'ap_assassin':'后手进场：等敌方关键控制/保命技能交掉，利用位移贴近后排；技能空窗期先退。',
'crit_adc':'站在前排射程边缘，先打最近目标；等敌方突进/控制交掉后再向前，不要第一个进场。',
'onhit_adc':'站桩输出但别吃第一波控制：等敌方先手交掉再压上，优先打能打到的前排。',
'caster_adc':'先用技能消耗，等敌方血量/关键技能压下后再all-in；被贴脸先交保命。',
'melee_carry':'等队友先吃控制，再利用位移/风墙进场；没有保命技能时不先手。',
'poke_mage':'先用技能消耗，等敌方血量/关键技能压下后再进场；被贴脸先交保命。',
'burst_mage':'等控制命中或敌方交掉保命技能再进场；一套打完立刻后撤等CD。',
'battle_mage':'在中前排持续输出，等敌方第一波爆发交掉后压上；注意保持血量。',
'bruiser':'二进场：等敌方第一波控制/爆发交掉后切入后排；有R/闪现再进。',
'diver':'等队友跟上再突进后排；不要脱离队伍单独追人。',
'enchanter':'保持后排，等敌方突进后再给盾/奶/大招；不要为了奶人走到前排。',
'engage_support':'等队友能跟伤害再开团；用控制拆火或先手，不要单独越塔。',
'mage_support':'以控制/消耗为主，等队友先手；不要单独开团。',
}

CURATED_COMBOS = {
'Ahri':[('E→Q→W→R','魅惑起手，Q双段+W狐火，R追击/调整位置。'),('R→E→Q→W','团战用R拉近或绕后，E命中后接Q/W。')],
'Garen':[('Q→E→W→R','Q加速沉默，E旋转，W抗伤，R处决。'),('E→Q→W→R','先E贴脸再Q沉默，适合追击。')],
'Malphite':[('R→E→Q→W','R击飞开团，E减攻速，Q减速，W补伤害。'),('Q→E→R','先用Q消耗，E近身，R留作反手/追击。')],
'LeeSin':[('Q→Q→E→R','Q命中后二段贴近，E减速，R踢回。'),('W→R→Q→Q','摸眼/位移接近，R踢回，Q收尾。')],
'Yasuo':[('E→Q→AA→Q→R','E小兵接近，Q击飞后接R。'),('Q3→E→R','Q3吹起，E调整位置，R落地。')],
'Yone':[('Q3→R→W→E','Q3击飞接R，W补盾/伤害，E追击。'),('E→Q→R','E进场，Q叠层，R收割。')],
'Riven':[('E→Q→W→Q→Q→R','E接近，Q连段穿插W，R收尾。')],
'Zed':[('W→E→Q→R→AA','W影子减速，E/Q消耗，R进场收割。'),('R→W→E→Q','R进场，W位移，E/Q打爆发。')],
'Katarina':[('E→W→Q→R','E进场，W加速，Q标记，R旋转。')],
'Darius':[('E→Q→W→AA→R','E拉回，Q外圈，W减速，平A叠流血，R处决。')],
'Jinx':[('AA→Q→W→E→R','平A起手，Q切换火箭，W减速，E封路，R收割。')],
'Caitlyn':[('E→W→Q→R','E拉开距离，W夹子，Q消耗，R狙击。')],
'Ezreal':[('Q→W→E→R','Q消耗，W挂标记，E调整位置，R全图收尾。')],
'Lux':[('Q→E→R→W','Q定身，E减速，R爆发，W护盾。')],
'Morgana':[('Q→W→R→E','Q定身，W灼烧，R团控，E免控。')],
'Thresh':[('Q→E→R→W','Q钩中，E摆回，R牢笼，W救人。')],
'Leona':[('E→Q→R→W','E突进，Q眩晕，R开团，W抗伤。')],
'Nautilus':[('Q→R→E→W','Q钩中，R击飞，E减速，W护盾。')],
'Blitzcrank':[('Q→E→R→W','Q钩中，E击飞，R沉默，W加速。')],
'Amumu':[('Q→R→E→W','Q绷带，R大范围眩晕，E减攻速，W抗伤。')],
'Soraka':[('E→Q→W→R','E沉默/星蚀，Q消耗，W奶，R团奶。')],
'Sona':[('Q→E→W→R','Q消耗，E加速，W奶盾，R团控。')],
'Yuumi':[('Q→E→R→W','Q消耗，E加速/奶，R团控，W附身。')],
'Kaisa':[('W→R→Q→E','W挂被动，R进场，Q爆发，E隐身调整。')],
'Samira':[('E→Q→W→R','E进场，Q叠评分，W挡技能，R收割。')],
'Vayne':[('Q→AA→E→R','Q翻滚，平A，E钉墙，R隐身。')],
'Twitch':[('Q→R→W→E','Q隐身接近，R开大，W减速，E毒爆。')],
'Kogmaw':[('E→Q→W→R','E减速，Q减抗，W射程，R消耗。')],
'Senna':[('Q→W→E→R','Q穿透治疗，W定身，E隐身，R全图。')],
'Seraphine':[('E→Q→W→R','E减速/定身，Q伤害，W护盾，R团控。')],
'Pyke':[('E→Q→R→W','E位移，Q钩，R处决，W隐身。')],
'Akali':[('E→Q→W→R','E标记，Q减速，W隐身，R进场。')],
'Sylas':[('E→Q→W→R','E突进/控制，Q伤害，W奶，R偷大。')],
'Qiyana':[('E→Q→W→R','E贴近，Q伤害，W换元素，R团控。')],
'Talon':[('E→W→Q→R','E翻墙，W减速，Q近身，R隐身收割。')],
'Fizz':[('E→Q→W→R','E躲避，Q突进，W强化，R鲨鱼。')],
'Kassadin':[('R→E→Q→W','R进场，E减速，Q沉默，W回蓝。')],
'Vladimir':[('E→Q→W→R','E蓄力，Q吸血，W保命，R增伤。')],
'Ryze':[('E→Q→W→R','E扩散，Q刷新，W定身，R调整。')],
'Cassiopeia':[('Q→E→W→R','Q命中，E连吐，W减速，R石化。')],
'Anivia':[('Q→E→R→W','Q眩晕，E双倍，R风暴，W封路。')],
'Orianna':[('Q→W→E→R','Q球，W减速，E护盾，R团控。')],
'Syndra':[('Q→E→W→R','Q放球，E推晕，W砸，R爆发。')],
'Veigar':[('E→W→Q→R','E框住，W砸，Q补刀，R处决。')],
'Zoe':[('E→Q→R→W','E睡眠，Q拉远，R调整，W拾取。')],
'Xerath':[('E→Q→W→R','E眩晕，Q/ W消耗，R远程炮击。')],
'VelKoz':[('E→Q→W→R','E击飞，Q分裂，W叠加，R激光。')],
'Ziggs':[('E→Q→W→R','E地雷，Q弹跳，W位移，R核弹。')],
'Brand':[('E→Q→W→R','E点燃，Q眩晕，W爆发，R弹射。')],
'Malzahar':[('E→W→Q→R','E持续伤害，W虫子，Q沉默，R压制。')],
'Swain':[('E→W→Q→R','E定身，W减速，Q吸血，R团战。')],
'Lucian':[('E→Q→AA→W→R','E滑步，Q穿透，平A，W标记，R扫射。')],
'Graves':[('Q→W→E→R','Q爆发，W烟雾，E装弹，R收尾。')],
'MissFortune':[('E→Q→W→R','E减速，Q弹射，W攻速，R扫射。')],
'Sivir':[('Q→W→E→R','Q回旋，W弹射，E护盾，R加速。')],
'Tristana':[('W→E→Q→R','W跳脸，E炸弹，Q攻速，R推走。')],
'Xayah':[('Q→E→W→R','Q羽毛，E倒钩，W攻速，R保命。')],
'Zeri':[('E→Q→W→R','E穿墙，Q连射，W减速，R团战。')],
'Aphelios':[('Q→W→E→R','按武器组决定Q/W顺序；E减速，R收尾。')],
'Draven':[('Q→E→W→R','Q斧头，E打断，W加速，R收割。')],
'Jhin':[('Q→W→E→R','Q弹射，W定身，E减速，R狙击。')],
'Varus':[('E→Q→W→R','E减速，Q蓄力，W百分比，R团控。')],
'Ashe':[('W→Q→E→R','W消耗，Q攻速，E视野，R开团。')],
'Kalista':[('Q→E→W→R','Q穿刺，E拔矛，W视野，R救辅助。')],
'Nilah':[('E→Q→W→R','E进场，Q伤害，W闪避，R团控。')],
'Smolder':[('Q→W→E→R','Q叠层，W灼烧，E位移，R收割。')],
}

def compat(c, a, items):
    name = a['name_zh']
    core = c.get('core',[[]])[0] if c.get('core') else []
    pool = set(c.get('pool',[]))
    allids = set(core) | pool
    def has_tag(tag): return any(tag in items.get(i,{}).get('tags',[]) for i in allids)
    def has_item(iid): return iid in allids
    has_crit = has_tag('CriticalStrike')
    has_as = has_tag('AttackSpeed') or any(sp['flags']['asbuff'] for sp in c['spells'])
    has_ad = any(set(items.get(i,{}).get('tags',[])) & {'Damage','ArmorPenetration'} for i in core)
    has_ap = any(set(items.get(i,{}).get('tags',[])) & {'SpellDamage','MagicPenetration'} for i in core)
    ranged = c['range_type'] != 'melee'
    tanky = c['build_type'] == 'TANK' or c['archetype'] in ('tank','engage_tank','bruiser','diver')
    support = c['build_type'] == 'SUPPORT' or c['archetype'] in ('enchanter','engage_support','mage_support')
    spin = any(('旋转' in sp['desc'] or 'spin' in sp['desc'].lower()) for sp in c['spells']) or c['id'] in {'Garen','Wukong','Katarina','Tryndamere','Riven','Kayn'}
    if name == '旋转至胜': return spin
    if name == '物理转魔法': return has_ad
    if name == '纯粹主义者 - 术师': return has_as
    if name in ('大腕','珠光护手','升级：无尽之刃','会心防御','关键暴击','灵魂虹吸','珠光手镯','易损','双发快射','会心治疗'):
        return has_crit
    if name == '升级：收集者': return has_item(6676)
    if name == '升级：中娅': return has_item(3157)
    if name == '升级：风暴狂涌': return has_item(4646)
    if name == '升级：献祭': return has_item(3068) or has_item(6664)
    if name == '升级：焚天': return has_item(6610)
    if name == '升级：贪欲九头蛇': return has_item(3074)
    if name == '升级：死亡之舞': return has_item(6333)
    if name == '沃格勒特的巫师帽': return has_ap and (has_item(3089) or has_item(3157))
    if name in ('万用瞄准镜','更万用的瞄准镜','最万用的瞄准镜','远射天资'): return ranged
    if name in ('双刀流','台风','点亮他们！','战争交响乐'):
        return has_as or has_tag('OnHit')
    if name in ('坦克引擎','星界躯体','歌利亚巨人'):
        return tanky
    if name in ('天音爆','全心为你','喂呜喂呜','风语者的祝福','至高天诺言','由心及物'):
        return support
    if name == '死亡之环': return support or has_tag('LifeSteal') or has_tag('SpellVamp')
    if name == '邦！': return c['build_type'] in ('AD','TANK') or c['archetype'] in ('bruiser','diver','melee_carry')
    if name == '利刃华尔兹': return c['build_type'] == 'AD' or c['archetype'] in ('bruiser','diver','melee_carry')
    return True

def make_combos(c):
    cid = c['id']; spells = {s['slot']: s for s in c['spells']}
    seqs = CURATED_COMBOS.get(cid)
    out = []
    if seqs:
        for seq, note in seqs[:3]:
            parts = []
            for tok in seq.split('→'):
                tok = tok.strip()
                if tok in spells: parts.append(f"{tok} {spells[tok]['name']}")
                elif tok == 'AA': parts.append('平A')
                elif tok == 'Flash': parts.append('闪现')
                else: parts.append(tok)
            out.append({'name':'推荐连招' if not out else '实战变式', 'sequence':' → '.join(parts), 'note':note})
        if len(out) == 1:
            alt = ['Q','W','E','AA','R'] if c['archetype'] in ('crit_adc','onhit_adc','caster_adc') else ['R','E','Q','W']
            parts2 = ['平A' if x == 'AA' else f"{x} {spells[x]['name']}" for x in alt if x in spells]
            out.append({'name':'团战变式','sequence':' → '.join(parts2),'note':'等队友先手或敌方关键控制交掉后再进场；保留一个保命/位移技能。'})
        return out
    # generated fallback
    def names(letters): return ' → '.join(f"{x} {spells[x]['name']}" for x in letters if x in spells)
    arch = c['archetype']
    if arch in ('crit_adc','onhit_adc','caster_adc'):
        base = ['AA','Q','W','E','R']
    elif arch in ('engage_tank','tank'):
        base = ['R','E','Q','W']
    elif arch in ('enchanter','engage_support','mage_support'):
        base = ['E','W','Q','R']
    elif arch in ('ad_assassin','ap_assassin','diver','bruiser','melee_carry'):
        base = ['E','Q','W','R']
    else:
        base = ['E','Q','W','R']
    parts = ['平A' if x == 'AA' else f"{x} {spells[x]['name']}" for x in base if x in spells]
    out.append({'name':'基础连招','sequence':' → '.join(parts),'note':'按距离和CD调整起手；先保证控制/位移命中，再交主要伤害。'})
    # teamfight variant: ult first for tanks, else same with hold escape
    if arch in ('engage_tank','tank'):
        alt = ['R','Q','E','W']
    elif arch in ('crit_adc','onhit_adc','caster_adc'):
        alt = ['Q','W','E','AA','R']
    else:
        alt = ['E','Q','R','W']
    parts2 = ['平A' if x == 'AA' else f"{x} {spells[x]['name']}" for x in alt if x in spells]
    out.append({'name':'团战变式','sequence':' → '.join(parts2),'note':'等队友先手或敌方关键控制交掉后再进场；保留一个保命/位移技能。'})
    return out

def make_power_spikes(c):
    base = ['3级：第一个海克斯，开始有基础战斗力','6级：大招解锁，第一次质变','11级：第二个海克斯+大招升级','15级：第四个海克斯，进入后期']
    if c['id'] in POWER_OVERRIDES:
        return POWER_OVERRIDES[c['id']]
    arch = c['archetype']
    tail = {
    'crit_adc':['1件套：暴击装起步','2件套：无尽/飓风成型，团战强势','3件套：远程炮台接管'],
    'onhit_adc':['1件套：破败/羊刀起步','2件套：攻速/特效成型','3件套：持续输出峰值'],
    'caster_adc':['1件套：魔宗/三相成型','2件套：技能循环质变','3件套：爆发峰值'],
    'melee_carry':['1件套：暴击装起步','2件套：单挑/团战强势','3件套：后排杀手'],
    'poke_mage':['1件套：蓝量/法强成型','2件套：消耗质变','3件套：远程压制'],
    'burst_mage':['1件套：法强/穿透起步','2件套：单套爆发质变','3件套：秒脆皮'],
    'battle_mage':['1件套：持续输出成型','2件套：坦度/吸血质变','3件套：团战法坦'],
    'ad_assassin':['1件套：穿甲/攻击力起步','2件套：秒脆皮峰值','3件套：团战收割'],
    'ap_assassin':['1件套：法强/穿透起步','2件套：爆发峰值','3件套：后排噩梦'],
    'engage_tank':['1件防装：可以接团','2件套：开团/抗压峰值','3件套：团战前排'],
    'tank':['1件防装：成型','2件套：团战最稳','3件套：抗压峰值'],
    'bruiser':['1件套：黑切/三相起步','2件套：单带/团战强势','3件套：切后排'],
    'diver':['1件套：攻击力/穿甲起步','2件套：进场爆发','3件套：团战收割'],
    'enchanter':['1件套：奶盾量成型','2件套：团战保核质变','3件套：后期最强'],
    'engage_support':['1件套：鸟盾/基克成型','2件套：开团/抗压','3件套：团战前排'],
    'mage_support':['1件套：消耗成型','2件套：爆发/控制','3件套：团战'],
    }[arch]
    return base[:2] + tail

def make_engage(c):
    base = ENGAGE[c['archetype']]
    ult = next((s for s in c['spells'] if s['slot']=='R'), None)
    if ult and ult['flags']['hard_cc'] and c['archetype'] in ('engage_tank','engage_support','tank'):
        base += f" 你的R（{ult['name']}）是核心开团/反手技能，尽量等队友位置到位再交。"
    return base

def make_reason(c, a):
    tags = [TAG_CN.get(t,t) for t in a['tags'] if t in TAG_CN]
    tags = list(dict.fromkeys(tags))[:4]
    label = ARCH_LABEL.get(c['archetype'], c['archetype'])
    if tags:
        return f"提供{'/'.join(tags)}，直接补强{label}的核心需求。"
    return f"泛用强化件，作为{label}体系的功能/容错补充。"

SET_DEFS = {
'bread': ('面包三件套', ['面包和黄油','面包和奶酪','面包和果酱'],
          '三件集齐触发“面包三明治”：额外250终极技能急速，每个基础技能再+50技能急速。'),
'haste': ('技能急速三件套', ['循环往复','无限循环往复','终极循环往复'],
          '三件都提供技能急速/终极急速，技能循环拉满；适合靠技能反复进场。'),
'ap': ('法系爆发三件套', ['大法师','魔法飞弹','尤里卡'],
       '大法师返还CD、魔法飞弹补真伤、尤里卡把法强转成技能急速，法系越打越快。'),
'crit': ('暴击三件套', ['珠光护手','暴击律动','升级：无尽之刃'],
         '技能可暴击+暴击叠攻速+无尽升级，暴击收益互相放大。'),
'onhit': ('攻速特效三件套', ['双生火焰','灵巧','台风'],
          '攻速、额外飞弹和攻击特效叠加，站桩输出上限高。'),
'tank': ('前排三件套', ['巨像的勇气','蛋白粉奶昔','歌利亚巨人'],
         '控制触发护盾、治疗护盾强度随双抗成长、歌利亚给生命和适应之力，越肉越难杀。'),
'support': ('治疗护盾三件套', ['急救用具','信念者的强化','活力焕发'],
            '治疗/护盾强度叠加，并让治疗附带额外收益，适合保核。'),
'stats': ('属性三件套', ['属性！','属性叠属性！','属性叠属性叠属性！'],
          '三件都给属性铁砧，越叠越全面，属于通用成长套。'),
'snowball': ('雪球三件套', ['史上最大雪球','雪球扭蛋机','神圣雪球'],
             '三件都强化雪球/标记，开团和追击能力大幅提升。'),
}
ARCH_SETS = {
'crit_adc':['crit','onhit','haste','bread'], 'onhit_adc':['onhit','crit','haste','bread'],
'caster_adc':['haste','crit','stats','bread'], 'melee_carry':['crit','onhit','haste','bread'],
'poke_mage':['ap','haste','stats','bread'], 'burst_mage':['ap','haste','stats','bread'],
'battle_mage':['ap','tank','support','bread'], 'ad_assassin':['haste','crit','stats','bread'],
'ap_assassin':['ap','haste','stats','bread'], 'engage_tank':['tank','support','haste','bread'],
'tank':['tank','support','stats','bread'], 'bruiser':['tank','haste','crit','bread'],
'diver':['haste','crit','stats','bread'], 'enchanter':['support','haste','stats','bread'],
'engage_support':['tank','support','haste','bread'], 'mage_support':['ap','haste','support','bread'],
}

def make_packages(c, recs, aug_by_name):
    allrecs = sum([recs[t] for t in ('Silver','Gold','Prismatic')], [])
    top_names = {a['name_zh'] for a in allrecs}
    top10 = {a['name_zh'] for t in recs for a in recs[t][:10]}
    out = []
    for key in ARCH_SETS.get(c['archetype'], ['haste','stats','bread']):
        if key not in SET_DEFS: continue
        name, names, why = SET_DEFS[key]
        pieces = [aug_by_name.get(n) for n in names]
        if any(p is None for p in pieces): continue
        inpool = [p for p in pieces if p['name_zh'] in top_names]
        intop = [p for p in pieces if p['name_zh'] in top10]
        if len(inpool) >= 3:
            fit = '本英雄推荐池中三件都出现，优先级最高。'
        elif len(inpool) == 2:
            fit = '本英雄推荐池中出现2件，可追第3件。'
        elif len(inpool) == 1:
            fit = '本英雄推荐池中只出现1件，不建议硬追。'
        else:
            fit = '本英雄推荐池未出现，仅作全局成套参考。'
        out.append({'name':name, 'augments':[{'name':p['name_zh'],'tier':p['tier'],'id':p['id']} for p in pieces],
                    'why':why, 'fit':fit, 'in_pool':len(inpool), 'in_top10':[p['name_zh'] for p in intop],
                    'condition':'属于可遇不可求的成套联动；优先拿已出现的部件，不要为了凑套放弃当前强势海克斯。'})
    out.sort(key=lambda x:(-x['in_pool'], -len(x['in_top10'])))
    out = [x for x in out if x['in_pool'] >= 1]
    # guarantee at least two packages: add universal fallback sets with honest fit note
    if len(out) < 2:
        for key in ('stats','snowball','haste'):
            name, names, why = SET_DEFS[key]
            if any(x['name'] == name for x in out): continue
            pieces = [aug_by_name.get(n) for n in names]
            if any(p is None for p in pieces): continue
            inpool = [p for p in pieces if p['name_zh'] in top_names]
            out.append({'name':name, 'augments':[{'name':p['name_zh'],'tier':p['tier'],'id':p['id']} for p in pieces],
                        'why':why, 'fit':'本英雄推荐池中未出现，仅作全局成套参考。' if not inpool else f'本英雄推荐池中出现{len(inpool)}件。',
                        'in_pool':len(inpool), 'in_top10':[p['name_zh'] for p in pieces if p['name_zh'] in top10],
                        'condition':'属于可遇不可求的成套联动；优先拿已出现的部件，不要为了凑套放弃当前强势海克斯。'})
            if len(out) >= 2: break
    return out[:3]

def make_builds(c, items):
    def nm(i): return items.get(i,{}).get('name_zh',str(i))
    core = []
    for seq in c['core'][:3]:
        core.append({'items':[nm(i) for i in seq], 'ids':seq})
    boots = [nm(i) for i in c['boots'][:4]]
    starter = [nm(i) for i in c['starter'][:3]]
    pool = set(c['pool'])
    BT = c['build_type']
    CAND = {
    'vs_tank': {'AP':[3135,6653,2503], 'AD':[3036,3033,3071,3153], 'TANK':[3068,3075,3110], 'SUPPORT':[3075,3165,3102]},
    'vs_ad': {'AP':[3157,2420], 'AD':[3026,6333], 'TANK':[3143,3075,3110], 'SUPPORT':[3190,3001,3047]},
    'vs_ap': {'AP':[3102,2504], 'AD':[3156,3111], 'TANK':[2504,3065,4401], 'SUPPORT':[3190,3001,3111]},
    'vs_poke': {'AP':[3152,3116], 'AD':[3142,3742], 'TANK':[3190,3001,3742], 'SUPPORT':[3190,3001]},
    }
    branches = {}
    for key, cands in CAND.items():
        picks = [i for i in cands.get(BT,[]) if i in pool][:2]
        if len(picks) < 2:
            for i in cands.get(BT,[]):
                if i not in picks: picks.append(i)
                if len(picks) == 2: break
        picks = [i for i in picks if i in items and not items[i]['boots']]
        branches[key] = {
            'title': {'vs_tank':'对面肉多','vs_ad':'对面AD多','vs_ap':'对面AP多','vs_poke':'对面长手多'}[key],
            'items':[nm(i) for i in picks],
            'boots': '铁板靴' if key=='vs_ad' and 3047 in items else ('水银之靴' if key=='vs_ap' and 3111 in items else None),
            'note': {
                'vs_tank': ('不追穿透，优先减疗/保排：莫雷洛秘典或荆棘之甲。' if BT=='SUPPORT' else ('日炎/反甲/冰心，靠持续灼烧和减疗磨前排。' if BT=='TANK' else '优先百分比/穿透与减疗；不要只堆固定穿透。')),
                'vs_ad': ('优先鸟盾/基克/铁板靴，活着才能保核。' if BT=='SUPPORT' else ('补护甲/减伤；AP位可考虑中娅，前排补兰顿/反甲。' if BT!='TANK' else '兰顿/反甲/冰心，优先减攻速和暴击伤害。')),
                'vs_ap': ('优先鸟盾/薄暮法袍/水银靴，帮队友吃第一波控制。' if BT=='SUPPORT' else ('补魔抗/免控；AD位可考虑大饮魔刀，前排补败魔/自然之力。' if BT!='TANK' else '败魔/自然之力/水银靴，先扛住第一轮法术爆发。')),
                'vs_poke': ('鸟盾/移速装，别站在正面吃消耗；等雪球或闪现再开。' if BT=='SUPPORT' else '补移速/开团/护盾；不要站在正面吃消耗，等雪球或闪现再开。'),
            }[key]
        }
    return {'starter':starter,'boots':boots,'core':core,'branches':branches}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists(): DB_PATH.unlink()
    augs = build_augment_master()
    # manual descriptions for missing verified ones
    extra_desc = {
        '升级：焚天': '将焚天对每个目标的冷却时间缩短，并治疗你已损失生命值；获得金币。',
        '升级：贪欲九头蛇': '技能命中触发顺劈，并提升贪欲九头蛇的生命偷取；获得金币。',
        '快步': '使用指定技能时，朝鼠标指针方向冲刺。',
        '雪球扭蛋机': '雪球获得技能急速；命中敌人时随机对自己施放增益召唤师技能、对目标施放减益召唤师技能，二段再次触发增益。',
    }
    for a in augs:
        if a['name_zh'] in extra_desc: a['desc_zh'] = extra_desc[a['name_zh']]
    # drop unverified
    augs = [a for a in augs if a['desc_zh'] and a['name_zh'] != '卡皮巴拉空投']
    by_name = {a['name_zh']: a for a in augs}
    champs, items = build_champions()
    # fix archetypes for fighter/tank ordering
    for c in champs.values():
        tags = c['tags']
        if tags and tags[0] == 'Tank' and 'Marksman' not in tags and 'Support' not in tags:
            c['archetype'] = 'engage_tank' if any(s['flags']['hard_cc'] for s in c['spells']) else 'tank'
            c['build_type'] = 'TANK'
        elif 'Fighter' in tags and 'Marksman' not in tags and 'Support' not in tags and tags[0] != 'Tank':
            c['build_type'] = c['damage_type']
            if any(s['flags']['hard_cc'] for s in c['spells']) and any(s['flags']['dash'] for s in c['spells']):
                c['archetype'] = 'diver'
            else:
                c['archetype'] = 'bruiser'
    # tanks with clearly AP/AD core items use that branch pool
    for c in champs.values():
        if c['build_type'] == 'TANK':
            core = c['core'][0] if c['core'] else []
            ap = len([i for i in core if set(items.get(i,{}).get('tags',[])) & {'SpellDamage','MagicPenetration'}])
            ad = len([i for i in core if set(items.get(i,{}).get('tags',[])) & {'Damage','ArmorPenetration','CriticalStrike'}])
            tank = len([i for i in core if set(items.get(i,{}).get('tags',[])) & {'Health','Armor','SpellBlock'}])
            if ap >= 2 and tank < 2: c['build_type'] = 'AP'
            elif ad >= 2 and tank < 2: c['build_type'] = 'AD'
    # skill order validation
    for c in champs.values():
        if len(c['skill_order']) != 18 or len(set(c['skill_order'])) < 3:
            pri = c['skill_priority'] if len(set(c['skill_priority'])) >= 2 else 'QWE'
            seq = []
            for level in range(1, 19):
                if level in (6, 11, 16): seq.append('R')
                else: seq.append(pri[(level-1) % 3])
            c['skill_order'] = seq
    # recommendations
    parsed = json.load(open(W/'parsed_pages.json'))
    recs_by_champ = {}
    for cid, c in champs.items():
        p = parsed[cid]
        recs = {'Silver':[], 'Gold':[], 'Prismatic':[]}
        for n in p['augment_order']:
            a = by_name.get(n)
            if not a or a['disabled'] or not compat(c, a, items): continue
            if len(recs[a['tier']]) < 10:
                recs[a['tier']].append(a)
        # fill shortfalls from global frequency of same tier
        if any(len(v) < 10 for v in recs.values()):
            freq = {}
            for cc in parsed.values():
                for n in cc['augment_order']:
                    a = by_name.get(n)
                    if a and not a['disabled']:
                        freq[a['id']] = freq.get(a['id'],0)+1
            for tier in recs:
                if len(recs[tier]) >= 10: continue
                existing = {a['id'] for a in recs[tier]}
                for a in sorted([x for x in augs if x['tier']==tier and not x['disabled'] and compat(c, x, items)], key=lambda x:-freq.get(x['id'],0)):
                    if a['id'] not in existing:
                        recs[tier].append(a); existing.add(a['id'])
                    if len(recs[tier])==10: break
        recs_by_champ[cid] = recs
    # DB
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript('''
    CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE champions(id TEXT PRIMARY KEY, name_zh TEXT, title_zh TEXT, name_en TEXT, title_en TEXT,
      tags TEXT, partype TEXT, attackrange REAL, stats_json TEXT, spells_json TEXT, passive_json TEXT,
      aliases TEXT, pinyin_full TEXT, pinyin_initials TEXT, archetype TEXT, archetype_label TEXT,
      damage_type TEXT, build_type TEXT, range_type TEXT);
    CREATE TABLE augments(id TEXT PRIMARY KEY, name_zh TEXT, name_en TEXT, tier TEXT, desc_zh TEXT, desc_en TEXT,
      tags TEXT, disabled INTEGER, icon TEXT);
    CREATE TABLE champion_augments(champion_id TEXT, augment_id TEXT, tier TEXT, rank INTEGER, reason TEXT,
      PRIMARY KEY(champion_id, augment_id));
    CREATE TABLE items(id INTEGER PRIMARY KEY, name_zh TEXT, name_en TEXT, plaintext TEXT, desc_zh TEXT,
      tags TEXT, stats_json TEXT, gold INTEGER, boots INTEGER);
    CREATE TABLE champion_items(champion_id TEXT, item_id INTEGER, section TEXT, rank INTEGER,
      PRIMARY KEY(champion_id, item_id, section));
    CREATE TABLE champion_builds(champion_id TEXT, kind TEXT, rank INTEGER, items_json TEXT,
      PRIMARY KEY(champion_id, kind, rank));
    CREATE TABLE champion_skills(champion_id TEXT PRIMARY KEY, order_json TEXT, priority TEXT);
    CREATE TABLE champion_tips(champion_id TEXT PRIMARY KEY, tips_json TEXT);
    CREATE TABLE champion_guides(champion_id TEXT PRIMARY KEY, payload_json TEXT);
    CREATE INDEX idx_ca_champ ON champion_augments(champion_id, tier, rank);
    CREATE INDEX idx_ci_champ ON champion_items(champion_id);
    ''')
    cur.executemany('INSERT INTO meta VALUES(?,?)', [
        ('patch', PATCH), ('ddragon', DDRAGON), ('built_at', datetime.now(timezone.utc).isoformat()),
        ('source_opgg', 'https://op.gg/lol/modes/aram-mayhem'),
        ('source_wiki', 'https://wiki.leagueoflegends.com/en-us/ARAM:_Mayhem/Augments'),
        ('source_ddragon', f'https://ddragon.leagueoflegends.com/cdn/{DDRAGON}/data/zh_CN/'),
        ('source_cdragon', 'https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/zh_cn/v1/'),
        ('champion_count', str(len(champs))), ('augment_count', str(len(augs))),
    ])
    for a in augs:
        cur.execute('INSERT OR REPLACE INTO augments VALUES(?,?,?,?,?,?,?,?,?)', (
            a['id'], a['name_zh'], a['name_en'], a['tier'], a['desc_zh'], a['desc_en'],
            json.dumps(a['tags'],ensure_ascii=False), int(a['disabled']), a['icon']))
    for iid, it in items.items():
        cur.execute('INSERT OR REPLACE INTO items VALUES(?,?,?,?,?,?,?,?,?)', (
            iid, it['name_zh'], it['name_en'], it['plaintext'], it['desc_zh'],
            json.dumps(it['tags'],ensure_ascii=False), json.dumps(it['stats'],ensure_ascii=False),
            it['gold'], int(it['boots'])))
    for cid, c in champs.items():
        cur.execute('INSERT INTO champions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            cid, c['name_zh'], c['title_zh'], c['name_en'], c['title_en'], json.dumps(c['tags'],ensure_ascii=False),
            c['partype'], c['attackrange'], json.dumps(c['stats'],ensure_ascii=False), json.dumps(c['spells'],ensure_ascii=False),
            json.dumps(c['passive'],ensure_ascii=False), json.dumps(c['aliases'],ensure_ascii=False),
            c['pinyin_full'], c['pinyin_initials'], c['archetype'], ARCH_LABEL.get(c['archetype'],c['archetype']),
            c['damage_type'], c['build_type'], c['range_type']))
        recs = recs_by_champ[cid]
        for tier in ('Silver','Gold','Prismatic'):
            for rank, a in enumerate(recs[tier],1):
                cur.execute('INSERT INTO champion_augments VALUES(?,?,?,?,?)', (cid, a['id'], tier, rank, make_reason(c,a)))
        # items
        for kind, seqs in [('core',c['core']),('boots',[[i] for i in c['boots']]),('starter',[[i] for i in c['starter']])]:
            for rank, seq in enumerate(seqs,1):
                cur.execute('INSERT INTO champion_builds VALUES(?,?,?,?)', (cid,kind,rank,json.dumps(seq)))
        for iid in c['pool']:
            sec = 'pool'
            rank = c['pool'].index(iid)+1
            cur.execute('INSERT OR IGNORE INTO champion_items VALUES(?,?,?,?)', (cid,iid,sec,rank))
        cur.execute('INSERT INTO champion_skills VALUES(?,?,?)', (cid,json.dumps(c['skill_order']),c['skill_priority']))
        cur.execute('INSERT INTO champion_tips VALUES(?,?)', (cid,json.dumps(c['tips'],ensure_ascii=False)))
        payload = {
            'combos': make_combos(c),
            'power_spikes': make_power_spikes(c),
            'engage': make_engage(c),
            'builds': make_builds(c,items),
            'synergy_packages': make_packages(c, recs, by_name),
            'priority_augments': [{'tier':t,'name':recs[t][0]['name_zh'],'reason':make_reason(c,recs[t][0])} for t in ('Silver','Gold','Prismatic')],
            'tips': c['tips'][:4],
            'archetype': ARCH_LABEL.get(c['archetype'],c['archetype']),
            'range_type': c['range_type'],
        }
        cur.execute('INSERT INTO champion_guides VALUES(?,?)', (cid,json.dumps(payload,ensure_ascii=False)))
    con.commit(); con.close()
    # current pointer
    (OUT.parent/'current.json').write_text(json.dumps({'patch':PATCH,'ddragon':DDRAGON,'db':f'{DDRAGON}/lol.db'},ensure_ascii=False,indent=1))
    print('WROTE', DB_PATH, DB_PATH.stat().st_size)
    # sanity
    print('champs',len(champs),'augs',len(augs))
    for cid in ['Ahri','Garen','Jinx','Soraka','Malphite']:
        r=recs_by_champ[cid]
        print(cid, champs[cid]['archetype'], [len(r[t]) for t in ('Silver','Gold','Prismatic')], [a['name_zh'] for a in r['Prismatic'][:3]])

if __name__ == '__main__':
    main()
