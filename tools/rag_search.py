
"""
RAG 知识库检索工具（zhihu-ask 项目专用）

对 rag_build.py 构建的 SQLite 索引做 BM25 检索（中文按字符 bigram + 英文单词切分，
零第三方依赖）。用于研究启动前检索项目内已有经验：流程规则、关键词词库、
模板结构、写作规范等。

用法：
    python tools/rag_search.py "笔记本 8000 学生"          # 默认返回前 5 条
    python tools/rag_search.py "国补 政策" -k 10           # 指定条数
    python tools/rag_search.py "关键词 回填" --file docs    # 限定文件前缀
    python tools/rag_build.py                               # 先构建索引（改动 docs 后重跑）

输出：按相关性排序的分片（文件/章节/命中句），供主代理在阶段 0/1 参考。
"""

import sys
import os
import re
import math
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import knowledge_store as ks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = ks.DB_PATH

K1 = 1.5
B = 0.75
TOP_DEFAULT = 5

STOPWORDS = {
    "的", "了", "是", "在", "与", "和", "或", "及", "对", "为", "从", "到",
    "用", "本", "个", "中", "上", "下", "也", "都", "并", "不", "有", "等",
    "一个", "可以", "进行", "以及", "相关", "我们", "你", "我", "他", "它",
}

PUNCT_RE = re.compile(r"[\s\W_]+", re.UNICODE)

def tokenize(text):
    """中文切字符 bigram + 英文/数字按词切。"""
    toks = []

    for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.\-/]*", text):
        wl = w.lower()
        if len(wl) >= 2:
            toks.append(wl)

    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(seg) == 1:
            toks.append(seg)
        for i in range(len(seg) - 1):
            toks.append(seg[i:i + 2])
    return [t for t in toks if t not in STOPWORDS]

def load_index():
    if not os.path.exists(DB_FILE):
        print(f"错误: 数据库不存在 {DB_FILE}")
        print("请先运行: python tools/rag_build.py")
        sys.exit(1)
    conn = ks.connect()
    try:
        ks.init_db(conn)
        return ks.load_chunks(conn)
    finally:
        conn.close()

def bm25(chunks, query_tokens, file_filter=None):
    """标准 BM25 打分，返回 [(score, chunk)] 降序。"""
    if file_filter:
        chunks = [c for c in chunks if c["path"].startswith(file_filter)]
    if not chunks:
        return []
    N = len(chunks)
    avdl = sum(len(c["text"]) for c in chunks) / max(N, 1)

    df = Counter()
    for c in chunks:
        toks = set(tokenize(c["text"]))
        for t in set(query_tokens) & toks:
            df[t] += 1

    scored = []
    for c in chunks:
        toks = Counter(tokenize(c["text"]))
        dl = len(c["text"])
        score = 0.0
        for t in set(query_tokens):
            tf = toks.get(t, 0)
            if tf == 0:
                continue
            idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * dl / max(avdl, 1)))
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored

def highlight(text, tokens, width=120):
    """截取命中片段，标记关键词。"""
    pos = -1
    for t in set(tokens):
        i = text.find(t)
        if i >= 0 and (pos < 0 or i < pos):
            pos = i
    if pos < 0:
        return text[:width]
    start = max(0, pos - width // 3)
    seg = text[start:start + width]
    for t in set(tokens):
        seg = seg.replace(t, f"[{t}]")
    return ("…" if start > 0 else "") + seg

def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python tools/rag_search.py \"查询词\" [-k N] [--file 前缀]")
        sys.exit(1)
    query = None
    top = TOP_DEFAULT
    file_filter = None
    i = 0
    while i < len(args):
        if args[i] == "-k" and i + 1 < len(args):
            top = int(args[i + 1])
            i += 2
        elif args[i] == "--file" and i + 1 < len(args):
            file_filter = args[i + 1]
            i += 2
        else:
            query = args[i]
            i += 1
    if not query:
        print("用法: python tools/rag_search.py \"查询词\" [-k N] [--file 前缀]")
        sys.exit(1)

    chunks = load_index()
    q_tokens = tokenize(query)
    if not q_tokens:
        print("提示: 查询词过短或全为停用词，请用更具体的词。")
        sys.exit(1)

    results = bm25(chunks, q_tokens, file_filter)
    if not results:
        print("无匹配结果。建议：换更宽泛的关键词，或先跑 python tools/rag_build.py 重建索引。")
        sys.exit(0)

    print(f"查询: {query}")
    print(f"命中: {len(results)} 个分片（显示前 {min(top, len(results))} 条）")
    print("=" * 60)
    for score, c in results[:top]:
        print(f"[{score:.2f}] {c['path']}  ›  {c['section'][:40]}")
        print(f"    {highlight(c['text'], q_tokens)}")
        print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
