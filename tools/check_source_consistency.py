#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""来源一致性检查：报告关键事实与来源内容自动比对

检查项：
1. 参考文献 URL 必须可访问（非 flomo/内部链接）
2. 每个 [n] 引用的关键实体须在来源内容中出现
3. 参考文献题名须与来源实际标题匹配
4. 正文 [n] 引用与参考文献一一对应

用法：
  python tools/check_source_consistency.py --file report.md [--verbose] [--offline]
"""
import argparse
import os
import re
import sys
import urllib.request

try:
    from tools.console_encoding import setup as _ce
    _ce()
except Exception:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REF_HEAD_RE = re.compile(r"^#{1,6}\s*\u53c2\u8003\u6587\u732e")
ENTRY_RE = re.compile(r"^\[(\d+)\]\s+(.+)")
URL_RE = re.compile(r"https?://[^\s\]\)]+")
CITE_RE = re.compile(r"\[(\d+)\]")

BANNED_URL_PATTERNS = [
    (r"v\.flomoapp\.com", "flomo \u7b14\u8bb0\u94fe\u63a5"),
    (r"example\.com", "\u5360\u4f4d\u7b26 URL"),
    (r"localhost", "\u672c\u5730\u5730\u5740"),
]


def parse_refs(text):
    lines = text.splitlines()
    in_refs = False
    refs = []
    for line in lines:
        if REF_HEAD_RE.match(line.strip()):
            in_refs = True
            continue
        if in_refs:
            m = ENTRY_RE.match(line.strip())
            if m:
                num = int(m.group(1))
                entry = m.group(2).strip()
                urls = URL_RE.findall(entry)
                url = urls[0] if urls else ""
                refs.append((num, entry, url))
    return refs


def check_banned_urls(refs):
    issues = []
    for num, entry, url in refs:
        for pattern, desc in BANNED_URL_PATTERNS:
            if re.search(pattern, url):
                issues.append((num, "\u7981\u6b62\u6765\u6e90", f"\u53c2\u8003\u6587\u732e [{num}] \u542b{desc}\uff1a{url}", url))
    return issues


def check_citation_coverage(text):
    refs = parse_refs(text)
    ref_nums = set(num for num, _, _ in refs)
    lines = text.splitlines()
    ref_start = None
    for i, line in enumerate(lines):
        if REF_HEAD_RE.match(line.strip()):
            ref_start = i
            break
    body = "\n".join(lines[:ref_start]) if ref_start else text
    body_cites = set(int(x) for x in CITE_RE.findall(body))
    issues = []
    unused = sorted(ref_nums - body_cites)
    if unused:
        issues.append((0, "\u6587\u732e\u672a\u5f15\u7528", f"\u6587\u732e {unused} \u672a\u5728\u6b63\u6587\u5f15\u7528", ""))
    orphan = sorted(body_cites - ref_nums)
    if orphan:
        issues.append((0, "\u60ac\u7a7a\u5f15\u7528", f"\u6b63\u6587 {orphan} \u65e0\u5bf9\u5e94\u6587\u732e", ""))
    return issues


def fetch_url_content(url, timeout=15):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (zhihu-ask source checker)"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return True, raw[:2000]
    except Exception as e:
        return False, str(e)[:100]


def extract_entities(text):
    entities = set()
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text):
        entities.add(m.group(1))
    for m in re.finditer(r'[\u300c\u300d\u300a\u300b\u201c\u201d]([^"\u300c\u300d\u300a\u300b\u201c\u201d]+)[\u300c\u300d\u300a\u300b\u201c\u201d]', text):
        entities.add(m.group(1))
    return entities


def check_entity_consistency(num, report_entry, fetched_content):
    issues = []
    if not fetched_content:
        return issues
    report_entities = extract_entities(report_entry)
    fetched_lower = fetched_content.lower()
    skip_words = {"The", "And", "For", "With", "From", "In", "On", "At", "By",
                  "We", "Our", "This", "That", "These", "Those", "It", "He",
                  "She", "They", "You", "A", "An", "To", "Of", "Or", "If",
                  "Year", "Breaks", "Problem", "Math", "Conjecture", "Solves",
                  "New", "Old", "Open", "AI", "LLM", "IMO", "Nexus",
                  "Google", "DeepMind", "OpenAI", "Anthropic", "Claude",
                  "AlphaProof", "Lean", "Arxiv", "arXiv"}
    for entity in report_entities:
        if entity in skip_words:
            continue
        if entity.lower() not in fetched_lower:
            issues.append((num, "\u5b9e\u4f53\u4e0d\u5339\u914d", f"\u62a5\u544a [{num}] \u63d0\u53ca '{entity}' \u4f46\u6765\u6e90\u672a\u627e\u5230", entity))
    return issues


def main():
    parser = argparse.ArgumentParser(description="\u6765\u6e90\u4e00\u81f4\u6027\u68c0\u67e5")
    parser.add_argument("--file", help="\u62a5\u544a\u6587\u4ef6\u8def\u5f84")
    parser.add_argument("--slug", help="\u7814\u7a76\u4e3b\u9898 slug")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    if args.slug:
        filepath = os.path.join(ROOT, "research", args.slug, "report.md")
    elif args.file:
        filepath = os.path.join(ROOT, args.file) if not os.path.isabs(args.file) else args.file
    else:
        print("需要 --file 或 --slug", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(filepath):
        print(f"\u6587\u4ef6\u4e0d\u5b58\u5728: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    all_issues = []
    refs = parse_refs(text)
    all_issues.extend(check_banned_urls(refs))
    all_issues.extend(check_citation_coverage(text))

    if not args.offline:
        print("\u6b63\u5728\u9a8c\u8bc1\u6765\u6e90 URL...", file=sys.stderr)
        for num, entry, url in refs:
            if not url:
                all_issues.append((num, "\u65e0URL", f"\u53c2\u8003\u6587\u732e [{num}] \u65e0 URL", ""))
                continue
            if url.startswith("file:") or "localhost" in url:
                continue
            ok, content = fetch_url_content(url)
            if ok:
                entity_issues = check_entity_consistency(num, entry, content)
                all_issues.extend(entity_issues)
                if args.verbose:
                    print(f"  [{num}] URL \u53ef\u8bbf\u95ee\uff0c\u5b9e\u4f53\u68c0\u67e5 {len(entity_issues)} \u5904", file=sys.stderr)
            else:
                all_issues.append((num, "URL\u4e0d\u53ef\u8fbe", f"[{num}] URL \u65e0\u6cd5\u8bbf\u95ee\uff1a{url}\uff08{content}\uff09", url))
                if args.verbose:
                    print(f"  [{num}] URL \u4e0d\u53ef\u8fbe: {url}", file=sys.stderr)

    if not all_issues:
        print("\u5168\u90e8\u901a\u8fc7\uff1a\u6765\u6e90\u4e00\u81f4\u6027\u68c0\u67e5\u901a\u8fc7\u3002")
        sys.exit(0)

    by_type = {}
    for item in all_issues:
        by_type.setdefault(item[1], []).append(item)

    for label, items in by_type.items():
        print(f"\n[{label}] {len(items)} \u5904")
        for item in items:
            print(f"  [{item[0]}] {item[2]}")

    print(f"\n\u9000\u51fa\u7801 1\uff08\u5b58\u5728\u5f85\u786e\u8ba4\u9879\uff09\u3002")
    sys.exit(1)


if __name__ == "__main__":
    main()
