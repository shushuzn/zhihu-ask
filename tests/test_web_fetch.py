"""web_fetch.py 回归测试：HTML 正文提取与三级降级路径的纯逻辑（不联网）。

覆盖（均为纯函数/参数解析，不发起网络请求）：
- html_to_text：剥 script/style、标签、实体解码、表格/列表结构保留、压缩空行
- fetch 路径顺序：通过 monkeypatch fetch_jina/fetch_html 验证三级降级与错误收集
- main 参数解析默认值（--mode md / --proxy 默认 / --no-proxy）

运行：python tests/test_web_fetch.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import web_fetch as wf

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- html_to_text ----
html = "<html><head><style>a{}</style><script>var x=1;</script></head>" \
       "<body><h1>标题</h1><p>第一段 <b>加粗</b>。</p><p>第二段。</p>" \
       "<ul><li>条目 A</li><li>条目 B</li></ul></body></html>"
t = wf.html_to_text(html)
expect("ht+ 剥 script/style", "var x=1" not in t and "a{}" not in t, True)
expect("ht+ 剥标签", "<b>" not in t and "</p>" not in t, True)
expect("ht+ 实体解码", wf.html_to_text("&amp;&lt;tag&gt;"), "&<tag>")
expect("ht+ 段落换行", "\n\n" in t, True)
expect("ht+ 列表保留", "- 条目 A" in t and "- 条目 B" in t, True)
expect("ht+ 压缩空行", "\n\n\n" not in t, True)
expect("ht+ 表格行保留", "| a | b |" in wf.html_to_text("<tr><td>a</td><td>b</td></tr>"), True)
expect("ht+ 空输入", wf.html_to_text(""), "")

# ---- fetch 降级顺序（monkeypatch 模拟）----
calls = []


def fake_jina(url, proxy=None, timeout=40):
    calls.append(("jina", proxy))
    return ("MD:" + url), None


def fake_jina_fail(url, proxy=None, timeout=40):
    calls.append(("jina-fail", proxy))
    return None, "boom"


def fake_html(url, proxy=None, timeout=40):
    calls.append(("html", proxy))
    return ("<html>" + url + "</html>"), None


def fake_html_fail(url, proxy=None, timeout=40):
    calls.append(("html-fail", proxy))
    return None, "boom"


orig_jina, orig_html = wf.fetch_jina, wf.fetch_html
try:
    # 1. Jina 成功即返回
    wf.fetch_jina, wf.fetch_html = fake_jina, fake_html
    calls.clear()
    kind, content, err = wf.fetch("http://x/", proxy="http://p")
    expect("fk+ jina 优先", (kind, content, err), ("jina", "MD:http://x/", None))
    expect("fk+ jina 先走代理", calls[:1], [("jina", "http://p")])
    # 2. Jina 全失败 → 直连 HTML
    wf.fetch_jina, wf.fetch_html = fake_jina_fail, fake_html
    calls.clear()
    kind, content, err = wf.fetch("http://x/", proxy="http://p")
    expect("fk+ 降级直连 html", kind, "html")
    expect("fk+ 直连 html 内容", content, "<html>http://x/</html>")
    # 3. 全部失败 → 错误摘要
    wf.fetch_jina, wf.fetch_html = fake_jina_fail, fake_html_fail
    calls.clear()
    kind, content, err = wf.fetch("http://x/", proxy="http://p")
    expect("fk- 全败 None", kind, None)
    expect("fk- 错误收集", err and "jina-proxy" in err and "html-proxy" in err, True)
finally:
    wf.fetch_jina, wf.fetch_html = orig_jina, orig_html

# ---- main 参数解析（不联网：argparse 默认值/选择项）----
import argparse


def parse(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out")
    ap.add_argument("--mode", choices=["md", "html", "text"], default="md")
    ap.add_argument("--proxy", default=wf.DEFAULT_PROXY)
    ap.add_argument("--timeout", type=int, default=40)
    ap.add_argument("--no-proxy", action="store_true")
    return ap.parse_args(argv)


a = parse(["--url", "http://x/"])
expect("ap+ 默认 mode=md", a.mode, "md")
expect("ap+ 默认 proxy", a.proxy, wf.DEFAULT_PROXY)
expect("ap+ 默认 timeout=40", a.timeout, 40)
expect("ap+ no-proxy 默认 False", a.no_proxy, False)
a = parse(["--url", "http://x/", "--mode", "text", "--no-proxy", "--timeout", "25"])
expect("ap+ 显式参数", (a.mode, a.no_proxy, a.timeout), ("text", True, 25))
try:
    parse(["--url", "http://x/", "--mode", "xml"])
    expect("ap- 非法 mode 应报错", False, True)
except SystemExit:
    expect("ap- 非法 mode 报 SystemExit", True, True)

# ---- 反爬验证页识别 ----
expect("cp+ 微信验证页命中", wf._is_captcha_page("当前环境异常，完成验证后即可继续访问。\n[去验证]"), True)
expect("cp+ Jina warning 命中", wf._is_captcha_page("Warning: This page maybe requiring CAPTCHA"), True)
expect("cp+ 正常正文不命中", wf._is_captcha_page("# 李飞飞最新访谈：AI咋能代替人呢？\n正文内容。"), False)
expect("cp+ 空输入不命中", wf._is_captcha_page(""), False)

# ---- 字符集解码 ----
gbk_bytes = "中文测试GBK编码".encode("gbk")
utf8_bytes = "中文测试UTF8编码".encode("utf-8")
expect("dc+ 按 Content-Type charset 解码", wf._decode_bytes(gbk_bytes, {"Content-Type": "text/html; charset=gbk"}), "中文测试GBK编码")
expect("dc+ 无 charset 默认 UTF-8", wf._decode_bytes(utf8_bytes, {}), "中文测试UTF8编码")
expect("dc+ meta charset 嗅探", wf._decode_bytes(b'<html><meta charset="gb2312"><body>' + gbk_bytes, {}), "<html><meta charset=\"gb2312\"><body>中文测试GBK编码")
expect("dc+ 全失败 UTF-8 ignore 兜底", wf._decode_bytes(b"\xff\xfe\xfd", {}), "")

# ---- fetch 降级：Jina 命中验证页 → 继续降级 HTML ----
def fake_jina_captcha(url, proxy=None, timeout=40):
    calls.append(("jina-captcha", proxy))
    return "当前环境异常，完成验证后即可继续访问。", None

def fake_html_ok(url, proxy=None, timeout=40):
    calls.append(("html", proxy))
    return "<html><h1>真实标题</h1></html>", None

orig_jina, orig_html = wf.fetch_jina, wf.fetch_html
try:
    wf.fetch_jina, wf.fetch_html = fake_jina_captcha, fake_html_ok
    calls.clear()
    kind, content, err = wf.fetch("http://x/", proxy="http://p")
    expect("cp+ Jina 验证页不返回", kind, "html")
    expect("cp+ 降级到 HTML 内容", content, "<html><h1>真实标题</h1></html>")
    expect("cp+ 降级成功无错误摘要", err, None)
finally:
    wf.fetch_jina, wf.fetch_html = orig_jina, orig_html

print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
