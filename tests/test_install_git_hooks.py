"""install_git_hooks.py 回归测试：pre-commit hook 安装/移除（8 项）。

覆盖：
- HOOK_TEMPLATE 内容：必须调用 git_protect.py（保护链路的执行核心）、
  含 exit 0、标记勿手动编辑——模板回归会静默禁用提交保护
- 安装：写 hook 文件且内容与模板一致（HOOK_PATH 打补丁到临时 .git/hooks）
- 移除：删除已装 hook / 未装时提示不报错
- hooks 目录缺失：报错退出

运行：python tests/test_install_git_hooks.py
"""
import os
import sys
import tempfile
import shutil
from unittest import mock

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import install_git_hooks as igh

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- 模板内容（保护链路执行核心） ----
expect("tpl+ 调用 git_protect", "python3 tools/git_protect.py" in igh.HOOK_TEMPLATE, True)
expect("tpl+ 失败退出", "exit 1" in igh.HOOK_TEMPLATE, True)
expect("tpl+ 成功退出", "exit 0" in igh.HOOK_TEMPLATE, True)
expect("tpl+ 勿手动编辑标记", "勿手动编辑" in igh.HOOK_TEMPLATE, True)
expect("tpl+ 仓库根定位", "git rev-parse --show-toplevel" in igh.HOOK_TEMPLATE, True)

# ---- 安装 / 移除（HOOK_PATH 打补丁） ----
tmp = testutil.mktestdir()
hooks = os.path.join(tmp, ".git", "hooks")
os.makedirs(hooks, exist_ok=True)
hook_path = os.path.join(hooks, "pre-commit")
try:
    with mock.patch("install_git_hooks.HOOK_PATH", hook_path), \
         mock.patch("sys.argv", ["install_git_hooks.py"]):
        igh.main()
    expect("hook+ 安装后文件存在", os.path.exists(hook_path), True)
    with open(hook_path, "r", encoding="utf-8") as f:
        content = f.read()
    expect("hook+ 内容与模板一致", content == igh.HOOK_TEMPLATE, True)

    with mock.patch("install_git_hooks.HOOK_PATH", hook_path), \
         mock.patch("sys.argv", ["install_git_hooks.py", "--remove"]):
        igh.main()
    expect("hook- 移除后文件不存在", os.path.exists(hook_path), False)

    # 未装时再移除：不报错
    with mock.patch("install_git_hooks.HOOK_PATH", hook_path), \
         mock.patch("sys.argv", ["install_git_hooks.py", "--remove"]):
        try:
            igh.main()
            expect("hook+ 未装移除不抛错", True, True)
        except SystemExit as e:
            expect("hook- 未装移除不应退出", e.code, None)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- hooks 目录缺失 ----
tmp2 = testutil.mktestdir()
try:
    with mock.patch("install_git_hooks.HOOK_PATH", os.path.join(tmp2, ".git", "hooks", "pre-commit")), \
         mock.patch("sys.argv", ["install_git_hooks.py"]):
        try:
            igh.main()
            expect("hook- 缺 hooks 目录应退出", False, True)
        except SystemExit as e:
            expect("hook- 缺 hooks 目录退出码 1", e.code, 1)
finally:
    shutil.rmtree(tmp2, ignore_errors=True)


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
