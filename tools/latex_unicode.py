# -*- coding: utf-8 -*-
"""LaTeX → 可读 Unicode 文本（公众号 HTML 展示用）。

微信图文 HTML 不支持公式渲染，报告 md 的 $...$ 公式在推送前转为可读
Unicode 文本（如 \frac{a}{b} → (a)/(b)、\sqrt{x} → √(x)、\delta → δ），
避免公式消失或显示 LaTeX 源码。
"""

import re

_FRAC = re.compile(r"\\frac\{((?:[^{}]|\{[^{}]*\})*)\}\{((?:[^{}]|\{[^{}]*\})*)\}")
_SQRT = re.compile(r"\\sqrt\{([^{}]*)\}")
_SUP = re.compile(r"\^\{([^{}]*)\}")
_SUB = re.compile(r"_\{([^{}]*)\}")
_TEXT = re.compile(r"\\(?:text|mathrm|operatorname)\{([^{}]*)\}")

_SYM = {
    "\\delta": "δ", "\\Delta": "Δ", "\\alpha": "α", "\\beta": "β",
    "\\gamma": "γ", "\\theta": "θ", "\\lambda": "λ", "\\mu": "μ",
    "\\pi": "π", "\\sigma": "σ", "\\Sigma": "Σ", "\\omega": "ω",
    "\\Omega": "Ω", "\\phi": "φ", "\\rho": "ρ", "\\tau": "τ",
    "\\ell": "ℓ", "\\times": "×", "\\cdot": "·", "\\leq": "≤",
    "\\geq": "≥", "\\ge": "≥", "\\le": "≤", "\\approx": "≈",
    "\\neq": "≠", "\\in": "∈", "\\infty": "∞", "\\ldots": "…",
    "\\to": "→", "\\rightarrow": "→", "\\pm": "±", "\\partial": "∂",
    "\\nabla": "∇", "\\sum": "Σ", "\\prod": "∏", "\\int": "∫",
    "\\log": "log", "\\exp": "exp", "\\min": "min", "\\max": "max",
    "\\sup": "sup", "\\arg": "arg", "\\lim": "lim", "\\sqrt": "√",
    "\\tilde": "", "\\hat": "", "\\bar": "", "\\vec": "",
    "\\left": "", "\\right": "", "\\big": "", "\\,": "",
    "\\ ": " ", "\\;": " ", "\\!": "",
}


def latex_to_unicode(s):
    """LaTeX 公式文本 → 可读 Unicode 文本。"""
    s = _FRAC.sub(r"(\1)/(\2)", s)
    s = _SQRT.sub(r"√(\1)", s)
    s = _SUP.sub(r"^\1", s)
    s = _SUB.sub(r"_\1", s)
    # 按 key 长度降序替换，避免短键吞噬长键
    # （如 \in 先替换会把 \infty 变成 ∈fty）。
    for k in sorted(_SYM, key=len, reverse=True):
        s = s.replace(k, _SYM[k])
    s = _TEXT.sub(r"\1", s)
    return re.sub(r"\s+", " ", s).strip()
