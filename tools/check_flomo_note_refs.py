# -*- coding: utf-8 -*-
"""flomo 笔记参考文献检测工具（zhihu-ask 项目专用）

规则：
  flomo 检索命中的笔记若用作参考素材，必须有参考文献且符合 GB/T 7714-2015：
  1. 笔记含合规参考文献（[n] 条目 + 文献类型标识 + URL 带引用日期）→ 可用
  2. 有参考文献但不符合国标（缺类型标识/URL 缺日期/编号不连续/无 [n] 条目）→ 不可用
  3. 无参考文献 → 联网（ddgs）搜索笔记标题/关键词，找对应参考文献
  4. 网上也找不到对应来源 → 该笔记【不可用】

用法：
  python tools/check_flomo_note_refs.py --keywords "编程语言" [--limit 10]   # 实时检索 flomo 并检测
  python tools/check_flomo_note_refs.py --file notes/01_xxx.md               # 检测单个笔记文件
  python tools/check_flomo_note_refs.py --dir notes/                         # 批量检测目录下笔记
  python tools/check_flomo_note_refs.py --keywords "主题" --no-search        # 只检测有无参考文献，不联网
  python tools/check_flomo_note_refs.py --keywords "主题" --out report.md    # 结果落盘

退出码：0 全部可用或待确认；2 存在【不可用】笔记。
"""
import sys
import os
import re
import json
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.web_search import search as web_search  # noqa: E402


# ---------- 参考文献存在性检测 ----------

# 「来源:」是非规定字段，不算参考文献区标记（文献区只能以「参考文献:」开头）
REF_MARKERS = re.compile(
    r"(参考文献[^\n]{0,4}[:：]|##\s*参考文献|###\s*参考文献"
    r"|\[EB/OL\]|\[M\]|\[J\]|\[C\]|\[P\]|\[D\]|\[R\]|\[S\]"
    r"|https?://"
    r"|^\s*\[\d+\]\s*\S)",
    re.MULTILINE,
)

# 非规定字段（来源/概念等，模板只允许 tag 行 + 标题 + 正文 + 参考文献:）
FORBIDDEN_FIELD_RE = re.compile(
    r"^\s*(?:\*\*)?(?:来源|概念)[^\n]{0,6}[:：]",
    re.MULTILINE,
)

# GB/T 7714-2015 文献类型标识（含电子版 /OL）
TYPE_MARK = re.compile(r"\[(?:M|J|C|D|R|S|Z|N|EB|DB|CP|MT)(?:/OL)?\]")
CITE_DATE = re.compile(r"\[\d{4}-\d{2}-\d{2}\]")


def gbt_validate(text):
    """校验笔记参考文献是否符合 GB/T 7714-2015。返回 (ok, issues)。

    规则：1) 文献区须有 [n] 编号条目；2) 每条含文献类型标识 [X]/[X/OL]；
          3) 含 URL 的条目须带引用日期 [YYYY-MM-DD]；4) 编号从 1 连续。
    """
    m = re.search(r"(##\s*参考文献|参考文献[^\n]{0,4}[:：])", text or "")
    if not m:
        return False, ["无参考文献区"]
    ref_section = text[m.end():]
    entries = [ln.strip() for ln in ref_section.splitlines()
               if re.match(r"^\[\d+\]\s*\S", ln.strip())]
    if not entries:
        return False, ["参考文献区无 [n] 编号条目（如「**来源**：网络」不算合规参考文献）"]
    issues = []
    for i, e in enumerate(entries, 1):
        if not TYPE_MARK.search(e):
            issues.append(f"条目[{i}] 缺文献类型标识（如 [M]/[J]/[EB/OL]）: {e[:36]}")
        if "http" in e.lower() and not CITE_DATE.search(e):
            issues.append(f"条目[{i}] 含 URL 但缺引用日期 [YYYY-MM-DD]: {e[:36]}")
    nums = [int(re.match(r"^\[(\d+)\]", e).group(1)) for e in entries]
    if nums and nums != list(range(1, len(nums) + 1)):
        issues.append(f"文献编号不连续: {nums}")
    # 参考文献条目与正文 [n] 引注一一对应（不能少、不能多）
    head = text[:m.start()]
    body_cites = sorted({int(x) for x in re.findall(r"\[(\d+)\]", head)})
    ref_set = set(nums)
    if body_cites:
        dangling = [c for c in body_cites if c not in ref_set]
        if dangling:
            issues.append(f"正文引用 {dangling} 无对应参考文献条目")
        unused = [n for n in nums if n not in body_cites]
        if unused:
            issues.append(f"参考文献 {sorted(unused)} 未在正文引用（须一一对应）")
    elif nums:
        issues.append("正文未标注 [n] 引用但存在参考文献条目（须一一对应）")
    return (not issues, issues)


