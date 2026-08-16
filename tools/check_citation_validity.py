#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""违规引用检查：作者真实性 + 题名一致性 + URL 伪造

背景：此前报告参考文献 [2] 出现两类违规——编造作者
（"Li Y, et al." 系虚构，经 CrossRef 核实真实作者为 Miao Yuchun 等）与张冠李戴
（正文描述"策略覆盖视角"挂到 InfoRM 名下，与该文实际内容不符）。
check_gbt_refs 只查著录格式（编号/类型/日期），无法发现"引用本身不真实"。

学术纪律：
- 核验失败 ≠ 核验通过：联网核验失败默认升级为硬伤阻断（不得静默放行）；
  显式 --offline 才允许跳过，且输出中声明"离线模式"。
- 佚名必须真佚名：注册库有作者却著录"佚名"= 作者误用（GB/T：无作者才写佚名）。
- 引用日期须晚于/等于发布日期（引用日期早于发布 = 硬伤）。
- 引用 URL 须可溯源：普通 URL 死链（404/5xx）= 硬伤。
- arXiv 条目同样核验作者与发布日期（不只题名）。

硬性（命中即退出码 1，阻断）：
1. URL 伪造/占位符：URL 含 example.com、<...>、TBD、占位符；或含 #related/#anchor/#note 等
   伪锚点（真实文献 URL 不带这类锚点，如 arxiv.org/abs/xxxx 后拼 #related 属伪造）
2. 作者真实性核验（联网，--offline 跳过）：条目 URL 为 doi.org/10.xxxx 时调 CrossRef
   works API 核验：著录作者序列与注册作者序列前 3 位不匹配 → 疑似编造作者
3. 题名一致性核验（联网，--offline 跳过）：条目含 doi.org URL 时，著录题名与 CrossRef
   注册题名经规范化后不一致 → 张冠李戴；arxiv.org/abs 链接调 arxiv API 核验题名
4. arxiv URL 伪造：arxiv.org/abs/<id> 中 id 非法（须 YYMM.NNNNN 或 vN 后缀格式），或
   条目标题与 arxiv API 返回题名不一致 → 硬伤
5. 作者误用（佚名）：著录"佚名"但 CrossRef/arXiv 注册库有作者 → 硬伤（学术纪律）
6. 引用日期早于发布日期：著录引用日期 < 注册库发布日期 → 硬伤（学术纪律）
7. 普通 URL 死链：非 DOI/arxiv 的 URL 返回 404/5xx → 硬伤（学术纪律）
8. 联网核验失败：含 DOI/arxiv 条目但 CrossRef/arXiv 核验网络失败 → 硬伤（默认模式）

提示级（默认 RC=1，严格阻断为默认）：
9. 作者格式疑似异常：英文作者未按"姓全大写 名首字母"（如 "LI Y"），或作者字段过短
10. 正文引注处与文献题名关键词不匹配（启发式，仅报告模式正文含 [n] 时）：
    正文首次出现 [n] 的前后 100 字与文献题名共享的候选词 < 1 个 → 疑似张冠李戴
    （候选词含去尾字前缀，覆盖「遍历论/遍历理论」类词面差异；0 命中才报）
11. URL 可达性未验证：普通 URL 可达性检查因网络失败无法判定

用法：
  python tools/check_citation_validity.py --file path/to/file.md
  python tools/check_citation_validity.py --slug <slug>
  python tools/check_citation_validity.py --file x.md --offline   # 声明放弃联网核验（输出注明）
  python tools/check_citation_validity.py --file x.md   # 默认严格阻断，提示级命中同样失败
  python tools/check_citation_validity.py --file x.md --verbose   # 显示命中明细
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

UA = {"User-Agent": "Mozilla/5.0 (zhihu-ask citation validator)"}

# 与 check_gbt_refs 保持一致的解析常量
ENTRY_RE = re.compile(r"^\[(\d+)\]\s")
REF_HEAD_RE = re.compile(r"^#{1,6}\s*参考文献|^\*\*参考文献|^参考文献")
NOTE_REF_HEAD_RE = re.compile(r"^#{1,6}\s*参考文献|^\*\*参考文献|^参考文献|^来源:")
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


def is_note_file(filepath):
    return os.path.basename(os.path.dirname(os.path.abspath(filepath))) == "notes"


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


