# -*- coding: utf-8 -*-
"""
微信公众号检索包装工具（zhihu-ask 项目专用）

解决 PowerShell 命令行向 Python 传递中文参数乱码的问题：
绕开命令行传参，改为从 UTF-8 关键词文件读取。

用法:
    python tools/wechat_search.py --keywords tools/keywords.json --days 30
    python tools/wechat_search.py --keywords tools/keywords.json --time-range 2025-08-01 2026-08-01

keywords.json 格式:
    {
      "queries": ["<主题词> 突破", "<主题词> 产业化"],
      "count": 10
    }

输出: 每个关键词的搜索结果（标题 / 公众号 / 时间 / 摘要 / 链接），UTF-8。
"""

import sys
import json
import os
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 接入 skill 脚本（兼容不同路径）
SKILL_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "..",
                 "C", "Users", "35234", ".codebuddy", "plugins",
                 "marketplaces", "cb_teams_marketplace", "plugins",
                 "deep-research", "skills", "wechat-article-search", "scripts"),
    r"C:\Users\35234\.codebuddy\plugins\marketplaces\cb_teams_marketplace\plugins\deep-research\skills\wechat-article-search\scripts",
]
sogou = None
for p in SKILL_PATHS:
    script = os.path.join(p, "sogou_search.py")
    if os.path.exists(script):
        import importlib.util
        spec = importlib.util.spec_from_file_location("sogou_search", script)
        sogou = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sogou)
        break

if sogou is None:
    print("ERROR: 未找到 sogou_search.py，请检查 SKILL 路径")
    sys.exit(1)


def parse_args(argv):
    args = {"keywords_file": None, "days": None, "time_range": None}
    i = 0
    while i < len(argv):
        if argv[i] == "--keywords" and i + 1 < len(argv):
            args["keywords_file"] = argv[i + 1]
            i += 2
        elif argv[i] == "--days" and i + 1 < len(argv):
            args["days"] = int(argv[i + 1])
            i += 2
        elif argv[i] == "--time-range" and i + 2 < len(argv):
            args["time_range"] = (argv[i + 1], argv[i + 2])
            i += 3
        else:
            i += 1
    return args


def main():
    args = parse_args(sys.argv[1:])
    if not args["keywords_file"] or not os.path.exists(args["keywords_file"]):
        print("ERROR: 请提供 --keywords <json文件>")
        sys.exit(1)

    with open(args["keywords_file"], "r", encoding="utf-8") as f:
        cfg = json.load(f)
    queries = cfg.get("queries", [])
    count = cfg.get("count", 10)

    now = int(datetime.now(timezone.utc).timestamp())
    if args["time_range"]:
        time_from = int(datetime.strptime(args["time_range"][0], "%Y-%m-%d").replace(
            tzinfo=timezone.utc).timestamp())
        time_to = int(datetime.strptime(args["time_range"][1], "%Y-%m-%d").replace(
            tzinfo=timezone.utc).timestamp())
    elif args["days"]:
        time_from = now - args["days"] * 86400
        time_to = now
    else:
        time_from = now - 365 * 86400
        time_to = now

    print("=" * 60)
    print(f"微信公众号检索 | 时间范围: {datetime.fromtimestamp(time_from)} ~ {datetime.fromtimestamp(time_to)}")
    print(f"关键词数: {len(queries)} | 每词返回: {count}")
    print("=" * 60)

    for q in queries:
        print("\n" + "#" * 60)
        print(f"## 关键词: {q}")
        print("#" * 60)
        results = sogou.search_sogou(q, "article", 1, time_from, time_to)
        if not results:
            print("（无结果）")
            continue
        if isinstance(results[0], dict) and "error" in results[0]:
            print("ERROR:", results[0]["error"])
            continue
        for r in results[:count]:
            title = r.get("title", "")
            account = r.get("account", "")
            ts = r.get("time", "")
            digest = r.get("digest", "")
            link = r.get("sogou_link", "")
            print(f"- [{title}]")
            print(f"  公众号: {account} | 时间: {ts}")
            if digest:
                print(f"  摘要: {digest}")
            if link:
                print(f"  链接: {link}")


if __name__ == "__main__":
    main()
