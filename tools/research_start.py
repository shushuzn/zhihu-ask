
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

config 文件格式（UTF-8，示例见 tools/start.example.json）：
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
- min_keywords 为关键词下限（默认 6，对应 SKILL.md 阶段0「关键词≥6组」边界）；不足时提示但不阻塞（可降级以更少关键词继续）。
- 本脚本做「阶段0初始化 + 阶段1通道A」，产出素材库后进入阶段2；不产观点，后续按 skills/zhihu-ask-research/SKILL.md 阶段 2 继续。
"""

import sys
import os
import json
import subprocess

try:
    from tools.console_encoding import setup as _ce
    _ce()
except Exception:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import channel_state as cs

try:
    from tools.run_util import ROOT  # 统一路径入口
except ModuleNotFoundError:
    from run_util import ROOT  # 被测导入时 tools 不在包路径

PROGRESS_FILE = ".progress.json"

def run(cmd):
    """捕获模式执行子命令（与 check_all 的 run 同形：返回 bool 成功标志）。

    注意：调用方已传 `[sys.executable, 子脚本, ...]`，run_util.capture 内部会再
    前置 PY，故此处不走 run_util 封装，直接 `subprocess` 捕获（避免双重 `[PY, [PY, ...]]`）。
    """
    import subprocess

    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001 - 兜底：缺口径时启动仍可继续
        print(f"STDERR: {e}")
        return False
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if out:
        print(out)
    if r.returncode != 0:
        # 测试与线上均以 "STDERR:" 为锚点判定子进程失败原因
        print(f"STDERR: {err}" if err else f"STDERR: exit {r.returncode}")
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
    """写阶段进度，供流程闭环判断。

    与已有进度文件合并而非覆盖：init_research.py 已落盘 round=1 等字段，
    直接覆盖会丢失 round，导致 check_progress --require_round auto 读到 0
    而必然阻塞（标准流程走不通）。此处保留已有键，仅更新本次产出的字段。
    并发安全：与 channel_state.mark 共用 file_lock（search_all 并行子进程
    与启动流程可能同时写同一进度文件），写盘用原子替换。
    """
    p = os.path.join(ROOT, "research", slug, PROGRESS_FILE)
    with cs.file_lock(p):
        old = {}
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    old = json.load(f)
            except (OSError, ValueError):
                old = {}
        merged = dict(old.get("data") or {})
        merged.update(data)
        merged.setdefault("round", 1)
        # 环境级未配置连接器的通道（ima E / 领域连接器 C 默认未配置）自动登记 skip，
        # 跨研究共享、无需逐篇手动检查；连接器接入后设 ZHIHU_ASK_UNCONFIGURED_CHANNELS 调整。
        cd = merged.get("channels_done") or {}
        if not isinstance(cd, dict):
            cd = {}
        for ch in cs.env_unconfigured_channels():
            cd.setdefault(ch, cs.env_skip_entry(ch))
        merged["channels_done"] = cd
        d = {"stage": stage, "data": merged}
        try:
            cs.save(p, d)
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
    days = cfg.get("days", 365)
    min_kw = int(cfg.get("min_keywords", 6))

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

    # 领域类型判定与通道优先级计划（领域矩阵工具化）
    # config 可显式指定 domain_type（学术科研/科技产业/财经时政）覆盖自动判定
    try:
        import channel_state as _cs
        dtype = cfg.get("domain_type") or _cs.classify_domain(domain)
        if dtype not in _cs.DOMAIN_TYPES:
            dtype = _cs.classify_domain(domain)
        plan = _cs.channel_plan(dtype)
        print(f"\n==> [领域判定] {dtype}{'（config 显式指定）' if cfg.get('domain_type') else '（关键词自动判定）'}")
        pri_str = "  ".join(f"{ch}[{p}]" for ch, p, _ in plan)
        print(f"  通道计划: {pri_str}")
        for ch, p, name in plan:
            action = "必须执行（P0）" if p == "P0" else ("应执行（P1）" if p == "P1" else "可选/记 skip（P2）")
            print(f"    {ch} {name}: {action}")
    except Exception as e:
        print(f"  [提示] 领域判定失败（{e}），按默认计划执行。")
    print("=" * 60)

    print("\n==> [阶段0] 初始化研究目录")
    init_cfg = {"question": question, "domain": domain, "slug": slug, "priority": priority}
    try:
        import channel_state as _cs
        init_cfg["domain_type"] = cfg.get("domain_type") or _cs.classify_domain(domain)
    except Exception:
        pass
    tmp_init = os.path.join(ROOT, "tools", "_start_init.json")
    with open(tmp_init, "w", encoding="utf-8") as f:
        json.dump(init_cfg, f, ensure_ascii=False)
    ok = run([sys.executable, os.path.join(ROOT, "tools", "init_research.py"), "--config", tmp_init])
    if not ok:
        print("提示: 初始化失败（目录可能已存在），继续尝试素材收集。")

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

    has_material = os.path.exists(gathered_path) and os.path.getsize(gathered_path) > 0
    if keywords and not has_material:
        print("\n[校验] 公众号素材库为空。可能原因：关键词无命中 / 公众号接口限流。")
        print("  - 建议：补充或更换关键词后重跑；或转 Web 通道（阶段1/通道B）为主。")
    elif keywords and has_material:
        print(f"\n[校验] 公众号素材库非空: {os.path.relpath(gathered_path, ROOT)}，通道A通过。")

    write_progress(slug, "phase1_done", {
        "question": question,
        "domain": domain,
        "has_wechat_material": has_material,
        "keyword_count": len(keywords),
    })

    print("\n==> [阶段1 待办] 其余通道（执行顺序 E → A → B → C → P；全部完成后才可写报告）")
    print("  0. 通道 E（ima，执行顺序第一）：主代理直执连接器工具——search_knowledge_base 定位库")
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
    print("  1. 通道 A（公众号，按领域优先级）：tools/wechat_search.py 检索，落盘 gathered_wechat.md")
    print("  2. 通道 B（Web，P0 通用）：官方数据/研报/新闻，落盘 gathered_web.md")
    print("  3. 通道 C（领域数据源，按领域优先级）：finance 插件 / 通达信 / 企查查 / 智慧芽；不适用则记录")
    print("  4. 通道 P（学术预印本聚合，arxiv 已归入本通道）：tools/preprint_search.py --platform all")
    print("     --keywords \"<主题词>\" --days 30 --count 5 --out research/<slug> --slug <slug>")
    print("     ——arxiv→gathered_arxiv.md + bioRxiv/浪淘沙/PSSXiv→gathered_preprints.md，一次性登记通道 P")
    print("  ⚠️ 红线：E/A/B/C/P 全部通道执行完毕（命中或记录无素材/不适用/跳过）后才可进入阶段 2 写报告；")
    print("     禁止只做部分通道即产出 report.md。通道执行清单（各通道命中数/状态）须写入 plan.md。")
    print("\n==> [阶段2-4] 后续步骤")
    print("  a. 阶段2 多视角收集：主代理按五视角（A公众号/B Web事实/C领域分析/D差异化/E反方）覆盖 plan.md 界定子问题")
    print("  b. 阶段3 交叉验证：来源类型标注（笔记内）；小点叙述化不单行、小节数量不设上限")
    print("  c. 阶段4 产出 report.md（适用通道全部完成后再写）")
    print("  d. 沉淀（必做）：有效关键词写入 SQLite 关键词库（tools/keywords_db.py --add），再 --export 同步 docs/KEYWORDS.md；写 process_notes.md；回填 plan.md 索引为已完成")
    print(f"  e. 进度已记录于 research/{slug}/{PROGRESS_FILE}，供闭环追溯")

    for p in (tmp_init,
              os.path.join(ROOT, "tools", "_start_keywords.json")):
        if os.path.exists(p):
            os.remove(p)

    print("\n完成。阶段0初始化与阶段1（通道A）已就绪。")

if __name__ == "__main__":
    main()
