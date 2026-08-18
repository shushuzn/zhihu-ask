# -*- coding: utf-8 -*-
"""LaTeX syntax check module."""
import re


def check_latex_syntax(body):
    """Check LaTeX syntax: $...$ pairing, $$...$$ pairing, symbol conventions, typo detection."""
    issues = []
    lines = body.splitlines()

    # 1. $...$ pairing (inline math)
    for i, line in enumerate(lines, 1):
        dollar_count = len(re.findall(r'(?<!\\)\$', line))
        if dollar_count % 2 == 1:
            issues.append((i, "LaTeX\u8bed\u6cd5", "\u884c\u5185\u516c\u5f0f $...$ \u672a\u95ed\u5408\uff08\u5355 $ \u6570\u91cf\u4e3a\u5947\u6570\uff09", line.strip()[:60]))

    # 2. $$...$$ pairing (display math)
    full_text = "\n".join(lines)
    display_dollar_count = len(re.findall(r'(?<!\\)\$\$', full_text))
    if display_dollar_count % 2 == 1:
        issues.append((0, "LaTeX\u8bed\u6cd5", "\u5757\u7ea7\u516c\u5f0f $$...$$ \u672a\u95ed\u5408\uff08\u5355 $$ \u6570\u91cf\u4e3a\u5947\u6570\uff09", full_text[:60]))

    # 3. Convention checks: recommended LaTeX symbols
    for i, line in enumerate(lines, 1):
        # middle dot (non-name) -> \cdot
        stripped = re.sub(r'[\u4e00-\u9fffA-Za-z]\xb7[\u4e00-\u9fffA-Za-z]', "", line)
        if "\xb7" in stripped:
            issues.append((i, "LaTeX\u89c4\u8303", "\u5efa\u8bae\u7528 \\cdot \u4ee3\u66ff\u5c45\u4e2d\u70b9 \xb7\uff08\u6570\u5b66\u516c\u5f0f\u4e2d\uff09", line.strip()[:60]))
        checks = [
            ("\u2265", "\\ge", "\u2265"),
            ("\u2264", "\\le", "\u2264"),
            ("\xd7", "\\times", "\xd7"),
            ("\u2260", "\\neq", "\u2260"),
            ("\u2248", "\\approx", "\u2248"),
            ("\u221e", "\\infty", "\u221e"),
            ("\u2211", "\\sum", "\u2211"),
            ("\u220f", "\\prod", "\u220f"),
            ("\u222b", "\\int", "\u222b"),
            ("\u221a", "\\sqrt", "\u221a"),
            ("\u2208", "\\in", "\u2208"),
            ("\u2209", "\\notin", "\u2209"),
            ("\u2282", "\\subset", "\u2282"),
            ("\u2283", "\\supset", "\u2283"),
            ("\u2286", "\\subseteq", "\u2286"),
            ("\u2287", "\\supseteq", "\u2287"),
            ("\u2192", "\\to", "\u2192"),
            ("\u2190", "\\leftarrow", "\u2190"),
            ("\u21d2", "\\Rightarrow", "\u21d2"),
            ("\u21d0", "\\Leftarrow", "\u21d0"),
        ]
        for sym, cmd, sym_char in checks:
            if sym_char in line:
                issues.append((i, "LaTeX\u89c4\u8303", f"\u5efa\u8bae\u7528 {cmd} \u4ee3\u66ff {sym_char}", line.strip()[:60]))

    # 4. Environment pairing: \begin{...} \end{...}
    full_text = "\n".join(body.splitlines())
    begin_envs = re.findall(r"\\begin\{([a-zA-Z*]+)\}", full_text)
    end_envs = re.findall(r"\\end\{([a-zA-Z*]+)\}", full_text)
    env_counts = {}
    for env in begin_envs:
        env_counts[env] = env_counts.get(env, 0) + 1
    for env in end_envs:
        env_counts[env] = env_counts.get(env, 0) - 1
    for env, count in env_counts.items():
        if count != 0:
            issues.append((0, "LaTeX\u8bed\u6cd5", f"\u6570\u5b66\u73af\u5883 \\begin{{{env}}} \u4e0e \\end{{{env}}} \u6570\u91cf\u4e0d\u5339\u914d", ""))

    # 5. Common typo detection
    common_typos = {
        r"\\alph": r"\\alpha",
        r"\\bet": r"\\beta",
        r"\\gama": r"\\gamma",
        r"\\delte": r"\\delta",
        r"\\epsion": r"\\epsilon",
        r"\\theata": r"\\theta",
        r"\\lamda": r"\\lambda",
        r"\\sigama": r"\\sigma",
        r"\\omege": r"\\omega",
        r"\\partical": r"\\partial",
        r"\\infinity": r"\\infty",
        r"\\summation": r"\\sum",
        r"\\product": r"\\prod",
    }
    for i, line in enumerate(lines, 1):
        for typo, correct in common_typos.items():
            if re.search(typo, line):
                issues.append((i, "LaTeX\u62fc\u5199", f"\u7591\u4f3c\u62fc\u5199\u9519\u8bef {typo} -> \u5e94\u4e3a {correct}", line.strip()[:60]))

    return issues
