
"""
ArXiv 学术预印本检索工具（zhihu-ask 项目专用）

背景：本环境沙箱 Bash 无外网出口（curl/urllib 即使放开沙箱也返回 0 字节），
导致 arxiv-watcher 的 search_arxiv.sh 在本机永远空返回。只有 agent 的 WebFetch
工具走 WorkBuddy 后端代理才能正常联网。本工具为此提供两条路径：

1) 直连模式（--query）：优先 urllib 强制直连 ArXiv API（有外网出口的环境可用）；
   直连不可用（无出口/超时）时自动经 HTTPS_PROXY（默认 http://127.0.0.1:7897/）
   重试一次，仍失败则打印清晰的 WebFetch 降级指引，不静默返回空。

2) 解析模式（--raw <file>）：解析一份「由 agent 经 WebFetch 抓取并保存」的 ArXiv
   API 原始响应，落盘 gathered_arxiv.md。支持两种输入格式：
     - Atom XML（ArXiv API 原生返回：<feed><entry>…</entry></feed>）
     - 分隔符文本（WebFetch 用本项目约定 prompt 产出的 ENTRY 块，见 --print-web-prompt）
   这样在当前无外网出口的环境，也能用 WebFetch 拿真实预印本再交给本工具解析。

用法：
  # 直连（有外网出口的环境）
  python tools/arxiv_search.py --query "constrained decoding JSON" --count 5 \
      --out research/<slug>/gathered_arxiv.md

  # 降级：打印 WebFetch 用 prompt 与 URL，由 agent 抓取后解析
  python tools/arxiv_search.py --query "constrained decoding JSON" --print-web-prompt
  # （agent 用 WebFetch 抓取该 URL，把响应原文保存为 arxiv_raw.txt）
  python tools/arxiv_search.py --raw arxiv_raw.txt --out research/<slug>/gathered_arxiv.md
"""

import argparse
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import channel_state as cs

try:
    from tools.console_encoding import setup as _ce
    _ce()
except Exception:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


def _arxiv_query(query):
    """多词查询自动转 AND 语义（修复 ArXiv API 空格=OR 陷阱），保留引号短语。

    实测：原实现多词裸查询（all:w1 w2 = all:w1 OR all:w2）
    + sortBy=submittedDate 返回的是最新无关论文；此处改为逐词 AND 并相关性排序。
    """
    q = (query or "").strip()
    if not q:
        return ""
    if '"' in q:
        return urllib.parse.quote_plus(q)
    words = q.split()
    if len(words) <= 1:
        return urllib.parse.quote_plus(q)
    return "+AND+".join("all:" + urllib.parse.quote_plus(w) for w in words)


def build_url(query, count):
    q = _arxiv_query(query)
    return (
        "https://export.arxiv.org/api/query?search_query="
        f"{q}&start=0&max_results={count}&sortBy=relevance"
    )


def query_semantics_hint(query):
    """纯函数：提示多词查询的语义处理。

    ArXiv API 中空格与 + 均为 OR 语义（all:a OR all:b），多词裸查询极易命中
    无关结果（实测：'Riemann zeta zeros critical line proportion' 返回自动驾驶/
    量子引力等无关论文）。本工具已自动把多词查询转 AND（all:w1 AND all:w2）
    并按相关性排序；精确短语仍建议用引号。查询含空格、且既无引号也无显式 AND
    时返回提示文本，否则 None。
    """
    if not query or " " not in query:
        return None
    if '"' in query or re.search(r"\bAND\b", query, re.IGNORECASE):
        return None
    return (
        "[提示] ArXiv API 中空格为 OR 语义，本工具已自动将多词查询转 AND（all:w1 "
        "AND all:w2）并按相关性排序；如需精确短语仍建议用引号（如 --query "
        "'\"exact phrase\"'）。"
    )


def _make_opener(proxy=None):
    """构造 urllib opener。proxy=None 强制直连（忽略系统代理）；
    proxy 为 URL 时强制走该代理。"""
    handler = urllib.request.ProxyHandler(
        {"http": proxy, "https": proxy} if proxy else {}
    )
    return urllib.request.build_opener(handler)


