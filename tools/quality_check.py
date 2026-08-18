
"""
正文质量自动检查工具（zhihu-ask 项目专用）

把报告模板中的"去 AI 味 + 立场中立"检查落地为自动扫描：
  1. 立场词检测：我认为/我的判断/结论很硬/显然/可见/证明/应该/不该/建议/最好/总之
  2. 框架词检测：先说结论/总结一下/综上所述/不难发现/总而言之
  3. 评价词检测：太猛/很差/厉害/离谱/糟糕/完美/惊人（评价性形容词）
  4. 形式检测：感叹号、反问句（？+语气）、无来源数字（粗略启发式）

用法：
    python tools/quality_check.py --file research/<slug>/report.md
    python tools/quality_check.py --file research/<slug>/report.md --verbose

说明：
- 扫描范围为正文（跳过"数据与来源备查"及之后的来源区）。
- 检测到违规词时退出码 1，全部通过退出码 0。
- 检查项为启发式规则，命中后需人工确认是否真正违规（如"建议"在"不构成投资建议"中是合法用法）。
"""

import sys
import os
import re

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

STANCE_WORDS = [
    "我认为", "我的判断", "我的看法", "结论很硬", "显然",
    "应该", "不该", "最好", "总之", "所以结论是", "说白了", "实话实说",
    "我建议", "我认",
    # 「我们」不再无条件命中：学术第一人称（我们定义 / 证明 / 考察 / 令 / 设 / 考虑 /
    # 推导 / 引入 / 给出 / 构造 / 分析 / 计算 / 称 / 假设 / 记 / 观察 …）是中性叙述，
    # 不是立场表达；仅当「我们」后接主观立场动词时才判立场词。
    "我们认为", "我们相信", "我们觉得", "我们以为", "我们主张", "我们强调",
    "我们支持", "我们反对", "我们建议", "我们希望", "我们倾向", "我们认同",
    "我们确信", "我们感到",
    "足以证明", "这证明", "证明我", "证明这",
]

FRAMEWORK_WORDS = [
    "先说结论", "总结一下", "综上所述", "总而言之", "不难发现",
    "值得注意的是", "总的来说", "一方面", "另一方面", "其一", "其二",
]

EVALUATIVE_WORDS = [
    "太猛", "很差", "非常差", "厉害", "离谱", "糟糕", "完美", "惊人",
    "令人震惊", "极其", "极其重要", "重大突破", "巨大", "显著提升",
    "狠狠", "暴跌", "暴涨", "至关重要", "不可或缺",
]

SOURCE_MARKERS = ["## 数据与来源备查", "## 参考文献", "### 数据与来源备查", "### 参考文献", "数据与来源备查"]

REF_MARKERS = ["## 参考文献", "### 参考文献"]

# 笔记模式（笔记用 Unicode、报告用 LaTeX）：
# 文件位于 research/<slug>/notes/ 目录下即视为模块化笔记——
# 文献段仅允许「参考文献:」标记（「来源:」为非规定字段，一律禁止），正文允许 Unicode 手写公式。
NOTE_SOURCE_MARKERS = ["## 参考文献", "\n参考文献:"]
NOTE_REF_MARKERS = ["## 参考文献", "参考文献:"]

# 笔记非规定字段：flomo 笔记模板只允许「tag 行 + 纯文本标题 + 正文 + 参考文献:」，
# 「来源」「概念」等字段一律禁止（来源信息只能以 GB/T 7714-2015 条目进参考文献区）。
FORBIDDEN_NOTE_FIELDS = [
    (r"^\s*\*\*来源\*\*\s*[:：]", "来源字段"),
    (r"^\s*\*\*概念\*\*\s*[:：]", "概念字段"),
    (r"^\s*来源\s*[:：]", "来源字段"),
    (r"^\s*概念\s*[:：]", "概念字段"),
]


def check_note_forbidden_fields(body):
    """检测笔记非规定字段（来源/概念等，flomo 笔记模板禁止）。

    判定：行首出现「**来源**：」「来源:」「**概念**：」「概念:」等字段形式
    （含全角/半角冒号、加粗变体）即报"非规定字段"。
    不匹配：正文普通用词（"这些数字的来源是官方文档""核心概念是……"——非行首字段形式）。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        for pat, label in FORBIDDEN_NOTE_FIELDS:
            if re.search(pat, line):
                issues.append((i, "非规定字段",
                               f"笔记禁止「{label}」字段——来源只能以 GB/T 7714-2015 条目写入「参考文献:」区",
                               line.strip()[:60]))
                break
    return issues

REF_BAD_LABELS = ["一手", "二手", "推断"]


def is_note_file(filepath):
    """按目录判定笔记模式：路径目录名为 notes（research/<slug>/notes/）。"""
    return os.path.basename(os.path.dirname(os.path.abspath(filepath))) == "notes"


def scan_body(filepath, note_mode=False):
    """读取回答，返回正文部分（来源区之前）。"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    markers = NOTE_SOURCE_MARKERS if note_mode else SOURCE_MARKERS
    cutoff = len(content)
    for marker in markers:
        idx = content.find(marker)
        if idx != -1:
            cutoff = min(cutoff, idx)
    return content[:cutoff], content

def strip_display_math(text):
    """移除块级 $$...$$ 与 \\[...\\] 公式，避免公式块被当作叙述段落计数。"""
    text = re.sub(r"\$\$.*?\$\$", "", text, flags=re.S)
    text = re.sub(r"\\\[.*?\\\]", "", text, flags=re.S)
    return text


def check_exclamation(body):
    """检查感叹号与反问句（跳过图片引用行 `![...](...)`——感叹号是 Markdown 图片语法；
    跳过 $...$ 与 $$...$$ LaTeX 内部——`!` 是阶乘/否定数学符号，非感叹号；nth-derivative-quotient 踩坑：块级公式内 `k!` 阶乘被误报，豁免正则补块级 $$...$$）。"""
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("!["):
            continue
        stripped = re.sub(r"\$\$[^$]*\$\$|\$[^$]*\$", "", line)
        if "！" in stripped or "!" in stripped:
            issues.append((i, "感叹号", line.strip()[:60]))

        if re.search(r"(难道|凭什么|怎么会|怎么不).*？", line):
            issues.append((i, "反问句", line.strip()[:60]))
    return issues

