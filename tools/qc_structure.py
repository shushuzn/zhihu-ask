"""quality_check 子模块（从 quality_check.py 拆分）：qc_structure 相关检查。"""
import re
from tools.qc_common import NOTE_REF_MARKERS, REF_MARKERS, strip_display_math

def check_placeholders(body):
    """检测模板占位符未替换残留（{{...}}），防止模板内容漏发。"""
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        for m in re.finditer(r"\{\{[^{}]*\}\}", line):
            issues.append((i, "模板占位符", m.group(0), line.strip()[:60]))
    return issues

def check_process_words(body):
    """检测成品报告中的过程性字样（SOP 硬性要求：正文禁止"第 N 轮/迭代/更新"等过程字样）。

    匹配：R 轮次（如 R1-R9，含括注形式）、第 N 轮、本轮/上一轮/下一轮、通道 X（检索通道标记）
    等迭代/流程过程标记。
    不匹配：URL 中的字母段（英文 R 数字用单词边界保证，如 4RUO50eR9Gh 不误报）、
    技术名词"迭代/更新"（如算力迭代/数据更新）、"通道"的其他技术含义（如电离通道/信道）。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if re.search(r"[\[（(]\s*R\d+\s*[-–—]?\s*R\d+\s*[\]）)]", stripped) or \
           re.search(r"\bR\d+\b\s*收|收敛\s*[：:（(]?\s*R\d|第\s*\d+\s*轮", stripped) or \
           "本轮" in stripped or "上一轮" in stripped or "下一轮" in stripped or \
           re.search(r"通道\s*[A-Z]", stripped):
            issues.append((i, "过程性字样", "R轮次/第N轮/本轮/通道X", stripped[:60]))
    return issues

def check_paragraph_len(body):
    """：叙述性段落超长检查（STYLE_GUIDE：每段 ≤4-5 行，知乎扫读友好）。

    按空行分段；跳过列表块/表格/标题/图片块（非叙述段）；参考文献区之后不计。
    """
    head = strip_display_math(body.split("## 参考文献")[0])
    paras, cur = [], []
    for line in head.splitlines():
        s = line.rstrip()
        if not s.strip():
            if cur:
                paras.append(cur)
                cur = []
            continue
        cur.append(s)
    if cur:
        paras.append(cur)
    issues = []
    for idx, p in enumerate(paras, 1):
        # 列表/表格/标题/图片行所在段落跳过；有序列表（1. / 1、）同样跳过（不报段落过长）
        if any(l.lstrip().startswith(("-", "*", "|", "#", "!["))
               or re.match(r"^\s*\d+[.、]", l) for l in p):
            continue
        if len(p) > 5:
            issues.append((idx, "段落过长", f"{len(p)} 行 > 5 行（建议拆分）", p[0][:50]))
    return issues

def check_para_points_eligible(body):
    """长段落「建议分点」启发式（能用 1. 2. 3. 分点就用）。

    并列多条同类信息（规格条目/能力清单/分项结果等）应优先用 1. 2. 3. 有序列表，
    禁止写成"第一……第二……"式长段落。机器无法可靠判断"是否并列"，故只做提示级：
    单叙述段字符数超过阈值（默认 300）且无任何分点/表格结构时提示人工复核——
    连续因果/演化逻辑链（推导过程、事件演化）仍允许文字叙述，不阻断。

    返回 (提示列表, 跳过标志)：跳过（非叙述段/已分点/表格段）时返回 ([], True)。
    """
    head = strip_display_math(body.split("## 参考文献")[0])
    paras, cur = [], []
    for line in head.splitlines():
        s = line.rstrip()
        if not s.strip():
            if cur:
                paras.append(cur)
                cur = []
            continue
        cur.append(s)
    if cur:
        paras.append(cur)
    issues = []
    for idx, p in enumerate(paras, 1):
        # 非叙述段跳过：表格/标题/图片/列表/有序列表/代码块
        if any(l.lstrip().startswith(("-", "*", "|", "#", "![", "```"))
               or re.match(r"^\s*\d+[.、]", l) for l in p):
            continue
        n_chars = sum(len(l) for l in p)
        if n_chars > 300:
            issues.append((idx, "长段落建议分点",
                           f"{n_chars} 字符：并列信息建议用 1. 2. 3. 分点或表格（因果链可保留叙述）",
                           p[0][:50]))
    return issues

def check_fact_section_budget(body):
    """检测正文小节内的小点是否未叙述化（用户要求"每个小点不要单行"）。

    仅检查小节内是否存在 bullet 单行（`- ` 行）；小节数量不再设上限。
    表格（`|` 行）是唯一允许的列表形式。
    """
    issues = []

    sec_pat = re.compile(r"^###\s+", re.M)
    secs = [(i, m.start()) for i, m in enumerate(sec_pat.finditer(body), 1)]
    if not secs:
        return issues

    m2 = re.search(r"^#\s+[^\n]*\n", body, re.M)  # H1 标题后起
    m3 = re.search(r"^##\s*参考文献", body, re.M)
    if not m2:
        return issues
    end = m3.start() if m3 else len(body)

    for i, (num, pos) in enumerate(secs):
        nxt = secs[i + 1][1] if i + 1 < len(secs) else end
        seg = body[pos:nxt]

        # 排除表格行（| 开头）和表格分隔行（|---|），只检测真正的 bullet（- 开头）
        bullets = [ln for ln in seg.splitlines()
                   if re.match(r"^\s*-\s+\S", ln)
                   and not re.match(r"^\s*\|", ln)]
        if bullets:
            issues.append((0, "小点未叙述化", f"第{num}节有 {len(bullets)} 条 bullet 单行——小点须写成连贯叙述段（表格行不受此检查限制）",
                           "bullet 单行"))
    return issues

def check_structure(body, full, note_mode=False):
    """结构完整性检查：
    1. 必须存在参考文献章节且含至少 1 条可溯源条目（GB/T 编号 / [标题](url) / 纯文本标题；SOP 硬性要求：纯事实报告可溯源）。
       笔记模式：文献段仅认「参考文献:」（「来源:」为非规定字段，禁止）。
    2. 正文不得残留未决占位标记（TODO/待补充/待填写/此处填写 等；"仍无法核实"为合法口径标注，不在此列）。
    """
    issues = []
    markers = NOTE_REF_MARKERS if note_mode else REF_MARKERS
    start = None
    for marker in markers:
        idx = full.find(marker)
        if idx != -1:
            start = idx
            break
    if start is None:
        issues.append((1, "结构完整性", "缺少参考文献章节（## 参考文献），报告无法溯源", ""))
    else:
        section = full[start:]
        ref_lines = [ln for ln in section.splitlines() if ln.strip()]

        link_count = sum(1 for ln in ref_lines
                         if re.search(r"\[[^\]]+\]\([^)]+\)", ln)
                         or re.match(r"^\d+[.、]\s*\S", ln)
                         or re.match(r"^[-*]\s*\S", ln)
                         or re.match(r"^\[\d+\]\s*\S", ln))  # GB/T 7714-2015 国标条目 [n] 责任者. 题名[M]...
        if link_count == 0:
            issues.append((1, "结构完整性", "参考文献章节为空或条目非 GB/T 编号/[标题](url)/纯文本标题格式", ""))
    for i, line in enumerate(body.splitlines(), 1):
        if re.search(r"(TODO|FIXME|待补充|待填写|待填|此处填写)", line):
            issues.append((i, "未决标记", "待补充/TODO 类残留", line.strip()[:60]))
    return issues

