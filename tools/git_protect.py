
"""
本地 git 提交保护工具（仅本地使用，不推送到公开仓库）

在提交前检查暂存区是否包含不应进入公开仓库的内部文件，防止误提交。
用法：
    python tools/git_protect.py            # 检查暂存区
    python tools/git_protect.py --commit    # 检查通过后自动提交（用 -f 传入消息文件）

内部文件清单（起见 tools/internal_files.py 公共模块，单一真相源）：
    plan.md / research/ / docs/PLAN__ARCHIVE.md / .codebuddy/ / .workbuddy/
    .commit_msg.tmp / .desc.tmp.txt / *.tmp
    tools/init.*.json / tools/keywords.*.json / tools/start.*.json（临时 config，example 除外）
"""

import sys
import os
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

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
from internal_files import is_internal
from health_check import REQUIRED_FILES as _REQUIRED_FILES

KEY_FILES = _REQUIRED_FILES + ["skills/zhihu-ask-research/SKILL.md"]

try:
    from tools.run_util import ROOT
except ModuleNotFoundError:
    from run_util import ROOT  # 被测导入时 tools 不在包路径

def staged_files():
    """返回暂存区文件列表（git diff --cached --name-only）"""
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, encoding="utf-8",
    )
    return [f.strip() for f in r.stdout.splitlines() if f.strip()]

def check_key_files():
    """：校验关键文件（docs/ 等）存在性。返回缺失列表。"""
    missing = []
    for f in KEY_FILES:
        if not os.path.exists(os.path.join(ROOT, f)):
            missing.append(f)
    return missing

def _touches_tested(files):
    """暂存区是否涉及被测工具 / 测试 / 测试文档。"""
    for f in files:
        if f.startswith("tools/") or f.startswith("tests/") or f == "docs/TOOLS.md":
            return True
    return False

def maybe_run_test_suite(files):
    """若暂存区涉及被测工具/测试/测试文档，则跑回归套件；失败返回 False 阻止提交。

    放在泄漏检查与关键文件检查之后、打印「检查通过」之前——比 check_all.py 更早拦截
    回归（提交即拦），且对纯文档/纯研究提交不增加任何延迟。
    """
    if not _touches_tested(files):
        return True
    runner = os.path.join(ROOT, "tests", "run_all.py")
    if not os.path.isfile(runner):
        return True
    print("检测到工具/测试改动，运行回归套件（tests/run_all.py）…")
    try:
        r = subprocess.run([sys.executable, runner], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=180)
    except Exception as e:
        print(f"  回归套件运行异常：{e}（请手动运行 python tests/run_all.py 确认）")
        return False
    out = (r.stdout or "") + (r.stderr or "")
    # 仅截取尾部以避免刷屏，但保留 TOTAL 行
    print(out[-2000:])
    if r.returncode != 0:
        print("回归套件未全过，已阻止提交。请修复后再试。")
        return False
    print("回归套件通过。")
    return True

def main():
    auto_commit = "--commit" in sys.argv
    files = staged_files()
    leaks = [f for f in files if is_internal(f)]

    if leaks:
        print("检测到不应提交的内部文件，已阻止：")
        for f in leaks:
            print(f"  - {f}")
        print("\n如需移除这些文件：")
        print("  git reset HEAD -- <file>    # 取消暂存")
        print("  或已确认不再需要则 git rm --cached <file>")
        sys.exit(1)

    missing = check_key_files()
    if missing:
        print("关键文件缺失，已阻止提交：")
        for f in missing:
            print(f"  - {f}")
        print("\n请先用 git checkout -- <path> 从 git 历史恢复，或确认删除意图后再提交。")
        sys.exit(1)

    if not maybe_run_test_suite(files):
        sys.exit(1)

    if not files:
        print("暂存区为空，无需提交。")
        sys.exit(0)

    print("检查通过：暂存区无内部文件。")
    if auto_commit:
        print("（未自动提交，请手动执行 git commit）")

    sys.exit(0)

if __name__ == "__main__":
    main()
