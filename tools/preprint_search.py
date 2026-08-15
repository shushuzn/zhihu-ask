#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学术预印本聚合检索：bioRxiv + 浪淘沙 + PSSXiv 哲学社会科学预印本

背景：学术预印本聚合通道 P 包含 arXiv 与三个补充预印本平台——
生物医学领域的 bioRxiv、跨学科中文预印本「浪淘沙」（LangTaoSha，OJS 3.5 实例）、
哲学社会科学预印本平台（PSSXiv，中国人民大学复印报刊资料运营，域名 zsyyb.cn）。

平台接入方式：
1. bioRxiv    —— 公开 REST API：https://api.biorxiv.org/pubs/biorxiv/<d1>/<d2>/<cursor>/<count>
                 返回 JSON（preprint_doi/title/authors/date）。注意服务端偶发 500，需重试。
2. 浪淘沙     —— OJS 3.5 WebFeedGatewayPlugin Atom feed（公开、无认证）：
                 https://langtaosha.org.cn/lts/gateway/plugin/WebFeedGatewayPlugin/atom
                 返回全部预印本（标题/作者/链接/日期/摘要），无搜索参数——本地过滤。
3. PSSXiv     —— POST https://zsyyb.cn/user/search.htm  searchVal=<关键词>
                 服务端渲染 HTML，条目含 PSSXiv 编号/标题/摘要/分类。

用法：
  python tools/preprint_search.py --platform all --keywords "关键词" --out research/<slug> --slug <slug>
      # 四平台聚合，全部归通道 P：arxiv → gathered_arxiv.md，
      #          bioRxiv/浪淘沙/PSSXiv → gathered_preprints.md；一次性登记通道 P
  python tools/preprint_search.py --platform arxiv --keywords "关键词" --count 5
  python tools/preprint_search.py --platform biorxiv --days 30 --keywords "cancer immunotherapy"
  python tools/preprint_search.py --platform langtaosha --keywords "RNA"
  python tools/preprint_search.py --platform pssxiv --keywords "人工智能"

