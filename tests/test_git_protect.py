# -*- coding: utf-8 -*-
"""git_protect.py 回归测试：仅覆盖纯决策逻辑（_touches_tested / maybe_run_test_suite）。

运行：python tests/test_git_protect.py
不触发真正的 git / subprocess（用 Fake 替换），只验证「何时该跑回归套件、何时该拦截」的分流逻辑。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import git_protect as gp

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---------- _touches_tested：分流判定 ----------
expect("touch tools", gp._touches_tested(["tools/foo.py"]), True)
expect("touch tools nested", gp._touches_tested(["tools/dir/x.py"]), True)
expect("touch tests", gp._touches_tested(["tests/test_x.py"]), True)
expect("touch TOOLS.md", gp._touches_tested(["docs/TOOLS.md"]), True)
expect("no-touch docs other", gp._touches_tested(["docs/SOP.md"]), False)
expect("no-touch research", gp._touches_tested(["research/slug/report.md"]), False)
expect("no-touch readme", gp._touches_tested(["README.md"]), False)
expect("no-touch empty", gp._touches_tested([""]), False)
expect("no-touch empty-list", gp._touches_tested([]), False)


# ---------- maybe_run_test_suite：是否拦截 ----------
# Fake 替换 os.path.isfile 与 subprocess.run，避免真实执行 git / 套件
_RUNNER_EXISTS = True
_orig_isfile = gp.os.path.isfile


def _fake_isfile(p):
    if p.replace("\\", "/").endswith("tests/run_all.py"):
        return _RUNNER_EXISTS
    return _orig_isfile(p)


gp.os.path.isfile = _fake_isfile

_calls = []


class _FakeRun:
    def __init__(self, rc):
        self.rc = rc

    def __call__(self, *a, **k):
        _calls.append(1)
        class R:
            pass
        r = R()
        r.returncode = self.rc
        r.stdout = "TOTAL: PASS=1 FAIL=0"
        r.stderr = ""
        return r


# 1) 纯文档提交（不触及 tested 路径）-> 直接通过，不跑套件
_calls.clear()
gp.subprocess.run = _FakeRun(0)
expect("no-touch passes", gp.maybe_run_test_suite(["docs/SOP.md"]), True)
expect("no-touch no-run", _calls, [])

# 2) 触及 tested 但 runner 缺失 -> 放行（不阻塞，提示手动）
_RUNNER_EXISTS = False
_calls.clear()
gp.subprocess.run = _FakeRun(0)
expect("touch-but-no-runner passes", gp.maybe_run_test_suite(["tools/x.py"]), True)

# 3) 触及 tested 且 runner 存在且套件通过 -> 放行
_RUNNER_EXISTS = True
_calls.clear()
gp.subprocess.run = _FakeRun(0)
expect("touch-runner-pass passes", gp.maybe_run_test_suite(["tools/x.py"]), True)
expect("touch-runner did-run", len(_calls) > 0, True)

# 4) 触及 tested 且 runner 存在但套件失败 -> 拦截（返回 False）
_calls.clear()
gp.subprocess.run = _FakeRun(1)
expect("touch-runner-fail blocks", gp.maybe_run_test_suite(["tests/test_x.py"]), False)


if __name__ == "__main__":
    print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
    sys.exit(1 if FAIL else 0)
