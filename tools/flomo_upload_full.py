# -*- coding: utf-8 -*-
"""flomo 单条完整版上传（本地直连 MCP 端点，绕过客户端工具调度层对大参数的拦截）。

背景：WorkBuddy 的 DeferExecuteTool 对超长 content（>~2KB）间歇性假报
"toolName is required"（请求未到达 flomo 代理层，elapsed 0ms 本地拦截）；而 flomo MCP
服务端本身支持长文（历史报告 4000-6500 字正常）。
本脚本按 MCP streamable-http 协议直连 flomo 端点，无该限制。

用法：
  python tools/flomo_upload_full.py --slug <slug>
  （读取 research/<slug>/flomo_full.md 全文，memo_create 上传，id 注释回文件）

凭证：只从环境变量 FLOMO_MCP_TOKEN 读取（不读 .env、不读 mcp.json）；不落盘、不打日志。
"""
import json
import sys
import re
import urllib.request
import urllib.error
import os
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def load_mcp_flomo():
    """返回 (url, token)。只从环境变量 FLOMO_MCP_TOKEN 读取（不读 .env、不读 mcp.json）。"""
    url = "https://flomoapp.com/mcp"
    token = os.environ.get("FLOMO_MCP_TOKEN", "").strip()
    if token.startswith("Bearer "):
        token = token[len("Bearer "):]
    return url, token


def _parse_sse_or_json(body):
    """streamable-http 响应可能是 SSE（event:/data: 行）或纯 JSON。提取最后一个 data: 的 JSON。"""
    if body.startswith("data:") or "event: message" in body:
        lines = body.splitlines()
        data_lines = [ln[5:].strip() for ln in lines if ln.startswith("data:")]
        if data_lines:
            return json.loads(data_lines[-1])
    return json.loads(body)


def mcp_initialize(url, token):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "zhihu-ask-flomo-uploader", "version": "1.0"},
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
        session = resp.headers.get("Mcp-Session-Id")
        data = _parse_sse_or_json(body)
        return session, data


def mcp_call_tool(url, token, session, name, arguments):
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = resp.read().decode("utf-8")
        return _parse_sse_or_json(body)



def check_channels(slug):
    """检查 A/B/P 通道是否都已使用（gathered_*.md 必须存在且非空）。"""
    import os
    base = os.path.join(os.path.dirname(__file__), "..", "research", slug)

    channels = {
        "A": ("gathered_wechat.md", "公众号检索"),
        "B": ("gathered_web.md", "Web检索"),
    }

    missing = []
    for ch, (filename, desc) in channels.items():
        filepath = os.path.join(base, filename)
        if not os.path.exists(filepath):
            missing.append(f"{ch}({desc}): 文件不存在")
        elif os.path.getsize(filepath) < 50:  # 小于50字节视为空
            missing.append(f"{ch}({desc}): 内容为空或过少")

    # 通道 P 的素材文件为 gathered_arxiv.md / gathered_preprints.md，任一存在且非空即可
    p_files = [os.path.join(base, "gathered_arxiv.md"), os.path.join(base, "gathered_preprints.md")]
    if not any(os.path.exists(p) and os.path.getsize(p) >= 50 for p in p_files):
        missing.append("P(学术预印本检索): gathered_arxiv.md / gathered_preprints.md 均不存在或为空")

    return missing



def run_checks(slug):
    """上传前运行所有检查，返回通过/失败。"""
    import subprocess
    base = os.path.join(os.path.dirname(__file__), "..", "research", slug)
    report_path = os.path.join(base, "report.md")
    
    checks = [
        ("check_report_structure.py", "结构检查"),
        ("check_ai_voice.py", "AI腔检查"),
        ("check_gbt_refs.py", "GB/T引用检查"),
    ]
    
    errors = []
    for script, name in checks:
        script_path = os.path.join(os.path.dirname(__file__), script)
        if os.path.exists(script_path):
            result = subprocess.run(
                [sys.executable, script_path, "--file", report_path],
                capture_output=True, text=True, cwd=os.path.dirname(__file__)
            )
            if result.returncode != 0:
                errors.append(f"{name}未通过")
    
    return errors


