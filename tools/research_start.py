# -*- coding: utf-8 -*-
"""
一键研究启动器（zhihu-ask 项目专用）

把「启动一次知乎问题研究」从手动多步操作压缩为一条命令，并按 SOP 附录 A 的执行级逻辑落地：
  1. 配置校验：question/slug 必填；keywords 不足 N 组时提示补足（对应 A.2 边界）
  2. 初始化研究目录（模板生成 + 索引登记）—— 阶段 0 产出
  3. 公众号检索并落盘素材库 research/<slug>/gathered_wechat.md —— 阶段 1 通道 A
  4. 知乎官方检索并落盘素材库 research/<slug>/gathered_zhihu.md —— 阶段 1 通道 Z（可选，需已认证）
  5. 素材库非空校验：为空时提示补关键词重试（对应 A.2 判断分支）
  6. 输出后续步骤提示（阶段 2-4 的执行上下文）

用法：
    python tools/research_start.py --config tools/start.json

config 文件格式（UTF-8，示例见 tools/start.example.json）：
    {
      "question": "问题完整标题",
      "domain": "示例领域",
      "slug": "example-slug",
      "priority": "高",
      "keywords": ["主题词 突破", "主题词 产业化", "主题词 争议"],
      "zhihu_keywords": ["主题词 高赞", "主题词 争议"],   // 可选，通道 Z 检索词
      "zhihu_mode": "zhihu",                             // 可选: zhihu|global|both
      "days": 30,
      "min_keywords": 6
    }

说明：
- keywords 为公众号检索关键词（每组一轮搜索）；days 为时间范围（天），默认 365。
- zhihu_keywords 为知乎官方检索关键词（可选）。通道 Z 需要 zhihu-cli 已安装且 Access Secret 已配置；未配置时自动跳过并提示，不阻塞其余通道。
- zhihu_mode 决定通道 Z 检索方式：zhihu（知乎站内，默认）/ global（知乎全网搜索）/ both（两者都跑，分别落盘 gathered_zhihu.md 与 gathered_zhihu_global.md）。
- min_keywords 为关键词下限（默认 6，对应 SOP A.2「关键词≥6组」边界）；不足时提示但不阻塞（可降级以更少关键词继续）。
- 本脚本做「阶段0初始化 + 阶段1通道A + 阶段1通道Z」，产出素材库后进入阶段2；不产观点，后续按 docs/SOP.md 附录 A 继续。
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


def get_ima_library_hints(domain):
    """按领域从 docs/IMA_LIBRARIES.md 匹配订阅库候选，供通道 E2 提示。

    解析「### 组名」及其后的库名表格行；匹配规则为词元双向包含：
    组名与 domain 各自按分隔符拆成词元（如「金融 / 投研 / 宏观」→ 金融/投研/宏观），
    domain 词元与组名词元任一互相包含（如 domain「金融投资」命中「金融」）即算匹配。
    返回 [(组名, [库名, ...]), ...]，最多 2 组，不匹配返回 []。
    """
    lib_path = os.path.join(ROOT, "docs", "IMA_LIBRARIES.md")
    if not os.path.isfile(lib_path):
        return []
    import re as _re
    domain = (domain or "").strip()
    if not domain:
        return []
    d_tokens = [t for t in _re.split(r"[/、,，\s]+", domain) if t]
    groups = []
    cur_group = None
    with open(lib_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("### "):
                cur_group = s[4:].strip()
                groups.append([cur_group, []])
            elif s.startswith("|") and cur_group is not None and not s.startswith("|---"):
                # 表格行取第一列（库名）
                cells = [c.strip() for c in s.strip("|").split("|")]
                if cells and cells[0] and cells[0] != "库名":
                    groups[-1][1].append(cells[0])
    hits = []
    for gname, libs in groups:
        g_tokens = [t for t in _re.split(r"[/、,，\s]+", gname) if t]
        if any(dt in gt or gt in dt for dt in d_tokens for gt in g_tokens):
            hits.append((gname, libs))
    return hits[:2]


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
    zhihu_keywords = cfg.get("zhihu_keywords") or []
    zhihu_mode = (cfg.get("zhihu_mode") or "zhihu").strip().lower()
    if zhihu_mode not in ("zhihu", "global", "both"):
        print("ERROR: zhihu_mode 只支持 zhihu/global/both")
        sys.exit(1)
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

    # ---- 阶段 1 通道 Z：知乎官方检索并落盘素材库（可选）----
    print("\n==> [阶段1/通道Z] 知乎官方检索")
    zhihu_path = os.path.join(ROOT, "research", slug, "gathered_zhihu.md")
    if zhihu_keywords:
        modes = ["zhihu", "global"] if zhihu_mode == "both" else [zhihu_mode]
        for zmode in modes:
            zout = os.path.join(ROOT, "research", slug,
                                "gathered_zhihu.md" if zmode == "zhihu" else "gathered_zhihu_global.md")
            zcfg_path = os.path.join(ROOT, "tools", "_start_zhihu.json")
            with open(zcfg_path, "w", encoding="utf-8") as f:
                json.dump({
                    "mode": zmode,
                    "queries": zhihu_keywords,
                    "count": 10,
                    "output": zout,
                }, f, ensure_ascii=False)
            ok_z = run([sys.executable, os.path.join(ROOT, "tools", "zhihu_search.py"),
                        "--config", zcfg_path])
            if not ok_z:
                print("  - 通道Z检索未完成（常见：Access Secret 未配置 / 配额限制）。")
                print("    未配置时请执行: zhihu-cli auth set --secret-stdin（见 docs/CONVENTIONS.md 第6节）")
                print("    该通道跳过，不阻塞其余通道。")
    else:
        print("（未提供 zhihu_keywords，跳过知乎检索）")

    # ---- 素材库非空校验（A.2 判断分支）----
    has_material = os.path.exists(gathered_path) and os.path.getsize(gathered_path) > 0
    if keywords and not has_material:
        print("\n[校验] 公众号素材库为空。可能原因：关键词无命中 / 公众号接口限流。")
        print("  - 建议：补充或更换关键词后重跑；或转 Web 通道（阶段1/通道B）为主。")
    elif keywords and has_material:
        print(f"\n[校验] 公众号素材库非空: {os.path.relpath(gathered_path, ROOT)}，通道A通过。")
    has_zhihu_material = os.path.exists(zhihu_path) and os.path.getsize(zhihu_path) > 0
    zhihu_global_path = os.path.join(ROOT, "research", slug, "gathered_zhihu_global.md")
    has_zhihu_global_material = os.path.exists(zhihu_global_path) and os.path.getsize(zhihu_global_path) > 0
    if zhihu_keywords and has_zhihu_material:
        print(f"[校验] 知乎素材库非空: {os.path.relpath(zhihu_path, ROOT)}，通道Z通过。")
    if zhihu_keywords and zhihu_mode in ("global", "both") and has_zhihu_global_material:
        print(f"[校验] 知乎全网素材库非空: {os.path.relpath(zhihu_global_path, ROOT)}，通道Z(global)通过。")

    # ---- 记录阶段进度（闭环追溯）----
    write_progress(slug, "phase1_done", {
        "question": question,
        "domain": domain,
        "has_wechat_material": has_material,
        "keyword_count": len(keywords),
        "has_zhihu_material": has_zhihu_material,
        "has_zhihu_global_material": has_zhihu_global_material,
        "zhihu_keyword_count": len(zhihu_keywords),
        "zhihu_mode": zhihu_mode,
    })

    # ---- 后续步骤（阶段2-4 上下文）----
    print("\n==> [阶段1 待办] 其余通道（执行顺序 F查重 → E→B→C）")
    print("  0. flomo 已有报告查重（执行顺序最先）：用问题主题词调 flomo MCP memo_search，")
    print("     查是否已有本主题报告——relevance ≥0.9 复用/更新不重复研究；0.5-0.9 参考素材；<0.5 正常研究")
    print("     前置：flomo MCP 已配置（~/.workbuddy/mcp.json）；未配置则跳过不阻塞")
    print("  1. 通道 E（ima，执行顺序第一）：主代理直执连接器工具——search_knowledge_base 定位库")
    print("     + search_knowledge 库内检索（E1 经验 + E2 订阅库素材，落盘 gathered_ima.md），")
    print("     候选库见 docs/IMA_LIBRARIES.md；连接器未连接则跳过")
    lib_hints = get_ima_library_hints(domain)
    if lib_hints:
        for gname, libs in lib_hints:
            shown = libs[:8]
            tail = "…" if len(libs) > 8 else ""
            print(f"     [{gname}] 候选库（{len(libs)} 个）: {'、'.join(shown)}{tail}")
    else:
        print(f"     （未在 docs/IMA_LIBRARIES.md 匹配到领域「{domain}」的订阅库分组，检索时人工选库）")
    print("  2. 通道 B（Web）：官方数据/研报/新闻，落盘 gathered_web.md")
    print("  3. 通道 C（领域数据源，按需）：finance 插件 / 通达信 / 企查查")
    print("\n==> [阶段2-4] 后续步骤")
    print("  a. 阶段2 多视角收集：主代理按五视角（A公众号/B Web事实/C领域分析/D差异化/E反方）覆盖 plan.md 界定子问题")
    print("  b. 阶段3 交叉验证与量化：数据分级标注 + 至少一项量化测算")
    print("  c. 阶段4 产出 report.md（过 CHECKLIST 数据可靠性自查）")
    print("  d. 沉淀（必做）：有效关键词回填 docs/KEYWORDS.md；写 process_notes.md；回填 plan.md 索引为已完成")
    print(f"  e. 进度已记录于 research/{slug}/{PROGRESS_FILE}，供闭环追溯")

    # 清理临时文件
    for p in (tmp_init,
              os.path.join(ROOT, "tools", "_start_keywords.json"),
              os.path.join(ROOT, "tools", "_start_zhihu.json")):
        if os.path.exists(p):
            os.remove(p)

    print("\n完成。阶段0初始化与阶段1（通道A/通道Z）已就绪。")


if __name__ == "__main__":
    main()
