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
    "templates/zhihu_answer_TEMPLATE.md",
    "templates/process_notes_TEMPLATE.md",
    "tools/research_start.py",
    "tools/wechat_search.py",
    "tools/init_research.py",
    "tools/git_protect.py",
    "tools/install_git_hooks.py",
    "tools/health_check.py",
    "tools/init.example.json",
    "tools/keywords.example.json",
]

# 不应出现在 git 跟踪中的内部文件
INTERNAL_FILES = [
    "plan.md",
    "docs/PLAN_v1_ARCHIVE.md",
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
    clean = "## " in out and "nothing to commit" not in out.lower() or out.startswith("## main")
    # 简单判断：输出以 ## 开头即正常（含分支信息）
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

    # 6. 隐私边界：内部文件不被跟踪
    rc, out, _ = run_git("ls-files")
    tracked = set(out.splitlines())
    leaks = [f for f in INTERNAL_FILES if f in tracked]
    all_ok &= check("内部文件未被 git 跟踪", not leaks,
                    "发现跟踪: " + ", ".join(leaks) if leaks else "")

    # 7. 关键文件完整性
    missing = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(ROOT, f))]
    all_ok &= check("关键文件完整", not missing,
                    "缺失: " + ", ".join(missing) if missing else "")

    print("=" * 60)
    print("结论: " + ("全部就绪" if all_ok else "存在问题，请按上方 FAIL 项处理"))
    print("=" * 60)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
