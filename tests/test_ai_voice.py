#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_ai_voice.py 单元测试：去 AI 腔检查"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_ai_voice as av

PASS = 0
FAIL = 0
TOTAL = 0


def expect(name, cond, detail=""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


# ---- 硬伤：固定禁用表达 ----
hard = av.check_hard("众所周知，该模型表现优秀。")
expect("hard+ 众所周知拦截", any("空转过渡" in h[1] for h in hard), hard)

hard = av.check_hard("需要强调的是，该数值为42。")
expect("hard+ 需要强调拦截", any("空转过渡" in h[1] for h in hard), hard)

hard = av.check_hard("这不是简单的测试，而是复杂的问题。")
expect("hard+ 立靶子句式拦截", any("不是" in h[1] for h in hard), hard)

hard = av.check_hard("纯事实陈述，无禁用表达。")
expect("hard- 正常语句通过", not hard, hard)

# ---- 硬伤：标题禁词 ----
hard = av.check_title_words("# 必须清楚的模型能力")
expect("title+ 标题禁词拦截", len(hard) > 0, hard)

hard = av.check_title_words("# 模型能力的解析")
expect("title- 正常标题通过", not hard, hard)

# ---- 提示：启发式 ----
warn = av.check_warn("该模型具有革命性的提升。")
expect("warn+ 装饰词提示", any("装饰词" in h[1] for h in warn), warn)

warn = av.check_warn("这是简单的事实陈述。")
expect("warn- 正常语句无提示", not warn, warn)

# ---- 破折号 ----
dashes = av.check_dashes("该模型性能提升明显——这是经过大量实验验证得出的结论，其统计显著性经过了严格检验且排除了多种干扰因素。")
expect("dash+ 长插入语提示", len(dashes) > 0, dashes)

dashes = av.check_dashes("该模型性能提升明显——经验证。")
expect("dash- 短解释通过", not dashes, dashes)

# ---- 参考文献区不适用正文行检查（著录题名可含合法标点） ----
ref_text = ("正文叙述段。\n\n## 参考文献\n\n"
            "[1] 博客园. 系统论 (十二)——混沌中的系统：复杂性、时间与形态的动态[EB/OL]. "
            "(2025-06-12)[2026-08-16]. https://example.com/p/1.")
dashes = av.check_dashes(ref_text)
expect("dash- 参考文献题名破折号跳过", not dashes, dashes)

hard = av.check_hard(ref_text)
expect("hard- 参考文献区硬伤规则跳过", not hard, hard)

warn = av.check_warn(ref_text)
expect("warn- 参考文献区启发式跳过", not warn, warn)

quotes = av.check_quotes(ref_text)
expect("quote- 参考文献区引号跳过", not quotes, quotes)

titles = av.check_title_words(ref_text)
expect("title- 参考文献标题行跳过", not titles, titles)

# ---- 正文区检查不受参考文献截断影响 ----
dashes = av.check_dashes("正文有长插入语——这是经过大量实验验证得出的结论，其统计显著性经过了严格检验且排除了多种干扰因素。\n\n## 参考文献\n\n[1] 题名。[EB/OL]. https://example.com.")
expect("dash+ 参考文献前正文仍检查", len(dashes) > 0, dashes)

# ---- 引号 ----
quotes = av.check_quotes("他说了\"消失\"的话。")
expect("quote+ 引号包裹日常词提示", len(quotes) > 0, quotes)

quotes = av.check_quotes("他说了\"机器学习\"的话。")
expect("quote- 术语引号通过", not quotes, quotes)

print(f"\nPASS={PASS} FAIL={FAIL}")
if FAIL > 0:
    sys.exit(1)