def http_get_json(url, timeout=10):
    """GET 并解析 JSON。urllib 失败时 curl 兜底（与 web_search 一致——
    urllib SSL/代理栈本机偶发失败而系统 curl 独立栈可用）。"""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        data = http_get_curl(url, timeout)
        if data is None:
            raise
        return data


def http_get_curl(url, timeout=10):
    """curl 兜底 GET：返回解析后的 JSON 或 None。"""
    try:
        import shutil
        import subprocess
        if shutil.which("curl") is None:
            return None
        r = subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout), "-A", UA.get("User-Agent", "Mozilla/5.0"), url],
            capture_output=True, timeout=timeout + 10)
    except Exception:
        return None
    if not r.stdout:
        return None
    try:
        return json.loads(r.stdout.decode("utf-8", "replace"))
    except Exception:
        return None


def verify_doi(doi, cited_authors, cited_title):
    """CrossRef 核验：返回 (作者核验, 题名核验, 注册题名, 注册作者列表, 发布日期, 网络是否失败)。

    学术纪律：
    - 佚名条目：若注册库有作者 → 返回 anon_abuse=True（作者误用硬伤）；
      注册库确实无作者 → auth_ok=None（无法判定，不报错）。
    - 网络失败时返回 (None, None, None, None, None, True)。
    """
    data = None
    for attempt in range(2):
        try:
            data = http_get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}", timeout=15)
            break
        except Exception:
            if attempt == 0:
                import time
                time.sleep(2)
    if data is None:
        return None, None, None, None, None, True
    msg = data.get("message", {})
    reg_authors = msg.get("author", [])
    reg_title = ""
    t = msg.get("title")
    if isinstance(t, list) and t:
        reg_title = t[0]
    # 发布日期（issued 优先，取最早 date-part）
    pub_date = ""
    for key in ("issued", "published-print", "published-online", "created"):
        dp = (msg.get(key) or {}).get("date-parts")
        if dp and dp[0]:
            pub_date = "-".join(str(x) for x in dp[0][:3])
            break
    # 佚名条目：检查注册库是否真有作者（作者误用检测）
    # 注意：不能用 normalize 判断佚名——normalize 会把"佚名"替换为空
    if cited_authors and any(c.strip() in ("佚名", "anonymous", "anon", "佚名,") for c in
                             [p.strip() for p in re.split(r"[，,]", cited_authors) if p.strip()]):
        if reg_authors:
            # 注册库有作者但著录佚名 → 作者误用（硬伤）
            return None, None, reg_title, reg_authors, pub_date, "anon_abuse"
        return None, None, reg_title, reg_authors, pub_date, False
    auth_ok = authors_match(cited_authors, reg_authors)
    title_ok = None
    if reg_title and cited_title:
        # CrossRef 注册题名可能含 HTML 标签（如下标 <sub>2</sub>），比对前剥离
        reg_title_clean = re.sub(r"<[^>]+>", "", reg_title)
        nt = normalize(reg_title_clean)
        nc = normalize(cited_title)
        title_ok = (nt in nc) or (nc in nt) or (len(set(nt) & set(nc)) >= max(4, min(len(nt), len(nc)) // 2))
    return auth_ok, title_ok, reg_title, reg_authors, pub_date, False


def verify_arxiv(arxiv_id, cited_title, cited_authors=None):
    """arXiv API 核验：返回 (题名核验, 注册题名, 注册作者列表, 发布日期, 网络是否失败)。

    返回注册作者与发布日期，支持作者比对与引用日期合理性检查。
    """
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(arxiv_id)}&max_results=1"
    xml = fetch_text(url)
    if xml is None:
        return None, None, None, None, True
    m = re.search(r"<entry>\s*<id>.*?</id>\s*<title>(.*?)</title>", xml, re.S)
    if not m:
        return None, None, None, None, True
    reg_title = re.sub(r"\s+", " ", m.group(1)).strip()
    # 注册作者（<name> 元素）
    reg_authors = [re.sub(r"\s+", " ", a).strip() for a in re.findall(r"<name>(.*?)</name>", xml)]
    # 发布日期
    pub_date = ""
    pm = re.search(r"<published>(\d{4}-\d{2}-\d{2})", xml)
    if pm:
        pub_date = pm.group(1)
    title_ok = None
    if cited_title:
        nt = normalize(reg_title)
        nc = normalize(cited_title)
        title_ok = (nt in nc) or (nc in nt) or (len(set(nt) & set(nc)) >= max(4, min(len(nt), len(nc)) // 2))
    # 作者比对（佚名判定与 DOI 相同：注册有作者却写佚名 → "anon_abuse" 由调用方处理，
    # 此处返回 None 表示无法判定——调用方另行处理）
    return title_ok, reg_title, reg_authors, pub_date, False


def fetch_text(url, timeout=10):
    """GET 返回文本；urllib 失败时 curl 兜底。全部失败返回 None。"""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        pass
    try:
        import shutil
        import subprocess
        if shutil.which("curl") is None:
            return None
        r = subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout), "-A", UA.get("User-Agent", "Mozilla/5.0"), url],
            capture_output=True, timeout=timeout + 10)
        return r.stdout.decode("utf-8", "replace") if r.stdout else None
    except Exception:
        return None


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


