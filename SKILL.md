---
name: lol-aram-mayhem
description: 英雄联盟「海克斯大乱斗」（ARAM Mayhem）英雄查询与推荐。用户说英雄名/外号/拼音，或问某英雄的海克斯（白银/黄金/棱彩）、联动组合、连招、强势期、进场时机、出装（对面肉多/AD多/AP多/长手多）时使用。数据来自当前版本本地 SQLite，按版本存档，不凭记忆编造海克斯或装备。
---

# 英雄联盟：海克斯大乱斗助手

## 这个 Skill 解决什么

用户给出一个英雄（中文名、英文名、拼音、常用外号均可），需要：

1. 先解析英雄；如果有歧义，给用户 2–6 个候选项二次选择。
2. 给出该英雄当前版本的白银/黄金/棱彩海克斯各前 10。
3. 给出几套能联动的海克斯组合。
4. 给出连招、强势期、进场时机。
5. 给出出装顺序，以及对面肉多/AD多/AP多/长手多时怎么换。
6. 所有海克斯、装备必须来自本地数据库，不能写不存在的名字。

## 运行环境（先看这段）

本技能纯本地运行，只要 Python 3.10+（只用标准库，无需 pip install）。**命令里的 Python 按平台换**：

| 平台 | Python 命令 | Skill 目录 |
| --- | --- | --- |
| macOS / Linux | `python3` | `~/.dsh/skills/lol-aram-mayhem/` |
| Windows（PowerShell） | `python`（或 `py -3`） | `%USERPROFILE%\.dsh\skills\lol-aram-mayhem\` |

- Windows 路径分隔符用 `\`，命令分隔符用 `;`（不是 `&&`）
- 下面示例统一写 macOS 的 `python3` 和 `~/.dsh/...`；在 Windows 上按上表替换即可
- 首次在 Windows 上使用，可先跑：`powershell -ExecutionPolicy Bypass -File .\install.ps1`

## 数据位置

- Skill 目录：本文件所在目录（macOS 示例 `~/.dsh/skills/lol-aram-mayhem/`，Windows `%USERPROFILE%\.dsh\skills\lol-aram-mayhem\`）
- 当前版本指针：`data/current.json`
- 当前数据库：`data/16.22.1/lol.db`
- 每个版本一个独立 SQLite 文件（`data/<ddragon版本>/lol.db`），表结构相同；更新版本时新建目录，不覆盖旧版本。
- 当前数据：Patch **16.22** / Data Dragon **16.22.1** / 173 英雄 / 255 个可用海克斯。

数据来源（报告里也会带）：

- 海克斯排序：<https://op.gg/lol/modes/aram-mayhem> 同英雄页面（16.22）
- 海克斯档位/机制：<https://wiki.leagueoflegends.com/en-us/ARAM:_Mayhem/Augments>
- 英雄/装备中文名与属性：<https://ddragon.leagueoflegends.com/cdn/16.22.1/data/zh_CN/>
- 海克斯中文名/官方文本：<https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/zh_cn/v1/>

## 工作流

### 第 1 步：解析英雄

```bash
cd ~/.dsh/skills/lol-aram-mayhem
python3 scripts/lol.py resolve "<用户输入>"
```

返回 JSON 数组，每项含 `id`、`name`（称号）、`title`（英雄本名）、`name_en`、`archetype`、`score`。

- **0 个结果**：不要猜。回复“没匹配到，给我中文名/英文名/拼音/外号其中一个就行”，并给 2–3 个示例。
- **1 个结果且 score ≥ 100**：直接进入第 2 步。
- **多个结果，或最高分 < 100**：必须让用户二次选择。用 `ask_user_question` 工具，把候选做成选项，最多 6 个；每个选项写 `中文本名（英文名）— 定位`，并在问题里说明“你要查哪个英雄？”。用户选完后，用对应的 `id` 进入第 2 步。
- 常见歧义：`js` 可能是剑圣/杰斯；`霞`/`洛`；`男刀`/`女刀`；`石头人`/`岩雀`。不要自行替用户选。

### 第 2 步：取英雄 + 玩法评估

```bash
python3 scripts/lol.py report "<上一步的 id>" --styles all
```

返回里除了基础报告，还有：

- `style_assessment`：`ad` / `ap` / `tank` / `poke` / `support` 五个玩法的 0–98 分、`label`（推荐/可玩/偏娱乐/不推荐）、`note`
- `variants`：每个玩法各自的完整方案（海克斯、联动、连招、强势期、出装）
- `styles`：五个玩法的中文名和颜色

**玩法是按英雄类型过滤过的**，不要给用户列不存在的玩法：

- `support`（辅助）只在辅助英雄（`build_type=SUPPORT`，40 位）身上出现，带治疗/护盾/功能装（月石、香炉、救赎、鸟盾、骑士之誓等）和对应海克斯（治疗护盾三件套、技能急速等）
- `tank`（肉）只在战士/坦克（`tags` 含 `Fighter` 或 `Tank`，80 位）身上出现
- 因此法师/射手/刺客的 `style_assessment` 里根本不会有 `tank`，非辅助英雄不会有 `support`；问起来就直说“这个英雄没有这条玩法线”

如果返回 `{"ambiguous": true}`，回到第 1 步让用户选；如果 `{"error":"not_found"}`，让用户换一种叫法。

### 第 3 步：让用户选玩法（可多选）

**必须问，除非用户已经明确说了玩法类型**（例如“AP阿狸”“石头人出肉”）。

用 `ask_user_question` 工具，`multi_select: true`，问题和选项这样写：

- 问题：`这把你想玩什么类型？可以多选，我会分别给完整方案。`
- 选项（用 `style_assessment` 的真实分数，不要自己编）：
  - `AP（推荐 92）` — 法强/法穿/技能爆发
  - `AD（偏娱乐 44）` — 攻击力/暴击/攻速/穿甲
  - `肉（可玩 70）` — 生命/双抗/开团抗伤（仅战士/坦克有）
  - `消耗（可玩 68）` — 远程消耗/压血线/拉扯
  - `辅助（推荐 84）` — 治疗/护盾/功能装（仅辅助英雄有）
  - 只列 `style_assessment` 里真实存在的玩法，不要自己补

如果英雄有歧义，可以在同一次 `ask_user_question` 里放两个问题：

1. `你要查哪个英雄？`（单选，最多 6 个候选）
2. `这把想玩什么类型？`（多选）

用户没选或选择为空时，默认用分数最高的玩法，并在回复里说明“没选，先按最高推荐度给你”。

### 第 4 步：按选中的玩法分别输出

```bash
python3 scripts/lol.py report "<id>" --styles ap,ad
```

`--styles` 支持 `ad,ap,tank,poke,support` 任意组合，也支持 `all`；不在该英雄开放范围内的玩法会被自动过滤掉。

用中文回复，结构如下：

```markdown
**16.22 海克斯大乱斗 · 九尾妖狐 阿狸（Ahri）**
玩法对比：AP 92 推荐 ｜ AD 44 偏娱乐 ｜ 消耗 68 可玩（只写该英雄有的玩法）

