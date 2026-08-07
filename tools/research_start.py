# -*- coding: utf-8 -*-
"""
一键研究启动器（zhihu-ask 项目专用）

把「启动一次知乎问题研究」从手动多步操作压缩为一条命令，并按 SOP 附录 A 的执行级逻辑落地：
  1. 配置校验：question/slug 必填；keywords 不足 N 组时提示补足（对应 A.2 边界）
  2. 初始化研究目录（模板生成 + 索引登记）—— 阶段 0 产出
  3. 公众号检索并落盘素材库 research/<slug>/gathered_wechat.md —— 阶段 1 通道 A
  4. 素材库非空校验：为空时提示补关键词重试（对应 A.2 判断分支）
  5. 输出后续步骤提示（阶段 2-4 的执行上下文）

用法：
    python tools/research_start.py --config tools/start.json

config 文件格式（UTF-8）：
    {
      "question": "问题完整标题",
      "domain": "示例领域",
      "slug": "example-slug",
      "priority": "高",
      "keywords": ["主题词 突破", "主题词 产业化", "主题词 争议"],
      "days": 30,
      "min_keywords": 6
    }

说明：
- keywords 为公众号检索关键词（每组一轮搜索）；days 为时间范围（天），默认 365。
- min_keywords 为关键词下限（默认 6，对应 SOP A.2「关键词≥6组」边界）；不足时提示但不阻塞（可降级以更少关键词继续）。
- 本脚本做「阶段0初始化 + 阶段1通道A」，产出素材库后进入阶段2；不产观点，后续按 docs/SOP.md 附录 A 继续。
"""

import sys
import os
import json
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 阶段执行进度标记（写入 research/<slug>/.progress.json，供后续阶段判断）
PROGRESS_FILE = ".progress.json"


def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if out:
        print(out)
    if r.returncode != 0:
        print("STDERR:", err)
        return False
    return True


def validate_config(cfg, min_kw):
    """对应 SOP A.1/A.2：配置校验与边界条件。返回 (errors, warnings)。"""
    errors = []
    warnings = []
    if not cfg.get("question", "").strip():
        errors.append("question 必填")
    if not cfg.get("slug", "").strip():
        errors.append("slug 必填")
    else:
        import re
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", cfg["slug"].strip().lower()):
            errors.append("slug 须为英文小写短横线")
    kws = cfg.get("keywords") or []
    if not kws:
        warnings.append("未提供 keywords，公众号检索将跳过（仅初始化目录）")
    elif len(kws) < min_kw:
        warnings.append(f"关键词仅 {len(kws)} 组，少于建议下限 {min_kw}；可补充到 {min_kw} 组提升检索覆盖（当前继续，非阻塞）")
    return errors, warnings


def write_progress(slug, stage, data):
    """写阶段进度，供流程闭环判断。"""
    p = os.path.join(ROOT, "research", slug, PROGRESS_FILE)
    d = {"stage": stage, "data": data}
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"WARN: 无法写进度文件 {p}: {e}")


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "--config":
        print("用法: python tools/research_start.py --config <json>")
        sys.exit(1)

    cfg_path = sys.argv[2]
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: 无法读取 config {cfg_path}: {e}")
        sys.exit(1)

    question = cfg.get("question", "").strip()
    slug = (cfg.get("slug") or "").strip().lower()
    domain = cfg.get("domain", "其他")
    priority = cfg.get("priority", "中")
    keywords = cfg.get("keywords") or []
    days = cfg.get("days", 365)
    min_kw = int(cfg.get("min_keywords", 6))

    # A.1 配置校验
    errors, warnings = validate_config(cfg, min_kw)
    if errors:
        print("ERROR: config 校验失败：")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    if warnings:
        print("提示：")
        for w in warnings:
            print(f"  - {w}")

    print("=" * 60)
    print(f"开始研究: {question}")
    print(f"slug: {slug} | 领域: {domain} | 优先级: {priority}")
    print("=" * 60)

    # ---- 阶段 0：初始化研究目录 ----
    print("\n==> [阶段0] 初始化研究目录")
    init_cfg = {"question": question, "domain": domain, "slug": slug, "priority": priority}
    tmp_init = os.path.join(ROOT, "tools", "_start_init.json")
    with open(tmp_init, "w", encoding="utf-8") as f:
        json.dump(init_cfg, f, ensure_ascii=False)
    ok = run([sys.executable, os.path.join(ROOT, "tools", "init_research.py"), "--config", tmp_init])
    if not ok:
        print("提示: 初始化失败（目录可能已存在），继续尝试素材收集。")

    # ---- 阶段 1 通道 A：公众号检索并落盘素材库 ----
    print("\n==> [阶段1/通道A] 公众号检索")
    gathered_path = os.path.join(ROOT, "research", slug, "gathered_wechat.md")
    if keywords:
        kw_path = os.path.join(ROOT, "tools", "_start_keywords.json")
        with open(kw_path, "w", encoding="utf-8") as f:
            json.dump({"queries": keywords, "count": 8}, f, ensure_ascii=False)
        run([sys.executable, os.path.join(ROOT, "tools", "wechat_search.py"),
             "--keywords", kw_path, "--days", str(days), "--output", gathered_path])
    else:
        print("（未提供 keywords，跳过公众号检索）")

    # ---- 素材库非空校验（A.2 判断分支）----
    has_material = os.path.exists(gathered_path) and os.path.getsize(gathered_path) > 0
    if keywords and not has_material:
        print("\n[校验] 素材库为空。可能原因：关键词无命中 / 公众号接口限流。")
        print("  - 建议：补充或更换关键词后重跑；或转 Web 通道（阶段1/通道B）为主。")
    elif keywords and has_material:
        print(f"\n[校验] 素材库非空: {os.path.relpath(gathered_path, ROOT)}，通道A通过。")

    # ---- 记录阶段进度（闭环追溯）----
    write_progress(slug, "phase1_done", {
        "question": question,
        "has_wechat_material": has_material,
        "keyword_count": len(keywords),
    })

    # ---- 后续步骤（阶段2-4 上下文）----
    print("\n==> [阶段2-4] 后续步骤")
    print("  a. 阶段2 多视角收集：主代理按五视角（A公众号/B Web事实/C领域分析/D差异化/E反方）覆盖 plan.md 界定子问题")
    print("  b. 阶段3 交叉验证与量化：数据分级标注 + 至少一项量化测算")
    print("  c. 阶段4 产出 report.md（过 CHECKLIST 数据可靠性自查）")
    print("  d. 沉淀（必做）：有效关键词回填 docs/KEYWORDS.md；写 process_notes.md；回填 plan.md 索引为已完成")
    print(f"  e. 进度已记录于 research/{slug}/{PROGRESS_FILE}，供闭环追溯")

    # 清理临时文件
    for p in (tmp_init, os.path.join(ROOT, "tools", "_start_keywords.json")):
        if os.path.exists(p):
            os.remove(p)

    print("\n完成。阶段0初始化与阶段1通道A已就绪。")


if __name__ == "__main__":
    main()
