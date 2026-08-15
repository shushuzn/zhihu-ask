"""knowledge_store.py 回归测试：SQLite 存储纯函数与端到端（17 项）。

覆盖：
- parse_keywords_md：前导段落归「未分类」、## 分节、主题词/视角词/通用模式/已验证组合 kind 识别、
  - 列表继承 kind、空行忽略
- import_keywords_md / export_keywords_md：roundtrip 保留前导与各节条目
- add_keyword / list_keywords / search_keywords：新增、按节过滤、LIKE 搜索
- replace_chunks / load_chunks：RAG 分片写入与读取

运行：python tests/test_knowledge_store.py
"""
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import knowledge_store as ks

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


def make_db():
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "knowledge.db")
    conn = ks.connect(path)
    ks.init_db(conn)
    return tmp, path, conn


# ---- parse_keywords_md ----
text = """# 预置词库说明

## 金融 / 测试

主题词：股票、基金
视角词组合示例：
- 股票 + 动量
通用模式：
- 先查数据库
"""
entries = ks.parse_keywords_md(text)
expect("parse+ 前导归未分类", entries[0], ("未分类", "条目", "# 预置词库说明"))
expect("parse+ 主题词 kind", ("金融 / 测试", "主题词", "主题词：股票、基金") in entries, True)
expect("parse+ 视角词 kind", ("金融 / 测试", "视角词组合示例", "视角词组合示例：") in entries, True)
expect("parse+ 列表继承视角词", ("金融 / 测试", "视角词组合示例", "- 股票 + 动量") in entries, True)
expect("parse+ 通用模式 kind", ("金融 / 测试", "通用模式", "通用模式：") in entries, True)
expect("parse+ 列表继承通用模式", ("金融 / 测试", "通用模式", "- 先查数据库") in entries, True)
expect("parse+ 空行忽略", len(entries), 6)

# ---- import/export roundtrip ----
tmp, path, conn = make_db()
md_path = os.path.join(tmp, "KEYWORDS.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write(text)
n = ks.import_keywords_md(conn, md_path)
expect("io+ 导入条数", n, 6)
exported = ks.export_keywords_md(conn)
expect("io+ 导出含前导", exported.startswith("# 预置词库说明"), True)
expect("io+ 导出含节", "## 金融 / 测试" in exported, True)
expect("io+ 导出含条目", "- 股票 + 动量" in exported, True)

# ---- add/list/search ----
ks.add_keyword(conn, "数学 / 概率论", "已验证有效组合", "- `Equi-dependence`（arXiv 直查）", "foo")
rows = ks.list_keywords(conn, "数学")
expect("db+ 按节过滤", len(rows), 1)
expect("db+ 来源 slug", rows[0]["source_slug"], "foo")
rows = ks.search_keywords(conn, "arXiv")
expect("db+ 搜索命中", any(r["content"] == "- `Equi-dependence`（arXiv 直查）" for r in rows), True)

# ---- RAG chunks ----
chunks = [
    {"path": "docs/a.md", "section": "A", "text": "关键词 关键词 其他"},
    {"path": "docs/b.md", "section": "B", "text": "其他内容"},
]
ks.replace_chunks(conn, chunks, "test")
loaded = ks.load_chunks(conn)
expect("rag+ 写入条数", len(loaded), 2)
expect("rag+ 读取字段", loaded[0]["path"], "docs/a.md")
expect("rag+ meta chunk_count", ks.get_meta(conn, "chunk_count"), "2")

conn.close()
shutil.rmtree(tmp, ignore_errors=True)

print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
