"""arxiv_search.py 回归测试：查询语义提示（9 项）。

覆盖 query_semantics_hint 的判定：
- 含空格 + 无引号 + 无 AND → 提示（ArXiv API 空格=OR 语义陷阱）
- 引号短语 / 显式 AND（含大小写变体）→ 不提示
- 单词 / 空查询 → 不提示

实测背景：'Riemann zeta zeros critical line proportion'
裸查询返回自动驾驶/量子引力等无关结果；换 '"proportion of zeros" AND
"critical line"' 后命中相关论文——提示正是为防止此类误用。

运行：python tests/test_arxiv_query.py
"""
import os
import unittest.mock as mock
import urllib.parse
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import arxiv_search as ax

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- 触发提示：空格 + 无引号 + 无 AND ----
expect("hint+ 多词裸查询", ax.query_semantics_hint("Riemann zeta zeros") is not None, True)
expect("hint+ 提示含 OR 语义说明", "OR 语义" in (ax.query_semantics_hint("Riemann zeta zeros") or ""), True)
expect("hint+ 提示含引号建议", "引号" in (ax.query_semantics_hint("zeta zeros") or ""), True)

# ---- 不提示：引号短语 / 显式 AND ----
expect("hint- 引号短语", ax.query_semantics_hint('"exact phrase"'), None)
expect("hint- 引号+AND 组合", ax.query_semantics_hint('"proportion of zeros" AND "critical line"'), None)
expect("hint- 显式 AND 大写", ax.query_semantics_hint("zeta AND zeros"), None)
expect("hint- 显式 and 小写", ax.query_semantics_hint("zeta and zeros"), None)

# ---- 不提示：单词 / 空 ----
expect("hint- 单词", ax.query_semantics_hint("singleword"), None)
expect("hint- 空串", ax.query_semantics_hint(""), None)
expect("hint- None", ax.query_semantics_hint(None), None)


# ---- build_url / _arxiv_query：相关性排序 + 多词自动 AND ----
expect("q+ 多词转AND", ax._arxiv_query("medieval siege trebuchet"),
       "all:medieval+AND+all:siege+AND+all:trebuchet")
expect("q+ 单词保留", ax._arxiv_query("trebuchet"), "trebuchet")
expect("q+ 引号短语保留", ax._arxiv_query('"exact phrase"'),
       urllib.parse.quote_plus('"exact phrase"'))
expect("q+ 空串", ax._arxiv_query(""), "")
url = ax.build_url("medieval siege", 5)
expect("url+ 相关性排序", "sortBy=relevance" in url, True)
expect("url+ 不再按时间排序", "submittedDate" not in url, True)
expect("url+ 含AND语义", "AND" in url, True)
expect("hint+ 自动AND说明", "已自动将多词查询转 AND" in (ax.query_semantics_hint("zeta zeros") or ""), True)

# ---- curl 兜底：urllib 失败时自动尝试系统 curl ----
def test_curl_fallback():
    xml = "<feed><entry><title>T</title><id>x</id></entry></feed>"

    # curl 可用且成功 → (text, ok)
    with mock.patch("shutil.which", return_value="/usr/bin/curl"):
        r = mock.Mock()
        r.stdout = xml.encode()
        with mock.patch("subprocess.run", return_value=r):
            text, status = ax.fetch_atom_curl("https://export.arxiv.org/api/query?id_list=1")
            expect("curl+ 成功返回ok", status, "ok")
            expect("curl+ 返回内容", text, xml)

    # curl 命令缺失 → egress
    with mock.patch("shutil.which", return_value=None):
        text, status = ax.fetch_atom_curl("https://export.arxiv.org/api/query?id_list=1")
        expect("curl- 无curl命令egress", status, "egress")

    # 空响应 → empty
    with mock.patch("shutil.which", return_value="/usr/bin/curl"):
        r = mock.Mock()
        r.stdout = b"short"
        with mock.patch("subprocess.run", return_value=r):
            text, status = ax.fetch_atom_curl("https://export.arxiv.org/api/query?id_list=1")
            expect("curl- 空响应empty", status, "empty")

    # 异常 → egress
    with mock.patch("shutil.which", return_value="/usr/bin/curl"):
        with mock.patch("subprocess.run", side_effect=OSError("boom")):
            text, status = ax.fetch_atom_curl("https://export.arxiv.org/api/query?id_list=1")
            expect("curl- 异常egress", status, "egress")


test_curl_fallback()

print(f"TOTAL: PASS={PASS} FAIL={FAIL}")

if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
