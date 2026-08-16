---
name: zhihu-ask-research
description: 知乎深度回答研究流程。用于把知乎问题通过系统化检索、交叉验证、多轮迭代，产出事实陈述报告。
---

# 知乎深度回答研究

## Overview

研究流水线: 问题接收 → flomo 查重(命中已有笔记→过时检查: 过时→三步原地更新 / 未过时→复用还原) → 多通道检索 → 写笔记 → 写索引 → 组装报告 → 质检八件套 → 上传/更新笔记。

报告为**纯事实陈述、零立场**，正文按 GB/T 7714-2015 顺序编码制在引用处标注 [n]。

## 何时使用

- 知乎问题深度研究
- 事实核查、数据汇编
- 口径澄清、多维对比

## 工作目录

```
research/<slug>/
├── plan.md              # 问题界定
├── report.md            # 成品报告
├── report_draft.md      # 组装骨架(中间产物)
├── process_notes.md     # 检索踩坑
├── .progress.json       # 进度
└── notes/               # 模块化笔记(扁平)
    ├── _TEMPLATE.md
    ├── 00_xxx.md
    ├── 01_xxx.md
    └── ...
```

## 笔记格式

所有笔记统一放 `notes/` 一个目录, 不分子目录。

```
#维度1 #维度2 #主题/xxx

笔记标题

笔记内容(用自己的话, 不照搬原文)

来源:
[1] 作者. 题名[EB/OL]. (发布日期)[引用日期]. URL.
来源类型: 一手/二手/综合推断
```

**硬规则:**
1. 第一行必须是3个tag: `#维度1 #维度2 #主题/xxx`
2. 来源必须按 GB/T 7714-2015 著录
3. 标题不加 `#`
4. 正文不加 `#` (只有第一行有 `#`)
5. 索引笔记(00_index.md)和报告(report.md)禁止上传 flomo
6. 笔记上传前必须跑质检: `python tools/quality_check.py --file notes/xx.md`, 通过后再上传
7. **单篇独立可读**:
   - 每篇笔记自含出处：正文首次提到来源材料（论文/文章）时写全题名与出处（如"arXiv:2608.11313《…》（YYYY-MM-DD，作者）"），不得只写"本文/该文/前作"
   - 不依赖其他笔记：禁止"见笔记 02""如前文所述"等跨笔记指代；每条笔记是完整自足的单元
   - 不依赖来源材料内部编号：论文公式号/章节号/文献号（如"(4.50)""[31]""附录 C"）单独拿出无意义，一律改描述性表述（"论文附录中的单圈检验""其前期工作（JHEP 2025(10): 204）"）
   - 指代明确："本文/本篇/前作"在本篇笔记内必须有先行词或直接写全称
   - 公式书写：笔记允许 Unicode 手写公式（笔记用 Unicode、报告用 LaTeX）
   - **参考文献区禁止 LaTeX**：报告与笔记的参考文献/来源段一律不用 $...$——GB/T 7714 著录是纯文本格式，数学符号用 Unicode/文字（如 λ₁、10⁶）；正文 LaTeX 规则不变（正文仍用 $...$，仅参考文献区例外）

## 核心流程

### 阶段 0 · 问题接收与范围界定

1. 接收问题。知乎链接先 `web_fetch`；失败则请用户粘贴。
2. 拆解问题: 主概念、关键实体、隐含前提、真实诉求。
3. **搜 flomo**: `python tools/flomo_search.py --keywords "主题词"` — 查已有相关笔记, 避免重复研究。
4. 搜本地 RAG: `python tools/rag_search.py "<主概念>"`（SQLite 索引，改动 docs 后先 `rag_build.py`）。
5. 判定查询类型: 深度优先 / 广度优先 / 直接查询。
6. 写 `tools/start.json`, 执行 `python tools/research_start.py --config tools/start.json`。
7. 初始化后 `research/<slug>/notes/` 目录就绪。

### 阶段 1 · 信息检索 + 写笔记

**执行顺序: F查重 → E → A → B → C → P**

**每收到一个新链接/新信息, 必须先搜 flomo 再处理:**
```
1. 搜 flomo: python tools/flomo_search.py --keywords "关键词"
   → 命中: 看已有笔记, 只补新信息
   → 未命中: 从零写笔记
2. 处理内容, 写入 notes/01_xxx.md
```

**旧笔记过时信息更新(命中时必做)**: 命中已有笔记且新信息推翻了旧笔记中的表述时, 旧笔记中已过时的句子必须原地更新(如"尚无定论""待观察""未发布"被新事实证实/证伪后, 在该句补结局或改写), 不得只新增笔记而让旧笔记与新笔记自相矛盾; 更新后的旧笔记与新增笔记一并质检上传。

**flomo 笔记引用规则**: flomo 检索命中的笔记若用作素材, 必须有**符合 GB/T 7714-2015 的参考文献**; 参考文献不合规或没有 → 联网找对应来源; 找不到 → 该笔记不可用。检测: `python tools/check_flomo_note_refs.py --keywords "<主题词>"`。