def has_reference(text):
    """检测笔记是否含参考文献（GB/T 7714 来源/URL/编号条目）。"""
    return bool(REF_MARKERS.search(text or ""))


def extract_title(text):
    """提取笔记标题：优先取首行 tag 之后的标题行；无 tag 取第一行。"""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    first = lines[0]
    # 第一行是 tag（#tag1 #tag2 … 形式）→ 标题是第二行
    if re.match(r"^#[^\s]+(\s+#[^\s]+)+$", first):
        if len(lines) > 1:
            t = re.sub(r"^#+\s*", "", lines[1]).strip()
        else:
            return ""
    else:
        t = re.sub(r"^#+\s*", "", first).strip()
    t = t.replace("\\_", "_").strip("*# ")
    return t


def build_queries(title, text):
    """构造联网搜索关键词：标题 → 标题+正文要点。"""
    queries = []
    t = title or ""
    if t:
        queries.append(t)
        # 正文前 60 字去掉标点做第二候选
        body = re.sub(r"[#\s|*_`>\-\[\]()（）【】「」\"'，。、；：！？·]", "", (text or ""))
        body = re.sub(r"http[s]?://\S+", "", body)
        body = body[:60].strip()
        if body and body not in t:
            queries.append(f"{t} {body[:30]}")
    else:
        body = re.sub(r"http[s]?://\S+", "", (text or ""))[:80]
        queries.append(body)
    return [q for q in queries if q.strip()]


STOP_FRAGMENTS = {"编程", "技术", "语言", "笔记", "来源", "类型", "主题",
                  "学习", "发展", "趋势", "分析", "研究", "如何", "什么",
                  "一个", "相关", "整理", "汇总", "介绍", "入门", "实践"}


def match_keys(text):
    """从文本提取匹配键：连续中文串（≥2 字，超 4 字补前缀键）与英文串（≥3 字母，超 6 字母补前缀键）。"""
    keys = set()
    for seg in re.findall(r"[\u4e00-\u9fff]{2,}", text or ""):
        keys.add(seg)
        if len(seg) > 4:
            keys.add(seg[:4])
    for seg in re.findall(r"[A-Za-z]{3,}", text or ""):
        keys.add(seg.lower())
        if len(seg) > 6:
            keys.add(seg[:6].lower())
    return keys


def relevant_candidates(title, candidates):
    """按标题匹配键过滤候选：候选 title/body 命中任一匹配键才算相关。"""
    if not title:
        return candidates  # 无标题可依，保守全部列出待人确认
    keys = set()
    # 标题按分隔符切片段，跳过停用片段，取每片段的匹配键
    for frag in re.split(r"[_\s,，。；;、|/\\（）()\[\]【】<>「」\"'*#！!？?·.-]+", title):
        frag = frag.strip().strip("*#_")
        if not frag or frag in STOP_FRAGMENTS:
            continue
        keys |= match_keys(frag)
    keys.discard("")
    if not keys:
        return candidates
    out = []
    for c in candidates:
        blob = f"{c.get('title', '')} {c.get('body', '')}".lower()
        if any(k.lower() in blob for k in keys):
            out.append(c)
    return out


