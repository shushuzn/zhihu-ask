#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""今日最新 arXiv 论文拉取（zhihu-ask 专用）。

与 tools/arxiv_search.py（关键词检索，按相关性排序）互补：
本工具定位「拉取今日/近期最新提交」，按 submittedDate 倒序，支持
按分类（cat:cs.AI 等）过滤，落盘格式与 gathered_arxiv.md 一致。

用法:
  # 拉取全站最新 20 篇（按提交时间倒序）
  python tools/arxiv_daily.py --count 20 --out research/daily/2026-08-20.md

  # 按分类拉取（逗号分隔，大小写不敏感，前缀 cat: 可省略）
  python tools/arxiv_daily.py --categories "cs.AI,cs.CL,quant-ph" --count 10

  # 分类 + 关键词二次过滤
  python tools/arxiv_daily.py --categories "cs.AI" --query "diffusion" --count 10

  # 关联研究课题（自动登记通道 P）
  python tools/arxiv_daily.py --categories "cs.AI" --count 10 --slug my-topic

  # 打印 WebFetch 降级 prompt（无外网出口时由 agent 抓取）
  python tools/arxiv_daily.py --categories "cs.AI" --print-web-prompt

实现：复用 tools/arxiv_search.py 的网络栈（urllib 直连 → 代理 → curl
兜底 → WebFetch 降级指引），Atom XML 解析与落盘格式亦与之保持一致。
"""

import argparse
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

try:
    from tools.console_encoding import setup as _ce
    _ce()
except Exception:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

try:
    from tools.run_util import ROOT
except ModuleNotFoundError:
    from run_util import ROOT  # 被测导入时 tools 不在包路径
sys.path.insert(0, os.path.join(ROOT, "tools"))
import channel_state as cs

try:
    import arxiv_search as ax
except ModuleNotFoundError:
    ax = None  # 极端导入失败时走本地实现

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

WEB_PROMPT_TEMPLATE = """请抓取这个 ArXiv API 链接并返回原始条目，不要总结：
{url}

