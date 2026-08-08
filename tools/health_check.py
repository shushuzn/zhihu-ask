# -*- coding: utf-8 -*-
"""
项目健康自检工具（zhihu-ask 项目专用）

一键验证项目就绪状态，适合新会话启动或排障时运行。
检查项：
  1. Python 环境与脚本可导入
  2. git 仓库状态（分支、远程、跟踪）
  3. pre-commit hook 是否安装
  4. 隐私边界（内部文件是否被 git 跟踪）
  5. 关键文件完整性（模板、文档、工具）

用法：
    python tools/health_check.py
"""

import sys
import os
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 公开仓库应跟踪的文件（存在即视为完整）
REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    ".gitignore",
    "docs/AGENT_PROMPTS.md",
    "docs/CHECKLIST.md",
    "docs/CONVENTIONS.md",
    "docs/KEYWORDS.md",
    "docs/SOP.md",
    "docs/STYLE_GUIDE.md",
    "docs/TEMPLATE_INDEX.md",
    "docs/TOOLS.md",
    "templates/research_plan_TEMPLATE.md",
    "templates/research_report_TEMPLATE.md",
    "templates/process_notes_TEMPLATE.md",
    "tools/research_start.py",
    "tools/check_progress.py",
    "tools/iter_research.py",
    "tools/quality_check.py",
    "tools/rag_build.py",
    "tools/rag_search.py",
    "tools/wechat_search.py",
    "tools/zhihu_search.py",
    "tools/init_research.py",
    "tools/git_protect.py",
    "tools/install_git_hooks.py",
    "tools/health_check.py",
    "tools/init.example.json",
    "tools/keywords.example.json",
    "tools/start.example.json",
]

# 不应出现在 git 跟踪中的内部文件/目录（隐私红线，覆盖须完整）
INTERNAL_FILES = [
    "plan.md",
    "docs/PLAN_v1_ARCHIVE.md",
    "research/",
    ".codebuddy/",
    "tools/start.json",
]


def run_git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8")
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def check(name, ok, detail=""):
    status = "OK " if ok else "FAIL"
    print(f"[{status}] {name}" + (f"  ({detail})" if detail else ""))
    return ok


def main():
    print("=" * 60)
    print("zhihu-ask 项目健康自检")
    print("=" * 60)
    all_ok = True

    # 1. Python 环境
    py_ok = sys.version_info >= (3, 8)
    all_ok &= check("Python 3.8+", py_ok, sys.version.split()[0])

    # 2. git 状态
    rc, out, _ = run_git("status", "--short", "--branch")
    branch_info = out.splitlines()[0] if out else "?"
    all_ok &= check("git 仓库状态", rc == 0, branch_info)

    # 3. 远程配置
    rc, out, _ = run_git("remote", "-v")
    has_remote = "origin" in out and "git@github.com" in out
    all_ok &= check("远程 origin (SSH)", has_remote,
                    out.splitlines()[0] if out else "未配置")

    # 4. 本地 main 与 origin/main 是否同步
    rc, out, _ = run_git("status", "--short", "--branch")
    synced = "origin/main" in out and "ahead" not in out and "behind" not in out
    all_ok &= check("main 与 origin/main 同步", synced,
                    "ahead/behind" if not synced else "已同步")

    # 5. pre-commit hook
    hook = os.path.join(ROOT, ".git", "hooks", "pre-commit")
    hook_ok = os.path.exists(hook)
    all_ok &= check("pre-commit hook 已安装", hook_ok,
                    "未安装，运行 python tools/install_git_hooks.py" if not hook_ok else "")

    # 6. 隐私边界：内部文件/目录不被跟踪
    rc, out, _ = run_git("ls-files")
    tracked = out.splitlines()
    leaks = []
    for pat in INTERNAL_FILES:
        p = pat.rstrip("/")
        for f in tracked:
            f2 = f.replace("\\", "/")
            if f2 == p or f2.startswith(p + "/"):
                leaks.append(f)
                break
    all_ok &= check("内部文件未被 git 跟踪", not leaks,
                    "发现跟踪: " + ", ".join(leaks) if leaks else "")

    # 7. 关键文件完整性
    missing = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(ROOT, f))]
    all_ok &= check("关键文件完整", not missing,
                    "缺失: " + ", ".join(missing) if missing else "")

    # 8. zhihu skill / CLI（通道 Z 增强，未安装/未认证不判 FAIL，仅提示）
    import json
    zhihu_cli_candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ZhihuCLI", "current", "zhihu-cli.exe"),
        os.path.expanduser("~/Library/Application Support/zhihu-cli/current/zhihu-cli"),
    ]
    zhihu_cli = next((p for p in zhihu_cli_candidates if p and os.path.exists(p)), None)
    if not zhihu_cli:
        check("通道 Z (zhihu-cli)", False, "未安装，跳过（可选增强，不影响其余通道）")
    else:
        zhihu_detail = f"CLI 已安装 ({os.path.basename(zhihu_cli)})"
        try:
            r = subprocess.run([zhihu_cli, "auth", "status"], capture_output=True,
                               text=True, encoding="utf-8", timeout=30)
            # auth status 为多层嵌套 JSON（外层 execute_command_result -> stdout 字符串）
            # 循环剥离，直至找到含 "ok"/"source" 的认证对象
            inner = {}
            try:
                obj = json.loads(r.stdout)
                for _ in range(6):
                    if isinstance(obj, dict) and "ok" in obj:
                        inner = obj
                        break
                    out_str = obj.get("stdout") if isinstance(obj, dict) else None
                    if not isinstance(out_str, str) or not out_str.strip():
                        break
                    obj = json.loads(out_str)
                else:
                    inner = {}
            except Exception:
                inner = {}
            ok_flag = inner.get("ok") is True
            source = inner.get("source", "")
            keychain = inner.get("keychain", "")
            masked = inner.get("masked", "")
            verified_at = inner.get("last_verified_at", "")
            if ok_flag and source:
                zhihu_detail += f" | 认证: 已配置({source})"
                if masked:
                    zhihu_detail += f" | {masked}"
                if verified_at:
                    zhihu_detail += f" | 上次校验 {verified_at[:10]}"
                elif inner.get("verification") == "not_performed":
                    zhihu_detail += " | 未执行验证"
            elif not ok_flag and keychain == "not_found":
                zhihu_detail += " | 认证: 未配置(AUTH_REQUIRED)"
            else:
                zhihu_detail += " | 认证: 异常(ok=%s source=%s)" % (inner.get("ok"), source)
        except Exception:
            zhihu_detail += " | 认证检查失败"
        check("通道 Z (zhihu-cli)", True, zhihu_detail)

    print("=" * 60)
    print("结论: " + ("全部就绪" if all_ok else "存在问题，请按上方 FAIL 项处理"))
    print("=" * 60)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
