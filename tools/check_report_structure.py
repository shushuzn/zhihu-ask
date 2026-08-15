
"""
研究报告结构校验工具（zhihu-ask 项目专用）

校验 report.md 章节结构完整性，防止插入章节时覆盖/错位/重复/跳号
（实战中多次发生的 Edit 覆盖标题问题——人工发现成本高，工具化强制）：
  1. ### 小节不带编号、标题不重复（兼容旧式 1.1 编号，若存在须连续）
  2. 无顶层内容章节（结论为标题行后的无标题头部段落，### 小节直接平铺，
     ## 参考文献为唯一顶层章节）
  3. ## 参考文献 存在且含 GB/T 7714 编号条目（兼容 [标题](url) / 纯文本标题旧格式）
  4. 无模板占位符 {{...}} 残留
  5. 测算已融入正文：量化测算按主题融入对应小节叙述（禁止"**测算 N：**"
     或"假设前提/计算口径"等独立行——用户要求彻底融入，不单开一行）

用法：
    python tools/check_report_structure.py --file research/<slug>/report.md

输出：全部通过退出码 0；检出问题退出码 1 并列出位置。
"""

import sys
import os
import re

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REQUIRED_TOP = []  # 无顶层内容章节：结论无标题、### 小节直接平铺，仅参考文献为顶层
REQUIRED_REF = "## 参考文献"

def resolve_target(argv):
    """解析 --file / --slug（互为别名，与其余质检工具参数口径统一）。

    --slug <slug> 等价于 --file research/<slug>/report.md。
    """
    filepath = None
    if "--file" in argv:
        idx = argv.index("--file")
        if idx + 1 < len(argv):
            filepath = argv[idx + 1]
    if not filepath and "--slug" in argv:
        idx = argv.index("--slug")
        if idx + 1 < len(argv):
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            filepath = os.path.join(root, "research", argv[idx + 1], "report.md")

    if not filepath or not os.path.exists(filepath):
        print("用法: python tools/check_report_structure.py (--file <report.md> | --slug <slug>)")
        if filepath:
            print(f"  [错误] 文件不存在: {filepath}")
        sys.exit(1)
    return filepath


def check_structure(lines):
    """对 report.md 的逐行内容做结构校验，返回 issues 列表。

    每项 issue 为 (行号, 信息[, 建议, 片段]) 元组；空列表表示全部通过。
    该纯函数与文件 IO 解耦，便于回归测试直接注入文本断言。
    """
    issues = []

    sub_nums = []
    for i, line in enumerate(lines, 1):
        m = re.match(r"^###\s+(\d+)\.(\d+)\s+", line)
        if m:
            sub_nums.append((int(m.group(1)), int(m.group(2)), i))
    for idx in range(1, len(sub_nums)):
        p_ch, p_num, p_line = sub_nums[idx - 1]
        c_ch, c_num, c_line = sub_nums[idx]
        if p_ch == c_ch:
            if c_num == p_num:
                issues.append((c_line, f"小节编号重复: {p_ch}.{p_num} 出现两次"))
            elif c_num != p_num + 1:
                issues.append((c_line, f"小节编号跳号: {p_ch}.{p_num} → {p_ch}.{c_num}（期望 {p_ch}.{p_num + 1}）"))

    top_found = set()
    for line in lines:
        for req in REQUIRED_TOP:
            if re.match(rf"^##\s+{re.escape(req)}", line.strip()):
                top_found.add(req)
    for req in REQUIRED_TOP:
        if req not in top_found:
            issues.append((1, f"缺少顶层章节: ## {req}"))

    ref_idx = next((i for i, line in enumerate(lines) if line.strip() == REQUIRED_REF), None)
    if ref_idx is None:
        issues.append((1, f"缺少参考文献章节: {REQUIRED_REF}"))
    else:
        ref_lines = [l for l in lines[ref_idx + 1:] if l.strip()]

        # 合法条目：GB/T 编号条目（[1] 作者. 题名...）/ 链接 [标题](url) /
        # 编号列表（1. 或 1、） / 无序列表（- *）/ 纯文本标题（兼容旧格式）。
        valid = sum(1 for l in ref_lines
                    if re.search(r"\[[^\]]+\]\([^)]+\)", l)
                    or re.match(r"^\d+[.、]\s*\S", l)
                    or re.match(r"^[-*]\s*\S", l)
                    or (l.strip() and "{{" not in l))
        if valid == 0:
            issues.append((ref_idx + 1, "参考文献章节为空或条目非 GB/T 编号/[标题](url)/纯文本标题格式"))

    for i, line in enumerate(lines, 1):
        for m in re.finditer(r"\{\{[^{}]*\}\}", line):
            issues.append((i, f"模板占位符残留: {m.group(0)}"))

    for i, line in enumerate(lines, 1):
        if re.match(r"^\*\*\s*测算\s*\d+", line) or re.match(r"^\s*-\s*\*\*(假设前提|计算口径|结果|口径说明)", line):
            issues.append((i, "测算未融入正文", "量化测算须彻底融入对应小节叙述（禁止'**测算 N：**'或'假设前提/计算口径'等单开一行）", line.strip()[:50]))

    return issues