## 玩法一：AP（推荐 92）
### 海克斯推荐
...
### 联动组合
...
### 连招
...
### 强势期与进场
...
### 出装
...
### 技能加点
...

## 玩法二：AD（偏娱乐 44）
### 海克斯推荐
...
（同样六段，完整输出）

### 数据说明
...
```

每个玩法都必须有这六段，不能只给一个玩法、其他玩法只写一句：

1. **海克斯推荐**：白银/黄金/棱彩各 10 条；前 3 名详细，4–10 名一行一个。
2. **联动组合**：优先级三件 + 2–3 套成套组合（带 `fit`，说明本玩法池里出现几件）。
3. **连招**：2–3 套，用真实技能名；`玩法提醒` 这类条目要保留。
4. **强势期与进场**：`power_spikes` + `engage`。
5. **出装**：`starter`、`boots`、`core`、四个 `branches`。
6. **技能加点**：`skill_order.priority` + 1–18 级顺序。

`variants.<style>` 里的字段和基础报告一致：

- `augments.silver/gold/prismatic`：该玩法下各 10 条
- `priority_augments`：该玩法三档第 1 名
- `synergy_packages`：该玩法成套联动
- `combos` / `power_spikes` / `engage`
- `builds`：该玩法出装
- `viability` / `viability_note`：推荐度与原因

### 玩法输出要求

- 如果 `viability` 是 **不推荐** 或 **偏娱乐**，开头必须明确写“这套是娱乐/低强度玩法”，不能包装成主流。
- 出装必须是该玩法 `builds` 里的装备；不要拿 AP 玩法的海克斯去配 AD 出装。
- 不同玩法之间的海克斯、出装、进场时机要能看出区别；如果两个玩法数据完全一样，检查是不是选错了 `--styles`。
- 仍然遵守：不存在的海克斯/装备不能写；不编胜率；有歧义先让用户选英雄。

## 硬性约束

1. **不存在的海克斯/装备绝对不能写。** 所有名字从 `report` JSON 取；不要凭记忆补“好像有”。
2. **不要编胜率/选取率。** 数据库没有具体百分比；只说“同英雄综合排序/优先级”。
3. **不要替用户选英雄。** 有歧义必须二次确认。
4. **不要把所有 30 个海克斯都展开成长篇。** 前 3 名详细，4–10 名一行一个。
5. **不要忽略版本。** 每次回复开头写 `16.22`；版本更新后先跑更新流程。
6. **不要写“海克斯大乱斗”以外的模式数据**（如普通大乱斗、竞技场）冒充本模式。
7. 用户如果问“对面肉多怎么出”等，优先用 `branches` 对应项；不要另起炉灶编装备。

## 网页版（Vue 3 + Vite，可选）

同目录下有一个可视化网页，支持搜索英雄、多选玩法、并排查看各玩法完整方案。需要 Node.js 20+。

```bash
cd ~/.dsh/skills/lol-aram-mayhem/web
npm install
npm run dev
# 打开 http://127.0.0.1:5178/
```

Windows：**直接双击仓库根目录的 `start-web.bat`**（自动装依赖、自动开浏览器，关掉窗口即停服务）；
也可以在 PowerShell 里手动起：

```powershell
cd "$env:USERPROFILE\.dsh\skills\lol-aram-mayhem\web"
npm install
npm run dev
```

生产构建：

```bash
npm run build
```

网页数据来自 `web/public/data/lol.json`，由下面命令生成：

```bash
cd ~/.dsh/skills/lol-aram-mayhem
python3 scripts/export_web.py
```

版本更新后要重新导出一次，再 `npm run build`。网页当前包含：

- 首页：收藏置顶 + 全英雄 A–Z 拼音分组 + 右侧字母索引（可点击/拖动快速定位），头像 90×90
- 顶栏固定搜索：任何页面都能直接搜英雄并跳转，`/` 或 `⌘K` 聚焦，`↑/↓` 选择、`Enter` 打开
- 详情页：返回按钮在左上角（顶栏），玩法改为标签页单选切换，不再多选
- AD / AP / 肉 / 消耗 / 辅助 五个玩法标签（肉只对战士/坦克开放，辅助只对辅助英雄开放，按评分从高到低排列）
- 海克斯三档（白银/黄金/棱彩）默认各显示前 3，右上角一个按钮三档一起展开 4–10；档位用银/金/彩虹色区分，top3 名称放大
- 出装优先、吸顶对局速览；吸顶栏“出装/海克斯/连招”与右侧大纲都在本页滚动跳转，不会回首页
- 右侧大纲（手机端为横向大纲），可跳转到海克斯/联动/连招/强势期/出装/加点
- 顶栏设置抽屉：字号五档（115%–165%，本地保存）、数据版本、快捷键说明
- 从详情返回英雄库会恢复之前的滚动位置和搜索词（页面缓存）
- 推荐度低的玩法会显示“偏娱乐/不推荐”提示，但仍给完整方案

## 维护 / 更新版本

当前版本数据已经构建好。版本更新时：

```bash
cd ~/.dsh/skills/lol-aram-mayhem
python3 scripts/update.py
```

更新脚本会：

1. 读取 Data Dragon 最新版本号；
2. 抓取新版本的英雄、装备、海克斯、OP.GG 同英雄页面；
3. 新建 `data/<新版本>/lol.db`（旧版本保留）；
4. 校验所有海克斯/装备 ID 是否存在、每个英雄是否仍有各档 10 条；
5. 更新 `data/current.json` 指针。

如果更新脚本因网站改版失败：不要手改旧库冒充新版本；保留旧指针，把失败原因告诉用户，等修好抓取脚本再更新。

## 常用命令

```bash
python3 scripts/lol.py status
python3 scripts/lol.py list
python3 scripts/lol.py resolve "狐狸"
python3 scripts/lol.py report "Ahri"
python3 scripts/lol.py report "Ahri" --styles ap,ad
python3 scripts/lol.py augments "Garen" --tier Gold
python3 scripts/lol.py search "魔法飞弹"
```

## 数据口径（回答时可简短说明）

- 海克斯档位：白银 / 黄金 / 棱彩；以 LoL Wiki 与 CommunityDragon 当前数据交叉核对。
- 海克斯排序：OP.GG 同英雄 ARAM: Mayhem 页面顺序，表示该英雄的综合表现排序，不是纯胜率。
- 已过滤：当前版本禁用海克斯、与英雄机制明显不适配的海克斯（如给没有旋转技能英雄的“旋转至胜”）。
- 出装：OP.GG 16.22 同英雄核心装序列；分支装按英雄类型、敌方伤害结构与当前装备池给出。
- 嚎哭深渊口径：出门装统一为守护者系列 + 生命药水（不用峡谷的多兰/鞋子出门）；肉玩法第一件固定心之钢，再按对局补日炎/反甲/振奋/鸟盾。
- 海克斯是随机三选一，成套组合“可遇不可求”；优先级高于硬凑套装。
- 玩法推荐度是启发式评分（英雄标签、技能范围、装备池、海克斯池），**不是胜率**；分数高说明本英雄的装备/海克斯池更匹配这个玩法。
- 偏娱乐/不推荐的玩法仍会返回完整方案，但回复里必须标注，不要包装成主流。