def search_refs(text, max_results=6):
    """对无参考文献的笔记联网搜索候选来源，按标题相关性过滤。返回 [(query, candidates, err)]。"""
    title = extract_title(text)
    out = []
    for q in build_queries(title, text):
        try:
            items = web_search(q, max_results=max_results)
        except Exception as e:
            out.append((q, [], f"搜索异常: {str(e)[:80]}"))
            continue
        cands = [{"title": r.get("title", ""), "href": r.get("href", ""),
                  "body": r.get("body", "")[:150]} for r in items]
        cands = relevant_candidates(title, cands)
        if cands:
            out.append((q, cands, ""))
            break  # 首个命中相关候选的查询即停止
        out.append((q, [], ""))
    return out


def normalize(text):
    """反转义 flomo 存储格式：\\[ → [、\\] → ]、\\_ → _。"""
    return (text or "").replace(r"\[", "[").replace(r"\]", "]").replace(r"\_", "_")


def detect(text, do_search=True):
    """检测单条笔记。返回 dict:
    status: ok（有参考文献且符合 GB/T 7714）/ pending（无参考文献，有相关网络候选待确认）/
            error（联网搜索网络失败，需重试）/ fail（无参考文献且联网无对应来源，或参考文献不合国标）
    """
    text = normalize(text)
    if FORBIDDEN_FIELD_RE.search(text):
        return {"status": "fail",
                "reason": "含非规定字段（「来源」「概念」等）——来源只能以 GB/T 7714-2015 条目写入「参考文献:」区，须改造后重新判定"}
    if has_reference(text):
        ok, issues = gbt_validate(text)
        if ok:
            return {"status": "ok", "reason": "含参考文献且符合 GB/T 7714-2015"}
        return {"status": "fail", "reason": f"参考文献不符合 GB/T 7714-2015（{'；'.join(issues[:3])}），不可用"}
    if not do_search:
        return {"status": "fail", "reason": "无参考文献（未联网搜索）"}
    results = search_refs(text)
    candidates = [c for _, cands, _ in results for c in cands]
    if candidates:
        return {"status": "pending", "reason": "无参考文献，联网找到相关候选来源，需确认对应性", "candidates": candidates[:5]}
    all_err = all(e for _, _, e in results)
    if all_err:
        return {"status": "error", "reason": "联网搜索网络失败（ddgs 异常），需稍后重试再判定",
                "queries": [q for q, _, _ in results]}
    return {"status": "fail", "reason": "无参考文献且联网未找到与笔记主题对应的参考文献，笔记不可用", "queries": [q for q, _, _ in results]}


# ---------- 输入装配 ----------

def load_from_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return [{"name": os.path.basename(path), "content": f.read()}]


def load_from_dir(path):
    notes = []
    for fname in sorted(os.listdir(path)):
        if fname.endswith(".md") and not fname.startswith("_"):
            with open(os.path.join(path, fname), "r", encoding="utf-8") as f:
                notes.append({"name": fname, "content": f.read()})
    return notes


def batch_get(ids):
    """用 flomo MCP memo_batch_get 拉取笔记全文（memo_search 只返回截断/摘要版）。"""
    from tools.flomo_search import mcp_call
    result = mcp_call("tools/call", {"name": "memo_batch_get", "arguments": {"ids": ids}})
    if not result or "result" not in result:
        return {}
    text = result["result"]["content"][0]["text"]
    data = json.loads(text)
    return {m["id"]: (m.get("content") or "") for m in data.get("memos", [])}


def load_from_flomo(keywords, tag, limit):
    from tools.flomo_search import search as flomo_search
    memos = flomo_search(keywords=keywords, tag=tag, limit=limit)
    ids = [m.get("id") for m in memos if m.get("id")]
    full = batch_get(ids) if ids else {}
    notes = []
    for m in memos:
        c = full.get(m.get("id")) or m.get("content") or ""
        notes.append({"name": (m.get("url") or m.get("id") or "flomo"), "content": c, "meta": m})
    return notes


