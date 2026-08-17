
"""
研究初始化脚本（zhihu-ask 项目专用）

一键创建新的研究目录：
1. 在 research/<slug>/ 下生成 3 个文件（plan/report/process_notes），从模板复制并填入基础占位符
   （含元信息行的领域与 slug——report_to_flomo.py 依赖该行解析 flomo 标签）。
2. 落盘 .progress.json（stage=phase1_done, round=1, domain），供 check_progress.py 校验。
3. 更新 plan.md 的问题索引表（追加一行，状态=进行中）。

用法（Windows PowerShell 下中文必须走 --config 文件，见 docs/CONVENTIONS.md）：

    # 方式一：config 文件（推荐，规避中文乱码；示例格式见 tools/init.example.json）
    python tools/init_research.py --config tools/init.json

    # 方式二：直接传参（非 Windows 或参数无中文时）
    python tools/init_research.py --question "问题标题" --domain "示例领域" --slug example-slug

config 文件格式（UTF-8）：
    {
      "question": "问题完整标题",
      "domain": "示例领域",
      "slug": "example-slug",
      "priority": "中"
    }
"""

import sys
import os
import re
import json
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import channel_state as cs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")
RESEARCH = os.path.join(ROOT, "research")
PLAN = os.path.join(ROOT, "plan.md")
PROGRESS_FILE = ".progress.json"

FILES = [
    ("research_plan_TEMPLATE.md", "plan.md"),
    ("research_report_TEMPLATE.md", "report.md"),
    ("process_notes_TEMPLATE.md", "process_notes.md"),
]

# 模块化笔记目录结构 (扁平化, 标签区分类型)
NOTE_DIR = "notes"  # 所有笔记统一放 notes/ 目录
NOTE_TEMPLATE = "note_TEMPLATE.md"  # 统一模板

def parse_args(argv):
    args = {"config": None, "question": None, "domain": "其他", "slug": None, "priority": "中",
            "domain_type": ""}
    i = 0
    while i < len(argv):
        if argv[i] == "--config" and i + 1 < len(argv):
            args["config"] = argv[i + 1]
            i += 2
        elif argv[i] == "--question" and i + 1 < len(argv):
            args["question"] = argv[i + 1]
            i += 2
        elif argv[i] == "--domain" and i + 1 < len(argv):
            args["domain"] = argv[i + 1]
            i += 2
        elif argv[i] == "--slug" and i + 1 < len(argv):
            args["slug"] = argv[i + 1]
            i += 2
        elif argv[i] == "--priority" and i + 1 < len(argv):
            args["priority"] = argv[i + 1]
            i += 2
        elif argv[i] == "--domain-type" and i + 1 < len(argv):
            args["domain_type"] = argv[i + 1]
            i += 2
        else:
            i += 1
    return args

def slug_ok(slug):
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug or ""))