对每个 <entry>，按以下格式逐条输出（不要加额外评论）：
ENTRY
TITLE: <论文标题>
AUTHORS: <作者，逗号分隔>
DATE: <发布日期 YYYY-MM-DD>
SUMMARY: <摘要，合并成一段>
LINK: <arxiv abs 链接>
PDF: <arxiv pdf 链接>
---
把全部条目都输出出来。"""


def _normalize_categories(raw):
    """归一化分类：'cs.AI, cat:quant-ph' → ['cs.AI', 'quant-ph']。"""
    if not raw:
        return []
    parts = re.split(r"[,\s]+", raw.strip())
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p.lower().startswith("cat:"):
            p = p[4:]
        out.append(p)
    # 去重保序
    seen, uniq = set(), []
    for c in out:
        lc = c.lower()
        if lc not in seen:
            seen.add(lc)
            uniq.append(c)
    return uniq


def build_daily_url(categories, query, count):
    """构造 ArXiv 日更查询 URL（按 submittedDate 倒序）。

    ArXiv API 不允许 search_query 为空（400），空分类时需构造一个
    有效但覆盖全站的查询：此为「今日最新」语义，退化为「近期待审不限分类」
    的最新提交（按提交时间倒序，等价于站点日更流）。实现上用通配前缀
    ``cat:*`` 兜底（ArXiv 服务端等价于全站），避免 400。
    """
    cats = _normalize_categories(categories)
    # 构造 search_query
    if cats and query and query.strip():
        q = " AND ".join(f"cat:{urllib.parse.quote_plus(c)}" for c in cats)
        # query 视为 all 关键词（多词自动 AND，由 arxiv_search 处理引号短语）
        if ax is not None:
            q = f"({q}) AND ({ax._arxiv_query(query)})"
        else:
            q = f"({q}) AND (all:{urllib.parse.quote_plus(query.strip())})"
    elif cats:
        q = "+OR+".join(f"cat:{urllib.parse.quote_plus(c)}" for c in cats)
    elif query and query.strip():
        q = ax._arxiv_query(query) if ax is not None else urllib.parse.quote_plus(query.strip())
    else:
        # 全站日更：空 search_query 会 400，退化为 cat:*（全站最新提交流）
        q = "cat:*"
    base = "https://export.arxiv.org/api/query"
    params = f"search_query={q}&start=0&max_results={count}&sortBy=submittedDate&sortOrder=descending"
    return f"{base}?{params}"


def _fetch_with_fallback(url, proxy_default="http://127.0.0.1:7897/"):
    """复用 arxiv_search 的四级降级：urllib 直连 → 代理 → curl 直连 → curl 代理。"""
    if ax is not None:
        text, status = ax.fetch_atom(url, timeout=12)
        if text:
            return text, status, None
        if status in ("egress", "empty"):
            proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or proxy_default
            print(f"[重试] 经代理 {proxy} 重试一次…", file=sys.stderr)
            text, status = ax.fetch_atom(url, timeout=25, proxy=proxy)
            if text:
                return text, status, proxy
        if not text and status in ("egress", "empty"):
            print("[curl兜底] urllib 通道失败，尝试系统 curl 直连…", file=sys.stderr)
            text, status = ax.fetch_atom_curl(url, timeout=20)
            if text:
                return text, status, None
            print(f"[curl兜底] 直连失败（{status}），尝试经代理…", file=sys.stderr)
            text, status = ax.fetch_atom_curl(url, timeout=25, proxy=proxy)
            if text:
                return text, status, proxy
        return text, status, proxy if 'proxy' in locals() else None
    # 无 ax 兜底：自实现直连
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        if data and len(data) >= 50:
            return data.decode("utf-8", errors="ignore"), "ok", None
    except Exception as e:
        print(f"  [连接失败] {type(e).__name__}: {e}", file=sys.stderr)
    return None, "egress", None


def _auto_mark_p(out, entries, slug_explicit):
    slug = slug_explicit or (cs.derive_slug_from_out(out) if out else None)
    if not slug:
        return
    status = "done" if entries else "empty"
    note = f"命中 {len(entries)} 条（arxiv 日更）" if entries else "通道 P 无有效素材（arxiv 日更）"
    if cs.mark(slug, "P", status, note=note):
        print(f"[自动登记] 通道 P（arxiv 日更）: {status} —— {note}", file=sys.stderr)
    else:
        print(f"[提示] 未找到 research/{slug}/.progress.json，跳过通道 P 自动登记（请先 research_start）", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="今日最新 arXiv 论文拉取（按 submittedDate 倒序）")
    ap.add_argument("--categories", default="", help="分类过滤，逗号分隔（如 cs.AI,cs.CL,quant-ph；前缀 cat: 可省略）")
    ap.add_argument("--query", default="", help="可选关键词二次过滤（多词自动 AND，精确短语用引号）")
    ap.add_argument("--count", type=int, default=20, help="返回条数（默认 20）")
    ap.add_argument("--out", help="输出文件（默认打印到 stdout）")
    ap.add_argument("--slug", help="研究报告 slug（自动登记通道 P；省略则从 --out 路径反推）")
    ap.add_argument("--proxy", help="经指定代理重试（默认读 HTTPS_PROXY 环境变量或 http://127.0.0.1:7897/）")
    ap.add_argument("--print-web-prompt", action="store_true", help="打印 WebFetch 用 prompt 与 URL（无外网出口环境走此路径）")
    args = ap.parse_args()

    url = build_daily_url(args.categories, args.query, args.count)

    if args.print_web_prompt:
        print("=== 拷贝以下 prompt 到 WebFetch 工具 ===\n", file=sys.stderr)
        print(WEB_PROMPT_TEMPLATE.format(url=url), file=sys.stderr)
        print("\n=== 把 WebFetch 返回内容保存为 arxiv_raw.txt 后运行 ===", file=sys.stderr)
        print(f"python tools/arxiv_daily.py --raw arxiv_raw.txt{' --out ' + args.out if args.out else ''}", file=sys.stderr)
        # 兼容 arxiv_search 的 --raw 解析入口：提示复用
        print(f"或: python tools/arxiv_search.py --raw arxiv_raw.txt{' --out ' + args.out if args.out else ''}", file=sys.stderr)
        return

    # --raw 解析入口（复用 arxiv_search 的解析能力）
    # 为便于 WebFetch 降级，支持 --raw <file> 解析已保存的原始响应
    # 通过未声明参数兼容：检测 sys.argv 中 --raw
    raw_path = None
    if "--raw" in sys.argv:
        idx = sys.argv.index("--raw")
        if idx + 1 < len(sys.argv):
            raw_path = sys.argv[idx + 1]
    if raw_path:
        if not os.path.isfile(raw_path):
            print(f"ERROR: 未找到原始响应文件 {raw_path}", file=sys.stderr)
            sys.exit(1)
        with open(raw_path, encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        entries = ax.parse_atom_xml(raw) if ax is not None else []
        if not entries and ax is not None:
            entries = ax.parse_delimited(raw)
        if ax is not None:
            content = ax.format_gathered(entries, f"daily:{args.categories or 'all'} {args.query or ''}".strip())
        else:
            content = f"# ArXiv 日更\n> 检索：{args.categories or 'all'} {args.query}\n> 命中：{len(entries)} 条\n"
        if args.out:
            os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"已解析并落盘 {args.out}（{len(entries)} 条）", file=sys.stderr)
            _auto_mark_p(args.out, entries, args.slug)
        else:
            sys.stdout.write(content)
        return

    print(f"[日更] {url}", file=sys.stderr)
    text, status, _proxy = _fetch_with_fallback(url)

    if text:
        entries = ax.parse_atom_xml(text) if ax is not None else []
        # 若 Atom 解析失败，尝试分隔符文本
        if not entries and ax is not None:
            # 已是 Atom，空则直接按无结果处理
            pass
        label = f"daily:{args.categories or 'all'} {args.query or ''}".strip()
        content = ax.format_gathered(entries, label) if ax is not None else text
        if args.out:
            os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"已落盘 {args.out}（{len(entries)} 条）", file=sys.stderr)
            _auto_mark_p(args.out, entries, args.slug)
        else:
            sys.stdout.write(content)
        return

    if status == "429":
        print("\n[降级] ArXiv 直连被限流（HTTP 429，代理 IP 共享常被限），改用 WebFetch 更稳。", file=sys.stderr)
    elif status == "http":
        print("\n[降级] ArXiv 直连与代理均返回 HTTP 错误，改用 WebFetch。", file=sys.stderr)
    else:
        print("\n[降级] 当前环境无外网出口（直连与代理均失败），ArXiv 直连不可用。", file=sys.stderr)
    print("请改用 agent 的 WebFetch 工具完成检索：\n", file=sys.stderr)
    print(WEB_PROMPT_TEMPLATE.format(url=url), file=sys.stderr)
    print("\n把返回内容保存为 arxiv_raw.txt 后运行：", file=sys.stderr)
    print(f"  python tools/arxiv_daily.py --raw arxiv_raw.txt{' --out ' + args.out if args.out else ''}", file=sys.stderr)
    print(f"  或: python tools/arxiv_search.py --raw arxiv_raw.txt{' --out ' + args.out if args.out else ''}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
