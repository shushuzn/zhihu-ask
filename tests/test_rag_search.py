"""rag_search.py 回归测试：BM25 检索纯函数（23 项）。

覆盖：
- tokenize：中文 bigram / 单字 / 英文≥2 词小写 / 数字 / 停用词过滤 / 标点断词 /
  下划线连词 / 混合
- bm25：tf 排序（词频高者优先）、df/idf 稀有词加分、file_filter 限定、
  空分片 / 无命中 / 空查询词
- highlight：命中标记 / 上下文窗口 / 省略号前缀 / 无命中截断

行为锁定：检索算法回退会让研究启动时的经验召回失真（漏检/错位），
且 rag_build 与 rag_search 共用同一 tokenize 语义，需回归守护。

运行：python tests/test_rag_search.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import rag_search as rs

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- tokenize：中文 bigram ----
expect("tok+ 双字词", rs.tokenize("检索"), ["检索"])
expect("tok+ 三字词 bigram", rs.tokenize("关键词"), ["关键", "键词"])
expect("tok+ 多词分隔", rs.tokenize("关键词 检索"), ["关键", "键词", "检索"])
expect("tok+ 中文标点断词", rs.tokenize("笔记本，8000 元。"), ["8000", "笔记", "记本", "元"])
expect("tok+ 单字保留", rs.tokenize("啊"), ["啊"])

# ---- tokenize：英文/数字 ----
expect("tok+ 英文小写", rs.tokenize("BM25 Retrieval"), ["bm25", "retrieval"])
expect("tok- 单字母英文丢弃", rs.tokenize("a b"), [])
expect("tok+ 数字", rs.tokenize("2026"), ["2026"])
expect("tok+ 下划线连词", rs.tokenize("foo_bar"), ["foo_bar"])
expect("tok+ 5G 混合", rs.tokenize("5G"), ["5g"])
expect("tok+ 中英混合", rs.tokenize("国补 2026 policy"), ["2026", "policy", "国补"])

# ---- tokenize：停用词 ----
expect("tok- 停用词过滤", rs.tokenize("的 了 是"), [])
expect("tok- 停用词在句中剔除", rs.tokenize("我们的研究"), ["们的", "的研", "研究"])
expect("tok+ 非停用词保留", rs.tokenize("关键词"), ["关键", "键词"])

# ---- bm25：tf 排序 ----
chunks = [
    {"path": "docs/a.md", "section": "A", "text": "关键词 关键词 其他内容"},
    {"path": "docs/b.md", "section": "B", "text": "关键词 一次 其他内容"},
    {"path": "docs/c.md", "section": "C", "text": "完全无关的内容"},
]
q = ["关键", "键词"]
res = rs.bm25(chunks, q)
expect("bm25+ 词频高者排前", [c["path"] for _, c in res][:2], ["docs/a.md", "docs/b.md"])
expect("bm25+ 无命中不入列", any(c["path"] == "docs/c.md" for _, c in res), False)
expect("bm25+ 分数降序", all(res[i][0] >= res[i + 1][0] for i in range(len(res) - 1)), True)

# ---- bm25：file_filter ----
res = rs.bm25(chunks, q, file_filter="docs/")
expect("bm25+ filter 命中 docs", {c["path"] for _, c in res}, {"docs/a.md", "docs/b.md"})
res = rs.bm25(chunks, q, file_filter="templates/")
expect("bm25+ filter 无命中为空", res, [])

# ---- bm25：df/idf 稀有词加分 ----
chunks2 = [
    {"path": "docs/a.md", "section": "A", "text": "罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词 罕见词"},
    {"path": "docs/b.md", "section": "B", "text": "常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词"},
    {"path": "docs/c.md", "section": "C", "text": "常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词 常见词"},
]
r_rare = rs.bm25(chunks2, ["罕见", "见词"])[0][0]
r_common = rs.bm25(chunks2, ["常见", "见词"])[0][0]
expect("bm25+ 稀有词 idf 更高", r_rare > r_common, True)

# ---- bm25：边界 ----
expect("bm25+ 空分片", rs.bm25([], ["x"]), [])
expect("bm25+ 查询词无命中", rs.bm25(chunks, ["不存", "存在"]), [])
expect("bm25+ 空查询词", rs.bm25(chunks, []), [])

# ---- highlight ----
text = "前面内容" + "中" * 60 + "目标词" + "后面" * 40
seg = rs.highlight(text, ["目标"])
expect("hl+ 命中标记", "[目标]" in seg, True)
expect("hl+ 返回片段限宽", len(seg) <= 125, True)

expect("hl- 无命中取前 120", rs.highlight("abc" * 100, ["zzz"]), "abc" * 40)

long_text = "前" * 1000 + "目标词" + "后" * 200
seg = rs.highlight(long_text, ["目标"])
expect("hl+ 长文取命中上下文", "目标" in seg and seg.startswith("…"), True)
expect("hl+ 上下文宽度", len(seg) <= 125, True)

seg = rs.highlight("AA 与 BB", ["AA", "BB"])
expect("hl+ 多词全标记", seg.count("["), 2)


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
