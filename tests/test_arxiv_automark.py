"""arxiv_search.py 落盘自动登记通道 P（arxiv 归入 P）回归测试。

直接调用 _auto_mark_p(out, entries, slug_explicit)，覆盖：
  - 标准路径 + 有命中 → P done（从 out 路径反推 slug）
  - 标准路径 + 零命中 → P empty
  - .progress.json 缺失 → 静默跳过、不创建
  - out 非标准路径（无法反推 slug）→ 不登记

运行：python tests/test_arxiv_automark.py
"""
import os
import sys
import json
import shutil

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


def setup_slug(slug, with_progress=True):
    slug_dir = os.path.join(ROOT, "research", slug)
    os.makedirs(slug_dir, exist_ok=True)
    if with_progress:
        with open(os.path.join(slug_dir, ".progress.json"), "w", encoding="utf-8") as f:
            json.dump({"stage": "phase1_done", "data": {}}, f, ensure_ascii=False, indent=2)
    return slug_dir


def read_channels(slug):
    p = os.path.join(ROOT, "research", slug, ".progress.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("data", {}).get("channels_done", {})


def cleanup(slug):
    d = os.path.join(ROOT, "research", slug)
    shutil.rmtree(d, ignore_errors=True)


# 1) 标准路径 + 有命中 → P done
slug = "arxiv_am_done"
d = setup_slug(slug)
out = os.path.join(d, "gathered_arxiv.md")
ax._auto_mark_p(out, [{"title": "x"}], None)
cd = read_channels(slug)
expect("am+ 有命中→P done", cd.get("P", {}).get("status"), "done")
cleanup(slug)

# 2) 标准路径 + 零命中 → P empty
slug = "arxiv_am_empty"
d = setup_slug(slug)
out = os.path.join(d, "gathered_arxiv.md")
ax._auto_mark_p(out, [], None)
cd = read_channels(slug)
expect("am+ 零命中→P empty", cd.get("P", {}).get("status"), "empty")
cleanup(slug)

# 3) .progress.json 缺失 → 静默跳过、不创建
slug = "arxiv_am_nofile"
d = setup_slug(slug, with_progress=False)
out = os.path.join(d, "gathered_arxiv.md")
try:
    ax._auto_mark_p(out, [{"title": "x"}], None)
    raised = False
except Exception:
    raised = True
expect("am- 无进度文件不报错", raised, False)
expect("am- 无进度文件不创建", os.path.exists(os.path.join(d, ".progress.json")), False)
cleanup(slug)

# 4) out 非标准路径 → 无法反推 slug → 不登记
slug = "arxiv_am_nonstd"
d = setup_slug(slug)
# 用 /tmp 风格路径确保不含 research 段，无法反推 slug
out2 = os.path.join(ROOT, "arxiv_tmp_gathered.md")
ax._auto_mark_p(out2, [{"title": "x"}], None)
cd = read_channels(slug)
expect("am- 非标准路径不登记", "P" not in (cd or {}), True)
cleanup(slug)
if os.path.exists(out2):
    os.remove(out2)

print(f"\n==== arxiv_search 自动登记 回归测试：PASS={PASS} FAIL={FAIL} ====")
sys.exit(1 if FAIL else 0)