def _probe_via_webfetch(url, timeout=25):
    """WebFetch 降级复核（复用 tools/web_fetch.py，Jina Reader 代理优先）。

    直连被反爬拦截（403）或网络层失败（000）时，页面可能真实存在——
    用与 arxiv 429 WebFetch 降级相同的通道复核；复核成功说明非死链。
    返回 (是否可达, 说明)。
    """
    try:
        tools_dir = os.path.dirname(os.path.abspath(__file__))
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        import web_fetch as _wf
        kind, content, err = _wf.fetch(url, timeout=timeout)
        if kind and content and len(content) > 50:
            return True, f"WebFetch({kind}) 复核可达"
        return False, f"WebFetch 复核失败: {err or '内容为空'}"
    except Exception as e:
        return False, f"WebFetch 复核异常: {str(e)[:60]}"


def check_url_reachable(url, timeout=10):
    """URL 可达性：返回 (是否可达, 状态说明)。重定向视为可达；404/5xx 不可达；网络失败返回 None。

    403（反爬拒绝）与 000（网络层无响应）不直接判死链：降级 WebFetch 复核，
    复核成功说明页面存在、仅直连被拦截，按可达处理（死链判定的核心是「内容不存在」，
    而非「本机直连被拒」）。
    """
    try:
        import shutil
        import subprocess
        if shutil.which("curl") is None:
            return None, "无 curl"
        r = subprocess.run(
            ["curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout),
             "-A", UA.get("User-Agent", "Mozilla/5.0"), url],
            capture_output=True, timeout=timeout + 10)
        code = (r.stdout or b"").decode("utf-8", "replace").strip()
        if not code:
            return None, "空响应"
        # 429（限流）视为"暂不可达但非死链"——网页存在但被限流，
        # 与 404 死链本质不同；返回 True 交由提示级处理（URL 可达性未验证）。
        if code.startswith(("2", "3")):
            return True, f"HTTP {code}"
        if code.startswith("429"):
            return None, f"HTTP 429（限流，非死链）"
        # 403/000：直连被拒 ≠ 内容不存在，WebFetch 复核后判定
        if code.startswith(("403", "000")):
            ok, detail = _probe_via_webfetch(url)
            if ok:
                return True, f"HTTP {code}（直连被拒，{detail}）"
            return False, f"HTTP {code}（{detail}）"
        return False, f"HTTP {code}"
    except Exception as e:
        return None, str(e)[:40]


