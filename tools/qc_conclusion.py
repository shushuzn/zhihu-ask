"""quality_check 子模块（从 quality_check.py 拆分）：qc_conclusion 相关检查。"""
import re

def extract_conclusion(full):
    """提取 H1 标题后的无标题结论段（位于首个 heading 之前）。

    结论段定义：紧跟 H1 标题、且位于首个 heading（## 或 ###）之前的连续
    段落。若该区域不存在（H1 后首行即为标题），返回 ("", False) 表示结论段
    被标题占用/缺失——交由 check_report_structure 报硬伤，此处不重复报。

    修订：原正则 `^# [^\\n]*\\n\\n(.*?)(?=^##\\s|$)` 在 `## 结论` 紧贴标题时
    捕获到空文本，导致"结论过长/分点"检查全部空跑通过（本次缺口根因）。
    改为显式定位 H1 后首个非空内容，非标题才视为结论段。
    """
    m = re.search(r"^#\s+[^\n]*\n(.*)$", full, re.S)
    if not m:
        return ("", False)
    rest = re.sub(r"^\s*\n", "", m.group(1))
    if re.match(r"^#{1,6}\s+", rest):
        return ("", False)
    end_m = re.search(r"^#{1,6}\s+", rest, re.M)
    concl = rest[:end_m.start()] if end_m else rest
    concl = concl.strip()
    # 结论为单段：取首个空行之前
    para = re.split(r"\n\s*\n", concl, 1)[0].strip()
    return (para, True)

def check_conclusion_len(full):
    """检测结论章节篇幅（结论控制在 300 字符内，含标题）。

    结论应为事实归并的浓缩，一两句话点明最终判断；过长说明把正文内容
    重复了一遍；如确实需要更多要点，应精简句式而非堆叠。核心要素
    （最终判断/关键数字/方法名）不得为压缩而删除。
    """
    issues = []
    text, ok = extract_conclusion(full)
    if not ok:
        return issues  # 缺失/被标题占用由 check_report_structure 报硬伤
    length = len(text)
    if length > 300:
        issues.append((0, "结论过长", f"结论 {length} 字符 > 300 上限", f"结论章节 {length} 字符"))
    return issues

def check_conclusion_style(full):
    """检测结论章节格式（结论应为一段式总述，禁止分点列条；禁止分层帽子词）。

    匹配：结论章节内出现以 - 或 * 开头的列表行（分点式结论）；
    或以"XX层面，/XX端，/XX方面，/XX上，"开头的分层骨架句式。
    说明：结论是对上述报告的一段自然叙事式事实归并，不以 bullet 或
    "层面/端/方面"分层罗列；信息用分号在段落内串联。
    """
    issues = []
    text, ok = extract_conclusion(full)
    if not ok:
        return issues
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if re.match(r"^\s*[-*]\s+", stripped):
            issues.append((i, "结论分点", "结论应一段式总述，禁分点", stripped[:60]))
        elif re.match(r"^[^，。；]{1,8}层面[，,]|^[^，。；]{1,8}端[，,]|^[^，。；]{1,8}方面[，,]|^[^，。；]{1,8}上[，,]", stripped):
            issues.append((i, "结论分层", "结论禁'XX层面/端/方面'分层骨架", stripped[:60]))
    return issues

def check_cross_ref(body):
    """检测旧式编号交叉引用有效性（正文"见 2.x / 2.x 节 / 2.x/2.y 节"必须指向存在的编号小节）。

    只匹配明确的旧式编号引用："见 2.5"、"2.5 节"、"2.5/2.6 节"；
    不匹配："Industry 5.0"、"4IR/5IR"等版本号/产品名（无"见"前导且无"节"后缀）。
    当前无编号小节报告不使用此规则；标题类交叉引用由人工核对。
    """
    issues = []
    exist = set(re.findall(r"^###\s*(\d\.\d+)\b", body, re.M))
    pat = re.compile(r"(?:见\s*|\s+)?(\d\.\d+)(?:/(\d\.\d+))?\s*节")
    for i, line in enumerate(body.splitlines(), 1):
        refs = set()
        for m in pat.finditer(line):
            refs.add(m.group(1))
            if m.group(2):
                refs.add(m.group(2))

        for m in re.finditer(r"见\s*(\d\.\d+)", line):
            refs.add(m.group(1))
        for r in refs:
            if r not in exist:
                issues.append((i, "交叉引用错误", f"引用 {r} 但该小节不存在", line.strip()[:60]))
    return issues

