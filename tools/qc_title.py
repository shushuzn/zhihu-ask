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

