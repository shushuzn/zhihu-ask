"""quality_check 子模块（从 quality_check.py 拆分）：qc_ref 相关检查。"""
import re
from tools.qc_common import NOTE_REF_MARKERS, REF_BAD_LABELS, REF_MARKERS

def check_references(full, note_mode=False):
    """检查参考文献区：条目行尾不得带"一手/二手/推断"等分级标注（来源类型只写在笔记来源段，报告正文不出现分级括注）。
    仅针对参考文献区（从 ## 参考文献 / 笔记「来源:」起到文末）内的条目行。"""
    issues = []
    markers = NOTE_REF_MARKERS if note_mode else REF_MARKERS
    start = None
    for marker in markers:
        idx = full.find(marker)
        if idx != -1:
            start = idx
            break
    if start is None:
        return issues
    section = full[start:]
    for i, line in enumerate(section.splitlines(), 1):
        stripped = line.strip()
        if not re.search(r"\[[^\]]+\]\([^)]+\)", stripped):
            continue

        tail = re.sub(r"^.*\]\([^)]*\)", "", stripped)
        for label in REF_BAD_LABELS:
            if f"— {label}" in tail or f"：{label}" in tail:
                issues.append((i, "参考文献标注", f"链接后带 [{label}]", stripped[:60]))
                break
    return issues

def check_ref_latex_ban(full, note_mode=False):
    """检查参考文献区禁止 LaTeX。

    理由：GB/T 7714-2015 著录是纯文本格式（作者. 题名[类型]. 出版信息.），
    数学符号应直接用 Unicode/文字（如"π""10⁶"），$...$ LaTeX 会破坏著录结构
    且 docx 转换器（report_to_docx.py）对参考文献区的 $ 不做 OMML 转换。
    命中即硬伤：$...$ / $$...$$ 出现在参考文献区（## 参考文献 / 笔记「参考文献:」之后；
    「来源:」为非规定字段，不算文献区）。
    """
    issues = []
    # marker 用行首正则匹配 + 行偏移累计定位——find() 子串会命中
    # 正文的"一手来源:..."，把正文 $...$ 误判为参考文献区（chang-yang 笔记质检踩坑）。
    head_re = (re.compile(r"^\s*参考文献[:：]?|^#{1,6}\s*参考文献")
               if note_mode else re.compile(r"^#{1,6}\s*参考文献"))
    start = None
    offset = 0
    for line in full.splitlines():
        if head_re.match(line):
            start = offset
            break
        offset += len(line) + 1  # 含换行符
    if start is None:
        return issues
    section = full[start:]
    for i, line in enumerate(section.splitlines(), 1):
        stripped = line.strip()
        # 跳过空行/分隔行
        if not stripped:
            continue
        m = re.search(r"\$[^$]*\$", stripped)
        if m:
            issues.append((i, "参考文献LaTeX", f"参考文献区禁止 LaTeX（$...$），数学符号用 Unicode/文字", stripped[:60]))
    return issues

def check_unsourced_numbers(body, full=None):
    """启发式：行内出现"约 X 元/万亿/亿/万"等数字表述但同行无来源字样。
    跳过表格行（| 开头）与列表项（- 开头且带来源括注），因表格/列表数字通常在行内或表前已说明来源。
    来源特征词含来源/口径/媒体等，与项目"每个数字可溯源"约定配套。
正文按 GB/T 7714-2015 顺序编码制标注 [n] 引注，来源归文末「参考文献」区——报告含参考文献
    节（必需结构）即跳过本检查，正文无来源数字属合规。"""
    if full and "参考文献" in full:
        return []
    source_words = (
        r"(来源|据|数据|报道|推算|口径|官方|媒体|实测|参考|定价|备查|"
        r"一手|二手|计算|估算|预算|决算|公布|披露|统计)"
    )
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("|"):
            continue
        if stripped.startswith("!["):

            continue
        if re.search(r"[约|超过|高达]\s*[\d.]+", line):
            if not re.search(source_words, line):
                issues.append((i, "无来源数字(待确认)", stripped[:60]))
    return issues

def check_citation_correspondence(full, note_mode=False):
    """检测参考文献条目与正文 [n] 引注一一对应（flomo 上传质检，笔记模式强制）。

    顺序编码制规则（不能少、不能多、须一一对应）：
    1. 参考文献区每条 [n] 须在正文出现 [n] 引注（文献未被引用即报错）；
    2. 正文每个 [n] 引注须有对应文献条目（悬空引注即报错）；
    3. 二者编号集合须完全一致。

    以「来源:」「参考文献:」（笔记）或「## 参考文献」（报告）为界划分正文/文献区，
    文献区自身的 [n] 条目不计入正文引注。无参考文献区时返回 []（不触发）。
    """
    if note_mode:
        m = re.search(r"(?:^|\n)\s*(?:来源|参考文献)[:：]?\s*$", full, re.MULTILINE)
    else:
        m = re.search(r"(?:^|\n)\s*#{1,6}\s*参考文献\s*$", full, re.MULTILINE)
    if not m:
        return []
    head = full[:m.start()]
    ref_sec = full[m.end():]
    ref_nums = set(int(x) for x in re.findall(r"^\[(\d+)\]", ref_sec, re.MULTILINE))
    cite_nums = set(int(x) for x in re.findall(r"\[(\d+)\]", head))
    issues = []
    missing = sorted(ref_nums - cite_nums)
    orphan = sorted(cite_nums - ref_nums)
    if missing:
        issues.append((0, "文献未被引用",
                       f"参考文献 {missing} 未在正文标注 [n] 引用（须一一对应，不能少）", ""))
    if orphan:
        issues.append((0, "引用无对应文献",
                       f"正文 [n] {orphan} 无对应参考文献条目（须一一对应，不能多）", ""))
    return issues

