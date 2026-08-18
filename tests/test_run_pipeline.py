"""run_pipeline.py 回归测试：流水线门禁顺序与清单（9 项）。

覆盖：
- agent_todos：slug/query 替换、六通道步骤齐全、无占位符残留、
  query=None 时替换为空
- finish：收尾门禁执行顺序（结构→质量→轮次→落报告→docx→flomo）——
  顺序/缺步回归会静默跳过 SOP 硬门禁
- bootstrap：WECHAT_ARTICLE_SEARCH_SCRIPTS 未设时预警 + research_start 调用
- main：无参数报错退出

run()/subprocess 用 Mock 替换，不触发真实子进程。

运行：python tests/test_run_pipeline.py
"""
import os
import sys
import io
import contextlib
from unittest import mock

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import run_pipeline as rp

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- agent_todos：占位符替换与步骤覆盖 ----
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rp.agent_todos("my-slug", "formal proof")
out = buf.getvalue()
expect("acl+ slug 替换", "my-slug" in out, True)
expect("acl+ query 替换", "formal proof" in out, True)
expect("acl+ 无占位符残留", "<slug>" not in out and "<query>" not in out, True)
for step in ("通道 F", "通道 E", "通道 B", "通道 C", "通道 P", "preprint_search.py", "mark_channel.py"):
    expect(f"acl+ 步骤 {step}", step in out, True)

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rp.agent_todos("s2", None)
out2 = buf.getvalue()
expect("acl+ query=None 替换为空", "<query>" not in out2, True)

# ---- finish：门禁执行顺序（含前置校验） ----
calls = []

def fake_run(cmd, check=True, label=""):
    calls.append(os.path.basename(cmd[0]))
    return 0

with mock.patch("run_pipeline.run", side_effect=fake_run), \
     mock.patch("run_pipeline.subprocess.run", return_value=mock.Mock(returncode=0)):
    rp.finish("demo-slug")
# finish 包含前置校验（3次 check_progress）+ 核心门禁 + 收尾检查（2次 check_progress）+ mark phase4_done
expect("fin+ 门禁顺序（含前置校验）",
       "clean_workspace.py" in calls and "check_report_structure.py" in calls and "quality_check.py" in calls and
       "check_ai_voice.py" in calls and "check_gbt_refs.py" in calls and "check_citation_validity.py" in calls and
       "check_consistency.py" in calls and "report_to_docx.py" in calls and "report_to_flomo.py" in calls, True)

# ---- bootstrap：环境变量预警 + research_start 调用 ----
bootstrap_calls = []
with (
    mock.patch("run_pipeline.run",
               side_effect=lambda cmd, check=True, label="": bootstrap_calls.append(cmd)),
    mock.patch("run_pipeline.subprocess.run", return_value=mock.Mock(returncode=0)),
    mock.patch.dict(os.environ, {}, clear=False),
):
    os.environ.pop("WECHAT_ARTICLE_SEARCH_SCRIPTS", None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        # 用示例配置（tools/start.json 为本地遗留物，可随时删除，测试不依赖它）
        rp.bootstrap("tools/start.example.json")
    out = buf.getvalue()
expect("boot+ 未设环境变量预警", "WECHAT_ARTICLE_SEARCH_SCRIPTS" in out, True)
expect("boot+ 调用 research_start", any("research_start.py" in c[0] for c in bootstrap_calls), True)
flomo_calls = [c for c in bootstrap_calls if "flomo_search.py" in c[0]]
expect("boot+ flomo 查重执行（不带 --slug——查重结论人工判读后 mark_channel 登记）",
       len(flomo_calls) >= 1 and all("--slug" not in c for c in flomo_calls), True)

# ---- mark_plan_done：plan.md 索引回填 ----
plan_dir = testutil.mktestdir(prefix="tplan_")
plan_file = os.path.join(plan_dir, "plan.md")
with open(plan_file, "w", encoding="utf-8") as f:
    f.write("# 索引\n\n| 日期 | 领域 | topic_slug | 状态 |\n|---|---|---|---|\n"
            "| 2026-08-15 | 数学 | done-slug | 进行中 |\n"
            "| 2026-08-15 | 数学 | already-slug | 已完成（1 轮迭代） |\n")
old_root = rp.ROOT
rp.ROOT = plan_dir
try:
    expect("plan+ 进行中 → 已完成", rp.mark_plan_done("done-slug", plan_file), True)
    txt = open(plan_file, encoding="utf-8").read()
    expect("plan+ 行状态已回填", "| done-slug | 已完成 |" in txt, True)
    expect("plan+ 已完成的行不动", "| already-slug | 已完成（1 轮迭代） |" in txt, True)
    expect("plan+ 幂等（再跑无改动）", rp.mark_plan_done("done-slug", plan_file), False)
    expect("plan+ 缺失行返回 False", rp.mark_plan_done("nonexistent", plan_file), False)
    expect("plan+ 无 plan.md 返回 False", rp.mark_plan_done("x", os.path.join(plan_dir, "nope.md")), False)
finally:
    rp.ROOT = old_root

# ---- finish 收尾不再自动回填（验收通过后 --backfill 显式回填）----
plan_dir2 = testutil.mktestdir(prefix="tplan2_")
plan_file2 = os.path.join(plan_dir2, "plan.md")
with open(plan_file2, "w", encoding="utf-8") as f:
    f.write("| 日期 | 领域 | topic_slug | 状态 |\n|---|---|---|---|\n"
            "| 2026-08-15 | 数学 | demo-slug | 进行中 |\n")
old_root2 = rp.ROOT
rp.ROOT = plan_dir2
try:
    calls2 = []
    with mock.patch("run_pipeline.run", side_effect=lambda cmd, check=True, label="": calls2.append(cmd) or 0), \
         mock.patch("run_pipeline.subprocess.run", return_value=mock.Mock(returncode=0)):
        rp.finish("demo-slug")
    txt2 = open(plan_file2, encoding="utf-8").read()
    expect("fin+ 门禁后不自动回填（验收后 --backfill）", "| demo-slug | 已完成 |" in txt2, False)
finally:
    rp.ROOT = old_root2

# ---- --backfill：验收通过后显式回填 ----
buf3 = io.StringIO()
# 重新设置 rp.ROOT 以指向 plan_dir2（finish 测试后已恢复）
rp.ROOT = plan_dir2
try:
    with contextlib.redirect_stdout(buf3):
        with mock.patch.object(rp.sys, "argv", ["run_pipeline.py", "--slug", "demo-slug", "--backfill"]):
            rp.main()
    out3 = buf3.getvalue()
    txt3 = open(plan_file2, encoding="utf-8").read()
    expect("bf+ 输出回填信息", "[回填] plan.md 索引：demo-slug → 已完成" in out3, True)
    expect("bf+ 状态已回填", "| demo-slug | 已完成 |" in txt3, True)
finally:
    rp.ROOT = old_root2

# ---- main：无参数报错退出 ----
with mock.patch.object(rp.sys, "argv", ["run_pipeline.py"]):
    try:
        rp.main()
        expect("main- 无参数应退出", False, True)
    except SystemExit as e:
        expect("main- 无参数退出码 1", e.code, 1)


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