def fetch_atom(url, timeout=20, proxy=None):
    """尝试连接 ArXiv API（直连或经代理），返回 (text, status)。

    proxy=None 强制直连（忽略系统代理）；proxy 为 URL 时强制走该代理。
    status: 'ok'（成功）/ '429'（ArXiv 限流）/ 'http'（其他 HTTP 错误）/
            'empty'（空响应）/ 'egress'（连接失败/无外网出口）。
    """
    opener = _make_opener(proxy)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read()
        if not data or len(data) < 50:
            return None, "empty"
        return data.decode("utf-8", errors="ignore"), "ok"
    except urllib.error.HTTPError as e:
        if getattr(e, "code", None) == 429:
            print(f"  [ArXiv] HTTP 429 速率限制（代理 IP 常被限流）", file=sys.stderr)
            return None, "429"
        print(f"  [ArXiv] HTTP {getattr(e, 'code', '?')}：{e}", file=sys.stderr)
        return None, "http"
    except Exception as e:
        print(f"  [连接失败] {type(e).__name__}: {e}", file=sys.stderr)
        return None, "egress"


def fetch_atom_curl(url, timeout=20, proxy=None):
    """curl 兜底通道：urllib 直连/代理失败时自动尝试系统 curl。

    背景：urllib 在本机偶发 SSL/代理栈失败（报"无外网出口"），而系统 curl
    （libcurl/OpenSSL 独立栈）通常可用；此前只能降级让 agent 手动 WebFetch，
    现由工具自动完成。返回 (text, status)，语义与 fetch_atom 一致。
    """
    try:
        import shutil
        if shutil.which("curl") is None:
            return None, "egress"
        cmd = ["curl", "-sL", "--max-time", str(timeout), "-A", "Mozilla/5.0"]
        if proxy:
            cmd += ["--proxy", proxy]
        cmd.append(url)
        r = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    except Exception as e:
        print(f"  [curl兜底失败] {type(e).__name__}: {e}", file=sys.stderr)
        return None, "egress"
    data = r.stdout
    if not data or len(data) < 50:
        return None, "empty"
    return data.decode("utf-8", errors="ignore"), "ok"


def parse_atom_xml(text):
    """解析 ArXiv Atom XML，返回 entry 列表。"""
    entries = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return entries
    for e in root.findall("atom:entry", ATOM_NS):
        title = (e.findtext("atom:title", namespaces=ATOM_NS) or "").strip().replace("\n", " ")
        summary = (e.findtext("atom:summary", namespaces=ATOM_NS) or "").strip().replace("\n", " ")
        published = (e.findtext("atom:published", namespaces=ATOM_NS) or "").strip()
        date = published[:10] if published else ""
        authors = [
            (a.findtext("atom:name", namespaces=ATOM_NS) or "").strip()
            for a in e.findall("atom:author", ATOM_NS)
        ]
        abs_link, pdf_link = "", ""
        for l in e.findall("atom:link", ATOM_NS):
            href = l.get("href", "")
            if l.get("rel") == "alternate" or href.endswith("/abs/"):
                abs_link = href
            elif href.endswith(".pdf") or l.get("title") == "pdf":
                pdf_link = href
        if not abs_link:
            abs_link = pdf_link.replace("pdf", "abs") if pdf_link else ""
        entries.append({
            "title": title,
            "authors": ", ".join(a for a in authors if a),
            "date": date,
            "summary": summary,
            "link": abs_link,
            "pdf": pdf_link,
        })
    return entries


