#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_citation_validity.py 单元测试：违规引用检查（作者真实性/题名一致性/URL 伪造）"""

import os
import sys
import unittest.mock as mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_citation_validity as ccv

PASS = 0
FAIL = 0
TOTAL = 0


def expect(name, cond, detail=""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


GOOD = """# 测试报告

正文引用两处[1][2]。

**参考文献（GB/T 7714-2015）**
[1] Miao Y, Zhang S, Ding L, et al. InfoRM: Mitigating Reward Hacking in RLHF via Information-Theoretic Reward Modeling[C/OL]//Advances in Neural Information Processing Systems 37. 2024[2026-08-14]. https://doi.org/10.52202/079017-4270.

[2] 佚名. 普通网络资料[EB/OL]. (2026-01-01)[2026-08-14]. https://www.example.org/page.
"""

FAKE_AUTHOR = """# 测试报告

正文引用[1]。

**参考文献**
[1] Li Y, et al. InfoRM: Mitigating Reward Hacking in RLHF via Information-Theoretic Reward Modeling[C/OL]//Advances in Neural Information Processing Systems 37. 2024[2026-08-14]. https://doi.org/10.52202/079017-4270.
"""

FAKE_TITLE = """# 测试报告

正文引用[1]。

**参考文献**
[1] Miao Y, Zhang S, Ding L, et al. 完全无关的标题[C/OL]//Advances in Neural Information Processing Systems 37. 2024[2026-08-14]. https://doi.org/10.52202/079017-4270.
"""

FAKE_ANCHOR = """# 测试报告

正文引用[1]。

**参考文献**
[1] 佚名. 论文甲[EB/OL]. (2026-01-01)[2026-08-14]. https://arxiv.org/abs/2603.06957#related.
"""

PLACEHOLDER = """# 测试报告

正文引用[1]。

**参考文献**
[1] 佚名. 论文甲[EB/OL]. (2026-01-01)[2026-08-14]. https://example.com/xxx.
"""

ARXIV_BAD_ID = """# 测试报告

正文引用[1]。

**参考文献**
[1] 佚名. 论文甲[EB/OL]. (2026-01-01)[2026-08-14]. https://arxiv.org/abs/not-an-id.
"""

CITE_CONTEXT_MISMATCH = """# 测试报告

正文引用处完全讨论的是香蕉种植与热带农业[1]，与题名毫无关联。

**参考文献**
[1] 李益文. 电力股大涨，六大投资主线曝光（附股）[EB/OL]. 21世纪经济报道. (2026-08-13)[2026-08-14]. https://view.inews.qq.com/a/20260813A0BQJH00.
"""


# ---- 解析函数 ----
url = ccv.extract_url("[1] 甲. 题名[EB/OL]. (2026-01-01)[2026-08-14]. https://doi.org/10.52202/079017-4270.")
expect("extract_url 提取 DOI URL", url == "https://doi.org/10.52202/079017-4270", url)

# 括号 DOI（Elsevier 格式）不被截断
url_paren = ccv.extract_url("[1] 甲. 题名[J/OL]. 1993[2026-08-14]. https://doi.org/10.1016/0167-2789(93)90178-4.")
expect("extract_url 括号 DOI 完整", url_paren == "https://doi.org/10.1016/0167-2789(93)90178-4", url_paren)

# 引用日期紧邻 URL 不被吞
url_date = ccv.extract_url("[1] 甲. 题名[EB/OL]. (2026-01-01)[2026-08-14]. https://doi.org/10.52202/079017-4270[2026-08-14].")
expect("extract_url 不吞引用日期", url_date == "https://doi.org/10.52202/079017-4270", url_date)

# DOI_RE 允许括号
m = ccv.DOI_RE.search("https://doi.org/10.1016/0167-2789(93)90178-4")
expect("DOI_RE 括号 DOI 完整", m.group(0) if m else None, "10.1016/0167-2789(93)90178-4")

auth = ccv.extract_authors("[1] Miao Y, Zhang S, Ding L, et al. InfoRM: Mitigating...")
expect("extract_authors 提取作者", auth and "Miao" in auth, auth)

title = ccv.extract_title("[1] Miao Y, Zhang S. InfoRM: Mitigating Reward Hacking[C/OL]. 2024.")
expect("extract_title 提取题名", title and "InfoRM" in title, title)

expect("authors_match 真作者通过",
       ccv.authors_match("Miao Y, Zhang S, Ding L, et al",
                         [{"given": "Yuchun", "family": "Miao"}, {"given": "Sen", "family": "Zhang"},
                          {"given": "Liang", "family": "Ding"}]) is True)
expect("authors_match 编造作者拦截",
       ccv.authors_match("Li Y, et al",
                         [{"given": "Yuchun", "family": "Miao"}, {"given": "Sen", "family": "Zhang"}]) is False)
expect("authors_match 空作者返回 None",
       ccv.authors_match("", [{"given": "A", "family": "B"}]) is None)

# ---- 连字符变体归一化（破折号风格差异不判题名不符）----
expect("normalize 破折号统一",
       ccv.normalize("Euler–Poisson Dark-Fluid Model") == ccv.normalize("Euler-Poisson Dark-Fluid Model"),
       f"{ccv.normalize('Euler–Poisson')} vs {ccv.normalize('Euler-Poisson')}")

# ---- LaTeX 命令归一化（arXiv 注册题名含 LaTeX 源码不误判不符）----
expect("normalize 剥 LaTeX mathbb",
       ccv.normalize("on $\\mathbb{S}^N$") == ccv.normalize("on S^N"),
       f"{ccv.normalize('on $\\mathbb{S}^N$')} vs {ccv.normalize('on S^N')}")
expect("normalize 剥通用 LaTeX 命令",
       ccv.normalize("\\frac{1}{2}\\int u") == ccv.normalize("12int u"),
       f"{ccv.normalize('\\frac{1}{2}\\int u')} vs {ccv.normalize('12int u')}")


# ---- 离线检查（不联网）----
hard, warn = ccv.check(GOOD, offline=True)
expect("offline+ 合规报告零硬伤", not hard, f"hard={hard}")

hard, warn = ccv.check(FAKE_ANCHOR, offline=True)
expect("offline- 伪锚点拦截",
       any(h[2] == "URL 伪锚点" for h in hard), f"hard={hard}")

hard, warn = ccv.check(PLACEHOLDER, offline=True)
expect("offline- 占位符 URL 拦截",
       any(h[2] == "URL 占位符" for h in hard), f"hard={hard}")

hard, warn = ccv.check(ARXIV_BAD_ID, offline=True)
expect("offline- arxiv 非法 id 拦截",
       any(h[2] == "arxiv URL 非法" for h in hard), f"hard={hard}")

# ---- 联网核验（mock CrossRef 响应）----
REG = {
    "message": {
        "author": [{"given": "Yuchun", "family": "Miao"}, {"given": "Sen", "family": "Zhang"},
                   {"given": "Liang", "family": "Ding"}, {"given": "Rong", "family": "Bao"}],
        "title": ["InfoRM: Mitigating Reward Hacking in RLHF via Information-Theoretic Reward Modeling"],
        "issued": {"date-parts": [[2024, 12, 1]]},
    }
}

FAKE_AUTHOR_ANON = """# 测试报告

正文引用[1]。

**参考文献**
[1] 佚名. InfoRM: Mitigating Reward Hacking in RLHF via Information-Theoretic Reward Modeling[C/OL]//Advances in Neural Information Processing Systems 37. 2024[2026-08-14]. https://doi.org/10.52202/079017-4270.
"""

BAD_CITE_DATE = """# 测试报告

正文引用[1]。

**参考文献**
[1] Miao Y, Zhang S, Ding L, et al. InfoRM: Mitigating Reward Hacking in RLHF via Information-Theoretic Reward Modeling[C/OL]//Advances in Neural Information Processing Systems 37. 2024[2020-01-01]. https://doi.org/10.52202/079017-4270.
"""


def fake_crossref(url, timeout=10):
    if "10.52202/079017-4270" in url or "10.52202%2F079017-4270" in url:
        return REG
    raise OSError("no")


with mock.patch.object(ccv, "http_get_json", side_effect=fake_crossref):
    hard, warn = ccv.check(GOOD, offline=False)
    expect("online+ 真实作者通过", not any(h[2] == "疑似编造作者" for h in hard), f"hard={hard}")
    expect("online+ 真实题名通过", not any(h[2] == "题名与文献不符" for h in hard), f"hard={hard}")

    hard, warn = ccv.check(FAKE_AUTHOR, offline=False)
    expect("online- 编造作者拦截",
           any(h[2] == "疑似编造作者" for h in hard), f"hard={hard}")

    hard, warn = ccv.check(FAKE_TITLE, offline=False)
    expect("online- 题名不符拦截",
           any(h[2] == "题名与文献不符" for h in hard), f"hard={hard}")

    # 佚名误用（学术纪律）：注册库有作者却著录佚名 → 硬伤
    hard, warn = ccv.check(FAKE_AUTHOR_ANON, offline=False)
    expect("online- 佚名误用拦截",
           any(h[2] == "作者误用（佚名）" for h in hard), f"hard={hard}")

    # 引用日期早于发布日期（学术纪律）→ 硬伤
    hard, warn = ccv.check(BAD_CITE_DATE, offline=False)
    expect("online- 引用日期早于发布拦截",
           any(h[2] == "引用日期早于发布日期" for h in hard), f"hard={hard}")

# ---- 网络失败（学术纪律：硬伤阻断，不静默放行）----
with mock.patch.object(ccv, "http_get_json", side_effect=OSError("down")):
    hard, warn = ccv.check(FAKE_AUTHOR, offline=False)
    expect("网络失败产生硬伤（新纪律）",
           any(h[2] == "联网核验失败" for h in hard), f"hard={hard}")

    # 显式 --offline 声明放弃核验 → 不阻断
    hard, warn = ccv.check(FAKE_AUTHOR, offline=True)
    expect("offline 显式声明不阻断",
           not any(h[2] in ("联网核验失败", "疑似编造作者") for h in hard), f"hard={hard}")

# ---- 普通 URL 死链（学术纪律：硬伤）----
DEAD_LINK = """# 测试报告

正文引用[1]。

**参考文献**
[1] 佚名. 测试文章[EB/OL]. (2026-01-01)[2026-08-14]. https://example.org/definitely-not-exist-404.
"""
with mock.patch.object(ccv, "check_url_reachable", return_value=(False, "HTTP 404")):
    hard, warn = ccv.check(DEAD_LINK, offline=False)
    expect("online- 死链拦截",
           any(h[2] == "URL 不可访问" for h in hard), f"hard={hard}")

with mock.patch.object(ccv, "check_url_reachable", return_value=(True, "HTTP 200")):
    hard, warn = ccv.check(DEAD_LINK, offline=False)
    expect("online+ 可达 URL 通过",
           not any(h[2] == "URL 不可访问" for h in hard), f"hard={hard}")

# ---- 正文引注上下文匹配（提示级）----
hard, warn = ccv.check(CITE_CONTEXT_MISMATCH, offline=True)
expect("提示- 正文与题名疑似不符",
       any(w[2] == "正文与题名疑似不符" for w in warn), f"warn={warn}")

# ---- 作者格式提示 ----
hard, warn = ccv.check("正文[1]。\n\n**参考文献**\n[1] miao yuchun. 题名[M]. 京: 社, 2024. https://x.org/a.", offline=True)
expect("提示- 英文作者格式异常",
       any(w[2] == "作者格式疑似异常" for w in warn), f"warn={warn}")

# ---- arxiv.org/html/ 链接核验（此前 /html/ 被当普通 URL 只查可达性，
#      导致佚名/题名不符整体漏检）----
expect("is_arxiv_url 识别 html 链接",
       ccv.is_arxiv_url("https://arxiv.org/html/2406.18343v1"), "html 形式未识别")
expect("is_arxiv_url 识别 abs 链接",
       ccv.is_arxiv_url("https://arxiv.org/abs/2406.18343"), "abs 形式未识别")
expect("is_arxiv_url 识别 pdf 链接",
       ccv.is_arxiv_url("https://arxiv.org/pdf/2406.18343"), "pdf 形式未识别")
expect("is_arxiv_url 不误报普通 URL",
       not ccv.is_arxiv_url("https://example.com/arxiv.org/html/x"), "普通 URL 误判")

ARXIV_HTML_ANON = """# 测试报告

正文引用[1]。

**参考文献**
[1] 佚名. Optimal volume bound and volume growth for Ricci limit spaces[EB/OL]. (2024)[2026-08-15]. https://arxiv.org/html/2406.18343v1.
"""

ARXIV_HTML_XML = (
    "<feed><entry><id>http://arxiv.org/abs/2406.18343v1</id>"
    "<title>Optimal volume bound and volume growth for Ricci-nonnegative manifolds "
    "with positive Bi-Ricci curvature</title>"
    "<published>2024-06-26T00:00:00Z</published>"
    "<name>Jie Zhou</name><name>Jintian Zhu</name></entry></feed>"
)


def fake_arxiv_fetch(url, timeout=10):
    return ARXIV_HTML_XML


with mock.patch.object(ccv, "fetch_text", side_effect=fake_arxiv_fetch):
    hard, warn = ccv.check(ARXIV_HTML_ANON, offline=False)
    expect("html链接- 佚名误用拦截",
           any(h[2] == "作者误用（佚名）" for h in hard), f"hard={hard}")
    expect("html链接- 题名不符拦截",
           any(h[2] == "题名与文献不符" for h in hard), f"hard={hard}")


print(f"\nTOTAL: PASS={PASS} FAIL={FAIL}")
if FAIL > 0:
    sys.exit(1)