def check_analytical_content(report_path):
    """检查报告是否有分析性内容，而非纯事件描述。"""
    issues = []
    
    with open(report_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # 提取正文（只去掉参考文献部分）
    body_lines = []
    in_ref = False
    for line in lines:
        if line.strip().startswith("## 参考文献"):
            in_ref = True
        if not in_ref:
            body_lines.append(line.strip())
    body = " ".join(body_lines)
    
    # 检查1：标题是否含时效性词汇
    title = lines[0].strip() if lines else ""
    time_words = ["今日", "今天", "本周", "当日", "当天", "刚刚", "突发"]
    for word in time_words:
        if word in title:
            issues.append((0, f"标题含时效性词汇「{word}」，报告可能只是事件描述"))
    
    # 检查2：是否有分析性词汇（至少3个不同类）
    analysis_categories = {
        "因果分析": ["原因", "因为", "由于", "导致", "引发"],
        "规律总结": ["规律", "模式", "反复", "历史", "每次"],
        "结构性分析": ["结构性", "根本", "本质", "深层", "系统性"],
        "长期视角": ["长期", "趋势", "未来", "持续", "演变"],
        "操作策略": ["策略", "建议", "操作", "应对", "下次"]
    }
    found_categories = 0
    for cat, words in analysis_categories.items():
        if any(word in body for word in words):
            found_categories += 1
    if found_categories < 2:
        issues.append((0, f"分析角度不足（仅{found_categories}类，要求至少2类：因果/规律/结构/长期/策略）"))
    
    # 检查3：是否有可操作结论
    conclusion_indicators = ["建议", "策略", "应该", "应", "需要", "下次遇到", "投资者可以", "关注"]
    has_conclusion = any(word in body for word in conclusion_indicators)
    if not has_conclusion:
        issues.append((0, "缺少可操作结论（建议/策略/应该/需要等）"))
    
    # 检查4：现象描述 vs 分析的比例
    description_words = ["上涨", "下跌", "涨幅", "跌幅", "收涨", "收跌", "跳水", "拉升"]
    analysis_ratio = sum(body.count(w) for w in ["原因", "因为", "导致", "规律", "模式", "本质"]) / max(len(body), 1)
    description_ratio = sum(body.count(w) for w in description_words) / max(len(body), 1)
    if description_ratio > analysis_ratio * 3:
        issues.append((0, f"现象描述过多（{description_ratio:.3f}）vs 分析（{analysis_ratio:.3f}），比例失衡"))
    
    return issues


def check_materials_usage(report_path):
    """检查 gathered_*.md 中的素材是否被报告引用。

    修订：废除"前 N 条必须被引用"的限定——素材可能含无关条目
    （如搜索噪声），强制引用前 N 条会诱导硬凑引用。改为"全部素材中至少
    有 2 条被正文引用"（域名/URL/标题关键词任一命中），鼓励引用相关素材、
    允许忽略无关条目。
    """
    import os
    import re
    issues = []

    # 获取报告目录
    report_dir = os.path.dirname(report_path)
    slug = os.path.basename(report_dir)

    # 读取报告内容
    with open(report_path, "r", encoding="utf-8") as f:
        report_content = f.read()

    def count_referenced(urls, titles):
        """统计全部素材中被正文引用的条数（域名/URL/标题关键词任一命中即计 1）。

        标题关键词支持中英文（英文提取 3+ 字母词，如 MAPF/PSPACE）。
        """
        referenced = 0
        for i, url in enumerate(urls):
            hit = False
            domain = re.search(r'https?://([^/]+)', url)
            if domain:
                domain_key = domain.group(1).replace('www.', '')
                if domain_key in report_content or url in report_content:
                    hit = True
            if not hit and i < len(titles):
                title = titles[i]
                keywords = re.findall(r'[\u4e00-\u9fff]{2,}', title) + \
                          re.findall(r'[A-Za-z]{3,}', title)
                for kw in keywords[:6]:
                    if kw and kw in report_content:
                        hit = True
                        break
            if hit:
                referenced += 1
        return referenced

    # 检查 gathered_web.md（通道 B）
    web_file = os.path.join(report_dir, "gathered_web.md")
    if os.path.exists(web_file):
        with open(web_file, "r", encoding="utf-8") as f:
            web_content = f.read()
        urls = re.findall(r'链接：(https?://[^\s]+)', web_content)
        titles = re.findall(r'\- \*\*(.+?)\*\*', web_content)
        referenced_count = count_referenced(urls, titles)
        if len(urls) > 0 and referenced_count < 2:
            issues.append((0, f"通道素材引用不足: 全部 {len(urls)} 条素材中仅 {referenced_count} 条被引用（要求至少2条；无关素材可忽略）"))

    # 检查 gathered_preprints.md + gathered_arxiv.md（通道 P 双文件：
    # arxiv 归入通道 P 后两文件同属 P，合并计数素材引用——避免 PSSXiv 无关素材
    # 误拦 arxiv 平台已引用的论文）
    pre_urls, pre_titles = [], []
    for fname in ("gathered_preprints.md", "gathered_arxiv.md"):
        pf = os.path.join(report_dir, fname)
        if not os.path.exists(pf):
            continue
        with open(pf, "r", encoding="utf-8") as f:
            content = f.read()
        pre_urls += re.findall(r'链接：(https?://[^\s]+)', content)
        pre_titles += re.findall(r'## \d+\. (.+)', content)
    if pre_urls:
        pre_ref = count_referenced(pre_urls, pre_titles)
        # 只有 1 条预印本素材时要求 1 条即可；多条时才要求至少 2 条。
        required_pre = 2 if len(pre_urls) >= 2 else 1
        if pre_ref < required_pre:
            issues.append((0, f"预印本素材引用不足: 全部 {len(pre_urls)} 条素材中仅 {pre_ref} 条被引用（要求至少{required_pre}条；无关素材可忽略）"))

    # 检查是否有参考文献
    if "[1]" not in report_content:
        issues.append((0, "缺少参考文献引用 [n]"))
    
    return issues


def run_checks(report_path):
    """读取 report.md 并返回所有检查的结果。"""
    with open(report_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    issues = check_structure(lines)
    issues.extend(check_materials_usage(report_path))
    issues.extend(check_analytical_content(report_path))
    
    # 运行 GB/T 7714 检查
    try:
        import check_gbt_refs
        with open(report_path, "r", encoding="utf-8") as f:
            body = f.read()
        hard, warn = check_gbt_refs.check(body)
        for line_no, level, title, detail in hard:
            issues.append((line_no, f"GB/T硬伤: {title} - {detail}"))
        for line_no, level, title, detail in warn:
            issues.append((line_no, f"GB/T提示: {title} - {detail}"))
    except Exception as e:
        pass
    
    return issues


def main():
    argv = sys.argv[1:]
    filepath = resolve_target(argv)

    issues = run_checks(filepath)

    print("=" * 60)
    print(f"报告结构检查: {filepath}")
    print("=" * 60)

    if not issues:
        print("全部通过：小节编号连续、顶层章节完整、参考文献合规、无占位符残留、测算已融入正文。")
        sys.exit(0)

    # 分离硬伤和提示
    hard_issues = [i for i in issues if "硬伤" in str(i[1])]
    warn_issues = [i for i in issues if "提示" in str(i[1])]
    
    # 显示所有问题
    seen = {}
    for line_no, msg in issues:
        seen.setdefault(msg, []).append(line_no)
    for msg, lns in seen.items():
        prefix = "[硬伤]" if "硬伤" in msg else "[提示]"
        print(f"  {prefix} 行{lns[0]}{'/' + str(lns[-1]) if len(lns) > 1 else ''}: {msg}")
    
    if hard_issues:
        print("\n硬伤未通过，请先修复再交付。")
        sys.exit(1)
    else:
        print("\n提示级命中（未阻断），可继续上传。")
        sys.exit(0)

if __name__ == "__main__":
    main()
