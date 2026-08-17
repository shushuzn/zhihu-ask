# -*- coding: utf-8 -*-
"""笔记上传工具（zhihu-ask 项目专用）

上传笔记到 flomo, 自动拦截违规文件:
1. 索引笔记(00_index.md)禁止上传
2. 报告(report.md/report_draft.md)禁止上传
3. 上传前自动跑质检, 不通过则拒绝上传

用法:
  python tools/note_upload.py research/<slug>/notes/01_xxx.md
  python tools/note_upload.py research/<slug>/notes/  # 批量上传目录下所有笔记
"""

import sys
import os
import json
import subprocess
import argparse
import urllib.request
import re

try:
    # 行缓冲：stdout 被管道接管时默认全缓冲，进度打印会被吞掉（见"无输出"排查）
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass


def log(msg):
    """强制刷新进度打印（兼容未启用行缓冲的环境）。"""
    print(msg, flush=True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# flomo MCP 配置：Token 只从环境变量 FLOMO_MCP_TOKEN 读取（凭证不入库，见 docs/CONVENTIONS.md）。
# 曾硬编码在代码并进入公开仓库——请在 flomo 后台撤销旧 token 重建，再设环境变量。
MCP_URL = "https://flomoapp.com/mcp"
_raw = os.environ.get("FLOMO_MCP_TOKEN", "").strip()
MCP_TOKEN = _raw if _raw.startswith("Bearer ") else (f"Bearer {_raw}" if _raw else "")

# 禁止上传的文件名模式
BLOCKED_PATTERNS = [
    "00_index.md",
    "report.md",
    "report_draft.md",
]


def is_blocked(filepath):
    """检查文件是否被禁止上传。"""
    basename = os.path.basename(filepath)
    for pattern in BLOCKED_PATTERNS:
        if basename == pattern or basename.startswith(pattern.split(".")[0]):
            return True
    return False


def run_quality_check(filepath):
    """运行质检（quality_check 笔记模式 + check_gbt_refs 笔记模式 + 违规引用检查），返回 (passed, output)。

    笔记上传前除 quality_check 外，还须过 check_gbt_refs——
    笔记「参考文献:」段的 GB/T 7714 著录（编号连续/类型标识/URL 引用日期/悬空引注/正文一一对应）
    也纳入机器校验，防止不合规参考文献污染 flomo 知识库（对应"flomo 笔记引用须
    有合规参考文献"规则的上游防线）。
    另增加 check_citation_validity（离线模式）——URL 伪造/占位符、
    arxiv 非法 id、作者格式等离线可判项纳入上传拦截；联网核验（编造作者/题名不符）
    不在上传链中强制（网络不可用会阻塞上传），由报告质检阶段执行。
    """
    outputs = []
    for tool, extra in (("quality_check.py", ()), ("check_gbt_refs.py", ()),
                        ("check_citation_validity.py", ("--offline",))):
        cmd = [sys.executable, os.path.join(ROOT, "tools", tool),
               "--file", filepath, *extra]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        outputs.append((tool, r.returncode, (r.stdout or "") + (r.stderr or "")))
    passed = all(rc == 0 for _, rc, _ in outputs)
    output = "\n".join(f"== {tool} ==\n{out}" for tool, rc, out in outputs if rc != 0 or out)
    return passed, output


def mcp_call(method, params=None):
    """调用 flomo MCP。"""
    if not MCP_TOKEN:
        raise RuntimeError(
            "未配置 FLOMO_MCP_TOKEN：请设置环境变量 FLOMO_MCP_TOKEN=fmcp_xxx"
            "（此前硬编码 token 已从代码移除，请先在 flomo 后台撤销旧 token 重建）")
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


def memo_exists(memo_id, max_retries=2):
    """用 memo_batch_get 确认 memo 是否真实存在于当前 token 账户下。

    用于防止拿着 .flomo_ids.json 里的陈旧/失效 id 去 memo_update 一个
    根本不存在的 memo（常见于旧 token 上传后换 token）。不存在则回退新建。
    """
    import time as _t
    for _ in range(max(1, max_retries)):
        try:
            result = mcp_call("tools/call", {"name": "memo_batch_get",
                                             "arguments": {"ids": [memo_id]}})
            if result and "result" in result:
                text = result["result"]["content"][0]["text"]
                data = json.loads(text)
                if data.get("memos"):
                    return True
                return False
        except Exception as e:
            log(f"  (memo_exists 校验异常：{type(e).__name__}: {e})")
        _t.sleep(1)
    # 校验失败保守按"不存在"处理，回退新建，避免拿失效 id 反复 update
    return False


def _extract_id(result, label):
    """从 MCP 响应里取 memo id；解析失败返回 (None, 错误说明)。"""
    if not (result and "result" in result):
        return None, "MCP 返回无 result（疑似 error 响应）"
    try:
        text = result["result"]["content"][0]["text"]
        data = json.loads(text)
        return data.get("id"), None
    except Exception as e:
        snippet = ""
        try:
            snippet = result["result"]["content"][0]["text"][:120]
        except Exception:
            pass
        return None, f"响应解析失败 {type(e).__name__}: {e} | text前120字={snippet!r}"


def upload_to_flomo(content, max_retries=5, retry_delay=30):
    """上传内容到 flomo, 返回 memo_id 或 None。

    连接器故障（网络错误 / 超长
    content 假报 "toolName is required" 等）须**反复重试单条完整版直到成功**，
    禁止分段 / 精简 / 探测性调用；重试间隔 30 秒（用户指令"重试间隔用 bash
    sleep 30–60 秒"，工具化后为 30s×5 次）。传 --max-retries 0 可关闭重试。
    """
    import time as _time
    last_err = None
    for attempt in range(max(1, max_retries)):
        try:
            result = mcp_call("tools/call", {
                "name": "memo_create",
                "arguments": {"content": content}
            })
            memo_id, err = _extract_id(result, "memo_create")
            if memo_id:
                return memo_id
            last_err = err or "MCP 返回无 result"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < max_retries - 1:
            log(f"  (flomo 调用失败：{last_err}；{retry_delay}s 后重试 "
                f"{attempt + 2}/{max_retries}，单条完整版不变)")
            _time.sleep(retry_delay)
    log(f"  (flomo 重试 {max_retries} 次仍失败：{last_err})")
    return None


def update_to_flomo(content, memo_id, max_retries=5, retry_delay=30):
    """原地更新已有 flomo memo（--update 模式）。

    对应"更新一律 memo_update 原 id，禁止新建多版本"纪律；重试策略与
    upload_to_flomo 相同（单条完整版反复重试直到成功）。
    """
    import time as _time
    last_err = None
    for attempt in range(max(1, max_retries)):
        try:
            result = mcp_call("tools/call", {
                "name": "memo_update",
                "arguments": {"id": memo_id, "content": content}
            })
            new_id, err = _extract_id(result, "memo_update")
            if new_id:
                return new_id
            last_err = err or "MCP 返回无 result"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < max_retries - 1:
            log(f"  (flomo 更新失败：{last_err}；{retry_delay}s 后重试 "
                f"{attempt + 2}/{max_retries}，单条完整版不变)")
            _time.sleep(retry_delay)
    log(f"  (flomo 更新重试 {max_retries} 次仍失败：{last_err})")
    return None


# ---- memo id 持久化（--update 模式的记录依据）----
# 上传成功后把 {笔记文件名: flomo memo id} 记入 research/<slug>/.flomo_ids.json，
# 之后 `--update` 按记录原地更新；无记录则回退 memo_create（新建并记录）。
# ids 文件是内部文件（research/ 下，不入 git、不上云）。
def ids_path_for(notes_dir):
    """notes 目录 → research/<slug>/.flomo_ids.json（notes 的上一级）。"""
    return os.path.join(os.path.dirname(os.path.abspath(notes_dir)), ".flomo_ids.json")


def load_ids(ids_path):
    try:
        with open(ids_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_ids(ids_path, ids):
    with open(ids_path, "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False, indent=2)


def upload_file(filepath, max_retries=5, update=False,
                ids=None, ids_path=None):
    """上传单个文件, 返回 (success, memo_id, reason)。

    update=True 且 ids 记录中有该文件名 → memo_update 原地更新；否则 memo_create。
    上传成功且传入 ids 容器时把 {文件名: memo_id} 写入并落盘。
    """
    basename = os.path.basename(filepath)
    log(f"→ [{basename}] 开始处理")

    # 检查1: 是否被禁止
    if is_blocked(filepath):
        log(f"  ✗ 拦截: {basename} 是索引/报告文件，禁止上传")
        return False, None, f"禁止上传: {basename} (索引/报告文件)"

    # 检查2: 质检（强制，不可跳过）
    log(f"  · 质检中: {basename} (quality_check + GB/T + 引用校验)")
    passed, output = run_quality_check(filepath)
    if not passed:
        log(f"  ✗ 质检未通过: {basename}")
        return False, None, f"质检未通过: {basename}\n{output[:200]}"
    log(f"  ✓ 质检通过: {basename}")

    # 读取内容
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 修复标签格式：flomo 把 "# 文字" 渲染为标题（去掉 #），标签应为 "#文字"（无空格）
    # 仅处理首行（标签行），不影响正文中的 # 标题
    lines = content.split("\n", 1)
    if lines and re.match(r"^#\s+\S", lines[0]):
        lines[0] = re.sub(r"#(\s+)", r"#", lines[0])
        content = "\n".join(lines)

    # 检查3: 防重复——已有 ID 时先校验该 memo 是否真实存在，存在才更新，
    # 否则（陈旧/失效 id，常见于换 token）回退新建，避免对着不存在的 memo 空转。
    existing = (ids or {}).get(basename)
    if existing:
        if memo_exists(existing):
            log(f"  · 更新中: {basename} (memo id {existing})")
            memo_id = update_to_flomo(content, existing, max_retries=max_retries)
            action = "更新成功" if memo_id else None
        else:
            log(f"  · 记录 id {existing} 在当前账户不存在，回退新建: {basename}")
            memo_id = upload_to_flomo(content, max_retries=max_retries)
            action = "新建成功(旧id失效)" if memo_id else None
    else:
        log(f"  · 上传中: {basename} (flomo MCP)")
        memo_id = upload_to_flomo(content, max_retries=max_retries)
        action = "上传成功" if memo_id else None
    if memo_id:
        if ids is not None:
            ids[basename] = memo_id
            if ids_path:
                save_ids(ids_path, ids)
        return True, memo_id, action or "flomo MCP 调用失败（重试耗尽）"
    else:
        return False, None, "flomo MCP 调用失败（重试耗尽）"


def main():
    parser = argparse.ArgumentParser(description="笔记上传工具(自动拦截违规文件)")
    parser.add_argument("path", help="笔记文件或目录")
    parser.add_argument("--max-retries", type=int, default=5,
                        help="flomo 调用失败重试次数（默认 5，间隔 30s；0=不重试）")
    parser.add_argument("--update", action="store_true",
                        help="原地更新：按 .flomo_ids.json 记录用 memo_update 更新已有 memo；"
                             "无记录的文件回退 memo_create（新建并记录 id）")
    args = parser.parse_args()

    path = os.path.join(ROOT, args.path) if not os.path.isabs(args.path) else args.path

    if os.path.isfile(path):
        # 单文件：ids 记录按所在 notes 目录定位
        ids_path = ids_path_for(os.path.dirname(path))
        ids = load_ids(ids_path)
        log(f"== 单文件上传: {path} ==")
        success, memo_id, reason = upload_file(path, args.max_retries,
                                              args.update, ids, ids_path)
        status = "✓" if success else "✗"
        log(f"{status} {os.path.basename(path)}: {reason}")
        if memo_id:
            log(f"  flomo id: {memo_id}")
    elif os.path.isdir(path):
        # 目录批量：共享一份 ids 记录，全部处理完一次性落盘
        ids_path = ids_path_for(path)
        ids = load_ids(ids_path)
        files = sorted([f for f in os.listdir(path) if f.endswith(".md") and not f.startswith("_")])
        log(f"== 目录批量上传: {path} ==")
        log(f"   待处理文件({len(files)}): {', '.join(files) if files else '(无)'}")
        for fname in files:
            fpath = os.path.join(path, fname)
            success, memo_id, reason = upload_file(fpath, args.max_retries,
                                                   args.update, ids, ids_path)
            status = "✓" if success else "✗"
            log(f"{status} {fname}: {reason}")
            if memo_id:
                log(f"  flomo id: {memo_id}")
        if ids_path and os.path.exists(ids_path):
            log(f"   id 记录已落盘: {ids_path}")
    else:
        log(f"ERROR: 路径不存在: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