def check_words(body, word_list, label):
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        # 引文豁免：书名号《》、弯引号""、方引号『』、直引号 "" 内的内容为
        # 引述他人（原文标题/直接引语），不算本人立场/框架/评价表达——误报案例：
        # startup-pretend-success 原文标题《请不要假装我们已经成功了》、Imbue 直接引语
        stripped = re.sub(r"[《「『][^》」』]*[》」』]", "", line)
        stripped = re.sub(r"[\u201c\u2018][^\u201d\u2019]*[\u201d\u2019]", "", stripped)
        stripped = re.sub(r'"[^"]*"', "", stripped)
        for w in word_list:
            if w in stripped:
                # 来源转述豁免："论文证明这/文章证明这/该文证明这"是对文献
                # 的客观转述，不是作者本人立场，不应命中"证明这"立场词。
                if w == "证明这" and re.search(r"(论文|文章|该文|作者)证明这", line):
                    continue
                # 术语豁免：图论/组合数学术语「完美图/完美可除/完美权可除/
                # 完美划分/完美横贯/完美匹配」中"完美"是标准技术名词（perfect
                # graph / perfect divisibility / perfect matching），非评价性
                # 形容——gromov 系列与 fork-free 系列命中案例。
                # 允许词间含 LaTeX（如"完美 $\Omega_{G^h}$-横贯"）。
                if w == "完美" and re.search(r"完美.{0,30}?(图|权可除|可除|划分|横贯|匹配)", line):
                    continue
                issues.append((i, label, w, line.strip()[:60]))
    return issues

def check_references(full, note_mode=False):
    """检查参考文献区：条目行尾不得带"一手/二手/推断"等分级标注（来源类型只写在笔记来源段，报告正文不出现分级括注）。
    仅针对参考文献区（从 ## 参考文献 / 笔记「来源:」起到文末）内的条目行。"""
    issues = []
    markers = NOTE_REF_MARKERS if note_mode else REF_MARKERS
    start = None
    for marker in markers:
        idx = full.find(marker)
        if idx != -1:
            start = idx
            break
    if start is None:
        return issues
    section = full[start:]
    for i, line in enumerate(section.splitlines(), 1):
        stripped = line.strip()
        if not re.search(r"\[[^\]]+\]\([^)]+\)", stripped):
            continue

        tail = re.sub(r"^.*\]\([^)]*\)", "", stripped)
        for label in REF_BAD_LABELS:
            if f"— {label}" in tail or f"：{label}" in tail:
                issues.append((i, "参考文献标注", f"链接后带 [{label}]", stripped[:60]))
                break
    return issues


def check_ref_latex_ban(full, note_mode=False):
    """检查参考文献区禁止 LaTeX。

    理由：GB/T 7714-2015 著录是纯文本格式（作者. 题名[类型]. 出版信息.），
    数学符号应直接用 Unicode/文字（如"π""10⁶"），$...$ LaTeX 会破坏著录结构
    且 docx 转换器（report_to_docx.py）对参考文献区的 $ 不做 OMML 转换。
    命中即硬伤：$...$ / $$...$$ 出现在参考文献区（## 参考文献 / 笔记「参考文献:」之后；
    「来源:」为非规定字段，不算文献区）。
    """
    issues = []
    # marker 用行首正则匹配 + 行偏移累计定位——find() 子串会命中
    # 正文的"一手来源:..."，把正文 $...$ 误判为参考文献区（chang-yang 笔记质检踩坑）。
    head_re = (re.compile(r"^\s*参考文献[:：]?|^#{1,6}\s*参考文献")
               if note_mode else re.compile(r"^#{1,6}\s*参考文献"))
    start = None
    offset = 0
    for line in full.splitlines():
        if head_re.match(line):
            start = offset
            break
        offset += len(line) + 1  # 含换行符
    if start is None:
        return issues
    section = full[start:]
    for i, line in enumerate(section.splitlines(), 1):
        stripped = line.strip()
        # 跳过空行/分隔行
        if not stripped:
            continue
        m = re.search(r"\$[^$]*\$", stripped)
        if m:
            issues.append((i, "参考文献LaTeX", f"参考文献区禁止 LaTeX（$...$），数学符号用 Unicode/文字", stripped[:60]))
    return issues

def check_unsourced_numbers(body, full=None):
    """启发式：行内出现"约 X 元/万亿/亿/万"等数字表述但同行无来源字样。
    跳过表格行（| 开头）与列表项（- 开头且带来源括注），因表格/列表数字通常在行内或表前已说明来源。
    来源特征词含来源/口径/媒体等，与项目"每个数字可溯源"约定配套。
正文按 GB/T 7714-2015 顺序编码制标注 [n] 引注，来源归文末「参考文献」区——报告含参考文献
    节（必需结构）即跳过本检查，正文无来源数字属合规。"""
    if full and "参考文献" in full:
        return []
    source_words = (
        r"(来源|据|数据|报道|推算|口径|官方|媒体|实测|参考|定价|备查|"
        r"一手|二手|计算|估算|预算|决算|公布|披露|统计)"
    )
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("|"):
            continue
        if stripped.startswith("!["):

            continue
        if re.search(r"[约|超过|高达]\s*[\d.]+", line):
            if not re.search(source_words, line):
                issues.append((i, "无来源数字(待确认)", stripped[:60]))
    return issues

def check_placeholders(body):
    """检测模板占位符未替换残留（{{...}}），防止模板内容漏发。"""
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        for m in re.finditer(r"\{\{[^{}]*\}\}", line):
            issues.append((i, "模板占位符", m.group(0), line.strip()[:60]))
    return issues

def check_process_words(body):
    """检测成品报告中的过程性字样（SOP 硬性要求：正文禁止"第 N 轮/迭代/更新"等过程字样）。

    匹配：R 轮次（如 R1-R9，含括注形式）、第 N 轮、本轮/上一轮/下一轮、通道 X（检索通道标记）
    等迭代/流程过程标记。
    不匹配：URL 中的字母段（英文 R 数字用单词边界保证，如 4RUO50eR9Gh 不误报）、
    技术名词"迭代/更新"（如算力迭代/数据更新）、"通道"的其他技术含义（如电离通道/信道）。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if re.search(r"[\[（(]\s*R\d+\s*[-–—]?\s*R\d+\s*[\]）)]", stripped) or \
           re.search(r"\bR\d+\b\s*收|收敛\s*[：:（(]?\s*R\d|第\s*\d+\s*轮", stripped) or \
           "本轮" in stripped or "上一轮" in stripped or "下一轮" in stripped or \
           re.search(r"通道\s*[A-Z]", stripped):
            issues.append((i, "过程性字样", "R轮次/第N轮/本轮/通道X", stripped[:60]))
    return issues

# 成品报告实现过程残留词：正文禁止泄露"用什么语言/脚本/正则做的验证"或
# 指向内部过程记录文件。这些是实现细节，属内部研究过程（落 process_notes），
# 不得写进成品正文（对读者无信息量，且暴露工作手法）。
# 数学术语「正则」(regular) 不作为独立词拦截，仅拦「正则替换/匹配/提取/表达式/解析」
# 等工具实现用法，避免与数学含义冲突。
IMPL_RESIDUE_WORDS = [
    "纯 Python", "纯Python",
    "过程记录", "过程文件", "过程笔记", "见过程", "详见过程", "过程文档",
    "验证脚本", "脚本验证", "跑脚本", "用脚本", "脚本跑",
    "正则替换", "正则匹配", "正则提取", "正则表达式", "用正则", "正则解析",
    "临时文件", "草稿版",
    # 检索/来源过程痕迹：多源交叉验证、来源分级括注（一手/二手/口径）、
    # 预印本标注——均为研究过程描述，落 process_notes，成品正文禁止
    "多源交叉", "多源一致", "多源印证", "多源对照", "多源互证",
    "一手表述", "一手来源", "一手访谈", "一手记录", "一手数据", "一手材料",
    "二手转述", "二手数据", "二手来源",
    "口径标注", "口径一致", "口径对比", "仅媒体口径",
    "arXiv 预印本", "arXiv预印本",
]

def check_impl_residue(body):
    """检测成品报告正文中的实现过程残留（用什么语言/脚本/正则做的验证，
    或指向内部过程记录文件）。这些是实现细节，属内部研究过程，落 process_notes，
    不得写进成品正文（SOP：成品只陈述事实与结论）。

    匹配：
    - 裸 Python（大小写不敏感、词边界）：成品报告不应出现实现语言；
    - 纯 Python / 过程记录(文件/笔记) / 见过程 / 验证脚本 / 跑脚本 / 正则替换(匹配/
      提取/表达式/解析) / 临时文件 / 草稿版 等显式残留词。
    不匹配：引号内引述（《》/""/『』，check_words 同源豁免）、
    参考文献区（scan_body 已分离）、数学术语「正则」(仅拦工具用法组合)。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        # 引文豁免：书名号《》、弯引号""、方引号『』内为引述，不算本人实现残留
        stripped = re.sub(r"[《「『][^》」』]*[》」』]", "", line)
        stripped = re.sub(r"[\u201c\u2018][^\u201d\u2019]*[\u201d\u2019]", "", stripped)
        stripped = re.sub(r'"[^"]*"', "", stripped)
        # 裸 Python（大小写不敏感，词边界）——成品正文禁泄露实现语言
        if re.search(r"(?i)\bpython\b", stripped):
            issues.append((i, "实现过程残留", "Python（成品正文禁泄露实现语言）", line.strip()[:60]))
            continue
        for w in IMPL_RESIDUE_WORDS:
            if w in stripped:
                issues.append((i, "实现过程残留", w, line.strip()[:60]))
                break
    return issues