def parse_delimited(text):
    """解析 WebFetch 用约定 prompt 产出的分隔符文本。

    期望每块形如：
        ENTRY
        TITLE: ...
        AUTHORS: ...
        DATE: YYYY-MM-DD
        SUMMARY: ...
        LINK: https://arxiv.org/abs/...
        PDF: https://arxiv.org/pdf/...
        ---
    SUMMARY 可跨多行，直到下一个已知字段或块结束。
    """
    entries = []
    # 以 ENTRY 或 --- 切分块；兼容无 ENTRY 前缀的纯块列表
    blocks = re.split(r"(?i)^\s*ENTRY\s*$|^\s*---\s*$", text, flags=re.MULTILINE)
    field_re = re.compile(r"(?i)^(TITLE|AUTHORS?|DATE|SUMMARY|LINK|PDF):\s*(.*)$")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        cur = {"title": "", "authors": "", "date": "", "summary": "", "link": "", "pdf": ""}
        in_summary = False
        for line in block.splitlines():
            m = field_re.match(line)
            if m:
                key = m.group(1).upper()
                val = m.group(2).strip()
                in_summary = False
                if key == "TITLE":
                    cur["title"] = val
                elif key.startswith("AUTHOR"):
                    cur["authors"] = val
                elif key == "DATE":
                    cur["date"] = val
                elif key == "LINK":
                    cur["link"] = val
                elif key == "PDF":
                    cur["pdf"] = val
                elif key == "SUMMARY":
                    cur["summary"] = val
                    in_summary = True
            elif in_summary:
                cur["summary"] += " " + line.strip()
        if cur["title"]:
            entries.append(cur)
    return entries


def format_gathered(entries, query):
    lines = ["# ArXiv 学术预印本检索素材库", ""]
    lines.append(f"> 检索词：{query}")
    lines.append(f"> 命中：{len(entries)} 条（工具：tools/arxiv_search.py）")
    lines.append("")
    if not entries:
        lines.append("（无有效素材）")
        return "\n".join(lines) + "\n"
    for i, e in enumerate(entries, 1):
        lines.append(f"## {i}. {e['title']}")
        if e["authors"]:
            lines.append(f"- 作者：{e['authors']}")
        if e["date"]:
            lines.append(f"- 日期：{e['date']}")
        if e["link"]:
            lines.append(f"- 链接：{e['link']}")
        if e["pdf"]:
            lines.append(f"- PDF：{e['pdf']}")
        if e["summary"]:
            lines.append("")
            lines.append(f"  {e['summary']}")
        lines.append("")
    return "\n".join(lines) + "\n"


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


def _auto_mark_p(out, entries, slug_explicit):
    """落盘 gathered_arxiv.md 后自动登记通道 P（arxiv 归学术预印本聚合通道 P）。"""
    slug = slug_explicit or (cs.derive_slug_from_out(out) if out else None)
    if not slug:
        return
    status = "done" if entries else "empty"
    note = f"命中 {len(entries)} 条（arxiv）" if entries else "通道 P 无有效素材（arxiv）"
    if cs.mark(slug, "P", status, note=note):
        print(f"[自动登记] 通道 P（arxiv 平台）: {status} —— {note}", file=sys.stderr)
    else:
        print(f"[提示] 未找到 research/{slug}/.progress.json，跳过通道 P 自动登记（请先 research_start）", file=sys.stderr)


