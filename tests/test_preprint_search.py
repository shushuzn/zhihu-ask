#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preprint_search.py 单元测试：三平台检索（bioRxiv/浪淘沙/PSSXiv）"""

import os
import sys
import unittest.mock as mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import preprint_search as ps

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


# ---- 解析：arxiv（复用 arxiv_search） ----
ARXIV_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Towards de novo RNA 3D structure prediction</title>
    <published>2015-02-19T00:00:00Z</published>
    <summary>RNA is a fundamental class of biomolecules.</summary>
    <author><name>Sandro Bottaro</name></author>
    <author><name>Giovanni Bussi</name></author>
    <link rel="alternate" href="https://arxiv.org/abs/1502.05667v1"/>
  </entry>
</feed>"""


def test_arxiv():
    import arxiv_search as ax
    with mock.patch.object(ax, "fetch_atom", return_value=(ARXIV_XML, "ok")):
        out = ps.search_arxiv("RNA", 5)
        expect("arxiv+ 命中1条", len(out) == 1, out)
        expect("arxiv+ 标题", out[0]["title"] == "Towards de novo RNA 3D structure prediction", out)
        expect("arxiv+ 作者", "Bottaro" in out[0]["authors"], out[0]["authors"])
        expect("arxiv+ 链接", "1502.05667" in out[0]["link"], out[0]["link"])
        expect("arxiv+ 摘要", "biomolecules" in out[0]["abstract"], out[0]["abstract"])

    # 网络失败（fetch_atom egress + curl 兜底失败）→ None
    with mock.patch.object(ax, "fetch_atom", return_value=(None, "egress")), \
         mock.patch.object(ax, "fetch_atom_curl", return_value=(None, "egress")):
        out = ps.search_arxiv("RNA", 5)
        expect("arxiv- 网络失败None", out is None, out)


# ---- 解析：bioRxiv JSON ----
BIORXIV_JSON = json_str = '{"collection": [' \
    '{"preprint_doi": "10.1101/2025.08.19.670996", "preprint_title": "RNA aptamer for synucleinopathies", ' \
    '"preprint_authors": "Murakami, K.; Bitan, G.", "preprint_date": "2025-08-24T00:00:00Z"}, ' \
    '{"preprint_doi": "10.1101/2025.10.13.681987", "preprint_title": "Nanopore Direct RNA sequencing", ' \
    '"preprint_authors": "Cribbs, A. P.", "preprint_date": "2025-10-14T00:00:00Z"}]}'


def test_biorxiv():
    with mock.patch.object(ps, "http_get", return_value=BIORXIV_JSON):
        out = ps.search_biorxiv("RNA", 30, 10)
        expect("bioRxiv+ 命中2条", len(out) == 2, out)
        expect("bioRxiv+ 标题正确", out[0]["title"] == "RNA aptamer for synucleinopathies", out)
        expect("bioRxiv+ DOI链接", "10.1101/2025.08.19.670996" in out[0]["link"], out[0]["link"])
        expect("bioRxiv+ 作者字段", "Bitan" in out[0]["authors"], out[0]["authors"])

    # 关键词过滤
    with mock.patch.object(ps, "http_get", return_value=BIORXIV_JSON):
        out = ps.search_biorxiv("nanopore", 30, 10)
        expect("bioRxiv- 关键词过滤", len(out) == 1 and "Nanopore" in out[0]["title"], out)

    # 网络失败 → None
    with mock.patch.object(ps, "http_get", return_value=None):
        out = ps.search_biorxiv("RNA", 30, 10)
        expect("bioRxiv- 网络失败返回None", out is None, out)


# ---- 解析：浪淘沙 Atom feed ----
LTS_FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>MAGPiE enables RNA manipulation</title>
    <name>Long-Qi Li</name>
    <name>Yuan-Yuan Jiang</name>
    <link href="https://langtaosha.org.cn/lts/en/preprint/view/311"/>
    <published>2026-08-14T00:00:00+08:00</published>
    <summary type="html">&lt;p&gt;RNA editing offers a promising alternative.&lt;/p&gt;</summary>
  </entry>
  <entry>
    <title>Quantum walks in physics</title>
    <name>Shi Y</name>
    <link href="https://langtaosha.org.cn/lts/en/preprint/view/99"/>
    <published>2026-07-01T00:00:00+08:00</published>
    <summary type="html">&lt;p&gt;A different topic.&lt;/p&gt;</summary>
  </entry>
</feed>"""


