# ima 知识库接入评估

> 结论先行：**可以接入，且对研究流水线有三处明确增益**（历史经验语义检索、公开素材沉淀、产物回传闭环）。唯一硬约束是隐私分级——ima 为云服务，必须与项目「research/ 仅存本地」红线做内容分层，不可整目录上云。
>
> **接入状态（2026-08-08）**：已按方案 A 接入——SOP 阶段 1 升级五通道（新增通道 E：ima 历史经验检索，主代理直执连接器工具），TOOLS/CONVENTIONS/SKILL 已同步更新，连接器已授权并实测（search_knowledge_base / search_knowledge 均可用）。脚本化（方案 B，tools/ima_*.py）为可选增强，待用户提供 OpenAPI 凭证后实施。

## 一、ima 能力盘点（2026-08-08 核实）

| 能力 | 说明 | 本项目相关度 |
|---|---|---|
| 知识库 RAG | 支持 .md/.pdf/.docx/.xlsx/.pptx/.txt 入库，语义检索 | 高 |
| 微信生态打通 | 公众号文章一键入库（小程序/收藏），与通道 A 天然同源 | 高 |
| WorkBuddy 原生集成 | 侧边栏 OAuth 一键授权，`@ima知识库` 引用、RAG 检索、产物一键回传 | 高 |
| OpenAPI | `ima.qq.com/agent-interface` 获取 Client ID + API Key，POST+JSON 调用 | 高 |
| 移动端 | ima 小程序随时语音/文字提问知识库 | 中 |
| Skill / 知识号广场 | 公开知识生态（企查查、通达信等 MCP 服务已上线） | 低 |

**OpenAPI 已知端点**（供脚本化方案使用）：

- `openapi/wiki/v1/search_knowledge_base` — 搜索知识库（query/cursor/limit）
- `openapi/wiki/v1/get_addable_knowledge_base_list` — 可添加的知识库列表
- `openapi/note/v1/import_doc` — 新建笔记（content_format + content）
- `openapi/note/v1/search_note_book` / `list_note_by_folder_id` — 检索/列出笔记

认证：HTTP Header `ima-openapi-clientid` + `ima-openapi-apikey`，响应 `code: 0` 为成功。

## 二、接入点分析（研究流水线视角）

### 2.1 检索侧 — 新增「通道 E：ima 历史经验」

现状：阶段 0/1 前用 `rag_search.py` 查本地经验（BM25，词面匹配，索引仅 docs/templates/process_notes）。

增益：ima 为语义检索（RAG），可召回「措辞不同但语义相关」的历史沉淀；且随研究次数增长，ima 中的经验持续累积，形成跨问题「研究大脑」。

### 2.2 沉淀侧 — 公开产物自动入库

现状：每轮研究沉淀到 process_notes.md + KEYWORDS.md，仅本地，跨问题复用靠手动检索。

增益：将脱敏后的经验笔记、词库增量同步进 ima，后续任何会话（含移动端）可随时检索，不再局限于本项目目录。

### 2.3 生态侧 — 公众号素材归档

通道 A 检索到的公众号文章（标题/作者/链接），可经 ima 网页收藏/import_urls 归档进知识库，与「引用公众号须保留标题与作者」的项目规范天然兼容。

### 2.4 闭环

「取」（启动时从 ima 取经验）→「用」（研究中引用）→「存」（完成后回存），与研究流水线的多轮迭代机制契合。

## 三、隐私分级矩阵（硬约束）

项目红线：research/、plan.md 仅存本地，不推公开仓库（v7 起）。ima 为云知识库，**上云即等同于公开可见性变更，必须逐级确认**：

| 内容 | 是否可入 ima | 条件 |
|---|---|---|
| docs/ 公开文档（SOP/STYLE_GUIDE/KEYWORDS 等） | 可以 | 本身即公开仓库内容 |
| templates/ 模板 | 可以 | 公开 |
| process_notes.md（经验笔记） | 可以（脱敏后） | 剔除问题原文、具体链接，仅留方法性经验 |
| KEYWORDS.md 增量词条 | 可以 | 与公开仓库一致 |
| 已定稿 report.md | 视情况 | **须用户逐篇确认**；报告可能含被研究主体信息 |
| gathered_*.md 素材库 | 不可以 | 含原始抓取与链接 |
| plan.md / 问题原文 / 中间轮次记录 | 不可以 | 隐私红线 |

**实施原则**：默认只同步「公开级」内容；「需确认级」每篇单独征求用户同意；「禁止级」由脚本白名单硬性排除，不进入任何同步流程。

## 四、实施方案

### 方案 A：WorkBuddy 内置连接器（零代码，最快）

左侧边栏「更多 → ima知识库」OAuth 授权，授权后：
- 对话内 `@ima知识库` 引用 / 自然语言调用（RAG 检索）
- 产物区「上传到云端」一键回传

适合：手动/半自动使用，先跑通闭环。**需用户在连接器卡片完成授权。**

### 方案 B：脚本化（tools/ima_*.py，自动化）

基于 OpenAPI 写两个工具，纳入流水线：
- `tools/ima_search.py "查询"` — 阶段 0/1 前检索 ima 经验（对应 `search_knowledge_base`）
- `tools/ima_sync.py --slug <slug>` — 阶段 4 沉淀时同步公开级产物（process_notes 脱敏 + 关键词增量，对应 `import_doc`）

前置：用户在 https://ima.qq.com/agent-interface 生成 Client ID + API Key，存 `~/.config/ima/`（或环境变量），**凭证不进项目文件、不入库**（沿用 zhihu-cli 凭证安全约定）。

### 方案 C：A + B 混合（推荐）

A 用于交互式检索/手动回传，B 用于研究收尾自动沉淀。本地 BM25 RAG 保留不动（隐私底线 + 离线兜底），ima 作为语义层叠加。

## 五、落地步骤（用户确认后执行）

1. 用户授权 ima 连接器（方案 A）或提供 OpenAPI 凭证（方案 B）。
2. 在 ima 中建库：建议按「研究经验库」「报告归档库」分库，与研究索引表的领域维度对应。
3. 写 `tools/ima_sync.py`：白名单（仅公开级路径）+ 脱敏规则 + 关键词增量回传；写 `tools/ima_search.py`：检索封装（UTF-8 文件传参，规避本机乱码）。
4. 更新 docs/SOP.md 阶段 1 增加「通道 E」，docs/TOOLS.md 增加工具说明，docs/CONVENTIONS.md 增加 ima 凭证与隐私约定。
5. 试点：以 1 个已完成主题的 process_notes 脱敏版同步验证，再全量启用。

## 六、风险与边界

- **隐私**：ima 内容可视性由用户账号控制，同步前必须过第三章节分级；未经确认不回传 report.md。
- **凭证**：API Key 仅显示一次，丢失需撤销重建；严禁写入项目文件或日志。
- **依赖**：OpenAPI 端点/限额为 ima 官方动态提供，接口变更需跟进；脚本方案依赖网络可达 ima.qq.com。
- **定位**：ima 是语义检索层，不替代本地 RAG 的事实核查职责；检索结果仍需按阶段 3 交叉验证规则处理。

---

*本文件为公开文档，不含任何研究隐私内容。*