def main():
    import sys as _sys
    ap = argparse.ArgumentParser(description="ArXiv 学术预印本检索（含 WebFetch 降级）")
    ap.add_argument("--query", help="检索词（直连或生成 WebFetch prompt 用）")
    ap.add_argument("--count", type=int, default=5, help="返回条数（默认 5）")
    ap.add_argument("--raw", help="解析一份已保存的原始响应（XML 或分隔符文本）")
    ap.add_argument("--out", help="输出文件（默认打印到 stdout）")
    ap.add_argument("--slug", help="研究报告 slug（自动登记通道 P 用；省略则从 --out 路径反推）")
    ap.add_argument("--print-web-prompt", action="store_true",
                    help="打印 WebFetch 用 prompt 与 URL（无外网出口环境走此路径）")
    ap.add_argument("--proxy", help="经指定代理重试（默认读 HTTPS_PROXY 环境变量或 http://127.0.0.1:7897/）")
    args = ap.parse_args()

    if args.print_web_prompt:
        if not args.query:
            print("ERROR: --print-web-prompt 需要 --query", file=sys.stderr)
            sys.exit(1)
        hint = query_semantics_hint(args.query)
        if hint:
            print(hint + "\n", file=sys.stderr)
        url = build_url(args.query, args.count)
        print("=== 拷贝以下 prompt 到 WebFetch 工具 ===\n", file=sys.stderr)
        print(WEB_PROMPT_TEMPLATE.format(url=url), file=sys.stderr)
        print("\n=== 把 WebFetch 返回内容保存为 arxiv_raw.txt 后运行 ===", file=sys.stderr)
        print(f"python tools/arxiv_search.py --raw arxiv_raw.txt{' --out ' + args.out if args.out else ''}", file=sys.stderr)
        return

    if args.raw:
        if not os.path.isfile(args.raw):
            print(f"ERROR: 未找到原始响应文件 {args.raw}", file=sys.stderr)
            sys.exit(1)
        with open(args.raw, encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        entries = parse_atom_xml(raw)
        if not entries:
            entries = parse_delimited(raw)
        content = format_gathered(entries, args.query or "(from raw)")
        if args.out:
            os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"已解析并落盘 {args.out}（{len(entries)} 条）", file=sys.stderr)
            _auto_mark_p(args.out, entries, args.slug)
        else:
            sys.stdout.write(content)
        return

    if not args.query:
        print("ERROR: 需 --query（直连）或 --raw（解析）或 --print-web-prompt", file=sys.stderr)
        sys.exit(1)

    hint = query_semantics_hint(args.query)
    if hint:
        print(hint + "\n", file=sys.stderr)
    url = build_url(args.query, args.count)
    print(f"[直连] {url}", file=sys.stderr)
    text, status = fetch_atom(url, timeout=12)
    if not text and status in ("egress", "empty"):
        # 直连不可用（无外网出口/超时）→ 经代理重试一次。
        # 本环境 urllib 经 HTTPS_PROXY 可联网，但 ArXiv 对代理 IP 常限流，
        # 故仅重试一次，失败即走 curl 兜底/WebFetch 降级，不无限重试。
        proxy = (args.proxy
                 or os.environ.get("HTTPS_PROXY")
                 or os.environ.get("https_proxy")
                 or "http://127.0.0.1:7897/")
        print(f"[重试] 经代理 {proxy} 重试一次…", file=sys.stderr)
        text, status = fetch_atom(url, timeout=25, proxy=proxy)
        if text:
            print("  [代理重试成功]", file=sys.stderr)
    if not text and status in ("egress", "empty"):
        # curl 兜底：urllib 栈失败但系统 curl 常可用（独立 SSL 栈），
        # 直连与代理各试一次，仍失败才降级 WebFetch。
        print("[curl兜底] urllib 通道失败，尝试系统 curl 直连…", file=sys.stderr)
        text, status = fetch_atom_curl(url, timeout=20)
        if text:
            print("  [curl兜底成功]", file=sys.stderr)
        else:
            print(f"[curl兜底] 直连失败（{status}），尝试经代理…", file=sys.stderr)
            text, status = fetch_atom_curl(url, timeout=25, proxy=proxy)
            if text:
                print("  [curl兜底-代理成功]", file=sys.stderr)
    if text:
        entries = parse_atom_xml(text)
        if entries:
            content = format_gathered(entries, args.query)
            if args.out:
                os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
                with open(args.out, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"已落盘 {args.out}（{len(entries)} 条）", file=sys.stderr)
                _auto_mark_p(args.out, entries, args.slug)
            else:
                sys.stdout.write(content)
            return

    # 直连与代理均失败 → 清晰降级指引，不静默返回空
    if status == "429":
        print("\n[降级] ArXiv 直连被限流（HTTP 429，代理 IP 共享常被限），改用 WebFetch 更稳。", file=sys.stderr)
    elif status == "http":
        print("\n[降级] ArXiv 直连与代理均返回 HTTP 错误，改用 WebFetch。", file=sys.stderr)
    else:
        print("\n[降级] 当前环境无外网出口（直连与代理均失败），ArXiv 直连不可用。", file=sys.stderr)
    print("请改用 agent 的 WebFetch 工具完成检索：\n", file=sys.stderr)
    print(WEB_PROMPT_TEMPLATE.format(url=url), file=sys.stderr)
    print("\n把返回内容保存为 research/<slug>/arxiv_raw.txt 后运行：", file=sys.stderr)
    print(f"  python tools/arxiv_search.py --raw research/<slug>/arxiv_raw.txt{' --out ' + args.out if args.out else ''}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
