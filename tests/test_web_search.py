"""web_search.py 回归测试：域名提取 / 低质过滤 / region 判定 / 查询变体（14 项）。

覆盖：domain_of（http/https/无协议/www 前缀）、filter_results（黑名单域/非黑名单保留）、
pick_region（中文→cn-zh、英文→us-en、空）、query_variants（原样/去引号/超长截断/去重保序/空）。

运行：python tests/test_web_search.py
"""
import os
import sys
import json
import shutil
import unittest.mock as mock

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import web_search as ws

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


def test_domain_of():
    expect("http URL", ws.domain_of("http://example.com/a/b"), "example.com")
    expect("https URL", ws.domain_of("https://www.bbc.co.uk/news"), "bbc.co.uk")
    expect("www 前缀去除", ws.domain_of("https://www.pinterest.com/pin/1"), "pinterest.com")
    expect("无协议", ws.domain_of("example.org/x"), "")
    expect("空 URL", ws.domain_of(""), "")


def test_filter_results():
    items = [
        {"title": "好文", "href": "https://example.com/a", "body": "x"},
        {"title": "图片站", "href": "https://www.pinterest.com/pin/1", "body": "x"},
        {"title": "游戏站", "href": "https://www.epicwar.com/maps/1", "body": "x"},
        {"title": "正常站带路径", "href": "https://www.heraldscotland.com/news/1", "body": "x"},
    ]
    got = ws.filter_results(items)
    expect("过滤黑名单保留正常站", [r["title"] for r in got], ["好文", "正常站带路径"])


def test_pick_region():
    expect("中文查询", ws.pick_region("投石机 斯特灵城堡"), "cn-zh")
    expect("英文查询", ws.pick_region("trebuchet skeleton Stirling"), "us-en")
    expect("空查询", ws.pick_region(""), "us-en")
    expect("混合含中文", ws.pick_region("trebuchet 投石机"), "cn-zh")


def test_query_variants():
    expect("原样", ws.query_variants("trebuchet Stirling"), ["trebuchet Stirling"])
    expect("去引号", ws.query_variants('"first confirmed" trebuchet'),
           ['"first confirmed" trebuchet', "first confirmed trebuchet"])
    long_q = "a" * 100
    expect("超长截断", len(ws.query_variants(long_q)[-1]), 80)
    expect("超长保留原样+截断", len(ws.query_variants(long_q)), 2)
    expect("空查询无变体", ws.query_variants(""), [])
    expect("去重保序", ws.query_variants('"同" 同'), ['"同" 同', "同 同"])


def test_parse_openalex():
    data = {"results": [
        {"title": "Trebuchet mechanics", "doi": "10.1000/xyz",
         "publication_date": "2024-05-01",
         "primary_location": {"source": {"display_name": "J. Mechanics"}}},
        {"title": "无DOI条目", "id": "https://openalex.org/W123",
         "publication_date": "2023-01-01", "primary_location": {}},
        {"title": "", "doi": "10.1000/empty"},
    ]}
    got = ws.parse_openalex(data)
    expect("openalex解析2条", len(got), 2)
    expect("doi转链接", got[0]["href"], "https://doi.org/10.1000/xyz")
    expect("openalex-id兜底", got[1]["href"], "https://openalex.org/W123")
    expect("正文含来源与年份", "J. Mechanics" in got[0]["body"] and "2024" in got[0]["body"], True)
    # 带前缀的 DOI 不重复拼接
    got2 = ws.parse_openalex({"results": [
        {"title": "T", "doi": "https://doi.org/10.2000/pre", "publication_date": "2020-01-01", "primary_location": {}}]})
    expect("带前缀DOI不重复", got2[0]["href"], "https://doi.org/10.2000/pre")


def test_parse_crossref():
    data = {"message": {"items": [
        {"title": ["Siege engines"], "DOI": "10.1000/abc",
         "container-title": ["Medieval Review"], "published-print": {"date-parts": [[2022]]}},
        {"title": ["无DOI"], "DOI": ""},
    ]}}
    got = ws.parse_crossref(data)
    expect("crossref解析1条", len(got), 1)
    expect("DOI转链接", got[0]["href"], "https://doi.org/10.1000/abc")
    expect("正文含期刊年份", "Medieval Review" in got[0]["body"] and "2022" in got[0]["body"], True)


