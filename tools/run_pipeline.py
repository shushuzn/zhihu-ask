
"""
一键研究流水线驱动（zhihu-ask 项目专用）

把「阶段 0→4」中可由脚本确定的环节串起来，带 checkpoint 与质检门禁，
并明确标出必须由 agent 介入的步骤（Web 检索 / ima E 通道 / 企查查·通达信·智慧芽
C 通道 / arxiv 的 WebFetch 降级流程 / flomo 上传 / AI 封面）。

设计原则：脚本只做确定性动作 + 质检门禁；涉及外网检索与主观写作的步骤交 agent，
由本工具打印可复制的命令清单。每段失败即阻断，不带着错误继续。

用法：
  # 1) 启动一次新研究（阶段 0-1 的初始化 + 公众号 A 通道）
  python tools/run_pipeline.py --config tools/start.json

  # 2) 报告写好后的收尾（结构/质量/去AI腔/国标/违规引用/矛盾/轮次/落报告 八件套门禁 + docx + flomo 格式化 + 全库体检）
  python tools/run_pipeline.py --slug <slug>

  # 3) 一步到位：启动 + 收尾（中间需 agent 自行完成检索与写作）
  python tools/run_pipeline.py --config tools/start.json --slug <slug>
"""

import argparse
import os
import subprocess
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PY = sys.executable


def run(cmd, check=True, label=""):
    print(f"\n─── {label or cmd} ───")
    r = subprocess.run([PY] + cmd, cwd=ROOT)
    if check and r.returncode != 0:
        print(f"[阻断] 步骤失败（退出码 {r.returncode}），请修复后重试。")
        sys.exit(r.returncode)
    return r.returncode


