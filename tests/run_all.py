"""工具回归测试套件运行器（aggregator）。

发现 tests/test_*.py 并逐个以子进程运行，解析每模块的 PASS/FAIL 汇总，
输出每模块状态与 TOTAL。任一模块失败（FAIL>0 或退出码非 0）则整体退出码 1。

运行：python tests/run_all.py
"""
import os
import re
import sys
import glob
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
PY = sys.executable


def main():
    mods = sorted(glob.glob(os.path.join(TESTS, "test_*.py")))
    total_pass = 0
    total_fail = 0
    any_bad = False

    print("=" * 70)
    print("工具回归测试套件")
    print("=" * 70)

    for m in mods:
        name = os.path.basename(m)
        try:
            r = subprocess.run([PY, m], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
        except Exception as e:  # 运行异常（如导入错误）
            print(f"  [FAIL] {name}: 运行异常 {e}")
            any_bad = True
            continue
        out = (r.stdout or "") + (r.stderr or "")
        # 取最后一个 TOTAL 行：测试模块若自身调用子进程（如 git_protect 的
        # maybe_run_test_suite 回显），会被嵌套输出干扰；用最后一个（模块自身汇总）
        # 才是权威结果，避免误报 / 掩盖真实失败。
        matches = re.findall(r"PASS=(\d+)\s+FAIL=(\d+)", out)
        if matches:
            p, f = int(matches[-1][0]), int(matches[-1][1])
        else:
            # 无标准汇总行：尝试解析 unittest 风格输出（"Ran N tests ... OK/FAILED"）
            ran = re.search(r"Ran (\d+) tests? in", out)
            if ran and "OK" in out:
                p, f = int(ran.group(1)), 0
            elif ran:
                fail_m = re.search(r"FAILED\s*\([^)]*failures=(\d+)", out)
                p, f = 0, int(fail_m.group(1)) if fail_m else 1
            else:
                # 无任何汇总信息：以退出码判定
                p, f = (0, 0) if r.returncode == 0 else (0, 1)
        total_pass += p
        total_fail += f
        bad = f > 0 or r.returncode != 0
        any_bad = any_bad or bad
        status = "OK" if not bad else "FAIL"
        print(f"  [{status}] {name}: PASS={p} FAIL={f} exit={r.returncode}")

    print("-" * 70)
    print(f"TOTAL: PASS={total_pass} FAIL={total_fail}")
    print("=" * 70)
    sys.exit(1 if any_bad else 0)


if __name__ == "__main__":
    main()
