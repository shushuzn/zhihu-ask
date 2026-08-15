# -*- coding: utf-8 -*-
"""微信公众号自动发草稿工具（zhihu-ask 项目专用）

按腾讯云教程「WorkBuddy连接微信公众号——自动发文章」实现：
  access_token（2 小时缓存）→ 上传封面图（永久素材 media_id）→ draft/add 创建草稿。

用法：
  python tools/wechat_publish.py --slug <slug> [--title 标题] [--author 作者] [--digest 摘要] [--cover 封面.png]

凭证（环境变量，凭证纪律：不入项目文件）：
  WECHAT_APPID     公众号 AppID（后台→开发→基本配置）
  WECHAT_APPSECRET 公众号 AppSecret（同上页面重置获取，仅显示一次）
  IP 白名单：后台「基本配置」需加入本机出口 IP，否则 API 返回 40164 错误

前置：
  1. 报告为 Markdown，工具自动转公众号 HTML（内联样式；LaTeX 公式以文本保留）
  2. 封面图建议 900x500 比例；图片需上传为永久素材（正文内图片同理会处理）
  3. 发布后到公众号后台「草稿箱」人工点「发表」（半自动，与知乎一致）

依赖：requests（pip install requests）
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from latex_unicode import latex_to_unicode

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

API_BASE = "https://api.weixin.qq.com/cgi-bin"
TOKEN_CACHE = os.path.expanduser("~/.config/wechat_access_token.json")


# ─── access_token（2 小时缓存）─────────────────────────────────────────────

def get_access_token(appid, secret):
    """获取 access_token，带本地缓存（7200 秒有效期）。"""
    now = time.time()
    try:
        with open(TOKEN_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
        if cache.get("expires_at", 0) > now + 300:
            return cache["access_token"]
    except Exception:
        pass
    url = (f"{API_BASE}/token?grant_type=client_credential"
           f"&appid={urllib.parse.quote(appid)}&secret={urllib.parse.quote(secret)}")
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "access_token" not in data:
        sys.exit(f"[失败] 获取 token 失败：{data}")
    with open(TOKEN_CACHE, "w", encoding="utf-8") as f:
        json.dump({"access_token": data["access_token"],
                   "expires_at": now + data.get("expires_in", 7200)}, f)
    print(f"[OK] access_token 已获取（缓存至 {time.strftime('%H:%M:%S', time.localtime(now + data.get('expires_in', 7200)))}）")
    return data["access_token"]


def api_post(token, path, payload):
    """POST JSON 到微信 API。"""
    url = f"{API_BASE}/{path}?access_token={token}"
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ─── 封面图上传（永久素材）─────────────────────────────────────────────────

def upload_cover(token, cover_path):
    """上传封面图为永久图片素材，返回 media_id。"""
    import mimetypes
    import uuid
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    fname = os.path.basename(cover_path)
    ctype = mimetypes.guess_type(cover_path)[0] or "image/png"
    with open(cover_path, "rb") as f:
        filedata = f.read()
    body = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="media"; filename="{fname}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n").encode("utf-8") + filedata + f"\r\n--{boundary}--\r\n".encode()
    url = f"{API_BASE}/material/add_material?access_token={token}&type=image"
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "media_id" not in data:
        sys.exit(f"[失败] 封面上传失败：{data}")
    print(f"[OK] 封面已上传 media_id={data['media_id']}")
    return data["media_id"]


# ─── Markdown → 公众号 HTML（内联样式）───────────────────────────────────

_INLINE_STYLES = {
    "h1": 'style="font-size:24px;font-weight:bold;margin:28px 0 14px;color:#1a1a1a;border-left:4px solid #576b95;padding-left:10px;"',
    "h2": 'style="font-size:20px;font-weight:bold;margin:22px 0 10px;color:#2a2a2a;border-left:4px solid #9aa8c8;padding-left:10px;"',
    "h3": 'style="font-size:17px;font-weight:bold;margin:16px 0 8px;color:#333;"',
    "p": 'style="font-size:15px;line-height:1.8;margin:10px 0;color:#3f3f3f;text-align:justify;"',
    "li": 'style="font-size:15px;line-height:1.8;margin:4px 0;color:#3f3f3f;"',
    "td": 'style="border:1px solid #d8d8d8;padding:7px 10px;font-size:14px;line-height:1.6;color:#3f3f3f;"',
    "th": 'style="border:1px solid #d8d8d8;padding:7px 10px;font-size:14px;font-weight:bold;background:#f0f3f8;color:#333;"',
    "table": 'style="border-collapse:collapse;margin:14px 0;width:100%;border-radius:6px;overflow:hidden;"',
    "strong": 'style="font-weight:bold;color:#1a1a1a;"',
    "em": 'style="font-style:italic;color:#576b95;"',
    "blockquote": 'style="border-left:4px solid #576b95;background:#f7f8fa;padding:10px 14px;margin:12px 0;color:#57606a;font-size:14px;line-height:1.7;border-radius:0 6px 6px 0;"',
    "code": 'style="background:#f5f5f5;border-radius:4px;padding:2px 6px;font-family:Consolas,Menlo,monospace;font-size:13px;color:#c7254e;"',
    "pre": 'style="background:#f8f8f8;border:1px solid #e5e5e5;border-radius:6px;padding:12px 14px;margin:12px 0;font-family:Consolas,Menlo,monospace;font-size:13px;line-height:1.6;color:#333;overflow-x:auto;"',
    "img": 'style="max-width:100%;border-radius:6px;margin:12px 0;display:block;"',
    "hr": 'style="border:none;border-top:1px solid #e5e5e5;margin:20px 0;"',
}


def md_to_wechat_html(md_text):
    """Markdown → 公众号 HTML（轻量转换：标题/段落/列表/表格/引用/链接）。

    公式（LaTeX $...$）以 Unicode 可读文本保留（公众号不渲染公式）。
    首行 `# 标题` 跳过——图文消息 title 字段已承载，避免正文重复。
    """
    lines = md_text.split("\n")
    if lines and lines[0].lstrip().startswith("# "):
        lines = lines[1:]
    html, i, in_table = [], 0, False

    def esc(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    while i < len(lines):
        ln = lines[i]
        # 表格
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            cells0 = [c.strip() for c in rows[0].strip("|").split("|")]
            html.append(f"<table {' '.join([_INLINE_STYLES['table']])}>")
            html.append("<tr>" + "".join(f"<th {_INLINE_STYLES['th']}>{esc(c)}</th>" for c in cells0) + "</tr>")
            for r in rows[2:]:
                cells = [c.strip() for c in r.strip("|").split("|")]
                html.append("<tr>" + "".join(f"<td {_INLINE_STYLES['td']}>{esc(c)}</td>" for c in cells) + "</tr>")
            html.append("</table>")
            continue
        # 标题
        m = re.match(r"^(#{1,3})\s+(.*)", ln)
        if m:
            level = len(m.group(1))
            tag = f"h{level}"
            html.append(f"<{tag} {_INLINE_STYLES[tag]}>{esc(m.group(2))}</{tag}>")
            i += 1
            continue
        # 引用
        if ln.startswith(">"):
            lines_q = []
            while i < len(lines) and lines[i].startswith(">"):
                lines_q.append(lines[i][1:].strip())
                i += 1
            html.append(f"<blockquote {_INLINE_STYLES['blockquote']}>{esc(' '.join(lines_q))}</blockquote>")
            continue
        # 代码块（围栏）
        if ln.strip().startswith("```"):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            html.append(f"<pre {_INLINE_STYLES['pre']}>{esc(chr(10).join(code_lines))}</pre>")
            continue
        # 分隔线
        if re.match(r"^([-*_])\1{2,}$", ln.strip()):
            html.append(f"<hr {_INLINE_STYLES['hr']} />")
            i += 1
            continue
        # 无序列表
        if re.match(r"^[-*]\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i]):
                items.append(f"<li {_INLINE_STYLES['li']}>{esc(re.sub(r'^[-*]\s+', '', lines[i]))}</li>")
                i += 1
            html.append("<ul style='padding-left:20px;margin:10px 0;'>" + "".join(items) + "</ul>")
            continue
        # 有序列表
        if re.match(r"^\d+[.)]\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^\d+[.)]\s+", lines[i]):
                items.append(f"<li {_INLINE_STYLES['li']}>{esc(re.sub(r'^\d+[.)]\s+', '', lines[i]))}</li>")
                i += 1
            html.append("<ol style='padding-left:20px;margin:10px 0;'>" + "".join(items) + "</ol>")
            continue
        # 空行
        if not ln.strip():
            i += 1
            continue
        # 段落（合并相邻非空行）
        para = []
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", ">", "-", "*", "1.")):
            para.append(lines[i].strip())
            i += 1
        text = " ".join(para)
        if not text:
            i += 1  # 无法分类的行：推进跳过，防死循环
            continue
        # 公式：$...$ → Unicode 可读文本（md 换公式方案）
        text = re.sub(r"\$([^$]+)\$", lambda m: latex_to_unicode(m.group(1)), text)
        # 先转义原文，再生成行内标签（esc 不能吞掉生成的标签）
        text = esc(text)
        # 行内代码
        text = re.sub(r"`([^`]+)`", lambda m: f"<code {_INLINE_STYLES['code']}>{m.group(1)}</code>", text)
        # 简单行内：加粗 / 斜体
        text = re.sub(r"\*\*(.+?)\*\*", lambda m: f"<strong {_INLINE_STYLES['strong']}>{m.group(1)}</strong>", text)
        text = re.sub(r"\*([^*]+)\*", lambda m: f"<em {_INLINE_STYLES['em']}>{m.group(1)}</em>", text)
        # 行内图片（![]()）
        text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)",
                      lambda m: f"<img src='{m.group(2)}' {_INLINE_STYLES['img']} alt='{m.group(1)}' />", text)
        html.append(f"<p {_INLINE_STYLES['p']}>{text}</p>")
    return "\n".join(html)


def load_report(slug):
    """返回 (md 路径, docx 路径)。内容源：docx 优先（Word 排版版）。"""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "research", slug)
    return (os.path.join(base, "report.md"), os.path.join(base, "report.docx"))


def docx_to_wechat_html(docx_path, token=None):
    """docx → 公众号 HTML：标题/段落/表格/图片（上传微信素材）/公式文本。

    图片：内嵌 PNG 提取后上传为永久素材，img src 用素材 URL（公众号不支持外域图片）。
    公式：OMML 的 m:t 文本拼接（公众号不渲染公式，以文本保留）。
    """
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(docx_path)
    html = []

    def esc(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def omml_text(el):
        parts = []
        for mt in el.findall(".//" + qn("m:t")):
            if mt.text:
                parts.append(mt.text)
        return "".join(parts)

    def upload_blob(blob):
        import uuid
        boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
        body = (f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="media"; filename="img.png"\r\n'
                "Content-Type: image/png\r\n\r\n").encode() + blob + f"\r\n--{boundary}--\r\n".encode()
        url = f"{API_BASE}/material/add_material?access_token={token}&type=image"
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "url" not in data:
            raise RuntimeError(f"图片上传失败：{data}")
        return data["url"]

    def walk_para(p):
        style = ""
        ps = p.findall(".//" + qn("w:pStyle"))
        if ps:
            style = ps[0].get(qn("w:val")) or ""
        text = "".join(r.text or "" for r in p.findall(".//" + qn("w:t"))).strip()
        omml = omml_text(p)
        if omml and omml not in text:
            text = (text + " " + omml).strip()
        if not text:
            return ""
        if style.startswith("Heading1"):
            return f"<h1 {_INLINE_STYLES['h1']}>{esc(text)}</h1>"
        if style.startswith("Heading2"):
            return f"<h2 {_INLINE_STYLES['h2']}>{esc(text)}</h2>"
        if style.startswith("Heading3"):
            return f"<h3 {_INLINE_STYLES['h3']}>{esc(text)}</h3>"
        return f"<p {_INLINE_STYLES['p']}>{esc(text)}</p>"

    def walk_table(tbl):
        rows = []
        for tr in tbl.findall(".//" + qn("w:tr")):
            cells = []
            for tc in tr.findall(".//" + qn("w:tc")):
                ct = "".join(t.text or "" for t in tc.findall(".//" + qn("w:t")))
                cells.append(f"<td {_INLINE_STYLES['td']}>{esc(ct)}</td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        return f"<table {_INLINE_STYLES['table']}>" + "".join(rows) + "</table>"

    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            h = walk_para(child)
            if h:
                html.append(h)
            for blip in child.findall(".//" + qn("a:blip")):
                rId = blip.get(qn("r:embed"))
                if rId and token:
                    part = doc.part.related_parts.get(rId)
                    if part is not None and getattr(part, "blob", None):
                        try:
                            img_url = upload_blob(part.blob)
                            html.append(f"<img src='{img_url}' style='max-width:100%;margin:10px 0;' />")
                            print("[OK] 正文图片已上传素材")
                        except Exception as e:
                            print(f"[警告] 图片上传失败：{e}")
        elif child.tag == qn("w:tbl"):
            h = walk_table(child)
            if h:
                html.append(h)
    return "\n".join(html)


def auto_cover(title, out_path):
    """PIL 生成公众号封面（900x500，深色渐变 + 标题文字）。"""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 900, 500
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        for x in range(W):
            t = x / W
            px[x, y] = (int(18 + 30 * t), int(24 + 20 * t), int(42 + 15 * t))
    draw = ImageDraw.Draw(img)
    font = None
    for cand in ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc",
                 "C:/Windows/Fonts/simhei.ttf"]:
        try:
            font = ImageFont.truetype(cand, 40)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    # 标题按 24 字/行折行，最多 2 行
    lines, cur = [], ""
    for ch in title:
        cur += ch
        if len(cur) >= 22:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    lines = lines[:2]
    y = H // 2 - 30 * len(lines)
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font)
        draw.text(((W - (bbox[2] - bbox[0])) // 2, y), ln, fill=(240, 240, 245), font=font)
        y += 60
    img.save(out_path, "PNG")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="微信公众号自动发草稿（半自动：推送草稿箱，人工点发表）")
    ap.add_argument("--slug", required=True, help="研究 slug")
    ap.add_argument("--title", help="文章标题（默认取报告首行标题）")
    ap.add_argument("--author", default="", help="作者（默认取环境变量 WECHAT_AUTHOR）")
    ap.add_argument("--digest", default="", help="摘要（默认取报告结论前 80 字）")
    ap.add_argument("--cover", help="封面图路径（可选；上传为永久素材）")
    ap.add_argument("--source-md", action="store_true", help="强制用 report.md 而非 docx")
    args = ap.parse_args()

    appid = os.environ.get("WECHAT_APPID", "")
    secret = os.environ.get("WECHAT_APPSECRET", "")
    if not appid or not secret:
        sys.exit("[失败] 请设置环境变量 WECHAT_APPID 与 WECHAT_APPSECRET"
                 "（公众号后台→开发→基本配置；同时把本机出口 IP 加入 IP 白名单）")

    md = load_report(args.slug)
    md_path, docx_path = md
    # 内容源：docx 优先（Word 排版版）
    if not args.source_md and os.path.exists(docx_path):
        print("[内容源] report.docx（Word 排版版）")
        token = get_access_token(appid, secret)
        content_html = docx_to_wechat_html(docx_path, token=token)
        if args.title:
            title = args.title
        else:
            import re as _re2
            m = _re2.search(r"<h1[^>]*>(.*?)</h1>", content_html, _re2.S)
            title = _re2.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
        print(f"[内容] {title}（docx→HTML {len(content_html)} 字符）")
    else:
        if not os.path.exists(md_path):
            sys.exit(f"未找到报告: {md_path}")
        with open(md_path, encoding="utf-8") as f:
            md_text = f.read()
        print("[内容源] report.md（Markdown 版）")
        title = args.title or md_text.splitlines()[0].lstrip("# ").strip()
        content_html = md_to_wechat_html(md_text)
        print(f"[内容] {title}（HTML {len(content_html)} 字符）")
        token = get_access_token(appid, secret)
    if args.cover:
        cover_id = upload_cover(token, args.cover)
    else:
        cover_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "..", "research", args.slug, "_auto_cover.png")
        auto_cover(title, cover_path)
        print(f"[OK] 已自动生成封面 {cover_path}")
        cover_id = upload_cover(token, cover_path)

    digest = args.digest
    if not digest and content_html:
        # 从 HTML 取第一段 p 文本前 80 字作为摘要
        import re as _re
        m = _re.search(r"<p[^>]*>(.*?)</p>", content_html, _re.S)
        if m:
            digest = _re.sub(r"<[^>]+>", "", m.group(1))[:80]

    article = {
        "title": title,
        "author": args.author or os.environ.get("WECHAT_AUTHOR", ""),
        "digest": digest,
        "content": content_html,
        "content_source_url": "",
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    if cover_id:
        article["thumb_media_id"] = cover_id

    result = api_post(token, "draft/add", {"articles": [article]})
    if "media_id" not in result:
        sys.exit(f"[失败] 创建草稿失败：{result}")
    print(f"[OK] 草稿已创建 media_id={result['media_id']}")
    print("=" * 50)
    print("请到公众号后台「草稿箱」检查并人工点「发表」（半自动）")
    print("=" * 50)


if __name__ == "__main__":
    main()