落盘格式：与 gathered_arxiv.md 一致（## 条目 + 作者/日期/链接/摘要）；--out 为目录，
各平台按默认文件名分流（arxiv → gathered_arxiv.md；其余 → gathered_preprints.md），
检索完成后一次性自动登记通道 P（含 arxiv 平台）。
"""

import argparse
import html as _html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import channel_state as cs

UA = {"User-Agent": "Mozilla/5.0 (zhihu-ask preprint search)"}

BIORXIV_BASE = "https://api.biorxiv.org"
LANGTAOSHA_FEED = "https://langtaosha.org.cn/lts/gateway/plugin/WebFeedGatewayPlugin/atom"
PSSXIV_SEARCH = "https://zsyyb.cn/user/search.htm"


# ---------- 通用网络 ----------

def http_get(url, timeout=20):
    """GET 返回文本；urllib 失败时 curl 兜底（与 web_search 一致）。"""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout), "-A", UA.get("User-Agent", "Mozilla/5.0"), url],
            capture_output=True, timeout=timeout + 10)
        return r.stdout.decode("utf-8", "replace") if r.stdout else None
    except Exception:
        return None


def http_post(url, data, timeout=20):
    """POST 表单返回文本；urllib 失败时 curl 兜底。"""
    body = urllib.parse.urlencode(data).encode()
    try:
        req = urllib.request.Request(url, data=body, headers={**UA, "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        pass
    try:
        args = ["curl", "-sL", "--max-time", str(timeout), "-A", UA.get("User-Agent", "Mozilla/5.0"),
                "-X", "POST", "-d", urllib.parse.urlencode(data), url]
        r = subprocess.run(args, capture_output=True, timeout=timeout + 10)
        return r.stdout.decode("utf-8", "replace") if r.stdout else None
    except Exception:
        return None


# ---------- arxiv（复用 arxiv_search 工具，整合进聚合入口） ----------

def search_arxiv(keywords, count=10):
    """arxiv 平台：复用 tools/arxiv_search.py 的查询/抓取/解析，输出统一条目结构。

    返回 [{title, authors, date, doi, link, abstract}]；网络失败返回 None。
    """
    import arxiv_search as ax
    url = ax.build_url(keywords, max(count, 5))
    text, status = ax.fetch_atom(url, timeout=20)
    if not text and status in ("egress", "empty"):
        text, status = ax.fetch_atom_curl(url, timeout=25)
    if not text:
        return None
    out = []
    for e in ax.parse_atom_xml(text):
        out.append({
            "title": e["title"],
            "authors": e["authors"],
            "date": e["date"],
            "doi": "",
            "link": e["link"],
            "abstract": e["summary"],
        })
        if len(out) >= count:
            break
    return out


# ---------- bioRxiv ----------

def search_biorxiv(keywords, days=30, count=10):
    """bioRxiv 按日期区间检索（API 无关键词参数，取最近 days 天 preprints 本地过滤）。

    返回 [{title, authors, date, doi, link, abstract}]。服务端偶发 500，重试 3 次。
    分页：每页 100 条，最多翻 fetch_pages 页，本地按关键词（标题）过滤到 count 条。
    """
    end = date.today()
    start = end - timedelta(days=days)
    # bioRxiv 每页最多 100 条；按需取 1-3 页
    fetch_pages = max(1, (count + 99) // 100)
    kw = [k.lower() for k in keywords.split() if k]
    out = []
    for page in range(fetch_pages):
        url = f"{BIORXIV_BASE}/pubs/biorxiv/{start.isoformat()}/{end.isoformat()}/{page * 100}/100"
        text = None
        for attempt in range(3):
            text = http_get(url, timeout=40)
            if text:
                break
            time.sleep(3 + attempt * 2)
        if not text:
            if not out:
                return None  # 全部页面都失败
            break
        try:
            data = json.loads(text)
        except Exception:
            if not out:
                return None
            break
        for e in data.get("collection", []) or []:
            title = (e.get("preprint_title") or "").strip()
            if not title:
                continue
            if kw and not all(k in title.lower() for k in kw):
                continue
            doi = (e.get("preprint_doi") or "").strip()
            link = f"https://doi.org/{doi}" if doi else ""
            out.append({
                "title": title,
                "authors": (e.get("preprint_authors") or "").strip(),
                "date": (e.get("preprint_date") or "").strip()[:10],
                "doi": doi,
                "link": link,
                "abstract": "",
            })
            if len(out) >= count:
                return out
    return out


# ---------- 浪淘沙（OJS Atom feed） ----------

def search_langtaosha(keywords, count=10):
    """浪淘沙：拉取 Atom feed 全部条目，本地按关键词过滤。返回条目列表。"""
    text = http_get(LANGTAOSHA_FEED, timeout=30)
    if not text:
        return None
    kw = [k.lower() for k in keywords.split() if k]
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", text, re.S):
        def g(tag, flags=0):
            m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", e, flags)
            return m.group(1).strip() if m else ""
        title = re.sub(r"\s+", " ", g("title")).strip()
        if not title:
            continue
        if kw and not all(k in title.lower() for k in kw):
            continue
        authors = [re.sub(r"\s+", " ", a).strip() for a in re.findall(r"<name>(.*?)</name>", e)]
        link_m = re.search(r'<link[^>]*href="([^"]*)"', e)
        date_m = re.search(r"<published>(.*?)</published>", e)
        summary = _html.unescape(g("summary", re.S))
        summary = re.sub(r"<[^>]+>", "", summary)
        summary = re.sub(r"\s+", " ", summary).strip()
        out.append({
            "title": title,
            "authors": ", ".join(authors),
            "date": (date_m.group(1)[:10] if date_m else ""),
            "doi": "",
            "link": (link_m.group(1) if link_m else ""),
            "abstract": summary,
        })
        if len(out) >= count:
            break
    return out


# ---------- PSSXiv 哲学社会科学预印本 ----------

def search_pssxiv(keywords, count=10):
    """PSSXiv：POST 搜索返回服务端 HTML，解析 PSSXiv 编号/标题/摘要。"""
    text = http_post(PSSXIV_SEARCH, {"searchVal": keywords}, timeout=30)
    if not text:
        return None
    kw = [k.lower() for k in keywords.split() if k]
    out = []
    # 条目块：PSSXiv:YYYYMM.NNNNN 编号
    for m in re.finditer(r"PSSXiv:(\d{6}\.\d{5})", text):
        pid = m.group(1)
        block = text[m.start() - 600:m.start() + 3000]
        # 标题：编号后方的链接文字（块内跳过编号行/下载/评论等噪声链接）
        links = re.findall(r"<a[^>]*>\s*([^<]{4,100})\s*</a>", block)
        title = ""
        for l in links:
            t = re.sub(r"\s+", " ", l).strip()
            if t and "下载" not in t and "评论" not in t and "PSSXiv" not in t:
                title = t
                break
        # 摘要：找到"摘要："后取后续文本（去 HTML 标签），截断到"展开"或 400 字
        summ = ""
        i = block.find("摘要")
        if i >= 0:
            seg = block[i + 3:i + 1200]
            seg = re.sub(r"<[^>]+>", " ", seg)
            seg = _html.unescape(seg)
            seg = re.sub(r"\s+", " ", seg).strip()
            # 截断到"展开"标记或合理长度
            cut = seg.find("展开")
            if cut > 0:
                seg = seg[:cut]
            summ = seg[:400]
        # PSSXiv 搜索结果已由平台按关键词检索（标题未必含字面词），不额外本地过滤
        detail_url = f"https://zsyyb.cn/user/search.htm?showId={pid}"
        out.append({
            "title": title,
            "authors": "",
            "date": "",
            "doi": "",
            "link": detail_url,
            "abstract": summ,
            "pssxiv_id": pid,
        })
        if len(out) >= count:
            break
    return out


# ---------- 落盘与通道登记 ----------

def format_gathered(platform, entries, keywords):
    lines = [f"# 学术预印本检索素材库（{platform}）", ""]
    lines.append(f"> 检索词：{keywords}")
    lines.append(f"> 命中：{len(entries)} 条（工具：tools/preprint_search.py）")
    lines.append("")
    if not entries:
        lines.append("（无有效素材）")
        return "\n".join(lines) + "\n"
    for i, e in enumerate(entries, 1):
        lines.append(f"## {i}. {e['title']}")
        if e.get("authors"):
            lines.append(f"- 作者：{e['authors']}")
        if e.get("date"):
            lines.append(f"- 日期：{e['date']}")
        if e.get("pssxiv_id"):
            lines.append(f"- 编号：PSSXiv:{e['pssxiv_id']}")
        if e.get("link"):
            lines.append(f"- 链接：{e['link']}")
        if e.get("abstract"):
            lines.append("")
            lines.append(f"  {e['abstract']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def auto_mark_p(slug, total_entries, platforms_done):
    """全部平台检索完成后一次性登记通道 P（arxiv 已归入通道 P）。

    total_entries：累计命中条数；platforms_done：成功执行的平台数。
    """
    if not slug:
        return
    status = "done" if total_entries else "empty"
    note = f"命中 {total_entries} 条（{platforms_done} 平台）" if total_entries else "通道 P 无有效素材"
    if cs.mark(slug, "P", status, note=note):
        print(f"[自动登记] 通道 P（学术预印本聚合）: {status} —— {note}", file=sys.stderr)
    else:
        print(f"[提示] 未找到 research/{slug}/.progress.json，跳过通道 P 自动登记", file=sys.stderr)


PLATFORM_NAMES = {"arxiv": "arxiv", "biorxiv": "bioRxiv", "langtaosha": "浪淘沙", "pssxiv": "PSSXiv 哲学社科"}
# 平台 → 落盘文件（arxiv 与其余平台分文件落盘，但同属通道 P）
PLATFORM_OUT = {
    "arxiv": "gathered_arxiv.md",
    "biorxiv": "gathered_preprints.md",
    "langtaosha": "gathered_preprints.md",
    "pssxiv": "gathered_preprints.md",
}


def main():
    ap = argparse.ArgumentParser(description="学术预印本聚合检索（arxiv/bioRxiv/浪淘沙/PSSXiv）")
    ap.add_argument("--platform", choices=["arxiv", "biorxiv", "langtaosha", "pssxiv", "all"], default="all",
                    help="预印本平台（默认 all 四平台都查：arxiv + bioRxiv + 浪淘沙 + PSSXiv）")
    ap.add_argument("--keywords", default="", help="检索关键词（多词空格分隔）")
    ap.add_argument("--days", type=int, default=30, help="bioRxiv 时间范围（天，默认 30）")
    ap.add_argument("--count", type=int, default=10, help="每平台返回条数（默认 10）")
    ap.add_argument("--out", help="输出目录（默认 research/<slug>/；各平台按默认文件名分流落盘）")
    ap.add_argument("--slug", help="研究报告 slug（自动登记通道 P；省略则从 --out 目录名反推）")
    args = ap.parse_args()

    if not args.keywords:
        ap.error("--keywords 必填")

    platforms = ["arxiv", "biorxiv", "langtaosha", "pssxiv"] if args.platform == "all" else [args.platform]
    all_entries = {}
    any_fail = False
    for p in platforms:
        print(f"[检索] {PLATFORM_NAMES[p]}（{args.keywords or '全部'}）…", file=sys.stderr)
        if p == "arxiv":
            entries = search_arxiv(args.keywords, args.count)
        elif p == "biorxiv":
            entries = search_biorxiv(args.keywords, args.days, args.count)
        elif p == "langtaosha":
            entries = search_langtaosha(args.keywords, args.count)
        else:
            entries = search_pssxiv(args.keywords, args.count)
        if entries is None:
            print(f"[失败] {PLATFORM_NAMES[p]} 检索异常（网络/服务端）", file=sys.stderr)
            any_fail = True
            continue
        all_entries[p] = entries
        print(f"[命中] {PLATFORM_NAMES[p]}: {len(entries)} 条", file=sys.stderr)

    # 落盘：--out 为目录（或 research/<slug>/），各平台按默认文件名分流
    # arxiv → gathered_arxiv.md；biorxiv/浪淘沙/PSSXiv → gathered_preprints.md（均属通道 P）
    slug = args.slug or (os.path.basename(os.path.abspath(args.out)) if args.out else None)
    out_dir = args.out or (os.path.join("research", slug) if slug else None)
    wrote_any = False
    for p in platforms:
        if p not in all_entries:
            continue
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            target = os.path.join(out_dir, PLATFORM_OUT[p])
            with open(target, "a", encoding="utf-8") as f:
                f.write(format_gathered(PLATFORM_NAMES[p], all_entries[p], args.keywords))
            wrote_any = True
            print(f"[已落盘] {target}", file=sys.stderr)
        else:
            sys.stdout.write(format_gathered(PLATFORM_NAMES[p], all_entries[p], args.keywords))
            wrote_any = True

    # 一次性登记通道 P（累计命中）
    if wrote_any and out_dir:
        total = sum(len(v) for v in all_entries.values())
        auto_mark_p(slug, total, len(all_entries))
    if not wrote_any and any_fail:
        print("[提示] 全部平台检索失败，未产生输出", file=sys.stderr)
    if any_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