def check_turn_pattern(body):
    """：检测"不是……，是/而是……"转折句式（典型 AI 语言，用户禁止）。

    按行检测：行内含"不是"且其后 25 字内出现"而是/是/只是"承接转折。
    不误报：独立否定（"不是所有领域都有 1 万小时阈值"无承接转折）、图片行/表格行、
    跨句（句末标点截断）、URL。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("![") or stripped.startswith("|"):
            continue
        if "不是" in stripped and re.search(
            r"不是[^。！？]{1,25}[，,。]?(而?是|只是)", stripped
        ):
            issues.append((i, "AI转折句式", "不是…是/而是…（禁止）", stripped[:60]))
    return issues

def check_ai_phrases(body):
    """：检测典型 AI 腔句式（之所以…是因为 / 随着…发展 / 在…的背景下 / 可以看出 等）。

    按行正则匹配；图片行/表格行跳过。启发式，命中需人工确认。
    """
    patterns = [
        (r"之所以[^。！？]{1,20}是因为", "AI因果句式（之所以…是因为）"),
        (r"随着[^。！？，,]{1,12}(的发展|的到来|的推进|的普及|的深入|升级)", "AI背景套路（随着…发展）"),
        (r"在[^。！？，,]{1,12}的背景下|在此背景下", "AI背景套路（在…的背景下）"),
        (r"在[^。！？，,]{1,8}时代", "AI背景开场（在 XX 时代）"),
        (r"可以(看|得)出|由此可见|不难看出", "AI结论词（可以看出/由此可见）"),
    ]
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("![") or stripped.startswith("|"):
            continue
        for pat, label in patterns:
            if re.search(pat, stripped):
                issues.append((i, label, "禁止", stripped[:60]))
                break
    return issues

def check_paragraph_len(body):
    """：叙述性段落超长检查（STYLE_GUIDE：每段 ≤4-5 行，知乎扫读友好）。

    按空行分段；跳过列表块/表格/标题/图片块（非叙述段）；参考文献区之后不计。
    """
    head = strip_display_math(body.split("## 参考文献")[0])
    paras, cur = [], []
    for line in head.splitlines():
        s = line.rstrip()
        if not s.strip():
            if cur:
                paras.append(cur)
                cur = []
            continue
        cur.append(s)
    if cur:
        paras.append(cur)
    issues = []
    for idx, p in enumerate(paras, 1):
        # 列表/表格/标题/图片行所在段落跳过；有序列表（1. / 1、）同样跳过（不报段落过长）
        if any(l.lstrip().startswith(("-", "*", "|", "#", "!["))
               or re.match(r"^\s*\d+[.、]", l) for l in p):
            continue
        if len(p) > 5:
            issues.append((idx, "段落过长", f"{len(p)} 行 > 5 行（建议拆分）", p[0][:50]))
    return issues

def check_para_points_eligible(body):
    """长段落「建议分点」启发式（能用 1. 2. 3. 分点就用）。

    并列多条同类信息（规格条目/能力清单/分项结果等）应优先用 1. 2. 3. 有序列表，
    禁止写成"第一……第二……"式长段落。机器无法可靠判断"是否并列"，故只做提示级：
    单叙述段字符数超过阈值（默认 300）且无任何分点/表格结构时提示人工复核——
    连续因果/演化逻辑链（推导过程、事件演化）仍允许文字叙述，不阻断。

    返回 (提示列表, 跳过标志)：跳过（非叙述段/已分点/表格段）时返回 ([], True)。
    """
    head = strip_display_math(body.split("## 参考文献")[0])
    paras, cur = [], []
    for line in head.splitlines():
        s = line.rstrip()
        if not s.strip():
            if cur:
                paras.append(cur)
                cur = []
            continue
        cur.append(s)
    if cur:
        paras.append(cur)
    issues = []
    for idx, p in enumerate(paras, 1):
        # 非叙述段跳过：表格/标题/图片/列表/有序列表/代码块
        if any(l.lstrip().startswith(("-", "*", "|", "#", "![", "```"))
               or re.match(r"^\s*\d+[.、]", l) for l in p):
            continue
        n_chars = sum(len(l) for l in p)
        if n_chars > 300:
            issues.append((idx, "长段落建议分点",
                           f"{n_chars} 字符：并列信息建议用 1. 2. 3. 分点或表格（因果链可保留叙述）",
                           p[0][:50]))
    return issues

def check_title_paren(body):
    """检测标题行含括号（SOP 硬性要求：标题不带括号，数据分级/来源等说明只放正文）。

    匹配：以 # 开头的标题行，行内任意位置含中文/英文括号。
    不匹配：正文行、参考文献行（[标题](url) 不是标题行）。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if line.startswith("#") and not line.startswith("#!"):
            if re.search(r"[（(]", line):
                issues.append((i, "标题含括号", "标题不应带（来源/口径）等说明", line.strip()[:60]))
    return issues

