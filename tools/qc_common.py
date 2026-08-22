"""quality_check 共享常量与基础工具（从 quality_check.py 拆分，单一事实来源）。

其余 qc_* 子模块的常量与基础工具函数统一在此定义，避免重复。
"""
import os
import re

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

NOTE_SOURCE_MARKERS = ["## 参考文献", "\n参考文献:"]

NOTE_REF_MARKERS = ["## 参考文献", "参考文献:"]

FORBIDDEN_NOTE_FIELDS = [
    (r"^\s*\*\*来源\*\*\s*[:：]", "来源字段"),
    (r"^\s*\*\*概念\*\*\s*[:：]", "概念字段"),
    (r"^\s*来源\s*[:：]", "来源字段"),
    (r"^\s*概念\s*[:：]", "概念字段"),
]

REF_BAD_LABELS = ["一手", "二手", "推断"]

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

MATH_UNICODE_CHARS = "√∫∥∮∑∏⊕⊗⟨⟩∪∩∅⊂⊃⊆⊇∈∉∀∃∂∇∞≈≠·½¼¾₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹⁻ᶻᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ⁺⁻⁼⁽⁾πΣΘΦΨΩαβγδεζηθλμξρστφχω"

TRANSLATION_PATTERNS = [
    r"以下解读[^。；\n]{0,30}(博客|文章|论文|姊妹篇|研究)",
    r"(博客|文章|论文|姊妹篇|研究)[^。；\n]{0,10}的价值在于",
    r"(博客|文章|论文|姊妹篇|研究)[^。；\n]{0,15}(处理|讨论|提出|给出)[^。；\n]{0,15}相反问题",
    r"这篇(博客|文章|论文)[^。；\n]{0,15}(讲了|介绍了|解读了|研究)",
]

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

NUMBERED_LABEL_RE = re.compile(
    r"(?<![\u4e00-\u9fffA-Za-z])"
    r"(?:Theorem|Definition|Proposition|Lemma|Corollary|Remark|Assumption|Conjecture|Example"
    r"|定理|定义|命题|引理|推论|注记|假设|猜想|例)\s*"
    r"(\d+(?:\.\d+)*|[A-Z](?:[A-Za-z0-9]*)?)"
)

ATTRIBUTION_SOURCE_MARKERS = ("arxiv:", "arxiv.org", "arXiv:", "arXiv 全文", "arxiv/abs", "《")

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

def check_note_forbidden_fields(body):
    """检测笔记非规定字段（来源/概念等，笔记模板禁止）。

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

def strip_display_math(text):
    """移除块级 $$...$$ 与 \\[...\\] 公式，避免公式块被当作叙述段落计数。"""
    text = re.sub(r"\$\$.*?\$\$", "", text, flags=re.S)
    text = re.sub(r"\\\[.*?\\\]", "", text, flags=re.S)
    return text

