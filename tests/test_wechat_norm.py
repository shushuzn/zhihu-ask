"""wechat_search.py 消费端防御 + 落盘自动登记 回归测试。

通过注入假 sogou_search 模块（环境变量指向临时目录），在不需要真实
wechat-article-search 技能的情况下覆盖：
  - _strip_html / _normalize_record / _normalize_results（防御层）
  - _is_recoverable_error / search_with_retry 四态分类
  - _search 解析结构漂移检测
  - main() 落盘 gathered_wechat.md 后自动登记通道 A（done/empty）

运行：python tests/test_wechat_norm.py
"""
import os
import sys
import json
import shutil
import tempfile

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

# 注入假 sogou_search 模块（必须在 import wechat_search 之前设置环境变量）
_SKILL_TMP = testutil.mktestdir(prefix="tsogou_")
with open(os.path.join(_SKILL_TMP, "sogou_search.py"), "w", encoding="utf-8") as f:
    f.write("# fake sogou_search for tests\n"
            "def search_sogou(q, st, page, tf, tt):\n"
            "    return []\n")
os.environ["WECHAT_ARTICLE_SEARCH_SCRIPTS"] = _SKILL_TMP

import wechat_search as w  # noqa: E402

# 用可控假函数替换真实检索
_fake = []


def _fake_search(q, st, page, tf, tt):
    return _fake[:]


w.sogou.search_sogou = _fake_search

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- _normalize_skill_path：Git Bash /c/ 路径归一化 ----
expect("path+ /c/ 转驱动器", w._normalize_skill_path("/c/Users/foo/scripts"), "c:/Users/foo/scripts")
expect("path+ /C:/ 保留盘符", w._normalize_skill_path("/C:/Users/foo"), "C:/Users/foo")
expect("path+ 原生 Windows 不变", w._normalize_skill_path("C:/Users/foo/scripts"), "C:/Users/foo/scripts")
expect("path+ 小写驱动器不变", w._normalize_skill_path("d:/x/y"), "d:/x/y")
expect("path+ /d/ 转驱动器", w._normalize_skill_path("/d/other"), "d:/other")
expect("path+ 空串", w._normalize_skill_path(""), "")


# ---- _strip_html ----
expect("strip+ 标签+实体", w._strip_html("<b>标题</b>&amp;副"), "标题&副")
expect("strip+ None→空串", w._strip_html(None), "")
expect("strip+ 非字符串→转字符串", w._strip_html(123), "123")

# ---- _normalize_record ----
valid = {"title": "T", "account": "A", "time": "", "digest": "", "sogou_link": ""}
nr = w._normalize_record(valid, 0, {"dropped": 0, "drop_reasons": []})
expect("rec+ 正常字典保留", nr.get("title"), "T")
err_rec = w._normalize_record({"error": "x"}, 0, {"dropped": 0, "drop_reasons": []})
expect("rec+ 错误契约透传", "error" in err_rec, True)
expect("rec- 非字典丢弃", w._normalize_record("裸字符串", 0, {"dropped": 0, "drop_reasons": []}), None)
expect("rec- 标题公众号均空丢弃", w._normalize_record({"title": "", "account": ""}, 0, {"dropped": 0, "drop_reasons": []}), None)

# ---- _normalize_results ----
out, stats = w._normalize_results([valid, {"error": "e"}, "裸"])
expect("norm+ 保留正常+错误契约", len(out), 2)
expect("norm+ 丢弃非字典", stats["dropped"], 1)
out2, stats2 = w._normalize_results([{"title": "", "account": ""}])
expect("norm+ 漂移原始1条全丢", stats2["raw"], 1)
expect("norm+ 漂移kept=0", stats2["kept"], 0)
out3, _ = w._normalize_results("非列表")
expect("norm- 非列表返回空", out3, [])

# ---- _search 解析结构漂移 ----
_fake[:] = [{"title": "", "account": ""}]  # 原始有内容但归一化 0 条
drift = w._search("q", "article", 1, 0, 1)
expect("drift+ 合成error", isinstance(drift, list) and "error" in drift[0], True)
expect("drift+ 命中漂移关键词", "疑似搜狗页面结构变化" in drift[0]["error"], True)

# ---- _is_recoverable_error ----
expect("recov+ 验证码", w._is_recoverable_error([{"error": "触发验证码，请稍后重试"}]), True)
expect("recov- 普通错误", w._is_recoverable_error([{"error": "未知错误"}]), False)
expect("recov- 空结果", w._is_recoverable_error([]), False)
expect("recov- 正常结果", w._is_recoverable_error([{"title": "x"}]), False)

# ---- search_with_retry 四态 ----
_fake[:] = []
r, retried, st = w.search_with_retry("q", "article", 1, 0, 1, sleep=lambda *a: None)
expect("retry- 空→empty", st, "empty")
_fake[:] = [{"error": "非限流错误"}]
r, retried, st = w.search_with_retry("q", "article", 1, 0, 1, sleep=lambda *a: None)
expect("retry- 非限流错误→error", st, "error")
_fake[:] = [{"title": "x", "account": "a"}]
r, retried, st = w.search_with_retry("q", "article", 1, 0, 1, sleep=lambda *a: None)
expect("retry- 正常→ok", st, "ok")
_fake[:] = [{"error": "触发验证码，请稍后重试"}]
r, retried, st = w.search_with_retry("q", "article", 1, 0, 1, max_retries=3, sleep=lambda *a: None)
expect("retry- 限流耗尽→blocked", st, "blocked")
expect("retry+ 重试次数=2", retried, 2)

# ---- e2e：main() 落盘自动登记通道 A ----
def run_main(slug, kw, output, fake):
    _fake[:] = fake
    kwfile = os.path.join(_SKILL_TMP, "kw.json")
    with open(kwfile, "w", encoding="utf-8") as f:
        json.dump({"queries": kw, "count": 5}, f)
    old_argv = sys.argv
    sys.argv = ["wechat_search.py", "--keywords", kwfile, "--output", output,
                "--slug", slug, "--no-retry"]
    try:
        w.main()
    finally:
        sys.argv = old_argv


def setup_slug(slug):
    slug_dir = os.path.join(ROOT, "research", slug)
    os.makedirs(slug_dir, exist_ok=True)
    with open(os.path.join(slug_dir, ".progress.json"), "w", encoding="utf-8") as f:
        json.dump({"stage": "phase1_done", "data": {}}, f, ensure_ascii=False, indent=2)
    return slug_dir


def read_channels(slug):
    p = os.path.join(ROOT, "research", slug, ".progress.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("data", {}).get("channels_done", {})


slug1 = "wechat_e2e_done"
d1 = setup_slug(slug1)
run_main(slug1, ["测试主题 突破"], os.path.join(d1, "gathered_wechat.md"),
         [{"title": "标题A", "account": "公众号A", "time": "2026", "digest": "摘要", "sogou_link": "u"}])
cd1 = read_channels(slug1)
expect("e2e+ 命中→A done", cd1.get("A", {}).get("status"), "done")

slug2 = "wechat_e2e_empty"
d2 = setup_slug(slug2)
run_main(slug2, ["冷门主题"], os.path.join(d2, "gathered_wechat.md"), [])
cd2 = read_channels(slug2)
expect("e2e+ 零命中→A empty", cd2.get("A", {}).get("status"), "empty")

# 清理 e2e 产生的 research 临时目录
for sdir in (d1, d2):
    shutil.rmtree(sdir, ignore_errors=True)

print(f"\n==== wechat_search 回归测试：PASS={PASS} FAIL={FAIL} ====")
sys.exit(1 if FAIL else 0)