def banner(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def flomo_gate(config):
    """F 通道查重：第一步、阻断门禁。

    必须在任何后续检索/写作之前实际调用 flomo_search.py。
    只有查重执行成功（含“无命中”）才放行；MCP 失败或无关键词直接阻断。
    """
    banner("阶段 0 前置 · F 通道 flomo 查重（阻断）")
    try:
        with open(config, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"[阻断] 无法读取 config 以提取查重关键词：{e}")
        sys.exit(1)
    question = (cfg.get("question") or "").strip()
    keywords = cfg.get("keywords") or []
    if isinstance(keywords, list):
        keywords = " ".join(str(k) for k in keywords if str(k).strip())
    query = question or str(keywords).strip()
    if not query:
        print("[阻断] config 中缺少 question/keywords，无法执行 flomo 查重。")
        sys.exit(1)
    run([os.path.join(TOOLS, "flomo_search.py"), "--keywords", query, "--limit", "10"],
        label="flomo_search（F 通道查重，第一步阻断）")
    print("[通过] flomo 查重已实际执行；查重结论（复用/更新/参考/正常检索，含假阳性甄别）由主代理"
          "人工判读并用 mark_channel 登记通道 F，不做自动登记。")


def bootstrap(config):
    banner("阶段 0-1 · 初始化 + 公众号 A 通道")
    # F 通道查重必须是第一步，且作为阻断门禁：
    # 未实际执行 flomo_search 不得进入后续任何检索/写作。
    flomo_gate(config)
    # 出口探测：提前告知当前环境的外网能力（arxiv 直连 / WebFetch 降级判断依据）
    try:
        subprocess.run([PY, os.path.join(TOOLS, "net_check.py")], cwd=ROOT)
    except Exception as e:
        print(f"[提示] net_check 运行异常：{e}")
    if not os.environ.get("WECHAT_ARTICLE_SEARCH_SCRIPTS"):
        print("[提示] 未设置 WECHAT_ARTICLE_SEARCH_SCRIPTS；通道 A 可能失败。"
              "请指向 wechat-article-search 技能的 scripts 目录后重跑。")
    run([os.path.join(TOOLS, "research_start.py"), "--config", config],
        label="research_start.py")


def agent_checklist(slug, query):
    banner("需 agent 介入的检索与写作步骤（脚本无法自动化）")
    print("请逐项完成，再运行收尾：python tools/run_pipeline.py --slug " + slug)
    print("""
1) 通道 F 查重：已由启动阶段 flomo_gate 实际执行并阻断校验；
   查重结论由主代理人工判读（relevance ≥0.9 复用/更新、0.5~0.9 参考、<0.5 正常检索；
   命中但判定不相关的假阳性按 <0.5 处理），然后用
   `python tools/mark_channel.py --slug <slug> --channel F --status done --note "memo_search 已执行：命中 N 条；判读结论…"`
   登记通道 F（note 须含 memo_search 证据，供 report_channels 门禁）
2) 通道 E（ima）：连接器已连接时两级检索并落盘 gathered_ima.md
3) 通道 B（Web）：web_search / web_fetch 拿官方数据、研报、新闻
4) 通道 C 必做：企查查 get_company_by_query / 通达信 tdx_lookup_stock /
                 智慧芽 patsnap_search（专利+论文各一次）
5) 通道 P（学术预印本聚合，arxiv 已归入本通道，统一入口一条命令）：
      python tools/preprint_search.py --platform all --keywords "<主题词>" --days 30 \
          --count 5 --out research/<slug> --slug <slug>
   （arxiv → gathered_arxiv.md、bioRxiv/浪淘沙/PSSXiv → gathered_preprints.md，
     检索完成后一次性自动登记通道 P；若 arxiv 直连被 429 限流需 WebFetch 降级，
     单独走 tools/arxiv_search.py --query "<query>" --print-web-prompt 路径，落盘后同样登记通道 P）
6) 阶段 2-3：五视角收集 + 约 3 项量化测算，写入 report.md
7) 登记各通道完成态（落报告纪律条目级）：
     通道 A（--output 落盘 gathered_wechat.md）与通道 P（--out 落盘 gathered_arxiv.md /
     gathered_preprints.md）写盘时**自动登记**，无需手动；
     其余 F/E/B/C 须手动登记：
      python tools/mark_channel.py --slug <slug> --channel <F|E|B|C> --status <done|empty|skip> [--note ...]
   收尾门禁 check_progress --require report_channels 据此对六通道做「声明态 ⊕ 证据」双向交叉校验。
""".replace("<slug>", slug).replace("<query>", query or ""))


def finish(slug, offline=False):
    banner(f"阶段 4 收尾 · slug={slug}")
    # 收尾前自动清理工作区缓存/临时文件
    run([os.path.join(TOOLS, "clean_workspace.py")],
        label="clean_workspace")
    # 质检八件套（门禁）
    run([os.path.join(TOOLS, "check_report_structure.py"), "--slug", slug],
        label="check_report_structure")
    run([os.path.join(TOOLS, "quality_check.py"), "--slug", slug],
        label="quality_check")
    # 去 AI 腔门禁：硬伤与提示级命中均阻断（工具默认严格阻断）。
    run([os.path.join(TOOLS, "check_ai_voice.py"), "--slug", slug],
        label="check_ai_voice")
    # 参考文献国标门禁：GB/T 7714-2015 著录合规，
    # 硬伤与提示级命中均阻断（工具默认严格阻断）。正文无 [n] 引注时自动按参考来源清单模式跳过引注对应检查。
    run([os.path.join(TOOLS, "check_gbt_refs.py"), "--slug", slug],
        label="check_gbt_refs")
    # 违规引用门禁（学术纪律）：编造作者/题名不符/URL 伪造/佚名误用/
    # 引用日期早于发布/死链——硬伤与提示级命中均阻断（工具默认严格阻断）。
    citation_cmd = [os.path.join(TOOLS, "check_citation_validity.py"), "--slug", slug]
    if offline:
        citation_cmd.append("--offline")
    run(citation_cmd, label="check_citation_validity" + (" (offline)" if offline else ""))
    # 矛盾与废话门禁：硬伤与提示级命中均阻断（工具默认严格阻断）。
    # check_consistency 是项目级检查，不接受 --slug。
    run([os.path.join(TOOLS, "check_consistency.py")],
        label="check_consistency")
    run([os.path.join(TOOLS, "check_progress.py"), "--slug", slug, "--require_round", "auto"],
        label="check_progress auto")
    # 落报告纪律门禁：已执行通道的素材必须落到 report.md 正文，
    # 否则视为交付未完成、阻断收尾（通道执行过≠交付完成）。
    run([os.path.join(TOOLS, "check_progress.py"), "--slug", slug, "--require", "report_channels"],
        label="check_progress report_channels")

    # 产出
    run([os.path.join(TOOLS, "report_to_docx.py"), "--slug", slug],
        label="report_to_docx")
    run([os.path.join(TOOLS, "report_to_flomo.py"), "--slug", slug,
         "--out", "flomo_full.md"],
        label="report_to_flomo (格式化，未上传)")

    # 发布前全库体检（信息性，不阻断；当前 slug 的硬门禁已在上方八件套完成）
    # 使用 --quick 跳过重复的工具自测/项目自检，只输出后续提示。
    print("\n─── check_all（全库体检，信息性） ───")
    try:
        subprocess.run([PY, os.path.join(TOOLS, "check_all.py"), "--quick"], cwd=ROOT)
    except Exception as e:
        print(f"[提示] check_all 运行异常：{e}")

    # 沉淀自动化：门禁全过后回填本地 plan.md 索引状态「进行中 → 已完成」（幂等）
    try:
        if mark_plan_done(slug):
            print(f"[回填] plan.md 索引：{slug} → 已完成")
    except Exception as e:
        print(f"[提示] plan.md 回填失败（不影响交付）: {e}")

    banner("agent 待办（收尾人工步骤）")
    print(f"""
- flomo 笔记上传：python tools/note_upload.py research/{slug}/notes/ 逐条质检后上传（索引/报告禁止上传）；
  report_to_flomo.py 已生成本地存档 research/{slug}/flomo_full.md（仅存档，不上传）。
- AI 封面图：配置 AGNES_API_KEY 后
  python tools/report_images.py --slug {slug}
  （当前缺 key 可加 --skip-ai 仅生成数据图表）
- 全库体检（check_all）已在上方自动跑过；如需单独复跑：
  python tools/check_all.py
""")


def mark_plan_done(slug, plan_path=None):
    """回填本地 plan.md 问题索引：<slug> 行状态 进行中/规划中 → 已完成（幂等）。

    plan.md 为本地文件（gitignore，不入库）；行缺失或已为「已完成」时不做改动。
    返回 True 表示有行被更新。
    """
    import re as _re
    plan_path = plan_path or os.path.join(ROOT, "plan.md")
    if not os.path.isfile(plan_path):
        return False
    try:
        with open(plan_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return False
    changed = False
    for i, line in enumerate(lines):
        if f"| {slug} |" in line and "已完成" not in line:
            new_line = _re.sub(r"\| (进行中|规划中) \|\s*$", "| 已完成 |", line)
            if new_line != line:
                lines[i] = new_line
                changed = True
    if changed:
        try:
            with open(plan_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except OSError:
            return False
    return changed


def main():
    ap = argparse.ArgumentParser(description="一键研究流水线驱动")
    ap.add_argument("--config", help="research_start 用的配置 JSON（启动新研究）")
    ap.add_argument("--slug", help="研究报告 slug（收尾用）")
    ap.add_argument("--query", help="arxiv 检索词（仅用于打印提示，可选）")
    ap.add_argument("--offline", action="store_true",
                    help="违规引用检查使用离线模式（跳过 CrossRef/arXiv 联网核验）")
    args = ap.parse_args()

    if not args.config and not args.slug:
        print("ERROR: 需 --config（启动）或 --slug（收尾）至少其一")
        sys.exit(1)

    if args.config:
        bootstrap(args.config)
        # 尝试从 config 取 slug/query 供提示
        slug, query = args.slug, args.query
        if not slug and args.config and os.path.isfile(args.config):
            try:
                import json
                cfg = json.load(open(args.config, encoding="utf-8"))
                slug = slug or cfg.get("slug")
                query = query or cfg.get("question") or cfg.get("keywords", [""])[0]
            except Exception:
                pass
        if slug:
            agent_checklist(slug, query)
        else:
            print("[提示] 未解析到 slug，无法打印 agent 步骤清单；请手动按 SOP 继续。")
        # 若已同时给了 --slug，直接收尾
        if args.slug:
            finish(args.slug, offline=args.offline)
        return

    # 仅收尾
    finish(args.slug, offline=args.offline)


if __name__ == "__main__":
    main()
