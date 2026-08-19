#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引用解析层：纯离线解析（无网络依赖），供 check_citation_validity facade 复用。"""
import os
import re
import urllib.parse


# 与 check_gbt_refs 保持一致的解析常量
ENTRY_RE = re.compile(r"^\[(\d+)\]\s")
REF_HEAD_RE = re.compile(r"^#{1,6}\s*参考文献|^\*\*参考文献|^参考文献")
NOTE_REF_HEAD_RE = re.compile(r"^#{1,6}\s*参考文献|^\*\*参考文献|^参考文献")
CITE_RE = re.compile(r"\[(\d+)\]")

# 伪锚点：真实文献 URL 不会带这些片段
FAKE_ANCHORS = ("#related", "#anchor", "#note", "#ref", "#sourc", "#see", "#citation")
# 占位符 URL
PLACEHOLDER_URLS = ("example.com", "<", "TBD", "todo", "placeholder", "xxx", "your-url")
# DOI 合法格式：10.四位数字或更多/后缀
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\]]+")  # DOI 可含括号（Elsevier 格式 (93)）；排除空白与 ]
# arxiv id：YYMM.NNNNN 或旧式 YYMMNNNN，可带 vN
ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5}(?:v\d+)?|\d{7,8}(?:v\d+)?)")


def is_arxiv_url(url):
    """判断 URL 是否为 arxiv 文献链接（abs/pdf/html 三种形式：
    此前只认 /abs/ 与 /pdf/，arxiv.org/html/ 链接被当作普通 URL 只查可达性，
    导致该类条目的题名/作者/佚名核验整体跳过（gromov 报告"佚名"漏检根因）。"""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    if host not in ("arxiv.org", "export.arxiv.org"):
        return False
    return ("arxiv.org/abs/" in url or "arxiv.org/pdf/" in url
            or "arxiv.org/html/" in url)


# is_note_file 已统一迁至 qc_common（单一事实来源），本模块复用


def split_ref_block(body, note_mode=False):
    lines = body.splitlines()
    pat = NOTE_REF_HEAD_RE if note_mode else REF_HEAD_RE
    for i, line in enumerate(lines):
        if pat.match(line.strip()):
            return "\n".join(lines[:i]), "\n".join(lines[i:]), i + 1
    return body, "", None


def parse_entries(ref_block):
    entries = []
    for i, line in enumerate(ref_block.splitlines(), 1):
        m = ENTRY_RE.match(line)
        if m:
            entries.append((int(m.group(1)), line.strip(), i))
    return entries


def extract_url(text):
    """提取条目 URL。DOI 可含括号（Elsevier 格式如 10.1016/0167-2789(93)90178-4），
    仅当右括号在 URL 末尾（后接空白/标点/行尾）时截断。
    不吞引用日期 [YYYY-MM-DD] 与文献类型 [EB/OL] 等后续内容。
    """
    m = re.search(r"https?://[^\s]+", text)
    if not m:
        return None
    url = m.group(0)
    # 剥离尾部 [..] 块（引用日期/类型标识紧邻 URL 时，如 ...4270[YYYY-MM-DD].）
    # 顺序：先删尾部标点（. , 等使 ] 不在末尾），再删 ]，再删 [ 起始段
    while True:
        changed = False
        while url and url[-1] in ".,;:。，；：":
            url = url[:-1]
            changed = True
        while url.endswith("]"):
            url = url[:-1]
            changed = True
        m2 = re.search(r"\[[^\[\]]*$", url)
        if m2:
            url = url[:m2.start()]
            changed = True
        if not changed:
            break
    # 去掉尾部标点
    while url and url[-1] in ".,;:。，；：":
        url = url[:-1]
    # 括号平衡（半角与全角统一处理）：右括号数 > 左括号数时删尾部右括号
    for lparen, rparen in (("(", ")"), ("（", "）")):
        while url and url.count(rparen) > url.count(lparen):
            url = url[:-1]
            while url and url[-1] in ".,;:。，；：":
                url = url[:-1]
    return url or None


def extract_authors(text):
    """提取条目作者串（题名前的部分）：作者. 题名[类型]... 返回作者段或 None。

    兼容两种形态：作者段后跟「题名[类型]」（论文/专著）或作者段后直接「[类型]」（古籍类）。
    无作者条目（GB/T 以「题名[类型]」或「佚名」开头）：作者段含 [ 或 // → 判定无作者。
    """
    m = re.match(r"\[?\d+\]?\s*([^.\n]+?)\s*\.\s", text)
    if not m:
        return None
    candidate = m.group(1)
    if re.match(r"^\[?\d+\]?\s*(http|www)", candidate):
        return None
    if "[" in candidate or "//" in candidate:
        return None
    return candidate.strip()