def test_parse_hn():
    data = {"hits": [
        {"title": "Building a trebuchet", "url": "https://x.com/t",
         "objectID": "42", "points": 100, "num_comments": 30},
        {"title": "无url条目", "url": None, "objectID": "43", "points": 5, "num_comments": 1},
        {"title": "", "objectID": "44"},
    ]}
    got = ws.parse_hn(data)
    expect("hn解析2条", len(got), 2)
    expect("有url用url", got[0]["href"], "https://x.com/t")
    expect("无url兜底item", "item?id=43" in got[1]["href"], True)
    expect("正文含讨论数", "100 分" in got[0]["body"], True)


def test_curl_fallback():
    """http_get_json urllib 失败时 curl 兜底。"""
    import json as _json
    payload = b'{"message": {"items": [{"title": ["T"], "DOI": "10.1000/x"}]}}'

    def fake_curl(url, timeout=12):
        return _json.loads(payload.decode())

    with mock.patch.object(ws.urllib.request, "urlopen", side_effect=OSError("ssl down")), \
         mock.patch.object(ws, "http_get_curl", side_effect=fake_curl):
        try:
            got = ws.http_get_json("https://api.crossref.org/works?query=t")
            expect("curl兜底- urllib失败后接管", got["message"]["items"][0]["DOI"], "10.1000/x")
        except Exception as e:
            expect("curl兜底- urllib失败后接管", False, str(e))

    # 两者都失败 → 抛异常（调用方容错）
    with mock.patch.object(ws.urllib.request, "urlopen", side_effect=OSError("down")), \
         mock.patch.object(ws, "http_get_curl", return_value=None):
        try:
            ws.http_get_json("https://api.openalex.org/works?search=t")
            expect("curl兜底- 双通道失败抛异常", False, True)
        except Exception:
            expect("curl兜底- 双通道失败抛异常", True, True)


def test_parse_bing_html():
    html_text = (
        '<html><body><ol id="b_results">'
        '<li class="b_algo"><h2><a href="https://example.com/a">标题 A</a></h2>'
        '<div class="b_caption"><p>摘要 A 内容</p></div></li>'
        '<li class="b_algo"><h2><a href="https://example.com/b">标题 &amp; B</a></h2>'
        '<div class="b_caption"><p>摘要 B</p></div></li>'
        '<li class="b_no">无结果块</li>'
        "</ol></body></html>"
    )
    got = ws.parse_bing_html(html_text)
    expect("bing解析2条", len(got), 2)
    expect("标题解实体", got[1]["title"], "标题 & B")
    expect("链接保留", got[0]["href"], "https://example.com/a")
    expect("摘要提取", "摘要 A" in got[0]["body"], True)
    expect("无b_algo空列表", ws.parse_bing_html("<html>no results</html>"), [])


def test_bing_mirror_filter():
    """Bing 引擎实测污染源（Gemini/Claude 中文镜像站）应被低质过滤拦截。"""
    items = [
        {"title": "镜像站", "href": "https://www.gemini-cnblog.com/blog/x", "body": "x"},
        {"title": "镜像站2", "href": "https://gemini-cn.cn/", "body": "x"},
        {"title": "正常站", "href": "https://www.ithome.com/0/988/280.htm", "body": "x"},
        {"title": "新闻站", "href": "https://www.ai-master.cc/news/news-7753", "body": "x"},
    ]
    got = ws.filter_results(items)
    expect("镜像站过滤", [r["title"] for r in got], ["正常站"])


def test_search_tavily_nokey():
    """无 TAVILY_API_KEY 时 tavily 引擎返回 []（不报错、不请求）。"""
    saved = ws.TAVILY_API_KEY
    try:
        ws.TAVILY_API_KEY = ""
        got = ws.search_tavily("test query")
        expect("tavily 无 key 空列表", got, [])
    finally:
        ws.TAVILY_API_KEY = saved