# ---------- 主流程 ----------

def main():
    ap = argparse.ArgumentParser(description="flomo 笔记参考文献检测（无参考文献→联网找→找不到不可用）")
    ap.add_argument("--keywords", help="flomo 检索关键词（实时检索模式）")
    ap.add_argument("--tag", help="flomo 检索标签（与 --keywords 组合）")
    ap.add_argument("--limit", type=int, default=10, help="flomo 检索条数（默认 10）")
    ap.add_argument("--file", help="检测单个笔记文件")
    ap.add_argument("--dir", help="批量检测目录下笔记")
    ap.add_argument("--no-search", action="store_true", help="不联网搜索（只标有无参考文献）")
    ap.add_argument("--out", help="结果落盘为 Markdown 文件")
    args = ap.parse_args()

    notes = []
    if args.file:
        notes = load_from_file(args.file)
    elif args.dir:
        notes = load_from_dir(args.dir)
    elif args.keywords or args.tag:
        notes = load_from_flomo(args.keywords, args.tag, args.limit)
    else:
        print("用法: --keywords/--tag（flomo 检索）或 --file/--dir（本地笔记），至少一种", file=sys.stderr)
        sys.exit(2)

    if not notes:
        print("[无笔记] 未取到任何笔记", file=sys.stderr)
        sys.exit(0)

    print(f"检测 {len(notes)} 条笔记（联网搜索: {'关' if args.no_search else '开'}）\n", file=sys.stderr)

    summary = {"ok": 0, "pending": 0, "error": 0, "fail": 0}
    lines = ["# flomo 笔记参考文献检测结果", "",
             f"> 规则：笔记须有参考文献；无 → 联网找对应来源；找不到 → 不可用",
             f"> 检测 {len(notes)} 条 | 联网搜索: {'关' if args.no_search else '开'} | 日期: {__import__('datetime').date.today()}", ""]
    for n in notes:
        r = detect(n["content"], do_search=not args.no_search)
        summary[r["status"]] += 1
        status = {"ok": "✅ 可用", "pending": "🔎 待确认", "error": "⚠️ 重试", "fail": "❌ 不可用"}[r["status"]]
        title = extract_title(n["content"]) or n["name"]
        print(f"[{status}] {title[:50]}")
        print(f"    理由: {r['reason']}")
        if r.get("candidates"):
            for c in r["candidates"][:3]:
                print(f"    候选: {c['title'][:40]} | {c['href'][:60]}")
        print(file=sys.stderr)

        lines.append(f"## {status} {title}")
        lines.append("")
        lines.append(f"- 笔记: {n['name']}")
        lines.append(f"- 理由: {r['reason']}")
        if r.get("candidates"):
            lines.append("- 候选来源:")
            for c in r["candidates"]:
                lines.append(f"  - {c['title']} — {c['href']}")
        if r.get("queries"):
            lines.append(f"- 搜索词: {' / '.join(r['queries'])}")
        lines.append("")

    lines.insert(3, f"**汇总: 可用 {summary['ok']} | 待确认 {summary['pending']} | 需重试 {summary['error']} | 不可用 {summary['fail']}**")
    lines.insert(4, "")

    print(f"\n汇总: 可用 {summary['ok']} | 待确认 {summary['pending']} | 需重试 {summary['error']} | 不可用 {summary['fail']}", file=sys.stderr)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"[已落盘] {args.out}", file=sys.stderr)

    if summary["fail"]:
        print("存在【不可用】笔记（无参考文献且联网无对应来源），退出码 2", file=sys.stderr)
        sys.exit(2)
    if summary["error"]:
        print("存在【需重试】笔记（联网搜索失败），稍后重跑再判定", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
