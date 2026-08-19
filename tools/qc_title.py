"""quality_check 子模块（从 quality_check.py 拆分）：qc_title 相关检查。"""
import re

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


_EMPTY_SECTION_TITLES = frozenset(["因果", "结构", "规律", "策略", "长期"])

# 宽松匹配由多轮回归确认的合法极短标题（属固定概念名，非空洞标签）——此前
# 归因分析证明：移除近义轮次/新增团队判断术语的版式调整后，标题整体信息
# 仍足以定锚小节，无需在门禁中按字符计费。为避免空洞标题误过，合法短标题
# 仍须命中下一级“专业领域锚点”（Chinese / English / 数理符号 任一）。
_SHORT_OK = r"(?:作用|定义|框架|背景|来源|问题|挑战|影响|风险|启示|结论|展望|延伸|小结|索引|机制|原理|推导|模型|证明|定理|边界|条件|假设|记号|符号|记法|约定|纲要|综述|概述|引言|导言|脉络|摘要|注|制图|注记|镜像|评注)"


def check_empty_section_title(body):
    """检测小节标题（###）用空洞标签（因果/结构/规律/策略/长期）占位。

    来源：STYLE_GUIDE「标题即质量」（Fourier 示例）——大标题直给核心判断，
    小标题落到函数空间/技术机制，而非泛化标签。空洞标签仅为模板占位
    （{{主题名}}），成品报告须落到具体概念/机制。短标题若属领域固定
    概念名（定义/证明/引言 等）则豁免；首轮仅作提示，仅空洞标签列为硬伤，
    后续据事实反馈再收紧。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        s = line.strip()
        if not s.startswith("### "):
            continue
        title = re.sub(r"^###\s+", "", s).strip()
        # 去 LaTeX/$/空格/标点，仅保留内容字符后判是否为空洞标签
        inner = re.sub(r"\$[^\$]*\$", "", title).strip()
        inner = re.sub(r"[·・、,，:：\-—\s]+", "", inner).strip()
        if inner in _EMPTY_SECTION_TITLES:
            issues.append((i, "小标题空洞", f'小节标题「{title}」为模板占位，请改写为落到具体概念/技术机制的标题', s[:60]))
            continue
        # 字符信息不足的极短标题（如“延拓”“收敛”）：仅当同时缺专业锚点时才判空洞
        t0 = re.sub(r"\$[^\$]*\$", "", title)
        # 去条目序号/标点，仅保留可见字符
        core = re.sub(r"^[\d\.\s、，:：\-—]+", "", t0).strip()
        if 1 <= len(core) <= 2:
            if re.fullmatch(rf"^{_SHORT_OK}$", core):
                continue
            if not re.search(r"[\u4e00-\u9fffA-Za-z\$—\-∈∉⊂⊃⊆⊇∞πσωΔΣ∫∂∈√²³≤≥→←⇒×·]", title):
                issues.append((i, "小标题空洞", f'小节标题「{title}」过短且缺专业锚点，请补足落到具体概念的标题', s[:60]))
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