def check_title_len(body):
    """检测 H1 报告标题超长（报告标题 ≤30 字符）。

    只针对首行 H1（# 开头）；小节标题（###）与参考文献标题（##）不在此列。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if line.startswith("# "):
            title = line[2:].strip()
            if len(title) > 30:
                issues.append((i, "标题超长", f"H1 标题 {len(title)} 字符 > 30 上限", title[:60]))
            break  # 只查首个 H1
    return issues

def check_title_asterisk(body):
    """检测标题/小标题行使用 * 作为标题标记（flomo 笔记规范：标题一律纯文本，禁止 #/* 标记）。

    命中两类：
    1. markdown 标题行（以 # 开头）含 *（如 "**## 标题**" "*### 小标题*" "## 标题 *强调*"）；
    2. 整行被 * 包裹且较短（≤60 字符），视作用 * 充当标题标记（如 "*标题*" "**标题**"）。
    不匹配：正文行内 * 强调、bullet 列表项（-/* 后带空格）、表格行、长段落。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        # bullet 列表行（* / - / + 后带空格）不视为标题行
        if re.match(r"^[\*\-\+]\s+\S", stripped):
            continue
        # 表格行跳过
        if stripped.startswith("|"):
            continue
        # 1) markdown 标题行含 *
        if re.match(r"^#{1,6}\s+\S", stripped) and "*" in stripped:
            issues.append((i, "标题用*标记", "标题应用 #/##/###，禁止用 * 强调代替", stripped[:60]))
            continue
        # 2) 整行被 * 包裹且较短（标题式强调，非正文斜体）
        if re.match(r"^\*+[^\*].*\*+\s*$", stripped) and len(stripped) <= 60:
            issues.append((i, "标题用*标记", "整行 * 包裹视作标题标记，改用 #/##/###", stripped[:60]))
    return issues


def check_title_hash(body):
    """检测笔记标题行使用 # markdown 标题标记（flomo 笔记规范：仅首行 tag 行允许 #，
    大小标题一律用纯文本，禁止 #/##/### 层级标记）。

    命中：任何以 # 开头后接空白的标题行（如 "## 标题" "### 小标题" "# 标题"）。
    不匹配：首行 tag 行 "#技术 #AI"（# 后直接跟非空白字符，是 flomo 标签，非标题行）。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        # bullet 列表行（* / - / + 后带空格）不视为标题行
        if re.match(r"^[\*\-\+]\s+\S", stripped):
            continue
        # 表格行跳过
        if stripped.startswith("|"):
            continue
        # markdown 标题行：# 后接空白 + 内容（tag 行 #技术 的 # 后无空白，不命中）
        if re.match(r"^#{1,6}\s+\S", stripped):
            issues.append((i, "标题用#标记", "笔记标题禁止用 #/##/###，改为纯文本", stripped[:60]))
    return issues


def check_citation_correspondence(full, note_mode=False):
    """检测参考文献条目与正文 [n] 引注一一对应（flomo 上传质检，笔记模式强制）。

    顺序编码制规则（不能少、不能多、须一一对应）：
    1. 参考文献区每条 [n] 须在正文出现 [n] 引注（文献未被引用即报错）；
    2. 正文每个 [n] 引注须有对应文献条目（悬空引注即报错）；
    3. 二者编号集合须完全一致。

    以「来源:」「参考文献:」（笔记）或「## 参考文献」（报告）为界划分正文/文献区，
    文献区自身的 [n] 条目不计入正文引注。无参考文献区时返回 []（不触发）。
    """
    if note_mode:
        m = re.search(r"(?:^|\n)\s*(?:来源|参考文献)[:：]?\s*$", full, re.MULTILINE)
    else:
        m = re.search(r"(?:^|\n)\s*#{1,6}\s*参考文献\s*$", full, re.MULTILINE)
    if not m:
        return []
    head = full[:m.start()]
    ref_sec = full[m.end():]
    ref_nums = set(int(x) for x in re.findall(r"^\[(\d+)\]", ref_sec, re.MULTILINE))
    cite_nums = set(int(x) for x in re.findall(r"\[(\d+)\]", head))
    issues = []
    missing = sorted(ref_nums - cite_nums)
    orphan = sorted(cite_nums - ref_nums)
    if missing:
        issues.append((0, "文献未被引用",
                       f"参考文献 {missing} 未在正文标注 [n] 引用（须一一对应，不能少）", ""))
    if orphan:
        issues.append((0, "引用无对应文献",
                       f"正文 [n] {orphan} 无对应参考文献条目（须一一对应，不能多）", ""))
    return issues

def check_judgment_hints(body):
    """检测提示性套话（SOP 硬性要求：成品不出现"判断权留给读者"等元话语提示词）。

    匹配：判断权留给读者 / 判断权留给你 / 判断权交给读者 等变体。
    说明：结论仍可用事实映射句式（"若 X 指 A，事实是 B；若指 C，事实是 D"），
    但不得加"判断权留给读者："这类元话语前缀。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if "判断权留给读者" in line or "判断权留给你" in line or "判断权交给读者" in line:
            issues.append((i, "提示性套话", "判断权留给读者", line.strip()[:60]))
    return issues

def check_meta_discourse(body):
    """检测元话语自称（成品禁"本报告/本文"等反复自称）。

    匹配：本报告 / 本文 出现在正文（成品不应以"本报告"自称，
    改"以下/此处/上述"或直接叙述）。
    不匹配：引用他人"《…报告》"或"该报告/既有报告"（他指）。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if "本报告" in line or "本文" in line:
            issues.append((i, "元话语自称", "本报告/本文", line.strip()[:60]))
    return issues

def check_internal_refs(body):
    """检测内部工具标识泄漏（成品禁"flomo/内部笔记/信号笔记"等来源标识）。

    匹配：flomo / 内部笔记 / 信号笔记 / gathered_ / verify_*.py 出现在正文或参考文献；
    以及六通道检索过程痕迹词：智慧芽 / 企查查 / 通达信 /
    产业无对应 / 无适用主体 / 无约定主题布局——C 通道"无命中"是内部研究记录，
    落 process_notes 与进度文件，禁止写进正文（对读者无信息量）。
    说明：成品报告引用须为公开来源；内部素材（flomo 笔记/检索记录/验证脚本）不入成品，
    改为引用其对应的公开出处或删除（验证脚本只留存研究目录，不写入正文）。
    """
    issues = []
    internal_words = ["flomo", "内部笔记", "信号笔记", "gathered_",
                      "智慧芽", "企查查", "通达信", "产业无对应", "无适用主体", "无约定主题布局"]
    internal_re = re.compile(r"verify_[\w-]+\.py", re.I)
    for i, line in enumerate(body.splitlines(), 1):
        for w in internal_words:
            if w.lower() in line.lower():
                issues.append((i, "内部标识", w, line.strip()[:60]))
                break
        else:
            m = internal_re.search(line)
            if m:
                issues.append((i, "内部标识", m.group(0), line.strip()[:60]))
    return issues

def check_grade_paren(body):
    """检测正文分级词括注（正文禁止"（一手/二手/推算）"等数据强度括注）。

    匹配：括号内含 一手/二手/推算/推断/观点类/分析性推断 等数据强度分级词。
    不匹配："日本二手设备"（物理含义）、"单一手段"（相邻字误匹配——用括号限定）、
    表格"证据强度"列（| 官方 | 等已改中性词）。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if re.search(r"[（(][^（）()]*(?:一手|二手|推算|推断|观点类|分析性推断)[^（）()]*[）)]", line):
            issues.append((i, "分级词括注", "（一手/二手/推算）", line.strip()[:60]))
    return issues

def check_evidence_grade(body):
    """检测证据分级表述（用户要求：正文不写"证据较强/证据中等/证据强度"等分级词）。

    匹配：证据较强/证据中等/证据较弱/证据强度 等字面（含"证据强度不同"引导句）。
    不匹配："证据"单独使用（"反方证据""证据链"为正常表述）。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if re.search(r"证据(较强|中等|较弱|强度)", line):
            issues.append((i, "证据分级词", "证据较强/证据强度（禁止）", line.strip()[:60]))
    return issues

def check_stock_info(body):
    """检测 A 股行情信息（用户要求：报告禁止提及股票代号、股价等 A 股信息）。

    匹配三类：
    1. 股票代码：行内 6 位纯数字且前后非年份/金额（如 603986、301308、688525），
       常见 A 股代码段前缀（60/00/30/68/83/87）提高命中率；
    2. 股价行情词：现价/收盘价/涨跌幅/涨停/跌停/总市值/流通市值/PE(TTM)/市盈率
       等字段 + 行内含数字；
    3. 行情表格：表头含"代码|名称|现价"组合。
    不匹配：年份（2026）、普通大数（2828 亿无代码形态）、"代码"泛指。
    """
    issues = []
    code_re = re.compile(r"(?<![0-9A-Za-z])(60[0-9]{4}|00[0-9]{4}|30[0-9]{4}|68[0-9]{4}|83[0-9]{4}|87[0-9]{4})(?![0-9A-Za-z])")
    # 注：A 股代码为 6 位数字（600519/000001/300750 等）；5 位数字（30000 等）不匹配。
    # "涨停/跌停"为基金/期货/股票通用交易描述，非 A 股特有行情字段，不拦截。
    quote_words = ["收盘价", "涨跌幅", "总市值", "流通市值", "PE(TTM)", "市盈率", "换手率"]
    for i, line in enumerate(body.splitlines(), 1):
        has_digit = bool(re.search(r"\d", line))
        if code_re.search(line):
            issues.append((i, "A股行情信息", "股票代码（报告禁止提及 A 股代码）", line.strip()[:60]))
            continue
        # "现价"须后跟数字才判为股价（避免"兑现价值"等词语误报）
        if re.search(r"现价\s*[0-9０-９]", line):
            issues.append((i, "A股行情信息", "现价（报告禁止提及股价）", line.strip()[:60]))
            continue
        if has_digit and any(w in line for w in quote_words):
            issues.append((i, "A股行情信息", "股价/市值等行情字段（报告禁止）", line.strip()[:60]))
            continue
        if "代码" in line and "现价" in line and "名称" in line:
            issues.append((i, "A股行情信息", "行情表格（代码/现价列）", line.strip()[:60]))
    return issues

# 数学公式特征 Unicode 字符：report.md 数学内容必须用 LaTeX $...$（知乎渲染）
# 与 docx OMML 通道（report_to_docx.py）配合，禁止 Unicode 手写公式。仅数学符号（非标点）纳入；§、——等常用标点不拦。
MATH_UNICODE_CHARS = "√∫∥∮∑∏⊕⊗⟨⟩∪∩∅⊂⊃⊆⊇∈∉∀∃∂∇∞≈≠·½¼¾₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹⁻ᶻᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ⁺⁻⁼⁽⁾πΣΘΦΨΩαβγδεζηθλμξρστφχω"

def check_math_formula(body):
    """检测数学公式是否用 LaTeX 书写（md 公式一律 $...$ LaTeX，
    docx 由 report_to_docx.py 转 OMML；禁止 Unicode 手写公式）。

    判定：正文行内 $...$ 包裹之外的数学特征字符（√∫∥∑⊕⊗∈等）即报"Unicode 手写公式"。
    表格数据行（^| 开头）：**表格内禁公式**——表格单元格内出现 $...$ 或数学 Unicode 字符即报"表格内公式"，
    涉及公式的内容一律 LaTeX 正文叙述，表格只承载不涉及公式的文字对比。
    豁免：
    - 参考文献区（仅检查正文部分，scan_body 已分离 body）；
    - 图表引用行（![...](...)）；
    - 表格分隔行（|---|）；
    - 常用非数学用法：± 单独使用（公差语义）、× 用于中文数词搭配（如"1×1"仍属数学
      判定，但"人×天"类非数学量纲搭配不拦——按出现数学邻域综合判断）。
    """
    issues = []
    # 单字符逐个出现且周围非中文语境的多字符组合判定：避免"（≤5 个）"等中文句误报
    for i, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("!["):
            continue
        if re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", line):
            continue
        if line.strip().startswith("|"):
            # 表格数据行：涉及公式的内容不得表格化
            if "$" in line:
                issues.append((i, "表格内公式", "涉及公式的内容用 LaTeX 正文叙述，不制作表格", line.strip()[:60]))
            else:
                hits = [ch for ch in MATH_UNICODE_CHARS if ch in line]
                if hits:
                    issues.append((i, "表格内公式", "涉及公式的内容用 LaTeX 正文叙述，不制作表格",
                                   line.strip()[:60] + f"  → 命中: {''.join(sorted(set(hits)))[:12]}"))
            continue
        # 找出 $...$ 片段并剔除
        stripped = re.sub(r"\$[^$]*\$", "", line)
        if not stripped:
            continue
        # 人名间隔号豁免：中文/字母人名中的 ·（"迈克尔·克拉西奥斯""爱伦·坡"）非数学符号
        stripped = re.sub(r"[\u4e00-\u9fffA-Za-z]·[\u4e00-\u9fffA-Za-z]", "", stripped)
        hits = [ch for ch in MATH_UNICODE_CHARS if ch in stripped]
        if hits:
            issues.append((i, "Unicode手写公式", "数学公式须用 LaTeX $...$（禁止 Unicode 手写）",
                           line.strip()[:60] + f"  → 命中: {''.join(sorted(set(hits)))[:12]}"))
    return issues

# 转述体检测（发链接/文章/论文 = 提炼概念，正文以概念为主体，
# 禁止"解读 XX 的文章/博客"式转述——来源交代只放参考文献区）。
# 匹配把来源材料当叙述主语的句子（"XX 博客/文章/论文/姊妹篇/研究 + 解读/价值/处理/讲/说/介绍"）。
TRANSLATION_PATTERNS = [
    r"以下解读[^。；\n]{0,30}(博客|文章|论文|姊妹篇|研究)",
    r"(博客|文章|论文|姊妹篇|研究)[^。；\n]{0,10}的价值在于",
    r"(博客|文章|论文|姊妹篇|研究)[^。；\n]{0,15}(处理|讨论|提出|给出)[^。；\n]{0,15}相反问题",
    r"这篇(博客|文章|论文)[^。；\n]{0,15}(讲了|介绍了|解读了|研究)",
]

def check_translation_voice(body):
    """检测转述体/汇报腔（正文叙述主体必须是概念/事件本身，
    不得把来源材料（链接/博客/论文）当主语）。

    判定：正文行命中把来源材料当叙述主语的句式（"以下解读 XX 的博客""XX 文章的价值
    在于""这篇论文讲了"）即报"转述体"。豁免：参考文献区（scan_body 已分离）；
    "解读/转述"作定语修饰数据来源（如"媒体转述数字"）不拦——按句式上下文判断。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("!["):
            continue
        for pat in TRANSLATION_PATTERNS:
            m = re.search(pat, line)
            if m:
                issues.append((i, "转述体", "正文以来源材料为主语（概念为主体，来源归参考文献区）",
                               line.strip()[:60] + f"  → 命中: {m.group(0)[:20]}"))
                break
    return issues

# 无主语开头检测：句首禁止裸"这篇/该篇/本篇/此篇"等指代词，
# 必须紧跟"论文/文章/报告/研究/笔记"等实体名词才构成主语。
SUBJECTLESS_OPENERS = ("这篇", "该篇", "本篇", "此篇")
SUBJECT_NOUN_PREFIXES = (
    "论文", "文章", "报告", "研究", "工作", "笔记", "文档", "文件",
    "博客", "帖子", "回答", "方法", "结果", "结论", "定理",
    "章节", "部分", "内容", "成果", "案例", "数据", "理论", "模型",
    "策略", "方案", "版本", "作品", "课题", "项目", "分析", "问题",
    "现象", "过程", "机制", "规律", "视角", "思路", "观点", "线索",
    "素材", "来源", "标题", "特点", "性质", "特征", "系列", "类型",
    "方向", "领域", "结构", "框架", "实验", "代码", "公式", "定义",
    "命题", "推论", "引理", "附录", "文献", "综述", "专著", "教材",
)

SUBJECTLESS_OPENER_RE = re.compile(
    r"(^|[。！？\n])\s*(" + "|".join(SUBJECTLESS_OPENERS) + r")"
    r"(?!(" + "|".join(SUBJECT_NOUN_PREFIXES) + r"))"
)

def check_subjectless_openers(body):
    """检测句首无主语的裸指代（"这篇/该篇/本篇/此篇"后未接实体名词）。

    判定：句首（行首或句号/问号/感叹号后）出现"这篇"等，且后面不是
    "论文/文章/报告/研究/笔记"等名词，即报"无主语开头"。
    豁免："这篇论文""这篇文章"等带实体名词的完整主语。
    """
    issues = []
    for m in SUBJECTLESS_OPENER_RE.finditer(body):
        line_no = body[:m.start()].count("\n") + 1
        seg = body[m.start():m.start() + 40].replace("\n", " ")
        issues.append((line_no, "无主语开头",
                       "句首禁用裸“这篇/该篇/本篇/此篇”（须接论文/文章/报告等实体名词）",
                       seg[:60]))
    return issues

# 编号定理/定义/命题/引理等必须能在正文追溯到出处，否则读者无法判断是哪篇文献的编号。
NUMBERED_LABEL_RE = re.compile(
    r"(?<![\u4e00-\u9fffA-Za-z])"
    r"(?:Theorem|Definition|Proposition|Lemma|Corollary|Remark|Assumption|Conjecture|Example"
    r"|定理|定义|命题|引理|推论|注记|假设|猜想|例)\s*"
    r"(\d+(?:\.\d+)*|[A-Z](?:[A-Za-z0-9]*)?)"
)
ATTRIBUTION_SOURCE_MARKERS = ("arxiv:", "arxiv.org", "arXiv:", "arXiv 全文", "arxiv/abs", "《")

def check_source_attribution(body):
    """检测正文中的编号定理/定义/命题是否可追溯到出处。

    判定：正文出现 "Theorem 1.1 / Definition 3.14 / 定理 2.1" 等编号，
    但正文没有任何显式来源标记（arXiv 链接、arXiv 全文、中文书名号《》），
    即报"来源标注缺失"。
    说明：文末参考文献编号 [n] 不算正文显式出处；正文必须先说明
    "这些编号出自哪篇文献/哪本书"。
    """
    if any(marker in body for marker in ATTRIBUTION_SOURCE_MARKERS):
        return []
    issues = []
    for m in NUMBERED_LABEL_RE.finditer(body):
        # 计数语境过滤：「1000 例 0 不符 / 400 例」中"例"是量词（案例/个例），
        # 前 8 字符内出现数字即视为计数，非编号标签——transversal 系列命中案例。
        if m.group(0).startswith("例") and re.search(r"\d[\s　]*$",
                                                    body[max(0, m.start() - 8):m.start()]):
            continue
        line_no = body[:m.start()].count("\n") + 1
        seg = body[m.start():m.start() + 40].replace("\n", " ")
        issues.append((line_no, "来源标注缺失",
                       "编号定理/定义/命题须在正文注明出处（arXiv 链接、arXiv 全文或《题名》）",
                       seg[:60]))
    return issues



def extract_conclusion(full):
    """提取 H1 标题后的无标题结论段（位于首个 heading 之前）。

    结论段定义：紧跟 H1 标题、且位于首个 heading（## 或 ###）之前的连续
    段落。若该区域不存在（H1 后首行即为标题），返回 ("", False) 表示结论段
    被标题占用/缺失——交由 check_report_structure 报硬伤，此处不重复报。

    修订：原正则 `^# [^\\n]*\\n\\n(.*?)(?=^##\\s|$)` 在 `## 结论` 紧贴标题时
    捕获到空文本，导致"结论过长/分点"检查全部空跑通过（本次缺口根因）。
    改为显式定位 H1 后首个非空内容，非标题才视为结论段。
    """
    m = re.search(r"^#\s+[^\n]*\n(.*)$", full, re.S)
    if not m:
        return ("", False)
    rest = re.sub(r"^\s*\n", "", m.group(1))
    if re.match(r"^#{1,6}\s+", rest):
        return ("", False)
    end_m = re.search(r"^#{1,6}\s+", rest, re.M)
    concl = rest[:end_m.start()] if end_m else rest
    concl = concl.strip()
    # 结论为单段：取首个空行之前
    para = re.split(r"\n\s*\n", concl, 1)[0].strip()
    return (para, True)


def check_conclusion_len(full):
    """检测结论章节篇幅（结论控制在 300 字符内，含标题）。

    结论应为事实归并的浓缩，一两句话点明最终判断；过长说明把正文内容
    重复了一遍；如确实需要更多要点，应精简句式而非堆叠。核心要素
    （最终判断/关键数字/方法名）不得为压缩而删除。
    """
    issues = []
    text, ok = extract_conclusion(full)
    if not ok:
        return issues  # 缺失/被标题占用由 check_report_structure 报硬伤
    length = len(text)
    if length > 300:
        issues.append((0, "结论过长", f"结论 {length} 字符 > 300 上限", f"结论章节 {length} 字符"))
    return issues

def check_conclusion_style(full):
    """检测结论章节格式（结论应为一段式总述，禁止分点列条；禁止分层帽子词）。

    匹配：结论章节内出现以 - 或 * 开头的列表行（分点式结论）；
    或以"XX层面，/XX端，/XX方面，/XX上，"开头的分层骨架句式。
    说明：结论是对上述报告的一段自然叙事式事实归并，不以 bullet 或
    "层面/端/方面"分层罗列；信息用分号在段落内串联。
    """
    issues = []
    text, ok = extract_conclusion(full)
    if not ok:
        return issues
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if re.match(r"^\s*[-*]\s+", stripped):
            issues.append((i, "结论分点", "结论应一段式总述，禁分点", stripped[:60]))
        elif re.match(r"^[^，。；]{1,8}层面[，,]|^[^，。；]{1,8}端[，,]|^[^，。；]{1,8}方面[，,]|^[^，。；]{1,8}上[，,]", stripped):
            issues.append((i, "结论分层", "结论禁'XX层面/端/方面'分层骨架", stripped[:60]))
    return issues

def check_cross_ref(body):
    """检测旧式编号交叉引用有效性（正文"见 2.x / 2.x 节 / 2.x/2.y 节"必须指向存在的编号小节）。

    只匹配明确的旧式编号引用："见 2.5"、"2.5 节"、"2.5/2.6 节"；
    不匹配："Industry 5.0"、"4IR/5IR"等版本号/产品名（无"见"前导且无"节"后缀）。
    当前无编号小节报告不使用此规则；标题类交叉引用由人工核对。
    """
    issues = []
    exist = set(re.findall(r"^###\s*(\d\.\d+)\b", body, re.M))
    pat = re.compile(r"(?:见\s*|\s+)?(\d\.\d+)(?:/(\d\.\d+))?\s*节")
    for i, line in enumerate(body.splitlines(), 1):
        refs = set()
        for m in pat.finditer(line):
            refs.add(m.group(1))
            if m.group(2):
                refs.add(m.group(2))

        for m in re.finditer(r"见\s*(\d\.\d+)", line):
            refs.add(m.group(1))
        for r in refs:
            if r not in exist:
                issues.append((i, "交叉引用错误", f"引用 {r} 但该小节不存在", line.strip()[:60]))
    return issues

def check_fact_section_budget(body):
    """检测正文小节内的小点是否未叙述化（用户要求"每个小点不要单行"）。

    仅检查小节内是否存在 bullet 单行（`- ` 行）；小节数量不再设上限。
    表格（`|` 行）是唯一允许的列表形式。
    """
    issues = []

    sec_pat = re.compile(r"^###\s+", re.M)
    secs = [(i, m.start()) for i, m in enumerate(sec_pat.finditer(body), 1)]
    if not secs:
        return issues

    m2 = re.search(r"^#\s+[^\n]*\n", body, re.M)  # H1 标题后起
    m3 = re.search(r"^##\s*参考文献", body, re.M)
    if not m2:
        return issues
    end = m3.start() if m3 else len(body)

    for i, (num, pos) in enumerate(secs):
        nxt = secs[i + 1][1] if i + 1 < len(secs) else end
        seg = body[pos:nxt]

        # 排除表格行（| 开头）和表格分隔行（|---|），只检测真正的 bullet（- 开头）
        bullets = [ln for ln in seg.splitlines()
                   if re.match(r"^\s*-\s+\S", ln)
                   and not re.match(r"^\s*\|", ln)]
        if bullets:
            issues.append((0, "小点未叙述化", f"第{num}节有 {len(bullets)} 条 bullet 单行——小点须写成连贯叙述段（表格行不受此检查限制）",
                           "bullet 单行"))
    return issues

def check_structure(body, full, note_mode=False):
    """结构完整性检查：
    1. 必须存在参考文献章节且含至少 1 条可溯源条目（GB/T 编号 / [标题](url) / 纯文本标题；SOP 硬性要求：纯事实报告可溯源）。
       笔记模式：文献段仅认「参考文献:」（「来源:」为非规定字段，禁止）。
    2. 正文不得残留未决占位标记（TODO/待补充/待填写/此处填写 等；"仍无法核实"为合法口径标注，不在此列）。
    """
    issues = []
    markers = NOTE_REF_MARKERS if note_mode else REF_MARKERS
    start = None
    for marker in markers:
        idx = full.find(marker)
        if idx != -1:
            start = idx
            break
    if start is None:
        issues.append((1, "结构完整性", "缺少参考文献章节（## 参考文献），报告无法溯源", ""))
    else:
        section = full[start:]
        ref_lines = [ln for ln in section.splitlines() if ln.strip()]

        link_count = sum(1 for ln in ref_lines
                         if re.search(r"\[[^\]]+\]\([^)]+\)", ln)
                         or re.match(r"^\d+[.、]\s*\S", ln)
                         or re.match(r"^[-*]\s*\S", ln)
                         or re.match(r"^\[\d+\]\s*\S", ln))  # GB/T 7714-2015 国标条目 [n] 责任者. 题名[M]...
        if link_count == 0:
            issues.append((1, "结构完整性", "参考文献章节为空或条目非 GB/T 编号/[标题](url)/纯文本标题格式", ""))
    for i, line in enumerate(body.splitlines(), 1):
        if re.search(r"(TODO|FIXME|待补充|待填写|待填|此处填写)", line):
            issues.append((i, "未决标记", "待补充/TODO 类残留", line.strip()[:60]))
    return issues

def resolve_target(argv, tool_name, extra_usage=""):
    """解析 --file / --slug（互为别名）。

    质检工具此前参数不统一（本工具与 check_report_structure 只认 --file，
    check_progress 只认 --slug），调用时极易传错而报"用法"。
    此处双向兼容：--slug <slug> 等价于 --file research/<slug>/report.md。
    """
    filepath = None
    if "--file" in argv:
        idx = argv.index("--file")
        if idx + 1 < len(argv):
            filepath = argv[idx + 1]
    if not filepath and "--slug" in argv:
        idx = argv.index("--slug")
        if idx + 1 < len(argv):
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            filepath = os.path.join(root, "research", argv[idx + 1], "report.md")

    if not filepath or not os.path.exists(filepath):
        print(f"用法: python tools/{tool_name} (--file <文件> | --slug <slug>){extra_usage}")
        if filepath:
            print(f"  [错误] 文件不存在: {filepath}")
        sys.exit(1)
    return filepath


def main():
    argv = sys.argv[1:]
    verbose = "--verbose" in argv
    filepath = resolve_target(argv, "quality_check.py", " [--verbose]")
    note_mode = is_note_file(filepath)

    body, full = scan_body(filepath, note_mode=note_mode)
    if not body.strip():
        print(f"[跳过] {filepath}: 未找到正文（可能为空或全为来源区）")
        sys.exit(0)

    all_issues = []
    all_issues += check_words(body, STANCE_WORDS, "立场词")
    all_issues += check_words(body, FRAMEWORK_WORDS, "框架词")
    all_issues += check_words(body, EVALUATIVE_WORDS, "评价词")
    if note_mode:
        # 笔记模式（笔记用 Unicode、报告用 LaTeX）：
        # 笔记是内部研究记录（flomo 私人知识库），非发布成品，跳过面向报告成品的
        # 规范检查——标题/结论/小节/图片/LaTeX 公式规则不适用笔记；过程性字样
        # （笔记记录检索过程）、元话语自称（笔记引论文的"本文/前作"）、感叹号
        # （Unicode 公式中 k! 阶乘无 $ 保护易误报）均为笔记常态，一并跳过。
        # 标题禁止用 * 与 # 标记（flomo 上传质检要求，独立于报告标题检查规则）。
        # 笔记仅首行 tag 行允许 #，大小标题一律纯文本，禁止 #/##/### 与 * 标记。
        all_issues += check_title_asterisk(body)
        all_issues += check_title_hash(body)
        # 非规定字段（来源/概念等）一律禁止——来源只能以 GB/T 条目进「参考文献:」区
        all_issues += check_note_forbidden_fields(body)
        # 参考文献条目与正文 [n] 引注须一一对应（不能少、不能多）
        all_issues += check_citation_correspondence(full, note_mode=True)
    else:
        all_issues += check_exclamation(body)
        all_issues += check_process_words(body)
        all_issues += check_impl_residue(body)
        all_issues += check_meta_discourse(body)
        all_issues += check_title_paren(body)
        all_issues += check_title_len(body)
        all_issues += check_math_formula(body)
        all_issues += check_conclusion_len(full)
        all_issues += check_conclusion_style(full)
        all_issues += check_cross_ref(body)
        all_issues += check_caption_sequence(body)
        all_issues += check_cover_ban(body)
        all_issues += check_image_continuity(body)
        all_issues += check_fact_section_budget(body)
        # 段落长度限制（每段 ≤4-5 行 / 单段 ≤300 字符建议分点）是报告发布规则
        # （知乎扫读友好），笔记为内部研究素材、文末有整篇来源区，不适用——仅在报告模式检查。
        all_issues += check_paragraph_len(body)
        all_issues += check_para_points_eligible(body)
    all_issues += check_unsourced_numbers(body, full)
    all_issues += check_placeholders(body)
    all_issues += check_turn_pattern(body)
    all_issues += check_ai_phrases(body)
    all_issues += check_judgment_hints(body)
    all_issues += check_internal_refs(body)
    all_issues += check_grade_paren(body)
    all_issues += check_evidence_grade(body)
    all_issues += check_stock_info(body)
    all_issues += check_translation_voice(body)
    all_issues += check_subjectless_openers(body)
    all_issues += check_source_attribution(body)
    all_issues += check_references(full, note_mode=note_mode)
    # 参考文献区禁止 LaTeX（报告与笔记均适用——GB/T 著录为纯文本格式）
    all_issues += check_ref_latex_ban(full, note_mode=note_mode)
    all_issues += check_structure(body, full, note_mode=note_mode)

    print("=" * 60)
    print(f"正文质量自动检查: {filepath}")
    print("=" * 60)

    if not all_issues:
        print("全部通过：未检测到立场词/框架词/评价词/感叹号/参考文献标注。")
        print("说明：数字溯源与逻辑终审仍需人工复核。")
        sys.exit(0)

    by_type = {}
    for item in all_issues:
        by_type.setdefault(item[1], []).append(item)

    for label, items in by_type.items():
        print(f"\n[{label}] {len(items)} 处")
        for item in items:
            line_no = item[0]
            extra = item[2] if len(item) > 2 else ""
            ctx = item[-1]
            print(f"  行{line_no}: {ctx}")
            if verbose:
                print(f"    -> 命中: {extra}")

    print("\n提示：命中项为启发式检出，需人工确认是否真正违规（如\"不构成投资建议\"中的\"建议\"为合法用法）。")
    print("退出码 1（存在待确认项）。")
    sys.exit(1)

def check_caption_sequence(body):
    """图注编号连贯性：正文「图 N｜」必须从 1 开始且连续递增，
    图片数（![...] 行）与图注数必须相等——封面图不插入正文、不参与编号，
    编号不得跳号（如封面占号导致首图从图 2 开始）。"""
    issues = []
    img_count = len(re.findall(r"!\[[^\]]*\]\([^)]+\)", body))
    caps = []
    for m in re.finditer(r"^图\s*(\d+)\s*｜", body, re.M):
        caps.append(int(m.group(1)))
    if not caps and img_count == 0:
        return issues
    if img_count != len(caps):
        issues.append((0, "图注数量不符",
                       f"图片 {img_count} 处但图注 {len(caps)} 条，应一一对应",
                       "图注规范"))
        return issues
    expected = list(range(1, len(caps) + 1))
    if caps != expected:
        issues.append((0, "图注编号不连续",
                       f"图注编号 {caps}，应从 1 连续递增到 {len(caps)}",
                       "图注规范"))
    return issues

def check_cover_ban(body):
    """AI 概念图禁止进正文：ai_*.png 只作独立封面文件
    ai_cover.png 供发布使用，report.md 正文不得出现对它们的图片引用（硬性拦截，
    不再允许"进正文+图注标概念图"的旧做法）。"""
    issues = []
    for m in re.finditer(r"!\[[^\]]*\]\(([^)]*ai[^)]*\.png)\)", body, re.M):
        line_no = body[:m.start()].count("\n") + 1
        issues.append((line_no, "概念图进正文",
                       "AI 概念图（ai_*.png）禁止插入 report.md 正文，封面仅作独立文件 ai_cover.png",
                       m.group(1)))
    return issues

def check_image_continuity(body):
    """图片连续性：正文任意两张图片之间必须有文字内容（非空行、非图注行），
    禁止两张图片连续——连续图片之间无过渡文字，破坏阅读节奏且无内容需求依据。
    图片数量应随内容需求而定，同小节通常只配一张图。"""
    issues = []
    lines = body.split("\n")
    img_positions = [i for i, l in enumerate(lines) if l.strip().startswith("![")]
    for j in range(len(img_positions) - 1):
        a, b = img_positions[j], img_positions[j + 1]
        between = lines[a + 1:b]
        text = [l for l in between
                if l.strip() and not re.match(r"^图\s*\d+\s*｜", l.strip())]
        if not text:
            issues.append((a + 2, "图片连续",
                           "两张图片之间无文字内容（禁止连续图片）",
                           f"图@{a + 1} 与 图@{b + 1}"))
    return issues

if __name__ == "__main__":
    main()