def check_internal_refs(body):
    """检测内部工具标识泄漏（成品禁"flomo/内部笔记/信号笔记"等来源标识）。

    匹配：flomo / 内部笔记 / 信号笔记 / gathered_ / verify_*.py 出现在正文或参考文献；
    以及六通道检索过程痕迹词：智慧芽 / 企查查 / 通达信 /
    产业无对应 / 无适用主体 / 无约定主题布局——C 通道"无命中"是内部研究记录，
    落 process_notes 与进度文件，禁止写进正文（对读者无信息量）。
    说明：成品报告引用须为公开来源；内部素材（flomo 笔记/检索记录/验证脚本）不入成品，
    改为引用其对应的公开出处或删除（验证脚本只留存研究目录，不写入正文）。
    禁止在参考文献中使用 flomo 笔记地址（v.flomoapp.com）作为来源。
    """
    issues = []
    internal_words = ["flomo", "内部笔记", "信号笔记", "gathered_",
                      "智慧芽", "企查查", "通达信", "产业无对应", "无适用主体", "无约定主题布局"]
    internal_re = re.compile(r"verify_[\w-]+\.py", re.I)
    # flomo 笔记地址禁止作为参考文献来源
    flomo_url_re = re.compile(r"https?://v\.flomoapp\.com/")
    for i, line in enumerate(body.splitlines(), 1):
        for w in internal_words:
            if w.lower() in line.lower():
                issues.append((i, "内部标识", w, line.strip()[:60]))
                break
        else:
            m = internal_re.search(line)
            if m:
                issues.append((i, "内部标识", m.group(0), line.strip()[:60]))
                continue
        # 单独检测 flomo URL（即使不含 "flomo" 关键词也拦截域名）
        if flomo_url_re.search(line):
            issues.append((i, "非公开来源", "flomo 笔记地址不可作参考文献", line.strip()[:60]))
    return issues

def check_grade_paren(body):
    """检测正文分级词括注（正文禁止"（一手/二手/推算）"等数据强度括注）。

    匹配：括号内含 一手/二手/推算/推断/观点类/分析性推断 等数据强度分级词。
    不匹配："日本二手设备"（物理含义）、"单一手段"（相邻字误匹配——用括号限定）、
    表格"证据强度"列（| 官方 | 等已改中性词）。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if re.search(r"[（(][^（）()]*(?:一手|二手|推算|推断|观点类|分析性推断)[^（）()]*[）)]", line):
            issues.append((i, "分级词括注", "（一手/二手/推算）", line.strip()[:60]))
    return issues

def check_evidence_grade(body):
    """检测证据分级表述（用户要求：正文不写"证据较强/证据中等/证据强度"等分级词）。

    匹配：证据较强/证据中等/证据较弱/证据强度 等字面（含"证据强度不同"引导句）。
    不匹配："证据"单独使用（"反方证据""证据链"为正常表述）。
    """
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if re.search(r"证据(较强|中等|较弱|强度)", line):
            issues.append((i, "证据分级词", "证据较强/证据强度（禁止）", line.strip()[:60]))
    return issues

def check_stock_info(body):
    """检测 A 股行情信息（用户要求：报告禁止提及股票代号、股价等 A 股信息）。

    匹配三类：
    1. 股票代码：行内 6 位纯数字且前后非年份/金额（如 603986、301308、688525），
       常见 A 股代码段前缀（60/00/30/68/83/87）提高命中率；
    2. 股价行情词：现价/收盘价/涨跌幅/涨停/跌停/总市值/流通市值/PE(TTM)/市盈率
       等字段 + 行内含数字；
    3. 行情表格：表头含"代码|名称|现价"组合。
    不匹配：年份（2026）、普通大数（2828 亿无代码形态）、"代码"泛指。
    """
    issues = []
    code_re = re.compile(r"(?<![0-9A-Za-z])(60[0-9]{4}|00[0-9]{4}|30[0-9]{4}|68[0-9]{4}|83[0-9]{4}|87[0-9]{4})(?![0-9A-Za-z])")
    # 注：A 股代码为 6 位数字（600519/000001/300750 等）；5 位数字（30000 等）不匹配。
    # "涨停/跌停"为基金/期货/股票通用交易描述，非 A 股特有行情字段，不拦截。
    quote_words = ["收盘价", "涨跌幅", "总市值", "流通市值", "PE(TTM)", "市盈率", "换手率"]
    for i, line in enumerate(body.splitlines(), 1):
        has_digit = bool(re.search(r"\d", line))
        if code_re.search(line):
            issues.append((i, "A股行情信息", "股票代码（报告禁止提及 A 股代码）", line.strip()[:60]))
            continue
        # "现价"须后跟数字才判为股价（避免"兑现价值"等词语误报）
        if re.search(r"现价\s*[0-9０-９]", line):
            issues.append((i, "A股行情信息", "现价（报告禁止提及股价）", line.strip()[:60]))
            continue
        if has_digit and any(w in line for w in quote_words):
            issues.append((i, "A股行情信息", "股价/市值等行情字段（报告禁止）", line.strip()[:60]))
            continue
        if "代码" in line and "现价" in line and "名称" in line:
            issues.append((i, "A股行情信息", "行情表格（代码/现价列）", line.strip()[:60]))
    return issues

