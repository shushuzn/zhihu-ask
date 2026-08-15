"""init_research.py 回归测试：研究初始化的纯函数与 IO（36 项）。

覆盖：
- slug_ok：英文小写短横线校验（合法/非法/边界）
- parse_args：CLI 参数解析（各 flag / 缺值 / 未知参数 / 默认值）
- apply_replacements：模板占位符替换（plan 专属占位符仅 is_plan=True 时替换）
- fill_template：按文件 basename 判定 is_plan（临时目录集成）
- insert_index_row：plan.md 索引表插入（命中/未命中/表头缺 topic_slug/缺分隔行/
  仅索引小节内插入，不污染后续小节）
- write_initial_progress：落盘 .progress.json（check_progress 依赖的 stage/round/domain）

行为与重构前完全一致——main() 委托逻辑不变，本测试锁定抽取出的纯函数。

运行：python tests/test_init_research.py
"""
import os
import sys
import json
import tempfile
import shutil

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import init_research as ir

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- slug_ok：合法 ----
expect("slug+ 标准短横线", ir.slug_ok("example-slug"), True)
expect("slug+ 单段", ir.slug_ok("foo"), True)
expect("slug+ 多段", ir.slug_ok("a-b-c"), True)
expect("slug+ 数字混排", ir.slug_ok("x1-y2"), True)
expect("slug+ 数字开头段", ir.slug_ok("1a-2b"), True)

# ---- slug_ok：非法 ----
expect("slug- 大写", ir.slug_ok("Example"), False)
expect("slug- 开头连字符", ir.slug_ok("-a"), False)
expect("slug- 结尾连字符", ir.slug_ok("a-"), False)
expect("slug- 双连字符", ir.slug_ok("a--b"), False)
expect("slug- 空格", ir.slug_ok("a b"), False)
expect("slug- 下划线", ir.slug_ok("a_b"), False)
expect("slug- 点号", ir.slug_ok("a.b"), False)
expect("slug- 中文", ir.slug_ok("示例-slug"), False)
expect("slug- 空串", ir.slug_ok(""), False)
expect("slug- None", ir.slug_ok(None), False)

# ---- parse_args ----
a = ir.parse_args(["--config", "c.json"])
expect("args config", a["config"], "c.json")
expect("args config 默认 domain", a["domain"], "其他")
expect("args config 默认 priority", a["priority"], "中")

a = ir.parse_args(["--question", "Q", "--domain", "金融", "--slug", "foo", "--priority", "高"])
expect("args 四参数", (a["question"], a["domain"], a["slug"], a["priority"]),
       ("Q", "金融", "foo", "高"))

a = ir.parse_args(["--unknown", "--slug"])
expect("args 未知参数跳过", a["slug"], None)
a = ir.parse_args(["--slug", "x", "--unknown-flag", "y"])
expect("args 未知参数保留已知", a["slug"], "x")

# ---- apply_replacements：通用占位符 ----
out = ir.apply_replacements("标题：{{知乎问题完整标题}}；日期：{{YYYY-MM-DD}}",
                            "问题A", "领域B", "slug-c", "2026-08-11")
expect("replace+ 通用占位符", out, "标题：问题A；日期：2026-08-11")

out = ir.apply_replacements("{{知乎问题完整标题}} 与 {{知乎问题完整标题}}",
                            "重复", "d", "s", "t")
expect("replace+ 多处出现全局替换", out, "重复 与 重复")

out = ir.apply_replacements("【{{知乎问题完整标题}}】", "", "d", "s", "t")
expect("replace+ 空 question 替换为空串", out, "【】")

# ---- apply_replacements：plan 专属占位符（is_plan 开关） ----
tpl = "状态：{{进行中 / 已完成}}；领域：{{...}}；slug：{{topic-slug}}"
out = ir.apply_replacements(tpl, "Q", "金融", "fin-2026", "t", is_plan=True)
expect("replace+ plan 专属占位符", out, "状态：进行中；领域：金融；slug：fin-2026")

out = ir.apply_replacements(tpl, "Q", "金融", "fin-2026", "t", is_plan=False)
expect("replace- 非 plan 不替换专属占位符", out,
       "状态：{{进行中 / 已完成}}；领域：{{...}}；slug：{{topic-slug}}")

