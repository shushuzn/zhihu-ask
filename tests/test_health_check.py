"""health_check.py 回归测试：关键文件清单与纯函数（17 项）。

覆盖：
- find_missing：临时目录缺失检测（全在/缺一/空清单）
- git_synced：git status 输出判定同步（ahead/behind/无远程/空）
- REQUIRED_FILES 一致性（仓库级守护不变量）：
  · 无重复、全部真实存在于磁盘（缺失即 health_check 永久 FAIL）
  · 全量覆盖 tools/*.py、docs/*.md、templates/*.md（新增/改名工具漏登记即漂移）
  · 含 tests/run_all.py（回归套件聚合器）
  · 清单内无内部文件（否则 git_protect 会永久阻止提交自身关键文件）
  · git_protect.KEY_FILES 为 REQUIRED_FILES 超集且技能文件存在

REQUIRED_FILES 是 git_protect「关键文件缺失阻止提交」的单一真相源，
清单漂移（漏登记/冗余）会静默弱化提交保护，需回归守护。

运行：python tests/test_health_check.py
"""
import os
import sys
import tempfile
import shutil

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import health_check as hc
import internal_files as inf
import git_protect as gp

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- find_missing：纯函数 ----
tmp = testutil.mktestdir()
try:
    with open(os.path.join(tmp, "a.md"), "w", encoding="utf-8") as f:
        f.write("x")
    expect("miss+ 全在为空", hc.find_missing(["a.md"], tmp), [])
    expect("miss+ 缺一", hc.find_missing(["a.md", "b.md"], tmp), ["b.md"])
    expect("miss+ 空清单", hc.find_missing([], tmp), [])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- git_synced：纯函数 ----
expect("sync+ 干净同步", hc.git_synced("## main...origin/main"), True)
expect("sync+ 有未提交改动仍同步", hc.git_synced("## main...origin/main\n M a.py"), True)
expect("sync- ahead", hc.git_synced("## main...origin/main [ahead 1]"), False)
expect("sync- behind", hc.git_synced("## main...origin/main [behind 2]"), False)
expect("sync- 无远程", hc.git_synced("## main"), False)
expect("sync- 空输出", hc.git_synced(""), False)
expect("sync- 其他远程", hc.git_synced("## main...origin/other"), False)

# ---- REQUIRED_FILES：一致性守护不变量 ----
expect("rf+ 无重复", len(hc.REQUIRED_FILES), len(set(hc.REQUIRED_FILES)))

missing = hc.find_missing(hc.REQUIRED_FILES, hc.ROOT)
expect("rf+ 清单全部真实存在", missing, [])

# 全量覆盖：tools/*.py
tools_py = sorted(os.path.relpath(os.path.join(r, f), hc.ROOT).replace("\\", "/")
                  for r, _, fs in os.walk(os.path.join(hc.ROOT, "tools"))
                  for f in fs if f.endswith(".py"))
uncovered = [f for f in tools_py if f not in hc.REQUIRED_FILES]
expect("rf+ tools/*.py 全覆盖", uncovered, [])

# 全量覆盖：docs/*.md
docs_md = sorted(os.path.relpath(os.path.join(r, f), hc.ROOT).replace("\\", "/")
                 for r, _, fs in os.walk(os.path.join(hc.ROOT, "docs"))
                 for f in fs if f.endswith(".md"))
uncovered = [f for f in docs_md if f not in hc.REQUIRED_FILES]
expect("rf+ docs/*.md 全覆盖", uncovered, [])

# 全量覆盖：templates/*.md
tpl_md = sorted(os.path.relpath(os.path.join(r, f), hc.ROOT).replace("\\", "/")
                for r, _, fs in os.walk(os.path.join(hc.ROOT, "templates"))
                for f in fs if f.endswith(".md"))
uncovered = [f for f in tpl_md if f not in hc.REQUIRED_FILES]
expect("rf+ templates/*.md 全覆盖", uncovered, [])

expect("rf+ 含回归聚合器", "tests/run_all.py" in hc.REQUIRED_FILES, True)

# 清单内无内部文件（否则 git_protect 永久阻止提交关键文件本身）
leaks = [f for f in hc.REQUIRED_FILES if inf.is_internal(f)]
expect("rf+ 清单无内部文件", leaks, [])

# git_protect.KEY_FILES 一致性
extra = [f for f in gp.KEY_FILES if f not in hc.REQUIRED_FILES]
expect("gp+ KEY_FILES 仅追加技能文件", extra, ["skills/zhihu-ask-research/SKILL.md"])
expect("gp+ 技能文件存在",
       os.path.exists(os.path.join(hc.ROOT, "skills", "zhihu-ask-research", "SKILL.md")), True)


# ---- find_stale_docs：规则文档废话检测纯函数 ----
tmp2 = testutil.mktestdir()
try:
    # 构造规则文档目录与文件
    rule_dir = os.path.join(tmp2, "docs")
    os.makedirs(rule_dir)
    # 含裁定废话的文件
    with open(os.path.join(rule_dir, "bad.md"), "w", encoding="utf-8") as f:
        f.write("# 标题\n\n（2026-08-13 用户裁定：上传笔记）\n\n**规则（2026-08-13 新增）**：内容\n")
    # 豁免文件（历史日志/数据快照/文献示例）
    for ex in ("plan.md", "IMA_LIBRARIES.md", "KEYWORDS.md"):
        with open(os.path.join(rule_dir, ex), "w", encoding="utf-8") as f:
            f.write("（2026-08-09 用户要求）\n")
    # 干净文件
    with open(os.path.join(rule_dir, "clean.md"), "w", encoding="utf-8") as f:
        f.write("# 标题\n\n规则内容\n")

    hits = hc.find_stale_docs(tmp2, hc.STALE_DOC_PATTERNS, ["docs"], hc.STALE_DOC_EXCLUDE)
    hit_files = {h[0].replace("\\", "/") for h in hits}
    expect("stale+ 检出 bad.md", "docs/bad.md" in hit_files, True)
    expect("stale+ bad.md 命中 2 处",
           sum(1 for h in hits if h[0].replace("\\", "/") == "docs/bad.md"), 2)
    expect("stale+ 豁免 plan.md", "docs/plan.md" in hit_files, False)
    expect("stale+ 豁免 IMA_LIBRARIES.md", "docs/IMA_LIBRARIES.md" in hit_files, False)
    expect("stale+ 豁免 KEYWORDS.md", "docs/KEYWORDS.md" in hit_files, False)
    expect("stale+ 不误报 clean.md", "docs/clean.md" in hit_files, False)
finally:
    shutil.rmtree(tmp2, ignore_errors=True)

# 仓库级不变量：规则文档当前无废话（health_check 门禁同源）
live = hc.find_stale_docs(hc.ROOT, hc.STALE_DOC_PATTERNS, hc.STALE_DOC_SCAN, hc.STALE_DOC_EXCLUDE)
expect("stale+ 仓库规则文档无废话", live, [])

print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