def extract_title(text):
    """提取条目标题：作者. 题名[类型]... 题名为作者后的首个句子段；无作者条目直接取题名。"""
    if extract_authors(text) is None:
        m = re.match(r"\[?\d+\]?\s*([^.\n]+?)\s*\[", text)
        if m:
            return m.group(1).strip()
        return None
    m = re.match(r"\[?\d+\]?\s*[^.\n]+?\s*\.\s*([^.\n]+?)\s*\[", text)
    return m.group(1).strip() if m else None


def normalize(s):
    """规范化文本用于比对：小写、去标点空白、去 et al./等/参见/略。

    连字符类字符（- – — ‐）统一为连字符，避免同一题名
    因破折号风格差异（如 "Euler-Poisson" vs "Euler–Poisson"）被误判不符。
    剥除 LaTeX 命令——arXiv 注册题名常含源码形式
    （如 "on $\\mathbb{S}^N$"），著录按渲染后纯文本（"on S^N"）是 GB/T 规范，
    比对前须把 \\mathbb{S} → S、删反斜杠，避免含 LaTeX 的注册题名误判不符。
    """
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"\\mathbb\{([^{}]*)\}", r"\1", s)   # \mathbb{S} → S
    s = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", s)  # 通用 \cmd{arg} → arg
    s = re.sub(r"\{([^{}]*)\}", r"\1", s)            # 残余裸花括号组 {2} → 2
    s = s.replace("\\", "")                          # 残余反斜杠（\S^N 等）
    s = s.replace("–", "-").replace("—", "-").replace("‐", "-")
    s = re.sub(r"[，。．,.;；:：\"'“”‘’()（）\[\]【】《》<>/\\|_~^$]", "", s)
    s = re.sub(r"\s+", "", s)
    for w in ("etal", "等", "佚名", "anonymous", "见"):
        s = s.replace(w, "")
    return s


def parse_authors_list(author_str):
    """解析作者串为规范化个体列表。支持 'A B, C D' / 'A B和C D' / 'A B; C D' 分隔。"""
    if not author_str:
        return []
    author_str = author_str.replace("和", ",").replace(";", ",")
    parts = [p.strip() for p in author_str.split(",") if p.strip()]
    # 去掉尾部 et al./等 及空项
    parts = [p for p in parts if normalize(p) not in ("etal", "等") and normalize(p)]
    return [normalize(p) for p in parts]


