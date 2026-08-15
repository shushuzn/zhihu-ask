# -*- coding: utf-8 -*-
"""flomo 笔记搜索工具（zhihu-ask 项目专用）

通过 flomo MCP 搜索笔记, 支持关键词搜索和标签筛选。

用法:
  python tools/flomo_search.py --keywords "AI 编程"
  python tools/flomo_search.py --tag "AI编程"
  python tools/flomo_search.py --tag "AI编程" --keywords "定价"
  python tools/flomo_search.py --tag "主题/AI科学档案"
  python tools/flomo_search.py --keywords "定价" --full   # 输出完整正文
"""

import sys
import json
import os
import argparse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from env_loader import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# flomo MCP 配置：Token 从环境变量 FLOMO_MCP_TOKEN 读取（凭证不入库，见 docs/CONVENTIONS.md）。
# 优先真实环境变量，其次项目根 .env 兜底（沙箱下 setx 被拒的既有做法，见 tools/env_loader.py）。
# 曾硬编码在代码并进入公开仓库——请在 flomo 后台撤销旧 token 重建，再设环境变量（或 .env 兜底）。
MCP_URL = "https://flomoapp.com/mcp"
_raw = os.environ.get("FLOMO_MCP_TOKEN", "").strip()
MCP_TOKEN = _raw if _raw.startswith("Bearer ") else (f"Bearer {_raw}" if _raw else "")


def mcp_call(method, params=None):
    """调用 flomo MCP。"""
    if not MCP_TOKEN:
        raise RuntimeError(
            "未配置 FLOMO_MCP_TOKEN：请设置环境变量 FLOMO_MCP_TOKEN=fmcp_xxx"
            "（或项目根 .env 兜底；此前硬编码 token 已从代码移除，请先在 flomo 后台撤销旧 token 重建）")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": MCP_TOKEN,
    }
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }).encode()
    req = urllib.request.Request(MCP_URL, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read().decode()
    for line in raw.split("\n"):
        if line.startswith("data: "):
            return json.loads(line[6:])
    return None


def search(keywords=None, tag=None, limit=10, strict=False):
    """搜索 flomo 笔记。

    strict=True 时，MCP 调用失败直接抛异常，供流水线作为阻断门禁使用；
    默认 False 保持旧行为（失败返回空列表，兼容检查类调用）。
    """
    args = {"limit": limit}
    if keywords:
        args["keywords"] = keywords
    if tag:
        args["tag"] = tag
    result = mcp_call("tools/call", {"name": "memo_search", "arguments": args})
    if not result or "result" not in result:
        if strict:
            raise RuntimeError("flomo MCP 调用失败或返回无 result")
        return []
    content = result["result"]["content"][0]["text"]
    data = json.loads(content)
    return data.get("memos", [])


def fetch_full(memos):
    """按 id 批量获取笔记全文，返回 {id: memo}。

    memo_batch_get 单次最多 10 条；搜索 limit 可大于 10，因此按 10 条分块拉取。
    """
    ids = [m["id"] for m in memos if m.get("id")]
    if not ids:
        return {}
    full = {}
    for i in range(0, len(ids), 10):
        chunk = ids[i:i + 10]
        result = mcp_call("tools/call", {"name": "memo_batch_get", "arguments": {"ids": chunk}})
        if not result or "result" not in result:
            continue
        try:
            text = result["result"]["content"][0]["text"]
            data = json.loads(text)
            full.update({m["id"]: m for m in data.get("memos", [])})
        except (KeyError, IndexError, ValueError):
            continue
    return full


def auto_register_f(slug, n_hits):
    """查重执行后自动登记通道 F（done，note 含 memo_search 证据）。返回 (ok, message)。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import channel_state as _cs
        note = f"memo_search 已执行：命中 {n_hits} 条（查重结论以人工判读为准）"
        if _cs.mark(slug, "F", "done", note=note):
            return True, f"通道 F（flomo 查重）: done —— {note}"
        return False, f"未找到 research/{slug}/.progress.json，跳过通道 F 自动登记（请先 research_start）"
    except Exception as e:
        return False, f"通道 F 自动登记失败（不影响查重输出）: {e}"


def main():
    parser = argparse.ArgumentParser(description="flomo 笔记搜索")
    parser.add_argument("--keywords", help="搜索关键词 (空格分隔=AND)")
    parser.add_argument("--tag", help="按标签筛选")
    parser.add_argument("--limit", type=int, default=10, help="最多返回条数")
    parser.add_argument("--full", action="store_true", help="输出完整笔记正文（默认只显示摘要）")
    parser.add_argument("--slug", help="查重执行后自动登记通道 F（写入 research/<slug>/.progress.json 的 channels_done）")
    args = parser.parse_args()

    if not args.keywords and not args.tag:
        print("ERROR: 需要 --keywords 或 --tag")
        sys.exit(1)

    try:
        memos = search(args.keywords, args.tag, args.limit, strict=True)
    except Exception as e:
        print(f"ERROR: flomo 查重失败：{e}")
        sys.exit(1)
    # F 通道自动登记：查重已实际执行即登记 done（note 含 memo_search 证据，供 report_channels 门禁）。
    # 命中≥0.9 复用/更新、0.5~0.9 参考等结论由 agent 阅读结果后用 mark_channel 补充/覆盖 note。
    if args.slug:
        ok, msg = auto_register_f(args.slug, len(memos))
        print(f"[自动登记] {msg}" if ok else f"[提示] {msg}")

    if not memos:
        print("未找到匹配的笔记。")
        return

    full = fetch_full(memos) if args.full else {}

    print(f"找到 {len(memos)} 条笔记:\n")
    for m in memos:
        tags = ", ".join(m.get("tags", []))
        print(f"[{m['id']}] {tags}")
        if args.full and m["id"] in full:
            print(full[m["id"]].get("content", ""))
        else:
            content = m["content"].replace("\n", " ")[:120]
            print(f"  {content}...")
        print(f"  {m['url']}")
        print()


if __name__ == "__main__":
    main()
