# -*- coding: utf-8 -*-
"""
一键研究启动器（zhihu-ask 项目专用）

把「启动一次知乎问题研究」从手动多步操作压缩为一条命令：
  1. 调用 init_research.py 初始化研究目录（模板生成 + 索引登记）
  2. 自动生成公众号检索关键词文件（从 config 的 keywords 字段）
  3. 运行 wechat_search.py 公众号检索（UTF-8 文件传参，规避中文乱码）
  4. 把公众号检索结果落盘为 research/<slug>/gathered_wechat.md（素材库）
  5. 打印后续步骤提示（Web 检索关键词建议）

用法：
    python tools/research_start.py --config tools/start.json

config 文件格式（UTF-8）：
    {
      "question": "问题完整标题",
      "domain": "示例领域",
      "slug": "example-slug",
      "priority": "高",
      "keywords": ["主题词 突破", "主题词 产业化", "主题词 争议"],
      "days": 30
    }

说明：
- keywords 为公众号检索关键词（每组一轮搜索）；days 为时间范围（天），默认 365。
- 本脚本只做「初始化 + 素材收集」，不产观点，后续按 docs/SOP.md 阶段 2-3 继续。
"""

import sys
import os
import json
import subprocess
import time
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "--config":
        print("用法: python tools/research_start.py --config <json>")
        sys.exit(1)

    cfg_path = sys.argv[2]
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    question = cfg.get("question", "").strip()
    slug = (cfg.get("slug") or "").strip().lower()
    domain = cfg.get("domain", "其他")
    priority = cfg.get("priority", "中")
    keywords = cfg.get("keywords") or []
    days = cfg.get("days", 365)

    if not question or not slug:
        print("ERROR: config 需要 question 与 slug 字段")
        sys.exit(1)

    print("=" * 60)
    print(f"开始研究: {question}")
    print(f"slug: {slug} | 领域: {domain}")
    print("=" * 60)

    # 1. 初始化目录（临时 init config）
    init_cfg = {"question": question, "domain": domain, "slug": slug, "priority": priority}
    tmp_init = os.path.join(ROOT, "tools", "_start_init.json")
    with open(tmp_init, "w", encoding="utf-8") as f:
        json.dump(init_cfg, f, ensure_ascii=False)
    print("\n==> [1/4] 初始化研究目录")
    ok = run([sys.executable, os.path.join(ROOT, "tools", "init_research.py"), "--config", tmp_init])
    if not ok:
        print("初始化失败（目录可能已存在），继续尝试素材收集。")

    # 2. 公众号检索关键词文件
    kw_path = os.path.join(ROOT, "tools", "_start_keywords.json")
    with open(kw_path, "w", encoding="utf-8") as f:
        json.dump({"queries": keywords, "count": 8}, f, ensure_ascii=False)

    gathered_path = os.path.join(ROOT, "research", slug, "gathered_wechat.md")

    # 3. 跑公众号检索
    print(f"\n==> [2/4] 公众号检索（{len(keywords)} 组关键词，近 {days} 天）")
    if keywords:
        run([sys.executable, os.path.join(ROOT, "tools", "wechat_search.py"),
             "--keywords", kw_path, "--days", str(days)])
    else:
        print("（未提供 keywords，跳过公众号检索）")

    # 4. 落盘素材库
    print(f"\n==> [3/4] 生成素材库 {os.path.relpath(gathered_path, ROOT)}")
    print("\n==> [4/4] 后续步骤")
    print("  a. 在 research/<slug>/plan.md 补齐问题界定与 Web 检索关键词")
    print("  b. 用 web_search 做事实核查（官方/研报/新闻）")
    print("  c. 按 SOP 阶段 2-3 交叉验证，产出 report.md 与 zhihu_answer.md")
    print("  d. 完成后回填 plan.md 索引状态，写 process_notes.md")

    # 清理临时文件
    for p in (tmp_init, kw_path):
        if os.path.exists(p):
            os.remove(p)

    print("\n完成。素材库与目录已就绪。")


if __name__ == "__main__":
    main()