def authors_match(cited_authors, registered_authors):
    """核验著录作者与注册作者是否一致（比对前 3 位，忽略顺序与大小写）。

    规则：著录作者全体必须都能在注册作者中找到；且两者交集非空。
    注册作者支持三种形态：'姓 名'（CrossRef given/family 字段）、
    'Given Family' 全名（arXiv 返回格式，姓为最后词）、'姓'（宽松）。
    匿名条目（佚名/anonymous）无法核验，返回 None。
    """
    cited = parse_authors_list(cited_authors)
    if not cited:
        return None  # 无法判定
    if any(c.strip() in ("佚名", "anonymous", "anon") for c in cited):
        return None
    reg_forms = set()
    for a in registered_authors:
        given = normalize(a.get("given", ""))
        raw_family = (a.get("family", "") or "").strip()
        family = normalize(raw_family)
        if family:
            reg_forms.add(family + given)      # 姓 名（CrossRef）
            reg_forms.add(family)              # 仅姓（宽松）
            # arXiv 形态：family 字段是 "Given Family" 全名（含空格）→ 姓 = 最后词
            words = [w for w in raw_family.split() if w]
            if len(words) > 1:
                reg_forms.add(normalize(words[-1]))  # 仅姓
                reg_forms.add(family)                # 全名
    if not reg_forms:
        return None
    matched = [c for c in cited if any(r and (r in c or c in r) for r in reg_forms)]
    # 著录作者应至少一半能在注册库找到；找不到任何一位 → 疑似编造
    return len(matched) >= max(1, len(cited) // 2)


def check_cite_context(body_txt, ref_entries, ack=()):
    """正文引注处与文献题名关键词匹配（启发式）：正文 [n] 前后 100 字与题名共享
    bigram 词 <2 → 疑似张冠李戴。

    切词用重叠 2 字滑窗（bigram）：贪婪/非贪婪 findall 都会切碎自然词
    （「什么是混沌理论」→「什么是混沌理」或「是混/沌理」），滑窗保证
    「混沌」等完整 2 字词保留；停用词表去通用词与问句虚词。
    阈值 2 词：真张冠李戴场景（引注上下文与题名毫无关联）通常 0–1 词巧合
    （如正文恰含「电力」），仍被拦截。
    ack：人工判读确认合规的条目号（引注关系真实、词面差异属合法异称，
    如「遍历论 vs 遍历理论」），跳过本提示——确认即放行，输出注明。
    """
    issues = []
    body_flat = re.sub(r"\s+", "", body_txt)
    for n, text, lineno in ref_entries:
        if n in ack:
            continue
        title = extract_title(text)
        if not title:
            continue
        # 用原始题名切中文 bigram（normalize 会剥掉 / 等标点，把"分钟理解/接入"合并成
        # "分钟理解接入"导致上下文永远匹配不上——切词须在 normalize 之前做）
        chars = re.findall(r"[\u4e00-\u9fff]", title.replace("eb/ol", ""))
        zh_words = {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}
        # 取题名中最具辨识度的词（去通用词与问句虚词；消歧后缀如
        # 「统计学术语」「数学分支」留在词表，靠多词阈值容忍其缺失）
        common = {"研究", "分析", "综述", "报告", "理论", "方法", "模型", "及其", "一种",
                  "基于", "面向", "相关", "下", "中", "的",
                  "如何", "什么", "怎么"}
        zh_words = {w for w in zh_words if w not in common}
        if not zh_words:
            continue
        locs = [m.start() for m in re.finditer(rf"\[{n}\]", body_flat)]
        if not locs:
            continue
        # 阈值：多词题名要求 ≥2 词命中；单词题名（如「道教」只有 1 个 bigram）
        # 要求 ≥1 词——2 词阈值对单词题名必然误报
        need = 2 if len(zh_words) > 1 else 1
        # 任一出现位置与题名共享 ≥need 词即视为引用对应（重复引用处不必每次都复述题名词）；
        # 仅当全部出现位置都不匹配才报「疑似张冠李戴」
        matched_any = False
        for loc in locs[:3]:
            ctx = body_flat[max(0, loc - 100): loc + 100]
            if sum(1 for w in zh_words if w in ctx) >= need:
                matched_any = True
                break
        if not matched_any:
            issues.append((0, "提示", "正文与题名疑似不符",
                           f"文献[{n}] 题名《{title[:30]}》在正文引用处上下文未见关键词（启发式，需人工确认）"))
    return issues


# 引用日期 [YYYY-MM-DD]（与 check_gbt_refs 一致）
CITE_DATE_RE = re.compile(r"\[(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\]")


def extract_cite_date(text):
    """提取条目的引用日期 [YYYY-MM-DD]；无则返回 None。"""
    m = CITE_DATE_RE.search(text)
    return m.group(0).strip("[]") if m else None


def check_date_reasonableness(text, pub_date, lineno, head_line, n, issues_hard):
    """引用日期合理性（学术纪律）：引用日期不得早于文献发布日期。

    发布信息缺失时跳过（无法判定）；发布信息存在且引用日期早于发布日期 → 硬伤。
    日期按 (年,月,日) 元组比较（CrossRef/arXiv 发布日期可能无前导零，
    如 "2026-8-12"，与著录 "2026-08-17" 字符串比较会误判）。
    """
    if not pub_date:
        return
    cite_date = extract_cite_date(text)
    if not cite_date:
        # 电子资源缺引用日期已由 check_gbt_refs 拦截，此处不重复
        return

    def _norm(d):
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", d.strip())
        return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None

    c, p = _norm(cite_date), _norm(pub_date)
    if c and p and c < p:
        issues_hard.append((head_line + lineno, "硬伤", "引用日期早于发布日期",
                            f"[{n}] 引用日期 {cite_date} 早于文献发布日期 {pub_date}（学术纪律：引用日期须晚于/等于发布日期）"))


def format_authors(reg_authors):
    """格式化注册作者列表用于提示。"""
    names = []
    for a in reg_authors[:3]:
        given = a.get("given", "") or ""
        family = a.get("family", "") or ""
        names.append((given + " " + family).strip())
    return ", ".join(names) if names else "未知"


def load_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()
