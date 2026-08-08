# -*- coding: utf-8 -*-
"""
知乎开放平台检索包装工具（zhihu-ask 项目专用）

包装 zhihu-cli（知乎开放平台官方 CLI），解决 PowerShell 中文参数乱码：
用 Python subprocess 直接传 Unicode 参数调用 exe，绕开 PowerShell 命令行层。

用法:
    python tools/zhihu_search.py --config tools/zhihu_search.json

config 格式（UTF-8）:
{
  "mode": "zhihu",                    // zhihu | global | hot
  "queries": ["关键词1", "关键词2"],   // zhihu/global 模式必填
  "count": 10,                        // zhihu: 1-10, global: 1-20
  "search_db": "all",                 // global 模式可选: all|realtime|static
  "limit": 20,                        // hot 模式: 1-30
  "output": "research/<slug>/gathered_zhihu.md"   // 可选，落盘素材库
}

前置条件:
    zhihu-cli 已安装（zhihu skill setup 完成）。
    Access Secret 已配置（zhihu-cli auth set --secret-stdin）。
    未认证时工具返回 AUTH_REQUIRED 提示。

数据边界（zhihu skill 官方口径）:
    热榜适合发现议题，不等于完整事实。
    深度研究、事实核查和观点比较必须用 search，不能用直答(answer)替代。
    搜索返回的是摘要(ContentText)与链接，需要原文时用 web_fetch 打开 Url。
"""

import sys
import json
import os
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def find_cli():
    """定位 zhihu-cli 可执行文件。优先环境变量，其次 Windows/macOS 用户数据目录。"""
    home = os.environ.get("ZHIHU_CLI_HOME")
    if home:
        for name in ("zhihu-cli.exe", "zhihu-cli"):
            p = os.path.join(home, "current", name)
            if os.path.exists(p):
                return p
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        p = os.path.join(local, "ZhihuCLI", "current", "zhihu-cli.exe")
        if os.path.exists(p):
            return p
    mac_home = os.path.expanduser("~/Library/Application Support/zhihu-cli")
    p = os.path.join(mac_home, "current", "zhihu-cli")
    if os.path.exists(p):
        return p
    return None


def parse_args(argv):
    args = {"config": None}
    i = 0
    while i < len(argv):
        if argv[i] == "--config" and i + 1 < len(argv):
            args["config"] = argv[i + 1]
            i += 2
        else:
            i += 1
    return args