def main():
    import sys
    import argparse
    # 先解析 slug
    pre_ap = argparse.ArgumentParser(add_help=False)
    pre_ap.add_argument("--slug", required=True)
    pre_args, _ = pre_ap.parse_known_args()
    
    # 运行所有检查
    errors = run_checks(pre_args.slug)
    if errors:
        print(f"[禁止上传] 以下检查未通过:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print(f"请先修复报告再上传", file=sys.stderr)
        sys.exit(1)
    
    missing = check_channels(pre_args.slug)
    if missing:
        print(f"[禁止上传] 以下通道未使用:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        print(f"请先执行通道检索：python tools/research_start.py --config tools/start.json", file=sys.stderr)
        sys.exit(1)
    
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--force", action="store_true",
                    help="忽略已上传注释，强制重新上传（会创建新 memo，谨慎使用）")
    ap.add_argument("--update", action="store_true",
                    help="覆盖更新已有 memo（v25 纪律：更新一律 memo_update 原 id，禁止新建多版本）")
    args = ap.parse_args()

    base = os.path.join(os.path.dirname(__file__), "..", "research", args.slug)
    full_path = os.path.join(base, "flomo_full.md")
    if not os.path.exists(full_path):
        print(f"[失败] 未找到 {full_path}", file=sys.stderr)
        sys.exit(1)

    # 检测已有 memo id（自动决定创建或更新）
    existing_id = None
    with open(full_path, encoding="utf-8") as f:
        head = f.read(200)
    m = re.search(r"<!-- flomo id: (\S+)", head)
    if m:
        existing_id = m.group(1)
    
    with open(full_path, encoding="utf-8") as f:
        content = f.read().strip()

    url, token = load_mcp_flomo()
    print(f"[连接] {url}", file=sys.stderr)
    session, init = mcp_initialize(url, token)
    if "result" not in init and "error" in init:
        print(f"[失败] initialize: {init['error']}", file=sys.stderr)
        sys.exit(1)
    print(f"[就绪] session={'有' if session else '无'}，协议 {init.get('result', {}).get('protocolVersion', '?')}")

    # 自动决策：有 id 用 memo_update，无 id 用 memo_create
    if existing_id and not args.force:
        method = "memo_update"
        params = {"id": existing_id, "content": content}
        print(f"[策略] 检测到已有 memo id={existing_id}，使用 memo_update", file=sys.stderr)
    else:
        method = "memo_create"
        params = {"content": content}
        if existing_id and args.force:
            print(f"[策略] --force 模式，将创建新 memo（原 id={existing_id} 将废弃）", file=sys.stderr)
    result = mcp_call_tool(url, token, session, method, params)
    if "error" in result:
        print(f"[失败] {method}: {result['error']}", file=sys.stderr)
        sys.exit(1)
    # 提取 memo id
    text = ""
    for item in result.get("result", {}).get("content", []):
        if item.get("type") == "text":
            text += item.get("text", "")
    try:
        data = json.loads(text)
        mid = data.get("id", "?")
        wc = data.get("word_count", "?")
        print(f"[成功] {method} memo id={mid} word_count={wc}", file=sys.stderr)
        # 注释回 flomo_full.md
        comment = f"<!-- flomo id: {mid} | 上传时间: 本地直连脚本 -->"
        with open(full_path, "r", encoding="utf-8") as f:
            orig = f.read()
        if not orig.startswith("<!-- flomo id"):
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(comment + "\n" + orig)
        print(f"[已注释] {full_path}", file=sys.stderr)
    except Exception as e:
        print(f"[警告] 无法解析结果: {e}；原始结果: {text[:200]}", file=sys.stderr)


if __name__ == "__main__":
    main()
