"""Web 页面抓取工具（三级降级，从 Substack/ai.google.dev 等站点踩坑沉淀）。

背景：Substack、ai.google.dev、deepmind.google 等站点直连常超时（WinError 10060），
代理 127.0.0.1:7897 可通但部分页面只返回 JS 截断版（body_html JSON 缺正文）；
实测 r.jina.ai（Jina Reader）+ 代理对上述站点稳定返回完整 Markdown 正文。

策略（按序尝试，首个成功即返回）：
  1. Jina Reader（r.jina.ai/<url>）经代理 → Markdown 全文（优先）
  2. Jina Reader 直连
  3. 直连抓原始 HTML（urllib + certifi SSL）
  4. 经代理抓原始 HTML

用法：
  python tools/web_fetch.py --url <URL> [--out <file>] [--mode md|html|text] [--proxy http://127.0.0.1:7897] [--timeout 40]

  --mode md    输出 Markdown（Jina 结果；Jina 失败则从 HTML 提取正文文本）
  --mode html  输出原始 HTML（直连/代理抓取）
  --mode text  输出纯文本（Jina 结果或 HTML 剥标签）
  默认 --mode md；无 --out 时打印到 stdout。

退出码：0 成功；1 全部路径失败（stderr 打印各路径错误摘要）。
"""
import argparse
import html as htmllib
import re
import ssl
import sys
import urllib.request

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # certifi 不可用时退回系统默认
    _CTX = ssl.create_default_context()

DEFAULT_PROXY = "http://127.0.0.1:7897"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _opener(proxy=None):
    handlers = [urllib.request.HTTPSHandler(context=_CTX)]
    if proxy:
        handlers.append(urllib.request.ProxyHandler(
            {"https": proxy, "http": proxy}))
    return urllib.request.build_opener(*handlers)


def fetch_jina(url, proxy=None, timeout=40):
    """r.jina.ai 抓取 → (markdown, err)。"""
    try:
        opener = _opener(proxy)
        req = urllib.request.Request(
            "https://r.jina.ai/" + url, headers={"User-Agent": UA})
        return opener.open(req, timeout=timeout).read().decode("utf-8", "ignore"), None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:120]}"


def fetch_jina_with_arxiv_pdf_fallback(url, proxy=None, timeout=40):
    """Jina 抓取；arXiv HTML 返回过短时自动改抓同 id 的 PDF。

    踩坑：arxiv.org/html/2608.13544v1 经 Jina 只返回 270 字异常
    内容，而同 id PDF 可完整转 Markdown。这里对 arxiv.org/html/ 且结果过短
    （<1000 字符）的情况自动尝试 https://arxiv.org/pdf/<id>。
    """
    md, e = fetch_jina(url, proxy=proxy, timeout=timeout)
    if not md:
        return None, e
    m = re.search(r"arxiv\.org/html/([^/?#]+)", url or "")
    if m and len(md) < 1000:
        pdf_url = f"https://arxiv.org/pdf/{m.group(1)}"
        md2, e2 = fetch_jina(pdf_url, proxy=proxy, timeout=timeout)
        if md2 and len(md2) > len(md):
            return md2, None
    return md, None


def fetch_html(url, proxy=None, timeout=40):
    """直连/代理抓原始 HTML → (html, err)。"""
    try:
        opener = _opener(proxy)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        return opener.open(req, timeout=timeout).read().decode("utf-8", "ignore"), None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:120]}"


def html_to_text(html_text):
    """HTML → 可读纯文本（剥 script/style/标签、解实体、压缩空行）。

    保留标题/段落/列表的分段结构（换行），供 Jina 失败时降级提取正文。
    """
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html_text,
               flags=re.S | re.I)
    t = re.sub(r"<h[1-6][^>]*>", "\n\n", t)
    t = re.sub(r"</h[1-6]>", "\n", t)
    t = re.sub(r"<p[^>]*>", "\n\n", t)
    t = re.sub(r"<li[^>]*>", "\n- ", t)
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"<tr[^>]*>", "\n| ", t)
    t = re.sub(r"</td>|</th>", " | ", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = htmllib.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def fetch(url, proxy=DEFAULT_PROXY, timeout=40):
    """三级降级抓取 → (kind, content, err)。

    kind: 'jina'（Markdown）/ 'html'（原始 HTML）/ 'text'（HTML 提取文本）。
    全部失败返回 (None, None, errs)。
    """
    errs = []
    # 1. Jina 经代理（arXiv HTML 过短时自动转 PDF）
    md, e = fetch_jina_with_arxiv_pdf_fallback(url, proxy=proxy, timeout=timeout)
    if md:
        return "jina", md, None
    errs.append(f"jina-proxy: {e}")
    # 2. Jina 直连（同样带 arXiv PDF fallback）
    md, e = fetch_jina_with_arxiv_pdf_fallback(url, proxy=None, timeout=timeout)
    if md:
        return "jina", md, None
    errs.append(f"jina-direct: {e}")
    # 3. 直连 HTML
    html, e = fetch_html(url, proxy=None, timeout=timeout)
    if html:
        return "html", html, None
    errs.append(f"html-direct: {e}")
    # 4. 代理 HTML
    html, e = fetch_html(url, proxy=proxy, timeout=timeout)
    if html:
        return "html", html, None
    errs.append(f"html-proxy: {e}")
    return None, None, " | ".join(errs)


def main():
    ap = argparse.ArgumentParser(description="Web 页面抓取（Jina/直连/代理三级降级）")
    ap.add_argument("--url", required=True, help="目标 URL")
    ap.add_argument("--out", help="输出文件（默认 stdout）")
    ap.add_argument("--mode", choices=["md", "html", "text"], default="md",
                    help="输出形态：md=Markdown（默认）/ html=原始 HTML / text=纯文本")
    ap.add_argument("--proxy", default=DEFAULT_PROXY,
                    help=f"代理地址（默认 {DEFAULT_PROXY}；--no-proxy 禁用）")
    ap.add_argument("--timeout", type=int, default=40)
    ap.add_argument("--no-proxy", action="store_true", help="禁用代理（Jina 与 HTML 均直连）")
    args = ap.parse_args()

    proxy = None if args.no_proxy else args.proxy
    kind, content, err = fetch(args.url, proxy=proxy, timeout=args.timeout)
    if content is None:
        print(f"ERROR: 全部路径失败\n{err}", file=sys.stderr)
        sys.exit(1)

    if args.mode == "html":
        out = content
    elif kind == "jina":
        out = content  # Markdown
        if args.mode == "text":
            # Jina 输出已含 Markdown 标题语法，剥掉 # 前缀做纯文本
            out = re.sub(r"^#+\s*", "", content, flags=re.M)
    else:  # html 源 + 需要 md/text
        out = html_to_text(content)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"已保存（来源: {kind}）: {args.out}（{len(out)} 字符）")
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
