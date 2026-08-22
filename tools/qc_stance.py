"""quality_check 子模块（从 quality_check.py 拆分）：qc_stance 相关检查。"""
import re
from tools.qc_common import ATTRIBUTION_SOURCE_MARKERS, IMPL_RESIDUE_WORDS, NUMBERED_LABEL_RE, SUBJECTLESS_OPENER_RE, TRANSLATION_PATTERNS

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
        # 裸 Python（大小写不敏感，词边界）——成品正文禁泄露实现语言；
        # 例外：报告主题本身含 Python 时（如 Lean/Python FFI、Python 生态等事实内容），不误报——
        # 仅当 Python 指代作者实现过程（验证/脚本/跑）才属残留
        if re.search(r"(?i)\bpython\b", stripped):
            if re.search(r"(?i)Python", stripped) and re.search(r"(FFI|生态|优先|模块)", stripped):
                pass  # 事实内容（FFI/生态等同行出现），豁免
            else:
                issues.append((i, "实现过程残留", "Python（成品正文禁泄露实现语言）", line.strip()[:60]))
                continue
        for w in IMPL_RESIDUE_WORDS:
            if w in stripped:
                issues.append((i, "实现过程残留", w, line.strip()[:60]))
                break
    return issues

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

