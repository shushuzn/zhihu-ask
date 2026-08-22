# -*- coding: utf-8 -*-
"""统一并行检索入口（zhihu-ask 项目专用）

按领域优先级并行执行多通道检索（B Web / A 公众号 / P 预印本），各自落盘
research/<slug>/gathered_*.md 并自动登记通道（A/B/P 落盘即自动登记；
E/C 未配置为环境级 skip）。

用法：
  python tools/search_all.py --config tools/start.json
  python tools/search_all.py --slug <slug> --keywords "kw1" "kw2" ... [--days 365]
  python tools/search_all.py --slug <slug> --parallel 2 --skip-preprints

并行：
  - B 查询级并行：--parallel N（默认 4，web_search.py 多查询并行）
  - 通道级并行：B/A/P 三个子进程同时跑（ThreadPoolExecutor）

退出码：0=全部通道执行完（零命中属正常，自动登记 empty）；1=某通道子进程崩溃。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

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
    from tools.run_util import ROOT, TOOLS
except ModuleNotFoundError:
    from run_util import ROOT, TOOLS  # 被测导入时 tools 不在包路径
PY = sys.executable
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_internal_search(slug, keywords, max_results=5):
    """内部搜索：rag，返回命中数和关键词列表。

    返回 dict: {
        "rag_hits": int,
        "total": int,
        "keywords": list,
    }
    """
    result = {"rag_hits": 0, "total": 0, "keywords": list(keywords)}

    try:
        r = subprocess.run(
            [PY, os.path.join(TOOLS, "rag_search.py"), " ".join(keywords[:3]), "-k", "3"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30)
        for line in (r.stdout or "").splitlines():
            m = re.search(r"(\d+) 条结果", line)
            if m:
                result["rag_hits"] = int(m.group(1))
                break
    except Exception:
        pass

    result["total"] = result["rag_hits"]
    return result


def build_commands(cfg, slug, keywords, days, parallel, skip_preprints):
    """构造三通道子进程命令。返回 [(label, cmd, out_file), ...]（纯函数，可测试）。"""
    tmp_dir = os.path.join(ROOT, ".tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    cmds = []

    # B 通道：多查询并行 web_search
    web_qfile = os.path.join(tmp_dir, f"search_all_{slug}_web.json")
    with open(web_qfile, "w", encoding="utf-8") as f:
        json.dump({"queries": keywords}, f, ensure_ascii=False)
    web_out = os.path.join(ROOT, "research", slug, "gathered_web.md")
    cmds.append(("B Web",
                 [PY, os.path.join(TOOLS, "web_search.py"), "--queries-file", web_qfile,
                  "--parallel", str(parallel), "--out", web_out, "--slug", slug],
                 web_out))

    # A 通道：公众号（keywords.json 格式）
    wechat_qfile = os.path.join(tmp_dir, f"search_all_{slug}_wechat.json")
    with open(wechat_qfile, "w", encoding="utf-8") as f:
        json.dump({"queries": keywords, "count": 10}, f, ensure_ascii=False)
    wechat_out = os.path.join(ROOT, "research", slug, "gathered_wechat.md")
    cmds.append(("A 公众号",
                 [PY, os.path.join(TOOLS, "wechat_search.py"), "--keywords", wechat_qfile,
                  "--days", str(days), "--output", wechat_out],
                 wechat_out))

    # P 通道：预印本聚合（学术科研 P0；其他领域可用 --skip-preprints 跳过）
    if not skip_preprints:
        topic = (cfg.get("question") or "").strip() or keywords[0]
        cmds.append(("P 预印本",
                     [PY, os.path.join(TOOLS, "preprint_search.py"), "--platform", "all",
                      "--keywords", topic, "--days", "30", "--count", "5",
                      "--out", os.path.join(ROOT, "research", slug), "--slug", slug],
                     None))
    return cmds


def run_parallel(cmds):
    """并行执行命令，返回 [(label, returncode, tail_output, out_file), ...]。"""
    def _one(item):
        label, cmd, out_file = item
        try:
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=600)
            tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
            return label, r.returncode, "\n".join(tail[-12:]), out_file
        except Exception as e:
            return label, 1, f"运行异常：{e}", out_file

    if len(cmds) <= 1:
        return [_one(c) for c in cmds]
    with ThreadPoolExecutor(max_workers=len(cmds)) as ex:
        return list(ex.map(_one, cmds))


def main():
    ap = argparse.ArgumentParser(description="统一并行检索入口（B/A/P 三通道）")
    ap.add_argument("--config", help="start.json 路径（含 slug/domain/keywords/question）")
    ap.add_argument("--slug", help="研究 slug（与 --config 二选一）")
    ap.add_argument("--keywords", nargs="+", help="检索关键词组（≥2 组；与 --config 二选一时必填）")
    ap.add_argument("--days", type=int, default=365, help="公众号时间范围（天，默认 365）")
    ap.add_argument("--parallel", type=int, default=4, help="B 查询并行数（默认 4；1=串行）")
    ap.add_argument("--skip-preprints", action="store_true", help="跳过 P 预印本检索（P2 领域可用）")
    args = ap.parse_args()

    if args.config:
        try:
            cfg = load_config(args.config)
        except Exception as e:
            print(f"ERROR: 无法读取 config：{e}")
            sys.exit(2)
        slug = (cfg.get("slug") or "").strip()
        keywords = [str(k).strip() for k in (cfg.get("keywords") or []) if str(k).strip()]
    else:
        if not args.slug or not args.keywords:
            print("ERROR: 需 --config，或 --slug + --keywords 至少 2 组")
            sys.exit(2)
        cfg = {"slug": args.slug, "question": args.keywords[0]}
        slug = args.slug
        keywords = [k.strip() for k in args.keywords if k.strip()]

    if not SLUG_RE.match(slug):
        print(f"ERROR: slug 非法：{slug!r}（须英文小写短横线）")
        sys.exit(2)
    if len(keywords) < 2:
        print("WARN: 关键词仅 1 组，检索覆盖有限（建议 ≥2 组）")

    research_dir = os.path.join(ROOT, "research", slug)
    if not os.path.isdir(research_dir):
        print(f"ERROR: 研究目录不存在：{research_dir}（请先 run_pipeline --config 初始化）")
        sys.exit(2)

    # 领域档位 + 通道计划
    domain = (cfg.get("domain") or "").strip()
    dtype = cs.classify_domain(domain)
    plan = {ch: p for ch, p, _ in cs.channel_plan(dtype)}
    print(f"领域档位：{dtype}（domain={domain or '未填'}）")
    print(f"通道计划：B P0 通用；A={plan.get('A')} C={plan.get('C')} P={plan.get('P')} E={plan.get('E')}")

    print("\n─── 内部搜索 ───")
    internal = run_internal_search(slug, keywords)
    print(f"rag 命中：{internal['rag_hits']} 条")
    print(f"内部总命中：{internal['total']} 条")

    print(f"\n并行检索：B（{len(keywords)} 组查询 × {args.parallel} 并行）+ A + P 同时执行\n")

    cmds = build_commands(cfg, slug, keywords, args.days, args.parallel, args.skip_preprints)
    results = run_parallel(cmds)

    failed = []
    print("=" * 60)
    for label, rc, tail, out_file in results:
        # 判据：退出码 0 或落盘产物已生成（ddgs Rust 绑定偶发进程退出时崩溃，
        # 但检索与自动登记已完成——以产物为准，退出码异常仅提示）
        ok = rc == 0 or (out_file and os.path.isfile(out_file))
        status = "OK" if ok else f"EXIT {rc}"
        print(f"[{status}] {label}")
        for ln in tail.splitlines():
            print(f"    {ln}")
        if ok and rc != 0:
            print("    （进程退出码异常，但落盘产物已生成，按成功计）")
        if not ok:
            failed.append(label)
    print("=" * 60)

    print(f"\n落盘检查：research/{slug}/gathered_web.md（B，自动登记）· gathered_wechat.md（A，自动登记）"
          + (f" · gathered_arxiv.md/gathered_preprints.md（P，自动登记）" if not args.skip_preprints else ""))
    if failed:
        print(f"[失败] 通道崩溃：{', '.join(failed)}，请单独重跑对应命令排查。")
        sys.exit(1)
    print("检索完成。零命中属正常（已自动登记 empty）；素材请人工甄别后进入阶段 2。")


if __name__ == "__main__":
    main()
