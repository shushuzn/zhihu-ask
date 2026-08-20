#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ArXiv 全文抓取（zhihu-ask 专用）。

与 preprint_search/arxiv_search 的「元数据检索」互补：
本工具定位「必拉全文」——把 gathered_arxiv.md 命中的首篇 arXiv 论文
全文 HTML 拉回落盘，供阶段 3 以全文为准做交叉验证与论证完整性校验。

落盘：
  research/<slug>/arxiv_html.md  HTML 原文（LaTeXML）
  research/<slug>/arxiv_text.md  文本化（去标签，持续演进不作门禁口径）

用法：
  python tools/arxiv_fetch.py --slug <slug>
  python tools/arxiv_fetch.py --slug <slug> --id 2608.19193
  python tools/arxiv_fetch.py --slug <slug> --print-web-prompt  # 无外网出口时
  python tools/arxiv_fetch.py --slug localized-fourier-extension-inverse-source --raw arxiv_raw.html --out research/<slug>/arxiv_html.md

实现：复用 arxiv_search 的四级降级（urllib 直连→代理→curl 直连→curl 代理），
失败时打印 WebFetch 降级指引与 --raw 回填路径，不静默空返回。
"""

import argparse
import os
import re
import subprocess
import sys
import urllib.request

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
    from run_util import ROOT

sys.path.insert(0, os.path.join(ROOT, "tools"))

ARXIV_HTML_TMPL = "https://arxiv.org/html/{id}v1"
AR5IV_TMPL = "https://ar5iv.org/html/{id}v1"
WEB_PROMPT = """请抓取这个 ArXiv HTML 页面并返回完整原文（不要总结）：
{url}