def load_config(args):
    if args["config"]:
        with open(args["config"], "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg
    if not args["question"]:
        print("ERROR: 需要 --question 或 --config")
        sys.exit(1)
    return {
        "question": args["question"],
        "domain": args["domain"],
        "slug": args["slug"],
        "priority": args["priority"],
        "domain_type": args["domain_type"],
    }

def apply_replacements(content, question, domain, slug, today, is_plan=False, domain_type=""):
    """纯函数：模板内容占位符替换（不涉及文件 IO）。

    is_plan=True 时额外填充 plan 专属占位符。行为与旧 fill_template 一致——
    plan 模板才替换「{{进行中 / 已完成}} / {{...}} / {{topic-slug}}」。
    domain_type：领域类型（学术科研/科技产业/财经时政），
    填充 plan 模板的「{{领域档位}}」占位符；未指定则保持原样。
    """
    replacements = {
        "{{知乎问题完整标题}}": question,
        "{{YYYY-MM-DD}}": today,
    }

    if is_plan:
        replacements["{{进行中 / 已完成}}"] = "进行中"

        # 元信息行占位符（模板第 3 行）必须实填：report_to_flomo.py 从此行正则解析
        # 领域来决定 flomo 标签，残留 {{...}} 会导致标签兜底为 #{{...}} #综合。
        # 这两个占位符在模板中各仅出现 1 次（均在元信息行），全局替换安全。
        replacements["{{...}}"] = domain
        replacements["{{topic-slug}}"] = slug
        if domain_type:
            replacements["{{领域档位}}"] = domain_type
    for k, v in replacements.items():
        content = content.replace(k, v)
    return content

def fill_template(tpl_path, question, domain, slug, today, domain_type=""):
    with open(tpl_path, "r", encoding="utf-8") as f:
        content = f.read()
    is_plan = os.path.basename(tpl_path) == "research_plan_TEMPLATE.md"
    return apply_replacements(content, question, domain, slug, today, is_plan, domain_type)

def write_initial_progress(target_dir, question, domain):
    """落盘初始 .progress.json。

    check_progress.py 依赖 data.round（--require_round auto）与 data.domain
    （领域最低轮次判定）。此前仅 research_start.py 写该文件，单独走
    init_research.py 起研究时 check_progress 会报「未找到进度文件」而阻塞，
    需手工补造——故在初始化阶段即落盘，保证任一入口都自洽。
    """
    p = os.path.join(target_dir, PROGRESS_FILE)
    payload = {
        "stage": "phase1_done",
        "data": {
            "question": question,
            "domain": domain,
            "round": 1,
            "has_wechat_material": False,
            "keyword_count": 0,
            # 环境级未配置连接器的通道自动登记 skip（ima E / 领域连接器 C 默认未配置），
            # 跨研究共享，无需逐篇手动检查；连接器接入后设 ZHIHU_ASK_UNCONFIGURED_CHANNELS 调整。
            "channels_done": {ch: cs.env_skip_entry(ch) for ch in cs.env_unconfigured_channels()},
        },
    }
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[警告] 无法写进度文件 {p}: {e}")


def insert_index_row(content, domain, slug, today):
    """纯函数：在 plan.md 内容的问题索引表小节插入一行。

    返回 (new_content, ok)：找不到索引表 / 表头不含 topic_slug / 缺分隔行时
    ok=False 且内容不变（与旧 append_to_index 的失败语义一致）。
    """
    header_m = re.search(r"^## 三、问题索引表\s*\n", content, re.MULTILINE)
    if not header_m:
        return content, False
    section_end = content.find("\n## ", header_m.end())
    if section_end == -1:
        section_end = len(content)
    section = content[header_m.end():section_end]

    m = re.search(r"^\|.*topic_slug.*\|\s*\n(\s*\|[-:\s|]+\|\s*)\n", section, re.MULTILINE)
    if not m:
        return content, False

    row = f"| {today} | {domain} | {slug} | 进行中 |"
    insert_offset = header_m.end() + m.end()
    new_content = content[:insert_offset] + row + "\n" + content[insert_offset:]
    return new_content, True

def append_to_index(domain, slug, today):
    """在 plan.md「问题索引表」小节插入一行；找不到则提示手动添加。"""
    if not os.path.exists(PLAN):
        return False
    with open(PLAN, "r", encoding="utf-8") as f:
        content = f.read()

    new_content, ok = insert_index_row(content, domain, slug, today)
    if not ok:
        return False

    with open(PLAN, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True

def main():
    args = parse_args(sys.argv[1:])
    cfg = load_config(args)

    question = cfg.get("question", "").strip()
    domain = cfg.get("domain", "其他").strip()
    slug = (cfg.get("slug") or "").strip().lower()
    priority = cfg.get("priority", "中")
    domain_type = (cfg.get("domain_type") or "").strip()
    today = date.today().isoformat()

    if domain == "其他":
        print("[警告] 未传 --domain（如 --domain \"产业经济 / 制造业\"），plan 索引领域将为「其他」。"
              "初始化时请显式传领域，避免后续手动修正索引（纪律）。")

    if not question:
        print("ERROR: 缺少 question")
        sys.exit(1)
    if not slug:
        print("ERROR: 缺少 slug（英文小写短横线，如 example-slug）")
        sys.exit(1)
    if not slug_ok(slug):
        print("ERROR: slug 格式非法，须为英文小写短横线（如 example-slug）")
        sys.exit(1)

    target_dir = os.path.join(RESEARCH, slug)
    if os.path.exists(target_dir):
        print(f"ERROR: 目录已存在: {target_dir}")
        sys.exit(1)

    os.makedirs(target_dir)

    # 创建模块化笔记目录
    os.makedirs(os.path.join(target_dir, NOTE_DIR), exist_ok=True)
    print(f"已创建模块化笔记目录: notes/")

    # 初始化笔记模板
    tpl_path = os.path.join(TEMPLATES, NOTE_TEMPLATE)
    if os.path.exists(tpl_path):
        with open(tpl_path, "r", encoding="utf-8") as f:
            tpl_content = f.read()
        # 统一替换三种 slug 占位符写法（topic-slug/topic_slug/slug），
        # 避免模板与生成器不一致导致 _TEMPLATE.md 残留未替换占位符。
        tpl_content = tpl_content.replace("{{topic-slug}}", slug)
        tpl_content = tpl_content.replace("{{topic_slug}}", slug)
        tpl_content = tpl_content.replace("{{slug}}", slug)
        tpl_content = tpl_content.replace("{{YYYY-MM-DD}}", today)
        dst = os.path.join(target_dir, NOTE_DIR, "_TEMPLATE.md")
        with open(dst, "w", encoding="utf-8") as f:
            f.write(tpl_content)
    print("已初始化笔记模板: notes/_TEMPLATE.md")

    for tpl, name in FILES:
        src = os.path.join(TEMPLATES, tpl)
        dst = os.path.join(target_dir, name)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(fill_template(src, question, domain, slug, today, domain_type))
        print(f"已生成: {os.path.relpath(dst, ROOT)}")

    write_initial_progress(target_dir, question, domain)
    print(f"已生成: {os.path.relpath(os.path.join(target_dir, PROGRESS_FILE), ROOT)}（round=1）")

    if append_to_index(domain, slug, today):
        print(f"已登记索引: {slug}（状态=进行中，优先级={priority}）")
    else:
        print("提示: 未能自动更新 plan.md 索引表，请手动添加一行。")

    print("\n下一步：")
    print("  1. 按 skills/zhihu-ask-research/SKILL.md 阶段 0-4 执行检索")
    print("  2. 检索产出写入 gathered_*.md，模块化笔记写入 notes/（扁平目录，来源用 GB/T 7714-2015）")
    print("  3. 写 notes/00_index.md 索引，串联各模块化笔记")
    print("  4. 组装/撰写 report.md，跑质检与收尾")
    print("  5. 完成后回填 plan.md 索引状态为「已完成」")
    print("\n完成后请删除临时 config 文件（本机中文参数必须文件传参，见 docs/CONVENTIONS.md）。")

if __name__ == "__main__":
    main()
