"""research_start.py 回归测试：启动配置校验与进度合并（25 项）。

覆盖（ROOT 打补丁到临时目录，不触碰真实 research/ 与 docs/）：
- validate_config：question/slug 必填、slug 短横线格式（大写自动降级）、
  keywords 缺失/不足下限警告（非阻塞）
- write_progress：合并保 round（注释记录的真实历史 bug：覆盖丢 round 导致
  check_progress 阻塞）、新增字段、损坏文件回退、无 round 时 setdefault 1
- get_ima_library_hints：词元双向包含匹配、≤2 组上限、空 domain/无文件/无匹配

运行：python tests/test_research_start.py
"""
import os
import sys
import json
import tempfile
import shutil
import uuid

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import research_start as rs

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


def make_env():
    tmp = testutil.mktestdir()
    slug = "rs_" + uuid.uuid4().hex[:8]
    os.makedirs(os.path.join(tmp, "research", slug), exist_ok=True)
    return tmp, slug


# ---- validate_config ----
cfg = {"question": "问题", "slug": "foo-bar", "keywords": ["a 突破", "b 产业", "c 争议", "d x", "e y", "f z"]}
e, w = rs.validate_config(cfg, 6)
expect("vc+ 全通过", (e, w), ([], []))

cfg = {"slug": "foo", "keywords": ["a"]}
e, w = rs.validate_config(cfg, 6)
expect("vc- 缺 question", "question 必填" in e, True)

cfg = {"question": "q", "keywords": ["a"]}
e, w = rs.validate_config(cfg, 6)
expect("vc- 缺 slug", "slug 必填" in e, True)

cfg = {"question": "q", "slug": "Bad Slug!"}
e, w = rs.validate_config(cfg, 6)
expect("vc- slug 非法格式", "slug 须为英文小写短横线" in e, True)

cfg = {"question": "q", "slug": "Example-Slug", "keywords": ["a"] * 6}
e, w = rs.validate_config(cfg, 6)
expect("vc+ 大写 slug 降级合法", e, [])

cfg = {"question": "q", "slug": "foo"}
e, w = rs.validate_config(cfg, 6)
expect("vc- keywords 缺失警告", "未提供 keywords" in w[0], True)

cfg = {"question": "q", "slug": "foo", "keywords": ["a", "b", "c"]}
e, w = rs.validate_config(cfg, 6)
expect("vc- keywords 不足警告", "少于建议下限 6" in w[0], True)

cfg = {"question": "q", "slug": "foo", "keywords": ["a"] * 6}
e, w = rs.validate_config(cfg, 6)
expect("vc+ keywords 达标无警告", w, [])

cfg = {"slug": "foo", "keywords": []}
e, w = rs.validate_config(cfg, 6)
expect("vc+ 错误与警告并存", "question 必填" in e and "未提供 keywords" in w[0], True)

# ---- write_progress：合并保 round ----
tmp, slug = make_env()
old_ro = rs.ROOT
rs.ROOT = tmp
try:
    # 新建
    rs.write_progress(slug, "phase1_done", {"domain": "金融", "keyword_count": 3})
    with open(os.path.join(tmp, "research", slug, ".progress.json"), "r", encoding="utf-8") as f:
        prog = json.load(f)
    expect("wp+ 新建 stage", prog["stage"], "phase1_done")
    expect("wp+ 新建 data", prog["data"]["domain"], "金融")
    expect("wp+ 无 round 时 setdefault 1", prog["data"]["round"], 1)
    expect("wp+ 环境级 E/C skip 自动登记", sorted(prog["data"]["channels_done"].keys()), ["C", "E"])
    expect("wp+ 环境级 skip status", prog["data"]["channels_done"]["E"]["status"], "skip")

    # 合并：保留既有字段，round 不丢
    rs.write_progress(slug, "phase2", {"round": 2, "has_wechat_material": True})
    with open(os.path.join(tmp, "research", slug, ".progress.json"), "r", encoding="utf-8") as f:
        prog = json.load(f)
    expect("wp+ stage 更新", prog["stage"], "phase2")
    expect("wp+ 既有 domain 保留", prog["data"]["domain"], "金融")
    expect("wp+ round 按新值更新", prog["data"]["round"], 2)
    expect("wp+ 新字段合并", prog["data"]["has_wechat_material"], True)

    # 损坏文件回退重建
    with open(os.path.join(tmp, "research", slug, ".progress.json"), "w", encoding="utf-8") as f:
        f.write("{broken")
    rs.write_progress(slug, "phase1_done", {"round": 1})
    with open(os.path.join(tmp, "research", slug, ".progress.json"), "r", encoding="utf-8") as f:
        prog = json.load(f)
    expect("wp+ 损坏回退重建", prog["data"]["round"], 1)
finally:
    rs.ROOT = old_ro
    shutil.rmtree(tmp, ignore_errors=True)

# ---- get_ima_library_hints ----
tmp = testutil.mktestdir()
os.makedirs(os.path.join(tmp, "docs"), exist_ok=True)
rs.ROOT = tmp
try:
    lib = (
        "# ima 订阅库\n\n"
        "## 说明\n\n"
        "### 金融 / 投研 / 宏观\n\n"
        "| 库名 | 内容 |\n"
        "|---|---|\n"
        "| 全行业研报库 | 覆盖 |\n"
        "| 宏观数据 | x |\n\n"
        "### 电子 / 半导体\n\n"
        "| 库名 |\n"
        "|---|\n"
        "| 电子行业研究库 |\n\n"
        "### 投研 / 研究\n\n"
        "| 库名 |\n"
        "|---|\n"
        "| 深度投研库 |\n\n"
        "### 金融科技 / 区块链\n\n"
        "| 库名 |\n"
        "|---|\n"
        "| 区块链研报库 |\n"
    )
    with open(os.path.join(tmp, "docs", "IMA_LIBRARIES.md"), "w", encoding="utf-8") as f:
        f.write(lib)

    hits = rs.get_ima_library_hints("金融")
    expect("ima+ 命中组名", hits[0][0], "金融 / 投研 / 宏观")
    expect("ima+ 组内库名", hits[0][1], ["全行业研报库", "宏观数据"])

    hits = rs.get_ima_library_hints("半导体")
    expect("ima+ 精确词匹配", hits[0][0], "电子 / 半导体")

    hits = rs.get_ima_library_hints("金融投资")
    expect("ima+ 词元包含匹配", any(g == "金融 / 投研 / 宏观" for g, _ in hits), True)

    hits = rs.get_ima_library_hints("农业")
    expect("ima- 无匹配", hits, [])

    hits = rs.get_ima_library_hints("")
    expect("ima- 空 domain", hits, [])

    # 匹配 3 组 → 仅返回前 2
    hits = rs.get_ima_library_hints("金融投研")
    expect("ima+ 上限 2 组", len(hits), 2)
finally:
    rs.ROOT = old_ro
    shutil.rmtree(tmp, ignore_errors=True)

# 无 IMA_LIBRARIES.md
tmp2 = testutil.mktestdir()
rs.ROOT = tmp2
try:
    expect("ima- 无文件返回空", rs.get_ima_library_hints("金融"), [])
finally:
    rs.ROOT = old_ro
    shutil.rmtree(tmp2, ignore_errors=True)


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
