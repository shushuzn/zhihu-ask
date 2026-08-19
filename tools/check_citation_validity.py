#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""违规引用检查：作者真实性 + 题名一致性 + URL 伪造（门面聚合，详见模块 docstring 历史）。
拆分为 cv_parse（纯解析）/ cv_net（网络层）；本文件保留验证与聚合逻辑。
用法：
  python tools/check_citation_validity.py --file path/to/file.md
  python tools/check_citation_validity.py --slug <slug>
  python tools/check_citation_validity.py --file x.md --offline
"""
import argparse
import os
import re
import sys
import urllib.parse
from qc_common import is_note_file

try:
    from tools.console_encoding import setup as _ce
    _ce()
except Exception:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from cv_parse import *  # noqa: F401,F403  (注入解析符号到 facade.__dict__)
from cv_net import *    # noqa: F401,F403  (注入 UA/网络符号到 facade.__dict__)



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
                # 机构/平台名责任者为单一词（无空格、无逗号，如 Wikipedia、Nature、arXiv），
                # 不适用「姓全大写 名首字母」个人作者规范，豁免该提示（原误报 Wikipedia 等机构名）
                if re.search(r"[\s,]", authors):
                    # Title Case 多词组织名（每个词首字母大写其余小写，如 "Model Context Protocol"）
                    # 同为机构/平台责任者，非个人作者，豁免（原误报 MCP 官方机构名）
                    words = [w for w in re.split(r"[^A-Za-z]+", authors) if w]
                    is_title_case = bool(words) and all(
                        w[:1].isupper() and w[1:].islower() for w in words if len(w) > 1
                    )
                    if not is_title_case:
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