def check(body, offline=False, ack=(), skip_title_match=False):
    """返回 (硬性问题列表, 提示性问题列表)。问题元素：(行号, 级别, 标题, 详情)

    offline=True：跳过全部联网核验（作者/题名/日期/URL 可达性），只做离线可判项，
    并在提示中声明"离线模式"——调用方（note_upload 等）须知情。
    ack：人工判读确认合规的条目号元组——该条目跳过「正文与题名疑似不符」与
    「作者格式疑似异常」（机构/平台名责任者）两类提示
    （引注关系真实但词面差异、机构名不适用人名规范时由人确认后放行，输出注明）。
    skip_title_match=True：跳过题名一致性核验（硬伤「题名与文献不符」不报）。
    适用场景：注册库题名本身拼写笔误（如 arXiv 元数据 "Divosor" vs 正确 "Divisor"）
    或术语译法差异导致的一字之差误报——作者/日期/URL 等其余核验保留。
    学术纪律收紧：默认（联网）模式下，含 DOI/arxiv URL 的条目若网络核验
    失败，不再降级为提示，而是硬伤阻断——"核验失败"与"核验通过"必须区分。
    """
    hard, warn = [], []
    body_txt, ref_txt, ref_head_line = split_ref_block(body, note_mode=False)
    if ref_txt.strip() == "":
        return hard, warn  # 无参考文献块 = 不适用（check_gbt_refs 已覆盖）

    entries = parse_entries(ref_txt)
    if not entries:
        return hard, warn

    net_down = False
    checked_doi_arxiv = False  # 是否含需联网核验的条目
    for n, text, lineno in entries:
        url = extract_url(text)
        if not url:
            continue
        # 1) URL 伪造/占位符（离线可判）
        for anchor in FAKE_ANCHORS:
            if anchor in url.lower():
                hard.append((ref_head_line + lineno, "硬伤", "URL 伪锚点",
                             f"[{n}] URL 含伪造锚点「{anchor}」（真实文献 URL 不带此类锚点）：{url}"))
        for ph in PLACEHOLDER_URLS:
            if ph in url.lower():
                hard.append((ref_head_line + lineno, "硬伤", "URL 占位符",
                             f"[{n}] URL 疑似占位符：{url}"))
                break
        # 4a) arxiv id 合法性（离线可判）
        if is_arxiv_url(url):
            idm = ARXIV_ID_RE.search(url)
            if not idm:
                hard.append((ref_head_line + lineno, "硬伤", "arxiv URL 非法",
                             f"[{n}] arxiv URL 不含合法 id：{url}"))
                continue
        # 5) 作者格式提示（离线可判；仅非 DOI/arxiv 条目，因 DOI/arxiv 有联网核验兜底）
        # ack 条目跳过：机构/平台名责任者（如 "Easy Linear Algebra"）不适用
        # "姓全大写 名首字母" 个人作者规范，属人工判读可放行的误报场景
        authors = extract_authors(text)
        if authors and n not in ack and not (DOI_RE.search(url) or is_arxiv_url(url)):
            if re.search(r"[A-Za-z]", authors) and not re.search(r"\b[A-Z]{2,}\b", authors):
                warn.append((ref_head_line + lineno, "提示", "作者格式疑似异常",
                             f"[{n}] 英文作者「{authors}」未按 GB/T 规范（姓全大写 名首字母，如 'MIAO Y'）"))
        if offline:
            continue
        title = extract_title(text)

        # 2/3) DOI 核验（学术纪律：核验失败 = 硬伤，不静默放行）
        m = DOI_RE.search(url)
        if m:
            doi = m.group(0).rstrip(".")
            checked_doi_arxiv = True
            auth_ok, title_ok, reg_title, reg_authors, pub_date, extra = verify_doi(doi, authors, title)
            if extra is True:  # 网络失败
                net_down = True
                continue
            if extra == "anon_abuse":
                hard.append((ref_head_line + lineno, "硬伤", "作者误用（佚名）",
                             f"[{n}] 著录「佚名」但 CrossRef 注册作者为「{format_authors(reg_authors)}」——"
                             f"GB/T 规则：无作者才写佚名，应著录真实作者"))
                continue
            if auth_ok is False:
                hard.append((ref_head_line + lineno, "硬伤", "疑似编造作者",
                             f"[{n}] 作者「{authors}」与 CrossRef 注册作者不一致（核验 doi: {doi}）"))
            if title_ok is False and not skip_title_match:
                hard.append((ref_head_line + lineno, "硬伤", "题名与文献不符",
                             f"[{n}] 著录题名《{title}》与 CrossRef 注册题名《{reg_title}》不一致"))
            check_date_reasonableness(text, pub_date, lineno, ref_head_line, n, hard)
            continue

        # 4b) arxiv 核验（题名 + 作者 + 日期）
        if is_arxiv_url(url):
            checked_doi_arxiv = True
            title_ok, reg_title, reg_authors, pub_date, net_fail = verify_arxiv(idm.group(1), title)
            if net_fail:
                net_down = True
                continue
            if title_ok is False and not skip_title_match:
                hard.append((ref_head_line + lineno, "硬伤", "题名与文献不符",
                             f"[{n}] 著录题名《{title}》与 arXiv 注册题名《{reg_title}》不一致（{url}）"))
            # arXiv 作者比对（佚名判定与 DOI 相同）
            if authors:
                cited_anon = any(c.strip() in ("佚名", "anonymous", "anon") for c in
                                 [p.strip() for p in re.split(r"[，,]", authors) if p.strip()])
                if cited_anon:
                    if reg_authors:
                        hard.append((ref_head_line + lineno, "硬伤", "作者误用（佚名）",
                                     f"[{n}] 著录「佚名」但 arXiv 注册作者为「{', '.join(reg_authors[:3])}」——应著录真实作者"))
                else:
                    auth_ok = authors_match(authors, [{"given": "", "family": a} for a in reg_authors])
                    if auth_ok is False:
                        hard.append((ref_head_line + lineno, "硬伤", "疑似编造作者",
                                     f"[{n}] 作者「{authors}」与 arXiv 注册作者不一致（{url}）"))
            check_date_reasonableness(text, pub_date, lineno, ref_head_line, n, hard)
            continue

        # 6) 普通 URL 可达性（提示级；DOI/arxiv 已联网核验，不重复检查）
        reachable, detail = check_url_reachable(url)
        if reachable is None:
            warn.append((ref_head_line + lineno, "提示", "URL 可达性未验证",
                         f"[{n}] URL 可达性检查失败（{detail}）：{url}"))
        elif not reachable:
            hard.append((ref_head_line + lineno, "硬伤", "URL 不可访问",
                         f"[{n}] URL 返回 {detail}（死链，学术纪律：引用须可溯源）：{url}"))

    if net_down and checked_doi_arxiv:
        hard.append((0, "硬伤", "联网核验失败",
                     "CrossRef/arXiv 核验因网络失败被跳过——作者/题名/日期真实性未机器验证。"
                     "学术纪律：核验失败须阻断（不得静默放行）；网络恢复后重跑，或显式 --offline 声明放弃核验"))

    # 7) 提示级：正文引注处上下文与题名关键词匹配（仅正文含 [n] 引注时）
    if CITE_RE.search(body_txt):
        warn.extend(check_cite_context(body_txt, entries, ack=ack))

    return hard, warn


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


