"""note_upload.py 回归测试：拦截规则 / memo id 持久化 / update 分支（纯逻辑，不调 flomo）。

覆盖：
- is_blocked：索引(00_index.md)/报告(report.md/report_draft.md)禁止上传
- ids 持久化：ids_path_for 定位、load_ids 损坏回退、save_ids roundtrip
- upload_file 分支（mock upload/update 函数）：
  · update=False → memo_create（upload_to_flomo）
  · update=True 且有记录 → memo_update（update_to_flomo，原 id 传入）
  · update=True 无记录 → 回退 memo_create
  · 成功写回 ids 并落盘
- 质检拦截与禁止拦截前置

运行：python tests/test_note_upload.py
"""
import os
import sys
import json
import shutil

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import note_upload as nu

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- is_blocked ----
expect("block+ 索引禁止", nu.is_blocked("notes/00_index.md"), True)
expect("block+ 报告禁止", nu.is_blocked("notes/report.md"), True)
expect("block+ 草稿报告禁止", nu.is_blocked("notes/report_draft.md"), True)
expect("block+ 普通笔记放行", nu.is_blocked("notes/01_core.md"), False)
expect("block+ 非 notes 路径普通名放行", nu.is_blocked("x/01_core.md"), False)

# ---- ids 持久化 ----
tmp = testutil.mktestdir(prefix="nu_")
notes_dir = os.path.join(tmp, "research", "slug", "notes")
os.makedirs(notes_dir, exist_ok=True)
ids_path = nu.ids_path_for(notes_dir)
expect("ids+ 定位到 research/<slug>/.flomo_ids.json",
       os.path.basename(ids_path), ".flomo_ids.json")
expect("ids+ 缺失文件回退空", nu.load_ids(ids_path), {})

with open(ids_path, "w", encoding="utf-8") as f:
    f.write("{broken json")
expect("ids- 损坏回退空", nu.load_ids(ids_path), {})

nu.save_ids(ids_path, {"01_a.md": "MID1", "02_b.md": "MID2"})
expect("ids+ roundtrip", nu.load_ids(ids_path),
       {"01_a.md": "MID1", "02_b.md": "MID2"})

# ---- upload_file 分支（mock 网络函数）----
calls = {"create": [], "update": []}
nu.upload_to_flomo = lambda content, max_retries=5, retry_delay=30: (
    calls["create"].append(content) or "NEW_ID")
nu.update_to_flomo = lambda content, memo_id, max_retries=5, retry_delay=30: (
    calls["update"].append((content, memo_id)) or "OLD_ID")

note = os.path.join(notes_dir, "01_a.md")
with open(note, "w", encoding="utf-8") as f:
    f.write("#维度1 #维度2 #主题/x\n\n标题\n\n内容\n\n来源:\n[1] 甲. 书[M]. 京: 社, 2000.\n来源类型: 一手\n")

ids = {}
ok, mid, reason = nu.upload_file(note, force=True, ids=ids, ids_path=ids_path)
expect("up+ 默认模式 memo_create", (ok, mid), (True, "NEW_ID"))
expect("up+ 默认模式动作词", reason, "上传成功")
expect("up+ create 调用 1 次", len(calls["create"]), 1)
expect("up+ 成功写回 ids", ids.get("01_a.md"), "NEW_ID")
expect("up+ ids 已落盘", nu.load_ids(ids_path).get("01_a.md"), "NEW_ID")

# update=True 且有记录 → memo_update（原 id）
ok, mid, reason = nu.upload_file(note, force=True, update=True, ids=ids, ids_path=ids_path)
expect("up+ update 模式 memo_update", (ok, mid), (True, "OLD_ID"))
expect("up+ update 传原 id", calls["update"][-1][1], "NEW_ID")
expect("up+ update 动作词", reason, "更新成功")

# update=True 但无记录 → 回退 memo_create
ids2 = {}
ok, mid, reason = nu.upload_file(note, force=True, update=True, ids=ids2, ids_path=ids_path)
expect("up+ update 无记录回退 create", (ok, mid), (True, "NEW_ID"))
expect("up+ create 累计 2 次", len(calls["create"]), 2)

# 禁止文件：不触碰网络
calls["create"].clear()
ok, mid, reason = nu.upload_file(os.path.join(notes_dir, "00_index.md"),
                                 force=True, ids=ids, ids_path=ids_path)
expect("block+ 禁止文件不调用", (ok, mid), (False, None))
expect("block+ 无网络调用", len(calls["create"]), 0)

shutil.rmtree(tmp, ignore_errors=True)

print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
sys.exit(1 if FAIL else 0)