# ---- fill_template：basename 判定 is_plan（临时目录） ----
tmp = testutil.mktestdir()
try:
    plan_tpl = os.path.join(tmp, "research_plan_TEMPLATE.md")
    with open(plan_tpl, "w", encoding="utf-8") as f:
        f.write("## {{知乎问题完整标题}}\n状态：{{进行中 / 已完成}} 领域：{{...}} slug：{{topic-slug}} 日期：{{YYYY-MM-DD}}\n")
    out = ir.fill_template(plan_tpl, "问题X", "AI", "ai-01", "2026-08-11")
    expect("fill+ plan 模板完整填充",
           out, "## 问题X\n状态：进行中 领域：AI slug：ai-01 日期：2026-08-11\n")

    rep_tpl = os.path.join(tmp, "research_report_TEMPLATE.md")
    with open(rep_tpl, "w", encoding="utf-8") as f:
        f.write("# {{知乎问题完整标题}}\n{{...}} 保留\n")
    out = ir.fill_template(rep_tpl, "问题Y", "AI", "ai-02", "2026-08-11")
    expect("fill- 非 plan 模板专属占位符保留",
           out, "# 问题Y\n{{...}} 保留\n")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- insert_index_row：命中 ----
plan_content = (
    "# 研究计划\n\n"
    "## 一、当前研究\n\nfoo\n\n"
    "## 三、问题索引表\n\n"
    "| 日期 | 领域 | topic_slug | 状态 |\n"
    "|---|---|---|---|\n"
    "| 2026-08-01 | 产业经济 | old-slug | 已完成 |\n\n"
    "## 四、历史归档\n\nbaz\n"
)
out, ok = ir.insert_index_row(plan_content, "金融", "new-slug", "2026-08-11")
expect("index+ 命中返回 ok", ok, True)
expect("index+ 新行插在分隔行后", out.count("| 2026-08-11 | 金融 | new-slug | 进行中 |"), 1)
expect("index+ 新行在旧数据行之前",
       out.index("| 2026-08-11 | 金融 | new-slug | 进行中 |")
       < out.index("| 2026-08-01 | 产业经济 | old-slug | 已完成 |"), True)
expect("index+ 后续小节未被污染",
       out.index("## 四、历史归档") > out.index("| 2026-08-11 | 金融 | new-slug | 进行中 |"), True)
expect("index+ 旧内容保留", "## 一、当前研究\n\nfoo" in out, True)

# ---- insert_index_row：未命中 ----
out, ok = ir.insert_index_row("## 一、当前研究\n\nfoo", "d", "s", "t")
expect("index- 无索引表小节", ok, False)
expect("index- 无索引表内容不变", out, "## 一、当前研究\n\nfoo")

out, ok = ir.insert_index_row(
    "## 三、问题索引表\n\n| 日期 | 状态 |\n|---|---|\n| 2026-08-01 | 已完成 |\n",
    "d", "s", "t")
expect("index- 表头缺 topic_slug", ok, False)

out, ok = ir.insert_index_row(
    "## 三、问题索引表\n\n| 日期 | topic_slug | 状态 |\n（缺分隔行）\n",
    "d", "s", "t")
expect("index- 缺分隔行", ok, False)

out, ok = ir.insert_index_row("## 三、问题索引表\n\n正文无表格", "d", "s", "t")
expect("index- 小节内无表格", ok, False)

# ---- write_initial_progress：落盘（临时目录） ----
tmp2 = testutil.mktestdir()
try:
    ir.write_initial_progress(tmp2, "问题Z", "半导体")
    p = os.path.join(tmp2, ".progress.json")
    expect("progress+ 文件存在", os.path.exists(p), True)
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    expect("progress+ stage", data["stage"], "phase1_done")
    expect("progress+ round=1", data["data"]["round"], 1)
    expect("progress+ domain", data["data"]["domain"], "半导体")
    expect("progress+ question", data["data"]["question"], "问题Z")
    expect("progress+ has_wechat_material 初始 False", data["data"]["has_wechat_material"], False)
    expect("progress+ 环境级 E 自动 skip", data["data"]["channels_done"]["E"]["status"], "skip")
    expect("progress+ 环境级 C 自动 skip", data["data"]["channels_done"]["C"]["status"], "skip")
    expect("progress+ 环境级 note 含未配置", "未配置" in data["data"]["channels_done"]["E"]["note"], True)
finally:
    shutil.rmtree(tmp2, ignore_errors=True)


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
