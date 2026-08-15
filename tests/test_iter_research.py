"""iter_research.py 回归测试：多轮迭代研究逻辑（24 项）。

覆盖（ROOT 打补丁到临时目录，不触碰真实 research/）：
- parse_args：--slug / --round / 缺值 / 未知参数 / 默认值
- round_status：轮次达标文案（已达 / 还需 N 轮 / 恰好达标）
- get_current_round：缺失文件→1、data.round 读取、无 round→1、损坏 JSON→1（兜底）
- update_round：新建文件（stage 默认）、保留既有字段（domain/channels_done）、
  更新 round 与 round_updated
- write_template：生成问题清单模板（标题/小节）、归档行为（cur>=2 且推进时
  归档 round_notes_r<N>.md；cur=1 不归档）

轮次口径回退会破坏「1 轮成稿 / 最低轮次」纪律或覆盖迭代轨迹，需回归守护。

运行：python tests/test_iter_research.py
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
import iter_research as it

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
    """返回 (tmp_root, slug, slug_dir)：临时 ROOT + research/<slug> 目录。"""
    tmp = testutil.mktestdir()
    slug = "it_" + uuid.uuid4().hex[:8]
    slug_dir = os.path.join(tmp, "research", slug)
    os.makedirs(slug_dir, exist_ok=True)
    return tmp, slug, slug_dir


# ---- parse_args ----
a = it.parse_args(["--slug", "foo", "--round", "3"])
expect("args slug+round", (a["slug"], a["round"]), ("foo", 3))
a = it.parse_args(["--slug", "foo"])
expect("args 仅 slug", (a["slug"], a["round"]), ("foo", None))
a = it.parse_args([])
expect("args 默认", (a["slug"], a["round"]), (None, None))
a = it.parse_args(["--round", "2", "--unknown"])
expect("args 未知忽略", a["round"], 2)
a = it.parse_args(["--slug", "x", "--round"])
expect("args round 缺值", a["round"], None)

# ---- round_status ----
expect("st+ 未达标", it.round_status(2, 3), "未达领域最低轮次，还需 1 轮")
expect("st+ 恰好达标", it.round_status(3, 3), "已达领域最低轮次，可收敛（若问题清单未清空或用户要求继续则继续）")
expect("st+ 超达标", it.round_status(4, 3), "已达领域最低轮次，可收敛（若问题清单未清空或用户要求继续则继续）")

# ---- get_current_round ----
tmp, slug, slug_dir = make_env()
old_ro = it.ROOT
it.ROOT = tmp
try:
    expect("cur+ 无进度文件", it.get_current_round(slug), 1)

    with open(os.path.join(slug_dir, ".progress.json"), "w", encoding="utf-8") as f:
        json.dump({"data": {"round": 3}}, f)
    expect("cur+ 读取 round", it.get_current_round(slug), 3)

    with open(os.path.join(slug_dir, ".progress.json"), "w", encoding="utf-8") as f:
        json.dump({"data": {}}, f)
    expect("cur+ 无 round 字段", it.get_current_round(slug), 1)

    with open(os.path.join(slug_dir, ".progress.json"), "w", encoding="utf-8") as f:
        f.write("{broken json")
    expect("cur+ 损坏 JSON 兜底", it.get_current_round(slug), 1)
finally:
    it.ROOT = old_ro
    shutil.rmtree(tmp, ignore_errors=True)

# ---- update_round ----
tmp, slug, slug_dir = make_env()
it.ROOT = tmp
try:
    it.update_round(slug, 2)
    with open(os.path.join(slug_dir, ".progress.json"), "r", encoding="utf-8") as f:
        prog = json.load(f)
    expect("upd+ 新建文件 stage 默认", prog.get("stage"), "phase1_done")
    expect("upd+ round 更新", prog["data"]["round"], 2)
    import datetime
    expect("upd+ round_updated 落盘", prog["data"]["round_updated"], datetime.date.today().isoformat())

    # 既有字段保留
    with open(os.path.join(slug_dir, ".progress.json"), "w", encoding="utf-8") as f:
        json.dump({"stage": "phase2", "data": {"domain": "金融", "round": 1,
                                               "channels_done": {"A": {"status": "done"}}}}, f)
    it.update_round(slug, 3)
    with open(os.path.join(slug_dir, ".progress.json"), "r", encoding="utf-8") as f:
        prog = json.load(f)
    expect("upd+ stage 保留", prog["stage"], "phase2")
    expect("upd+ domain 保留", prog["data"]["domain"], "金融")
    expect("upd+ channels_done 保留", prog["data"]["channels_done"]["A"]["status"], "done")
    expect("upd+ round 覆写", prog["data"]["round"], 3)
finally:
    it.ROOT = old_ro
    shutil.rmtree(tmp, ignore_errors=True)

# ---- write_template ----
tmp, slug, slug_dir = make_env()
it.ROOT = tmp
try:
    # 生成模板（cur=1 不归档）
    notes = it.write_template(slug, 1, 2)
    with open(notes, "r", encoding="utf-8") as f:
        content = f.read()
    expect("tpl+ 标题含目标轮次", "# 第 2 轮研究问题清单" in content, True)
    expect("tpl+ 含未解决问题小节", "## 未解决/可深化的问题" in content, True)
    expect("tpl+ 含执行指引小节", "## 下一轮执行指引" in content, True)
    expect("tpl+ 编号占位", content.count("1. \n"), 1)
    expect("tpl- cur=1 不归档", os.path.exists(os.path.join(slug_dir, "round_notes_r1.md")), False)

    # 推进归档（cur=2 且 target>cur）
    with open(notes, "r", encoding="utf-8") as f:
        old_content = f.read()
    it.write_template(slug, 2, 3)
    expect("tpl+ 归档 r2", os.path.exists(os.path.join(slug_dir, "round_notes_r2.md")), True)
    with open(os.path.join(slug_dir, "round_notes_r2.md"), "r", encoding="utf-8") as f:
        archived = f.read()
    expect("tpl+ 归档保留旧内容", archived == old_content, True)
    with open(notes, "r", encoding="utf-8") as f:
        new_content = f.read()
    expect("tpl+ 新模板为第 3 轮", "# 第 3 轮研究问题清单" in new_content, True)
finally:
    it.ROOT = old_ro
    shutil.rmtree(tmp, ignore_errors=True)


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
