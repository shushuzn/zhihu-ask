#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""latex_unicode.py 单元测试：LaTeX → Unicode 公式转换"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import latex_unicode as lu

PASS = 0
FAIL = 0
TOTAL = 0


def expect(name, got, must_be):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  [FAIL] {name} got={got!r} want={must_be!r}")


expect("frac+ 分数", lu.latex_to_unicode(r"\frac{a}{b}"), "(a)/(b)")
expect("sqrt+ 根号", lu.latex_to_unicode(r"\sqrt{x}"), "√(x)")
expect("sup+ 上标", lu.latex_to_unicode(r"x^{2}"), "x^2")
expect("sub+ 下标", lu.latex_to_unicode(r"x_{1}"), "x_1")
expect("sym+ 希腊字母", lu.latex_to_unicode(r"\delta + \lambda"), "δ + λ")
expect("sym+ 运算符", lu.latex_to_unicode(r"a \times b \leq c"), "a × b ≤ c")
expect("sym+ 箭头/无穷", lu.latex_to_unicode(r"n \to \infty"), "n → ∞")
expect("text+ 文本命令", lu.latex_to_unicode(r"\text{求和}"), "求和")
# 嵌套分数为已知限制（_FRAC 正则不递归），只断言外层转换
expect("frac+ 嵌套分数外层", lu.latex_to_unicode(r"\frac{1}{1+\frac{2}{3}}"), "(1)/(1+\\frac{2}{3})")
expect("mix+ 组合", lu.latex_to_unicode(r"x_1 = \frac{\sqrt{2}}{2}"), "x_1 = (√(2))/(2)")
expect("plain+ 纯文本不变", lu.latex_to_unicode("普通文本 123"), "普通文本 123")
# 美元符剥离由调用方（wechat_publish）处理，本函数不负责
expect("dollar+ 保留美元符（调用方剥离）", lu.latex_to_unicode(r"$\lambda_1$"), "$λ_1$")
expect("prod+ 连乘", lu.latex_to_unicode(r"\prod_{i=1}^{n} x_i"), "∏_i=1^n x_i")

print(f"\nPASS={PASS} FAIL={FAIL}")
if FAIL > 0:
    sys.exit(1)
