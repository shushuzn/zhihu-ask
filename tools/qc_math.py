"""quality_check 子模块（从 quality_check.py 拆分）：qc_math 相关检查。"""
import re
from tools.qc_common import MATH_UNICODE_CHARS

def check_math_formula(body):
    """检测数学公式是否用 LaTeX 书写（md 公式一律 $...$ LaTeX，
    docx 由 report_to_docx.py 转 OMML；禁止 Unicode 手写公式）。

    判定：正文行内 $...$ 包裹之外的数学特征字符（√∫∥∑⊕⊗∈等）即报"Unicode 手写公式"。
    表格数据行（^| 开头）：**表格内禁公式**——表格单元格内出现 $...$ 或数学 Unicode 字符即报"表格内公式"，
    涉及公式的内容一律 LaTeX 正文叙述，表格只承载不涉及公式的文字对比。
    豁免：
    - 参考文献区（仅检查正文部分，scan_body 已分离 body）；
    - 图表引用行（![...](...)）；
    - 表格分隔行（|---|）；
    - 常用非数学用法：± 单独使用（公差语义）、× 用于中文数词搭配（如"1×1"仍属数学
      判定，但"人×天"类非数学量纲搭配不拦——按出现数学邻域综合判断）。
    """
    issues = []
    # 单字符逐个出现且周围非中文语境的多字符组合判定：避免"（≤5 个）"等中文句误报
    for i, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("!["):
            continue
        if re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", line):
            continue
        if line.strip().startswith("|"):
            # 表格数据行：涉及公式的内容不得表格化
            if "$" in line:
                issues.append((i, "表格内公式", "涉及公式的内容用 LaTeX 正文叙述，不制作表格", line.strip()[:60]))
            else:
                hits = [ch for ch in MATH_UNICODE_CHARS if ch in line]
                if hits:
                    issues.append((i, "表格内公式", "涉及公式的内容用 LaTeX 正文叙述，不制作表格",
                                   line.strip()[:60] + f"  → 命中: {''.join(sorted(set(hits)))[:12]}"))
            continue
        # 找出 $...$ 片段并剔除
        stripped = re.sub(r"\$[^$]*\$", "", line)
        if not stripped:
            continue
        # 人名间隔号豁免：中文/字母人名中的 ·（"迈克尔·克拉西奥斯""爱伦·坡"）非数学符号
        stripped = re.sub(r"[\u4e00-\u9fffA-Za-z]·[\u4e00-\u9fffA-Za-z]", "", stripped)
        hits = [ch for ch in MATH_UNICODE_CHARS if ch in stripped]
        if hits:
            issues.append((i, "Unicode手写公式", "数学公式须用 LaTeX $...$（禁止 Unicode 手写）",
                           line.strip()[:60] + f"  → 命中: {''.join(sorted(set(hits)))[:12]}"))
    return issues