def test_tavily_payload():
    """tavily 请求 payload 构造（含 news 主题、max_results、basic 深度）。"""
    # 通过 monkeypatch urllib.request.urlopen 捕获请求体验证 payload 正确
    import json as _json
    captured = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return _json.dumps({"results": [
                {"title": "T1", "url": "https://example.com/1", "content": "内容一"},
                {"title": "", "url": "https://example.com/empty"},
                {"title": "T2", "url": "https://example.com/2", "content": "内容二"},
            ], "answer": "综合答案"}).encode("utf-8")

    def fake_urlopen(req, timeout=20):
        captured["body"] = _json.loads(req.data.decode("utf-8"))
        captured["url"] = req.full_url
        return FakeResp()

    orig = ws.urllib.request.urlopen
    ws.urllib.request.urlopen = fake_urlopen
    try:
        ws.TAVILY_API_KEY = "test-key"
        got = ws.search_tavily("query x", max_results=5, news=True)
        expect("tavily 解析过滤空标题", [r["title"] for r in got], ["T1", "T2"])
        expect("tavily url 正确", captured["url"], "https://api.tavily.com/search")
        expect("tavily payload key", captured["body"]["api_key"], "test-key")
        expect("tavily payload news", captured["body"]["topic"], "news")
        expect("tavily payload 深度", captured["body"]["search_depth"], "basic")
        expect("tavily payload max", captured["body"]["max_results"], 5)
    finally:
        ws.urllib.request.urlopen = orig
        ws.TAVILY_API_KEY = ""


def test_auto_register_b():
    # 落盘标准 research/<slug>/gathered_web.md → 自动登记通道 B（done/empty）
    base = testutil.mktestdir(prefix="tb_")
    slug = "b-slug"
    slug_dir = os.path.join(base, "research", slug)
    os.makedirs(slug_dir)
    with open(os.path.join(slug_dir, ".progress.json"), "w", encoding="utf-8") as f:
        json.dump({"stage": "phase1_done", "data": {"domain": "AI"}}, f)
    import channel_state as cs
    old_root = cs.ROOT
    cs.ROOT = base
    try:
        ok, msg = ws.auto_register_channel_b(
            os.path.join("research", slug, "gathered_web.md"), None,
            [{"title": "t", "href": "h"}], "auto")
        expect("B+ 有素材登记 done", ok, True)
        prog = json.load(open(os.path.join(slug_dir, ".progress.json"), encoding="utf-8"))
        e = prog["data"]["channels_done"]["B"]
        expect("B+ status done", e["status"], "done")
        expect("B+ note 含命中数", "命中 1 条" in e["note"], True)

        ok2, _ = ws.auto_register_channel_b(
            os.path.join("research", slug, "gathered_web.md"), None, [], "auto")
        expect("B+ 零命中登记 empty", ok2, True)
        prog2 = json.load(open(os.path.join(slug_dir, ".progress.json"), encoding="utf-8"))
        expect("B+ empty status", prog2["data"]["channels_done"]["B"]["status"], "empty")

        ok3, msg3 = ws.auto_register_channel_b("C:/elsewhere/out.md", None, [], "auto")
        expect("B- 非标准路径不登记", ok3, False)
        expect("B- 反推失败提示", "无法从输出路径反推" in msg3, True)

        ok4, msg4 = ws.auto_register_channel_b(
            os.path.join("research", "nosuch-slug", "gathered_web.md"), None, [], "auto")
        expect("B- 无 progress 不登记", ok4, False)
        expect("B- 缺 progress 提示", "未找到 research" in msg4, True)
    finally:
        cs.ROOT = old_root
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    test_domain_of()
    test_filter_results()
    test_pick_region()
    test_query_variants()
    test_parse_openalex()
    test_parse_crossref()
    test_parse_hn()
    test_parse_bing_html()
    test_bing_mirror_filter()
    test_search_tavily_nokey()
    test_tavily_payload()
    test_curl_fallback()
    test_auto_register_b()
    print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
    sys.exit(1 if FAIL else 0)