def test_langtaosha():
    with mock.patch.object(ps, "http_get", return_value=LTS_FEED):
        out = ps.search_langtaosha("RNA", 10)
        expect("浪淘沙+ 命中1条（关键词过滤）", len(out) == 1, out)
        expect("浪淘沙+ 摘要HTML清理", "RNA editing" in out[0]["abstract"] and "<" not in out[0]["abstract"], out[0]["abstract"])
        expect("浪淘沙+ 作者逗号连接", out[0]["authors"] == "Long-Qi Li, Yuan-Yuan Jiang", out[0]["authors"])
        expect("浪淘沙+ 日期", out[0]["date"] == "2026-08-14", out[0]["date"])

    with mock.patch.object(ps, "http_get", return_value=None):
        out = ps.search_langtaosha("RNA", 10)
        expect("浪淘沙- 网络失败None", out is None, out)


# ---- 解析：PSSXiv HTML ----
PSSXIV_HTML = """<html><body>
<div class="item">
  <a>1. PSSXiv:202608.01840</a>
  <a href="download">下载全文</a>
  <a>央地司法关系对企业数字化转型的影响研究</a>
  <span>摘要：利用2010—2022年中国A股上市企业数据，实证检验司法改革影响。展开</span>
</div>
<div class="item">
  <a>2. PSSXiv:202608.01839</a>
  <a href="download">下载全文</a>
  <a>AI驱动下非遗数字IP打造研究</a>
  <span>摘要：AI技术突破传统非遗数字化局限。展开</span>
</div>
</body></html>"""


def test_pssxiv():
    with mock.patch.object(ps, "http_post", return_value=PSSXIV_HTML):
        out = ps.search_pssxiv("人工智能", 10)
        expect("PSSXiv+ 命中2条", len(out) == 2, out)
        expect("PSSXiv+ 标题正确", "央地司法关系" in out[0]["title"], out[0]["title"])
        expect("PSSXiv+ 编号", out[0]["pssxiv_id"] == "202608.01840", out)
        expect("PSSXiv+ 摘要提取", "A股上市企业" in out[0]["abstract"], out[0]["abstract"])
        expect("PSSXiv+ 摘要截断去展开", "展开" not in out[0]["abstract"], out[0]["abstract"])

    with mock.patch.object(ps, "http_post", return_value=None):
        out = ps.search_pssxiv("人工智能", 10)
        expect("PSSXiv- 网络失败None", out is None, out)


# ---- 落盘格式与分流 ----
def test_format():
    entries = [{"title": "T1", "authors": "A1", "date": "2026-01-01", "link": "https://x.org/a",
                "abstract": "摘要内容", "pssxiv_id": "202608.00001"}]
    md = ps.format_gathered("测试平台", entries, "关键词")
    expect("落盘+ 含标题", "## 1. T1" in md, md)
    expect("落盘+ 含编号", "PSSXiv:202608.00001" in md, md)
    expect("落盘+ 含摘要", "摘要内容" in md, md)
    empty_md = ps.format_gathered("测试平台", [], "关键词")
    expect("落盘+ 空素材标注", "无有效素材" in empty_md, empty_md)
    expect("分流+ arxiv→gathered_arxiv.md", ps.PLATFORM_OUT["arxiv"] == "gathered_arxiv.md", ps.PLATFORM_OUT)
    expect("分流+ 其余→gathered_preprints.md", ps.PLATFORM_OUT["pssxiv"] == "gathered_preprints.md", ps.PLATFORM_OUT)


def test_main_dispatch():
    """main 分流映射（mock 检索）：arxiv → gathered_arxiv.md，其余 → gathered_preprints.md（均属通道 P）。"""
    expect("分流+ arxiv 归入 P", ps.PLATFORM_OUT["arxiv"] == "gathered_arxiv.md", ps.PLATFORM_OUT)
    expect("分流+ 三平台归入 P", all(ps.PLATFORM_OUT[p] == "gathered_preprints.md"
                                   for p in ("biorxiv", "langtaosha", "pssxiv")), ps.PLATFORM_OUT)


test_biorxiv()
test_langtaosha()
test_pssxiv()
test_arxiv()
test_format()
test_main_dispatch()

print(f"\nPASS={PASS} FAIL={FAIL}")
if FAIL > 0:
    sys.exit(1)