def main():
    ap = argparse.ArgumentParser(description="违规引用检查（作者真实性 + 题名一致性 + URL 伪造）")
    ap.add_argument("--file", help="目标 markdown 文件")
    ap.add_argument("--slug", help="研究 slug（检查 research/<slug>/report.md）")
    ap.add_argument("--offline", action="store_true", help="跳过 CrossRef/arXiv 联网核验")
    ap.add_argument("--ack", help="人工确认合规的条目号（逗号分隔，如 2,5,8：跳过其『正文与题名疑似不符』与『作者格式疑似异常』提示）")
    ap.add_argument("--skip-title-match", action="store_true",
                    help="跳过题名一致性核验（注册题名拼写笔误/术语译法差异导致的误报场景；作者/日期/URL 核验保留）")
    ap.add_argument("--verbose", action="store_true", help="显示命中明细")
    args = ap.parse_args()

    if args.slug:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "research", args.slug, "report.md")
    elif args.file:
        path = args.file
    else:
        ap.error("须指定 --file 或 --slug")
    if not os.path.exists(path):
        print(f"文件不存在: {path}")
        sys.exit(1)

    ack = tuple(int(x) for x in args.ack.split(",") if x.strip()) if args.ack else ()
    body = load_text(path)
    hard, warn = check(body, offline=args.offline, ack=ack, skip_title_match=args.skip_title_match)

    print(f"违规引用检查: {path}{'（离线模式）' if args.offline else ''}")
    if args.skip_title_match:
        print("[跳过] 题名一致性核验已跳过（--skip-title-match：注册题名拼写笔误/术语译法差异场景；作者/日期/URL 核验保留）。")
    if ack:
        print(f"[人工确认] 条目 {','.join(str(a) for a in ack)} 已判读确认合规，跳过其『正文与题名疑似不符』提示。")
    print("=" * 60)
    if not hard and not warn:
        print("全部通过：未检出编造作者/题名不符/URL 伪造。")
    else:
        if hard:
            print(f"[硬伤] {len(hard)} 处（命中即阻断）")
            for lineno, level, title, detail in hard:
                print(f"  行{lineno} {title}: {detail}")
        if warn:
            print(f"[提示] {len(warn)} 处（启发式，默认同样阻断）")
            for lineno, level, title, detail in warn:
                print(f"  行{lineno} {title}: {detail}")

    if hard or warn:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