def run_cli(cli, cmd_args, timeout=60):
    """调用 zhihu-cli，返回 (returncode, stdout_text, stderr_text)。"""
    try:
        r = subprocess.run([cli] + cmd_args, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 5, "", "TIMEOUT: 请求超时（超过 %ds）" % timeout
    out = r.stdout.decode("utf-8", errors="replace")
    err = r.stderr.decode("utf-8", errors="replace")
    return r.returncode, out, err


def report_error(returncode, out, err):
    """解析 CLI 错误并输出可操作提示。返回是否已处理（是则退出）。"""
    try:
        data = json.loads(out)
        error = data.get("error") or {}
        code = error.get("code", "")
        message = error.get("message", out.strip())
        action_url = error.get("action_url", "")
    except json.JSONDecodeError:
        code = ""
        message = (out or err or "").strip()
        action_url = ""
    if code == "AUTH_REQUIRED":
        print("AUTH_REQUIRED: 尚未配置 Access Secret。")
        print("  请打开 %s 申请 Access Secret" % (action_url or "https://developer.zhihu.com/profile"))
        print("  然后执行: zhihu-cli auth set --secret-stdin （通过标准输入发送凭证）")
        return True
    if code == "AUTH_INVALID":
        print("AUTH_INVALID: Access Secret 无效。请到开放平台重新申请，不要回显旧凭证。")
        return True
    if code == "KEYCHAIN_UNAVAILABLE":
        print("KEYCHAIN_UNAVAILABLE: 系统密钥链不可用。请通过宿主 Secret Store 注入 ZHIHU_ACCESS_SECRET 环境变量。")
        return True
    if returncode == 4:
        print("配额耗尽或频率限制（退出码 4）：停止主动重试，确认当日额度状态。")
        return True
    print("zhihu-cli 调用失败（退出码 %d）：%s" % (returncode, message))
    if err.strip():
        print("stderr: %s" % err.strip())
    return True


def search_zhihu(cli, query, count):
    return run_cli(cli, ["search", "zhihu", "--query", query, "--count", str(count)])


def search_global(cli, query, count, search_db):
    cmd = ["search", "global", "--query", query, "--count", str(count)]
    if search_db:
        cmd += ["--search-db", search_db]
    return run_cli(cli, cmd)


def get_hot(cli, limit):
    return run_cli(cli, ["hot", "--limit", str(limit)])


def parse_ok(data):
    """zhihu-cli 成功时 stdout 为服务端原始 JSON。取 Data。"""
    if isinstance(data, dict) and data.get("Code") == 0:
        return data.get("Data") or {}
    return {}


def extract_items(data):
    """统一提取 Items 列表（search zhihu / search global / hot 均含 Items）。"""
    if not data:
        return []
    return data.get("Items") or []


def item_md(item, mode):
    """把单条结果转成素材库 Markdown 行。"""
    title = item.get("Title", "")
    author = item.get("AuthorName", "")
    votes = item.get("VoteUpCount", "")
    url = item.get("Url", "")
    ctype = item.get("ContentType", "")
    text = item.get("ContentText", "")
    auth_level = item.get("AuthorityLevel", "")
    if mode == "hot":
        summary = item.get("Summary", "")
        lines = ["- **%s**" % title]
        if url:
            lines.append("  - 链接：%s" % url)
        if summary:
            lines.append("  - 摘要：%s" % summary)
        return "\n".join(lines)
    lines = ["- **%s**" % title]
    if author:
        meta = "作者：%s" % author
        if votes not in ("", None):
            meta += " | 赞同：%s" % votes
        if ctype:
            meta += " | 类型：%s" % ctype
        if auth_level not in ("", None):
            meta += " | 权威等级：%s" % auth_level
        lines.append("  - %s" % meta)
    if url:
        lines.append("  - 链接：%s" % url)
    if text:
        # 摘要可能带 <em> 高亮，去掉标签，压缩换行
        clean = text.replace("<em>", "").replace("</em>", "")
        clean = " ".join(clean.split())
        lines.append("  - 摘要：%s" % clean[:500])
    return "\n".join(lines)


def main():
    args = parse_args(sys.argv[1:])
    if not args["config"] or not os.path.exists(args["config"]):
        print("ERROR: 请提供 --config <json文件>（UTF-8）")
        sys.exit(1)

    with open(args["config"], "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cli = find_cli()
    if cli is None:
        print("ERROR: 未找到 zhihu-cli。请先安装 zhihu skill 并完成 setup。")
        sys.exit(8)

    mode = cfg.get("mode", "zhihu")
    output = cfg.get("output", "")

    print("=" * 60)
    print(f"知乎开放平台检索 | 模式: {mode}")
    print(f"CLI: {cli}")
    print("=" * 60)

    out_lines = []
    out_lines.append("# 知乎开放平台检索素材库")
    out_lines.append("")
    out_lines.append(f"> 模式：{mode}")
    out_lines.append("> 数据边界：搜索返回摘要与链接，原文需打开链接核实；热榜仅用于发现议题。")
    out_lines.append("")

    if mode == "hot":
        limit = int(cfg.get("limit", 20))
        code, out, err = get_hot(cli, limit)
        if code != 0:
            report_error(code, out, err)
            sys.exit(code)
        data = parse_ok(json.loads(out))
        items = extract_items(data)
        print(f"热榜条目: {len(items)}")
        for it in items:
            print("-", it.get("Title", ""))
            out_lines.append(item_md(it, "hot"))
        out_lines.append("")
    else:
        queries = cfg.get("queries", [])
        if not queries:
            print("ERROR: zhihu/global 模式需要 queries 数组")
            sys.exit(2)
        count = int(cfg.get("count", 10))
        search_db = cfg.get("search_db", "all")
        for q in queries:
            print("\n" + "#" * 60)
            print(f"## 关键词: {q}")
            print("#" * 60)
            out_lines.append(f"## 关键词：{q}")
            out_lines.append("")
            if mode == "zhihu":
                code, out, err = search_zhihu(cli, q, count)
            else:
                code, out, err = search_global(cli, q, count, search_db)
            if code != 0:
                if report_error(code, out, err):
                    sys.exit(code)
            try:
                data = parse_ok(json.loads(out))
            except json.JSONDecodeError:
                print("ERROR: CLI 输出不是合法 JSON")
                sys.exit(6)
            items = extract_items(data)
            if not items:
                print("（无结果）")
                out_lines.append("（无结果）")
                out_lines.append("")
                continue
            for it in items:
                md = item_md(it, mode)
                print("  " + md.replace("\n", "\n  "))
                out_lines.append(md)
            out_lines.append("")

    if output:
        outdir = os.path.dirname(output)
        if outdir and not os.path.isdir(outdir):
            os.makedirs(outdir, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines))
        print(f"\n已写入素材库: {output}")


if __name__ == "__main__":
    main()