把返回的 HTML 原样输出，不要加评论。保存为 research/{slug}/arxiv_html.md 后，
本地再文本化为 arxiv_text.md（去标签）供全文核验。"""


def _parse_first_arxiv_id(slug):
    """从 gathered_arxiv.md 解析首个 arXiv ID。"""
    path = os.path.join(ROOT, "research", slug, "gathered_arxiv.md")
    if not os.path.isfile(path):
        return None
    try:
        text = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return None
    m = re.search(r"arxiv\.org/abs/([0-9]+\.[0-9]+)", text)
    if m:
        return m.group(1)
    m = re.search(r"arXiv:([0-9]+\.[0-9]+)", text, re.I)
    if m:
        return m.group(1)
    return None


def _fetch_html(url, timeout=20, proxy=None):
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    ) if proxy is not None else urllib.request.build_opener(urllib.request.ProxyHandler({}))
    # proxy=None 时强制直连（忽略系统代理）由 arxiv_search 的 opener 实现；
    # 此处简化：None→直连，str→经该代理
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        # 若 proxy 为 None 需强制直连：用空代理 opener
        if proxy is None:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        else:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read()
        if data and len(data) > 500:
            return data.decode("utf-8", errors="ignore"), "ok"
        return None, "empty"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _fetch_with_fallback(arxiv_id):
    urls = [ARXIV_HTML_TMPL.format(id=arxiv_id), AR5IV_TMPL.format(id=arxiv_id)]
    for url in urls:
        print(f"[全文] 尝试 {url}", file=sys.stderr)
        html, st = _fetch_html(url, timeout=20, proxy=None)
        if html:
            return html, url
        print(f"  失败: {st}", file=sys.stderr)
        # 代理重试一次
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "http://127.0.0.1:7897/"
        print(f"[全文] 经代理重试 {url}", file=sys.stderr)
        html, st = _fetch_html(url, timeout=25, proxy=proxy)
        if html:
            return html, url
        print(f"  代理仍失败: {st}", file=sys.stderr)
        # curl 兜底
        try:
            import shutil
            if shutil.which("curl"):
                for p in (None, proxy):
                    cmd = ["curl", "-sL", "--max-time", "20", "-A", "Mozilla/5.0", url]
                    if p:
                        cmd += ["--proxy", p]
                    r = subprocess.run(cmd, capture_output=True, timeout=25)
                    if r.stdout and len(r.stdout) > 500:
                        return r.stdout.decode("utf-8", errors="ignore"), url
        except Exception:
            pass
    return None, None


def _textize(html):
    import html as hm
    t = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style[^>]*>.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = hm.unescape(t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t


def main():
    ap = argparse.ArgumentParser(description="ArXiv 全文抓取（HTML 落盘，供全文为准校验）")
    ap.add_argument("--slug", required=True, help="研究报告 slug")
    ap.add_argument("--id", dest="arxiv_id", help="arXiv ID（如 2608.19193，省略则从 gathered_arxiv.md 解析首篇）")
    ap.add_argument("--out", help="HTML 输出路径（默认 research/<slug>/arxiv_html.md）")
    ap.add_argument("--raw", help="解析已保存的原始 HTML（WebFetch 降级回填）")
    ap.add_argument("--print-web-prompt", action="store_true", help="打印 WebFetch 用 prompt（无外网出口时）")
    args = ap.parse_args()

    slug = args.slug
    arxiv_id = args.arxiv_id or _parse_first_arxiv_id(slug)

    if args.print_web_prompt:
        if not arxiv_id:
            print("ERROR: 无法解析 arXiv ID，请显式 --id", file=sys.stderr)
            sys.exit(1)
        url = ARXIV_HTML_TMPL.format(id=arxiv_id)
        print(WEB_PROMPT.format(url=url, slug=slug), file=sys.stderr)
        print(f"\n保存为 research/{slug}/arxiv_html.md 后运行：", file=sys.stderr)
        print(f"  python tools/arxiv_fetch.py --slug {slug} --raw research/{slug}/arxiv_html.md", file=sys.stderr)
        return

    if args.raw:
        if not os.path.isfile(args.raw):
            print(f"ERROR: 未找到 {args.raw}", file=sys.stderr)
            sys.exit(1)
        html = open(args.raw, encoding="utf-8", errors="ignore").read()
        out_html = args.out or os.path.join(ROOT, "research", slug, "arxiv_html.md")
        os.makedirs(os.path.dirname(out_html) or ".", exist_ok=True)
        open(out_html, "w", encoding="utf-8").write(html)
        # 文本化
        out_text = os.path.join(os.path.dirname(out_html), "arxiv_text.md")
        open(out_text, "w", encoding="utf-8").write(_textize(html))
        print(f"[回填] 已从 {args.raw} 落盘 {out_html} + arxiv_text.md", file=sys.stderr)
        return

    if not arxiv_id:
        print(f"ERROR: 未找到 {slug} 的 arXiv ID（gathered_arxiv.md 无命中或 --id 未提供）", file=sys.stderr)
        print(f"  若为非 arXiv 主题（无论文），此检查不适用；否则请先完成 P 通道检索。", file=sys.stderr)
        sys.exit(1)

    url_primary = ARXIV_HTML_TMPL.format(id=arxiv_id)
    if args.print_web_prompt:
        print(WEB_PROMPT.format(url=url_primary, slug=slug))
        return

    html, url = _fetch_with_fallback(arxiv_id)
    if not html:
        print(f"\n[降级] 全文直连失败（{arxiv_id}）。请用 WebFetch 抓取：", file=sys.stderr)
        print(WEB_PROMPT.format(url=url_primary, slug=slug), file=sys.stderr)
        print(f"\n保存为 research/{slug}/arxiv_html.md 后运行：", file=sys.stderr)
        print(f"  python tools/arxiv_fetch.py --slug {slug} --raw research/{slug}/arxiv_html.md", file=sys.stderr)
        sys.exit(2)

    out_html = args.out or os.path.join(ROOT, "research", slug, "arxiv_html.md")
    os.makedirs(os.path.dirname(out_html) or ".", exist_ok=True)
    open(out_html, "w", encoding="utf-8").write(html)
    out_text = os.path.join(os.path.dirname(out_html), "arxiv_text.md")
    open(out_text, "w", encoding="utf-8").write(_textize(html))
    print(f"[全文] 已落盘 {out_html} ({len(html)//1024}KB) + arxiv_text.md", file=sys.stderr)
    print(f"  来源: {url}", file=sys.stderr)


if __name__ == "__main__":
    main()