**检索通道（优先级按主题领域分档——替代一刀切 P0）:**
- **统一入口**: 启动后跑 `python tools/search_all.py --config tools/start.json`——并行执行 B/A/P 三通道（B 多查询并行），各自落盘自动登记；F 判读登记仍人工
- F (flomo 查重, P0 通用): `memo_search` 查是否已有本主题笔记——判读 relevance: ≥0.9 已有笔记→**过时检查必做**(① `flomo_search --full` 拉全文; ② 逐条核对新版本/新信息是否推翻表述; ③ 过时→本地改写+`note_upload --update` memo_update 原地更新原 id / 未过时→本地缺失则按全文还原复用, 不新建不更新); 0.5–0.9 参考(须 GB/T 合规来源); <0.5 正常检索。结论与过时检查证据记 plan.md + F 通道 note
- B (Web, P0 通用): `web_search` / `tools/web_search.py`
- P (arxiv 平台单独检索): `tools/arxiv_search.py`(落盘 gathered_arxiv.md 登记通道 P)
- P (预印本聚合, 含 arxiv, 学术科研 P0 / 科技产业·财经时政 P2): `tools/preprint_search.py --platform all --keywords "<主题词>" --days 30 --count 5 --out research/<slug> --slug <slug>`——arxiv→gathered_arxiv.md + bioRxiv（生物医学）/ 浪淘沙（中文跨学科）/ PSSXiv（哲学社会科学）→gathered_preprints.md; 两文件同属通道 P, 一次性登记
- C (领域, 科技产业/财经时政 P0 / 学术科研 P1): 通达信/企查查/智慧芽
- A (公众号, 财经时政 P0 / 科技产业 P1 / 学术科研 P2): `tools/wechat_search.py`
- E (ima, P1, 未配置时初始化自动登记 skip，无需逐篇检查): `search_knowledge` 逐库检索

**领域分档**：学术科研类（数学/物理/生物医学/哲学社科/AI 理论）→ P 为 P0；科技产业类（AI 应用/半导体/机器人/3D 生成）→ C 为 P0、P 为 P2；财经时政类（股票/宏观/政策/民生）→ A/C 为 P0、P 为 P2。执行纪律：仍须登记全部六通道执行态（P0 缺失须补足、P1 无命中记"无有效素材"、P2 记 skip）；**环境级未配置连接器的通道（ima E / 领域连接器 C 默认未配置）由初始化自动登记 skip，无需逐篇手动检查**（连接器接入后设 `ZHIHU_ASK_UNCONFIGURED_CHANNELS` 调整）。

**笔记写入规则:**
- 每条笔记3个tag: `#维度1 #维度2 #主题/slug`
- 来源必须 GB/T 7714-2015 格式
- 每个通道命中写一条笔记

**校验:** `notes/` 下至少有2个不同通道的笔记才进入阶段2。

### 阶段 2 · 补充 + 加工

1. 五视角逐项覆盖 (A公众号/B Web/C领域/D争议/E反方)
2. 搜 flomo 补充同类笔记: `python tools/flomo_search.py --tag "主题/slug"`
3. 补充新笔记到 `notes/`

### 阶段 3 · 交叉验证与量化

- 多源冲突取舍: 最新 + 一手优先 + 口径一致
- 算式按需但必写: 有计算价值的内容算式必须写、融入叙述, 禁止凑数硬造也禁止该写不写
- 数学/证明/机制类内容给完整论证链(定理-引理-证明或步骤归约), 禁止只给方法名概述; 来源论文论证以全文(arXiv HTML 版)为准
- 数据不可得 → 标注"待核实"

### 阶段 4 · 写索引 + 组装报告

1. **写索引笔记** `notes/00_index.md`:
   ```
   #索引 #主题/slug #阶段/组装

   主题名 — 索引

   ## 维度1
   → #01: 标题

   ## 维度2
   → #02: 标题

   ## 缺口
   - 缺: xxx
   ```

2. **组装报告**:
   ```bash
   python tools/note_assemble.py --slug <slug>
   ```
   生成 `report_draft.md`

3. **补完报告**: 补过渡段落, 生成 `report.md`

4. **质检八件套**:
   ```bash
   python tools/check_report_structure.py --file research/<slug>/report.md
   python tools/quality_check.py --file research/<slug>/report.md
   python tools/check_ai_voice.py --file research/<slug>/report.md
   python tools/check_gbt_refs.py --file research/<slug>/report.md
   python tools/check_citation_validity.py --file research/<slug>/report.md   # 违规引用（学术纪律）
   python tools/check_consistency.py --file research/<slug>/report.md         # 矛盾与废话
   python tools/check_progress.py --slug <slug> --require_round auto
   ```
   (共 5 项;算式不单独跑校验工具——有计算价值的算式必须写并经 Python 验证, 禁止凑数硬造也禁止该写不写)

5. **迭代(如需)**: 补笔记 → 重新组装 → 重跑质检

6. **沉淀**:
   - 关键词写入 SQLite 关键词库: `python tools/keywords_db.py --add --section "<领域>" --kind "已验证有效组合" --content "<关键词行>" --slug <slug>`，再 `python tools/keywords_db.py --export docs/KEYWORDS.md` 同步
   - 写 `process_notes.md`
   - **上传 flomo: 上传的是「模块化笔记」而非报告**:
     `python tools/note_upload.py research/<slug>/notes/` — 逐条自动质检后上传;
     索引笔记(00_index.md)与报告(report.md/report_draft.md)由工具自动拦截, 禁止上传

## flomo 搜索用法

```bash
# 按关键词搜
python tools/flomo_search.py --keywords "AI 编程"

# 按标签搜
python tools/flomo_search.py --tag "AI编程"

# 组合搜
python tools/flomo_search.py --tag "AI编程" --keywords "定价"
```

## GB/T 7714-2015 来源格式

```
网络文献: 作者. 题名[EB/OL]. (发布日期)[引用日期]. URL.
会议论文: 作者. 题名[C]//论文集名. 出版地: 出版者, 年: 页码.
期刊论文: 作者. 题名[J]. 刊名, 年, 卷(期): 页码.
作者规则: 英文姓在前名缩写, 无作者写"佚名"
```

## 配套资源

- 工具: `tools/`
- 流程: `docs/SOP.md`
- 词库: SQLite `.codebuddy/knowledge/knowledge.db`（`tools/keywords_db.py` 管理；`docs/KEYWORDS.md` 为导出物）
- 模板: `templates/`
